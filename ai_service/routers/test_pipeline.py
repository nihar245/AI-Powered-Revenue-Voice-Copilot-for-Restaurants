"""
Diagnostic / test endpoints — zero database dependency.
Lets you verify each service independently while Qwen is still downloading.

Endpoints
---------
GET  /test/ping                 → API alive check
GET  /test/services             → Status of every service (loaded / reachable)
POST /test/stt                  → Upload audio → transcript + language
POST /test/nlu                  → Text → intent + entities
POST /test/tts                  → Text + language → base64 MP3
POST /test/llm                  → Prompt → Qwen response  (needs Ollama ready)
POST /test/pipeline             → Audio → STT → NLU → template/LLM → TTS  (dummy menu)
"""

import asyncio
import os
import re
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from services.nlu.intent_classifier import classify as semantic_classify
from services.nlu.keyword_maps import ADD_KEYWORDS, REMOVE_KEYWORDS
from services.nlu.rule_engine import classify_intent
from services.stt.normaliser import normalise
from services.stt.whisper_engine import is_loaded, transcribe
from services.tts.gtts_engine import text_to_speech_b64_async
from services.llm.qwen_client import check_ollama_health, generate
from services.llm.prompts import build_order_prompt
from services.menu.menu_resolver import resolve_multiple

router = APIRouter(prefix="/test", tags=["diagnostics"])

# ─── Dummy menu (no DB) ────────────────────────────────────────────────────────
DUMMY_MENU = [
    {"product_id": "1", "name": "Paneer Tikka",     "price": 250.0, "tax": 5.0, "category": "Starters"},
    {"product_id": "2", "name": "Masala Chai",       "price": 50.0,  "tax": 0.0, "category": "Beverages"},
    {"product_id": "3", "name": "Veg Biryani",       "price": 180.0, "tax": 5.0, "category": "Main Course"},
    {"product_id": "4", "name": "Garlic Naan",       "price": 40.0,  "tax": 5.0, "category": "Breads"},
    {"product_id": "5", "name": "Mango Lassi",       "price": 80.0,  "tax": 0.0, "category": "Beverages"},
    {"product_id": "6", "name": "Dal Makhani",       "price": 160.0, "tax": 5.0, "category": "Main Course"},
    {"product_id": "7", "name": "Gulab Jamun",       "price": 60.0,  "tax": 5.0, "category": "Desserts"},
    {"product_id": "8", "name": "Aloo Paratha",      "price": 90.0,  "tax": 5.0, "category": "Breads"},
    {"product_id": "9", "name": "Cold Coffee",       "price": 110.0, "tax": 0.0, "category": "Beverages"},
    {"product_id":"10", "name": "Butter Chicken",    "price": 280.0, "tax": 5.0, "category": "Main Course"},
]


# ─── /test/ping ───────────────────────────────────────────────────────────────

@router.get("/ping")
async def ping():
    return {"status": "ok", "message": "AI Voice Receptionist API is running"}


# ─── /test/services ───────────────────────────────────────────────────────────

@router.get("/services")
async def service_status():
    """Returns loaded/reachable status for every sub-service."""
    ollama_ready = await check_ollama_health()

    return {
        "whisper":   {"loaded": is_loaded(),    "model": "small (faster-whisper)"},
        "ollama":    {"reachable": ollama_ready, "note": "pull qwen2.5:3b if False"},
        "tts":       {"available": True,         "engine": "gTTS (requires internet)"},
        "database":  {"note": "skipped in test endpoints — uses dummy menu"},
    }


# ─── /test/stt ────────────────────────────────────────────────────────────────

@router.post("/stt")
async def test_stt(
    audio: UploadFile = File(..., description="Any audio file (webm, wav, mp3, ogg)"),
):
    """
    Upload an audio recording → get back the transcript and detected language.
    Whisper must be loaded (happens on server startup).
    """
    if not is_loaded():
        raise HTTPException(503, "Whisper model not loaded yet — server still starting up")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")

    t0     = time.perf_counter()
    result = await transcribe(audio_bytes)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    clean_text, language = normalise(result["transcript"], result["language"])

    return {
        "raw_transcript":    result["transcript"],
        "clean_transcript":  clean_text,
        "whisper_language":  result["language"],
        "normalised_language": language,
        "language_probability": result.get("language_probability", None),
        "latency_ms":        elapsed_ms,
    }


# ─── /test/nlu ────────────────────────────────────────────────────────────────

class NLURequest(BaseModel):
    text:     str
    language: str = "en"   # en | hi | gu


@router.post("/nlu")
async def test_nlu(body: NLURequest):
    """
    Send any text → get the rule-engine intent, entities, and semantic fallback.
    No audio needed — great for quick NLU regression checks.
    """
    t0 = time.perf_counter()
    intent_rule, entities = classify_intent(body.text, body.language)
    rule_ms = round((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    intent_semantic, confidence = semantic_classify(body.text)
    sem_ms = round((time.perf_counter() - t1) * 1000)

    final_intent = intent_rule if intent_rule.value != "unknown" else intent_semantic

    # Resolve entities against dummy menu
    resolved_items = []
    if entities:
        resolved = await resolve_multiple(entities, DUMMY_MENU)
        for item, qty, needs_clarification in resolved:
            resolved_items.append({
                "matched_item":         item["name"] if item else None,
                "price":                item["price"] if item else None,
                "quantity":             qty,
                "needs_clarification":  needs_clarification,
            })

    return {
        "text":             body.text,
        "language":         body.language,
        "rule_intent":      intent_rule.value,
        "rule_latency_ms":  rule_ms,
        "semantic_intent":  intent_semantic.value,
        "semantic_confidence": round(confidence, 3),
        "semantic_latency_ms": sem_ms,
        "final_intent":     final_intent.value,
        "entities":         entities,
        "resolved_items":   resolved_items,
    }


# ─── /test/tts ────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text:     str  = "Welcome! What would you like to order today?"
    language: str  = "en"   # en | hi | gu


@router.post("/tts")
async def test_tts(body: TTSRequest):
    """
    Send any text → get a base64-encoded MP3 back.
    Paste the base64 string into https://base64.guru/converter/decode/audio to hear it.
    """
    if not body.text.strip():
        raise HTTPException(400, "text must not be empty")

    t0       = time.perf_counter()
    audio_b64, audio_mime = await text_to_speech_b64_async(body.text, body.language)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return {
        "text":            body.text,
        "language":        body.language,
        "audio_base64":    audio_b64,
        "audio_mime":      audio_mime,
        "latency_ms":      elapsed_ms,
        "hint":            "Decode at https://base64.guru/converter/decode/audio",
    }


# ─── /test/llm ────────────────────────────────────────────────────────────────

class LLMRequest(BaseModel):
    prompt:      str   = "You are a restaurant assistant. Customer says: 'I want one paneer tikka'. Reply briefly."
    temperature: float = 0.3
    max_tokens:  int   = 100


@router.post("/llm")
async def test_llm(body: LLMRequest):
    """
    Send any prompt → get Qwen 2.5 3B's response via Ollama.
    Returns 503 with a clear message if Ollama is not reachable yet.
    """
    if not await check_ollama_health():
        return {
            "status":  "unavailable",
            "message": "Ollama is not reachable. Run: ollama pull qwen2.5:3b",
            "response": None,
        }

    t0 = time.perf_counter()
    try:
        response = await generate(body.prompt, body.temperature, body.max_tokens)
    except Exception as e:
        raise HTTPException(502, f"Ollama error: {e}")
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return {
        "status":      "ok",
        "prompt":      body.prompt,
        "response":    response,
        "latency_ms":  elapsed_ms,
    }


# ─── /test/pipeline ───────────────────────────────────────────────────────────

@router.post("/pipeline")
async def test_pipeline(
    audio: UploadFile = File(..., description="Audio file from microphone"),
    language_hint: str = Form(default="", description="Optional language hint (en/hi/gu)"),
):
    """
    Full end-to-end pipeline test using the dummy menu — NO database required.

    Flow: audio → STT (Whisper) → NLU → LLM (Qwen, always) → TTS (gTTS)

    The LLM receives the raw transcript AND the full menu so it can:
    - Correct speech-to-text mishearings (e.g. 'panettica' → 'Paneer Tikka')
    - Understand multi-action utterances ('add biryani and remove naan')
    - Generate a natural conversational response
    """
    timings: dict[str, int] = {}

    # 1 ── STT ─────────────────────────────────────────────────────────────────
    if not is_loaded():
        raise HTTPException(503, "Whisper not loaded yet")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")

    t0 = time.perf_counter()
    stt = await transcribe(audio_bytes)
    timings["stt_ms"] = round((time.perf_counter() - t0) * 1000)

    transcript   = stt["transcript"]
    whisper_lang = stt["language"]
    clean_text, language = normalise(transcript, whisper_lang)

    # 2 ── NLU ─────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    intent, entities = classify_intent(clean_text, language)
    if intent.value == "unknown":
        intent, _ = semantic_classify(clean_text)
    timings["nlu_ms"] = round((time.perf_counter() - t0) * 1000)

    # 3 ── Menu resolve (dummy menu) ───────────────────────────────────────────
    t0 = time.perf_counter()
    resolved = await resolve_multiple(
        entities or [{"raw_query": clean_text, "quantity": 1}],
        DUMMY_MENU
    )
    timings["menu_resolve_ms"] = round((time.perf_counter() - t0) * 1000)

    matched_item = resolved[0][0] if resolved else None
    matched_qty  = resolved[0][1] if resolved else 1

    # 4 ── LLM — always called, handles fuzzy speech + generates response ──────
    menu_ctx = "\n".join(f"- {i['name']}: ₹{i['price']} ({i['category']})" for i in DUMMY_MENU)
    cart_hint = f"{matched_item['name']} ×{matched_qty}" if matched_item else "(could not match)"

    prompt = build_order_prompt(
        language=language,
        cart=[],          # pipeline test has no persistent cart
        last_utterance=clean_text,
        intent=intent.value,
        dialogue_state="taking_order",
        menu_context=menu_ctx,
        upsell_hint="",
    )

    llm_used = False
    ollama_ready = await check_ollama_health()
    t0 = time.perf_counter()
    if ollama_ready:
        try:
            response_text = await generate(prompt, temperature=0.3, max_tokens=50)
            llm_used = True
        except Exception as e:
            response_text = f"LLM error: {e}"
    else:
        response_text = (
            f"[Ollama not ready] Transcript: '{transcript}'. "
            f"Closest menu match: {cart_hint}."
        )
    timings["llm_ms"] = round((time.perf_counter() - t0) * 1000)

    # 5 ── TTS ─────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    audio_b64 = await asyncio.create_task(text_to_speech_b64_async(response_text, language))
    timings["tts_ms"] = round((time.perf_counter() - t0) * 1000)

    timings["total_ms"] = sum(timings.values())

    # 6 ── Return ──────────────────────────────────────────────────────────────
    return {
        "transcript":    transcript,
        "clean_text":    clean_text,
        "language":      language,
        "intent":        intent.value,
        "entities":      entities,
        "matched_item":  {"name": matched_item["name"], "price": matched_item["price"], "quantity": matched_qty} if matched_item else None,
        "response_text": response_text,
        "llm_used":      llm_used,
        "audio_base64":  audio_b64,
        "timings_ms":    timings,
        "dummy_menu":    [i["name"] for i in DUMMY_MENU],
    }


# ─── /test/chat  (stateful text-based conversation loop, no audio needed) ─────

# In-memory sessions shared by /test/chat and /test/voice-chat
_chat_sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message:    str
    session_id: str  = ""   # auto-generated if empty
    language:   str  = "en" # en | hi | gu


@router.post("/chat")
async def test_chat(body: ChatRequest):
    """
    Stateful text-based conversation loop — no audio needed.
    Simulates the full voice pipeline (NLU → LLM → cart updates) using the
    dummy menu so you can test multi-turn ordering entirely from the Swagger UI.

    How to test a full conversation:
      Turn 1: {"message": "hi",                       "session_id": "",          "language": "en"}
      Turn 2: {"message": "I want 2 paneer tikka",    "session_id": "<from T1>", "language": "en"}
      Turn 3: {"message": "also add a mango lassi",   "session_id": "<from T1>", "language": "en"}
      Turn 4: {"message": "remove the garlic naan",   "session_id": "<from T1>", "language": "en"}
      Turn 5: {"message": "what's in my cart?",       "session_id": "<from T1>", "language": "en"}
      Turn 6: {"message": "confirm order",            "session_id": "<from T1>", "language": "en"}
    """
    import uuid as _uuid

    # Session management
    sid = body.session_id.strip() or str(_uuid.uuid4())
    if sid not in _chat_sessions:
        _chat_sessions[sid] = {"cart": [], "turn": 0, "history": []}
    session = _chat_sessions[sid]
    session["turn"] += 1

    # NLU
    intent, entities = classify_intent(body.message, body.language)
    if intent.value == "unknown":
        intent, _ = semantic_classify(body.message)

    # Menu resolve
    resolved = await resolve_multiple(
        entities or [{"raw_query": body.message, "quantity": 1}],
        DUMMY_MENU
    )

    # Cart update based on intent
    cart: list[dict] = session["cart"]
    cart_events: list[str] = []

    if intent.value == "add_item":
        for item, qty, needs_clarification in resolved:
            if item and not needs_clarification:
                existing = next((c for c in cart if c["product_id"] == item["product_id"]), None)
                if existing:
                    existing["quantity"] += qty
                else:
                    cart.append({"product_id": item["product_id"], "name": item["name"],
                                 "quantity": qty, "unit_price": item["price"]})
                cart_events.append(f"Added {item['name']} ×{qty}")
            elif needs_clarification:
                cart_events.append(f"Could not match '{entities[0].get('raw_query', body.message) if entities else body.message}' — please clarify")

    elif intent.value == "remove_item":
        for item, _, _ in resolved:
            if item:
                before = len(cart)
                cart = [c for c in cart if c["product_id"] != item["product_id"]]
                session["cart"] = cart
                if len(cart) < before:
                    cart_events.append(f"Removed {item['name']}")

    elif intent.value == "cancel_order":
        cart.clear()
        cart_events.append("Cart cleared")

    session["cart"] = cart

    # Build cart summary for LLM
    cart_lines = "\n".join(f"  - {c['name']} ×{c['quantity']} = ₹{c['unit_price']*c['quantity']:.0f}" for c in cart) or "  (empty)"
    subtotal   = sum(c["unit_price"] * c["quantity"] for c in cart)
    menu_ctx   = "\n".join(f"- {i['name']}: ₹{i['price']} ({i['category']})" for i in DUMMY_MENU)

    # Build history context (last 3 turns)
    history_ctx = ""
    if session["history"]:
        history_ctx = "Recent conversation:\n" + "\n".join(
            f"  Turn {h['turn']}: Customer: '{h['msg']}' → Assistant: '{h['resp']}'"
            for h in session["history"][-3:]
        ) + "\n\n"

    prompt = (
        f"{history_ctx}"
        + build_order_prompt(
            language=body.language,
            cart=cart,
            last_utterance=body.message,
            intent=intent.value,
            dialogue_state="taking_order",
            menu_context=menu_ctx,
            upsell_hint="",
        )
    )

    # LLM response
    ollama_ready = await check_ollama_health()
    if ollama_ready:
        try:
            response_text = await generate(prompt, temperature=0.3, max_tokens=50)
        except Exception as e:
            response_text = f"LLM error: {e}"
    else:
        response_text = f"[Ollama not ready] Cart events: {cart_events}. Cart: {cart_lines}"

    # Save to history
    session["history"].append({"turn": session["turn"], "msg": body.message, "resp": response_text})

    return {
        "session_id":   sid,
        "turn":         session["turn"],
        "message":      body.message,
        "intent":       intent.value,
        "cart_events":  cart_events,
        "cart":         cart,
        "cart_total":   f"₹{subtotal:.0f}",
        "response_text": response_text,
        "llm_ready":    ollama_ready,
    }


# ─── /test/voice-chat  (stateful voice loop — used by VoiceLab UI) ───────────

@router.post("/voice-chat")
async def test_voice_chat(
    audio:      UploadFile = File(..., description="Audio blob from browser microphone"),
    session_id: str        = Form(default="",  description="Session ID (auto-created if empty)"),
    language:   str        = Form(default="en", description="en | hi | gu"),
):
    """
    Stateful voice-in / voice-out endpoint used by the VoiceLab HTML UI.
    Flow: audio → STT → NLU → cart update → LLM response → TTS → return audio_base64 + cart
    """
    if not is_loaded():
        raise HTTPException(503, "Whisper not loaded yet — server still starting")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio")

    # ── STT ───────────────────────────────────────────────────────────────────
    stt          = await transcribe(audio_bytes)
    transcript   = stt["transcript"]
    whisper_lang = stt["language"]
    clean_text, detected_lang = normalise(transcript, whisper_lang)
    lang = detected_lang  # always trust Whisper over the form hint

    # ── Session ───────────────────────────────────────────────────────────────
    sid = session_id.strip() or str(uuid.uuid4())
    if sid not in _chat_sessions:
        _chat_sessions[sid] = {"cart": [], "turn": 0, "history": []}
    session = _chat_sessions[sid]
    session["turn"] += 1

    # ── NLU ───────────────────────────────────────────────────────────────────
    intent, entities = classify_intent(clean_text, lang)
    if intent.value == "unknown":
        intent, _ = semantic_classify(clean_text)

    # ── Compound intent detection (e.g. "add garlic naan and remove paneer tikka") ──
    # If BOTH add and remove keywords appear, split by connector and classify each segment.
    text_lower  = clean_text.lower()
    _add_hit    = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower)
                      for kws in ADD_KEYWORDS.values() for kw in kws)
    _remove_hit = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower)
                      for kws in REMOVE_KEYWORDS.values() for kw in kws)

    action_list: list[tuple] = []   # [(Intent, resolved_items)]

    if _add_hit and _remove_hit:
        segs = [s.strip() for s in re.split(
            r'\b(?:and|aur|aur\s+bhi|ane|also|tatha)\b', clean_text, flags=re.IGNORECASE
        ) if s.strip()]
        for seg in segs:
            seg_intent, seg_entities = classify_intent(seg, lang)
            if seg_intent.value in ("add_item", "remove_item"):
                seg_resolved = await resolve_multiple(
                    seg_entities or [{"raw_query": seg, "quantity": 1}], DUMMY_MENU,
                )
                action_list.append((seg_intent, seg_resolved))
        intent = type(intent)("add_item")   # keep a meaningful label
    else:
        resolved = await resolve_multiple(
            entities or [{"raw_query": clean_text, "quantity": 1}], DUMMY_MENU,
        )
        action_list = [(intent, resolved)]

    # ── Cart update ───────────────────────────────────────────────────────────
    cart: list[dict] = session["cart"]
    # Snapshot before any mutations — used to roll back if LLM refuses
    cart_before: list[dict] = [dict(item) for item in cart]
    cart_events: list[str] = []

    for act_intent, act_resolved in action_list:
        if act_intent.value == "add_item":
            for item, qty, needs_clarification in act_resolved:
                if item and not needs_clarification:
                    existing = next((c for c in cart if c["product_id"] == item["product_id"]), None)
                    if existing:
                        existing["quantity"] += qty
                    else:
                        cart.append({
                            "product_id": item["product_id"],
                            "name":       item["name"],
                            "quantity":   qty,
                            "unit_price": item["price"],
                        })
                    cart_events.append(f"Added {item['name']} x{qty}")
                elif needs_clarification:
                    raw = (entities[0].get("raw_query", clean_text) if entities else clean_text)
                    cart_events.append(f"Couldn't match '{raw}'")

        elif act_intent.value == "remove_item":
            for item, _, _ in act_resolved:
                if item:
                    before = len(cart)
                    cart   = [c for c in cart if c["product_id"] != item["product_id"]]
                    if len(cart) < before:
                        cart_events.append(f"Removed {item['name']}")

        elif act_intent.value == "cancel_order":
            cart.clear()
            cart_events.append("Cart cleared")

    session["cart"] = cart
    subtotal = sum(c["unit_price"] * c["quantity"] for c in cart)

    # ── Build LLM prompt  (compact — no history, no full system prompt = ~60% fewer tokens) ──
    menu_ctx  = ", ".join(f"{i['name']} ₹{i['price']}" for i in DUMMY_MENU)
    cart_ctx  = ", ".join(f"{c['name']}×{c['quantity']}" for c in cart) or "empty"
    events_ctx = ", ".join(cart_events) or "none"

    lang_instr = {"en": "English", "hi": "Hindi", "gu": "Gujarati"}.get(lang, "English")
    prompt = (
        f"You are a restaurant voice ordering assistant. "
        f"Speech-to-text may produce garbled words — always interpret them as food orders from the menu below. "
        f"NEVER refuse or say you cannot help. ONE short sentence in {lang_instr}.\n"
        f"MENU: {menu_ctx}\n"
        f"CART: {cart_ctx} | Total: \u20b9{subtotal:.0f}\n"
        f"Actions done: {events_ctx}\n"
        f"Customer said: \"{clean_text}\"\n"
        f"Response:"
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    ollama_ready = await check_ollama_health()
    if ollama_ready:
        try:
            response_text = await generate(prompt, temperature=0.3, max_tokens=35)
        except Exception:
            response_text = "Sorry, I had a problem understanding that. Could you repeat?"
    else:
        response_text = (
            ". ".join(cart_events) + "." if cart_events
            else f"I heard: {transcript}. Ollama is not ready yet."
        )

    # Roll back cart if LLM refused (garbled STT sometimes triggers safety filters)
    _REFUSE_SIGNALS = ("can't assist", "cannot assist", "i'm unable",
                       "apologies, but", "i cannot", "i don't assist")
    if any(sig in response_text.lower() for sig in _REFUSE_SIGNALS):
        session["cart"] = cart_before
        cart     = cart_before
        subtotal = sum(c["unit_price"] * c["quantity"] for c in cart)
        if cart:
            cart_str = ", ".join(f"{c['name']} x{c['quantity']}" for c in cart)
            response_text = f"Sorry, I didn't catch that. Your cart: {cart_str}. Total {subtotal:.0f} rupees."
        else:
            response_text = "Sorry, I didn't catch that. What would you like to order?"

    # ── TTS ───────────────────────────────────────────────────────────────────
    # Sanitize symbols that Piper / gTTS can't speak cleanly
    tts_input = (
        response_text
        .replace("₹", " rupees ")
        .replace("×", " ")       # multiplication sign (U+00D7)
        .replace("|", ", ")      # pipe separator → spoken comma
        .replace("*", "")
        .replace("#", "")
    )
    # Replace " x2" / " x3" quantity notation without clobbering every 'x' in real words
    tts_input = re.sub(r'(?<=\s)x(\d)', r'\1', tts_input)
    tts_input = " ".join(tts_input.split())   # collapse extra whitespace
    try:
        audio_b64, audio_mime = await asyncio.create_task(text_to_speech_b64_async(tts_input, lang))
    except Exception:
        audio_b64, audio_mime = None, "audio/mpeg"

    return {
        "session_id":    sid,
        "turn":          session["turn"],
        "transcript":    transcript,
        "clean_text":    clean_text,
        "language":      lang,
        "intent":        intent.value,
        "cart_events":   cart_events,
        "cart":          cart,
        "cart_total":    f"₹{subtotal:.0f}",
        "response_text": response_text,
        "audio_base64":  audio_b64,
        "audio_mime":    audio_mime,
    }


# ─── /test/voicelab  (serves the VoiceLab HTML UI) ───────────────────────────

@router.get("/voicelab", response_class=HTMLResponse)
async def voicelab_ui():
    """
    Opens the VoiceLab — a real-time voice-to-voice testing UI.
    Hold the mic button (or Space) to record, release to send.
    The AI responds with audio automatically.
    """
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "voicelab.html")
    html_path = os.path.normpath(html_path)
    if not os.path.exists(html_path):
        raise HTTPException(404, "voicelab.html not found in static/")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
