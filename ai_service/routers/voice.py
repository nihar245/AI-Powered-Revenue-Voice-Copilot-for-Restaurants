import asyncio
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import (
    CartItem,
    DialogueState,
    Intent,
    Language,
    ResetRequest,
    ResetResponse,
    VoiceOrderResponse,
)
from services.database.queries import (
    fetch_active_menu,
    generate_order_number,
    get_default_terminal_id,
    get_open_session_id,
    insert_order,
)
from services.dialogue.order_builder import get_cart_total
from services.dialogue.response_templates import get_template
from services.dialogue.session_store import get_session, reset_session, update_session
from services.dialogue.state_machine import _TRANSITIONS as TRANSITIONS
from services.dialogue.upsell_engine import get_upsell_hint
from services.llm.prompts import build_menu_prompt, build_order_prompt
from services.llm.qwen_client import generate
from services.menu.menu_resolver import resolve_multiple
from services.nlu.intent_classifier import classify as semantic_classify
from services.nlu.rule_engine import classify_intent
from services.stt.normaliser import normalise
from services.stt.whisper_engine import transcribe
from services.tts.gtts_engine import text_to_speech_b64_async

router = APIRouter()

_SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

# ─── Menu cache (avoids a DB round-trip on every request) ─────────────────────────────────
_menu_cache:    list[dict] = []
_menu_cache_ts: float     = 0.0
_MENU_TTL = 60.0  # seconds — safe for a restaurant menu that rarely changes


async def _get_menu() -> list[dict]:
    global _menu_cache, _menu_cache_ts
    if _menu_cache and (time.monotonic() - _menu_cache_ts) < _MENU_TTL:
        return _menu_cache
    _menu_cache    = await fetch_active_menu()
    _menu_cache_ts = time.monotonic()
    return _menu_cache


# ─── helpers ──────────────────────────────────────────────────────────────────

def _state_transition(current: DialogueState, intent: Intent) -> DialogueState:
    return TRANSITIONS.get((current, intent), current)


def _cart_summary(cart: list[dict], language: str) -> tuple[str, int]:
    lines = ", ".join(f"{i['name']} ×{i['quantity']}" for i in cart)
    _, _, total = get_cart_total(cart)
    return lines, round(total)


@router.post("/order", response_model=VoiceOrderResponse)
async def voice_order(
    audio: UploadFile = File(..., description="Audio file from browser microphone"),
    table_id: str = Form(..., description="UUID of the table placing the order"),
    session_id: str = Form(default="", description="Dialogue session ID (auto-generated if empty)"),
):
    # ── 1. Session ────────────────────────────────────────────────────────────
    if not session_id:
        session_id = str(uuid.uuid4())
    session = get_session(session_id, table_id)

    # ── 2. STT ────────────────────────────────────────────────────────────────
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    stt_result   = await transcribe(audio_bytes)
    transcript   = stt_result["transcript"]
    whisper_lang = stt_result["language"]

    # ── 3. Normalise ───────────────────────────────────────────────────────────────────
    clean_text, language = normalise(transcript, whisper_lang)

    # ── 4. NLU (sync, ~0ms) + launch menu fetch concurrently ──────────────────────
    intent, entities = classify_intent(clean_text, language)
    # Fire menu fetch immediately — it runs while we do sync state transitions
    menu_task = asyncio.create_task(_get_menu())
    if intent == Intent.UNKNOWN:
        # semantic_classify (~50ms) runs concurrently with menu fetch
        intent, _ = await semantic_classify(clean_text)

    # ── 5. Dialogue state transition + batched session update ──────────────────────
    current_state = DialogueState(session["state"])
    new_state     = _state_transition(current_state, intent)
    update_session(session_id, {
        "language":    language,
        "last_intent": intent.value,
        "state":       new_state,
    })
    session    = get_session(session_id)
    menu_items = await menu_task   # almost always already resolved by now

    # ── 7. Intent handlers ────────────────────────────────────────────────────
    response_text: str | None = None
    cart: list[dict]          = list(session["cart"])

    if intent == Intent.ADD_ITEM:
        resolved = await resolve_multiple(
            entities or [{"raw_query": clean_text, "quantity": 1}], menu_items
        )
        for menu_item, quantity, needs_clarification in resolved:
            if needs_clarification or menu_item is None:
                raw_q = entities[0].get("raw_query", clean_text) if entities else clean_text
                update_session(session_id, {
                    "state": DialogueState.CLARIFYING,
                    "clarification_context": {"raw_query": raw_q, "quantity": quantity},
                })
                response_text = get_template("add_item_clarify", language, query=raw_q)
            else:
                existing = next(
                    (i for i in cart if i["product_id"] == str(menu_item["product_id"])), None
                )
                if existing:
                    existing["quantity"] += quantity
                else:
                    cart.append({
                        "product_id":   str(menu_item["product_id"]),
                        "name":         menu_item["name"],
                        "quantity":     quantity,
                        "unit_price":   float(menu_item["price"]),
                        "tax_rate":     float(menu_item.get("tax", 5.0)),
                        "variant_id":   None,
                        "variant_name": None,
                        "notes":        None,
                    })
                response_text = get_template(
                    "add_item_ok", language,
                    item=menu_item["name"], qty=str(quantity)
                )
        update_session(session_id, {"cart": cart})

    elif intent == Intent.REMOVE_ITEM:
        resolved = await resolve_multiple(
            entities or [{"raw_query": clean_text, "quantity": 1}], menu_items
        )
        for menu_item, _, _ in resolved:
            if menu_item:
                pid  = str(menu_item["product_id"])
                name = menu_item["name"]
                cart = [i for i in cart if i["product_id"] != pid]
                response_text = get_template("remove_item_ok", language, item=name)
        update_session(session_id, {"cart": cart})

    elif intent == Intent.VIEW_CART:
        if not cart:
            response_text = get_template("view_cart_empty", language)
        else:
            lines, total = _cart_summary(cart, language)
            response_text = get_template("view_cart", language, cart_lines=lines, total=str(total))

    elif intent == Intent.GREETING:
        response_text = get_template(Intent.GREETING, language)

    elif intent == Intent.CONFIRM_ORDER and new_state == DialogueState.PLACING_ORDER:
        subtotal, tax, total = get_cart_total(cart)
        # Two independent DB reads — run in parallel
        pos_session_id, terminal_id = await asyncio.gather(
            get_open_session_id(_SYSTEM_USER_ID),
            get_default_terminal_id(),
        )
        if pos_session_id and terminal_id:
            order_number = await generate_order_number()
            await insert_order(
                order_number=order_number,
                table_id=table_id,
                session_id=pos_session_id,
                terminal_id=terminal_id,
                user_id=_SYSTEM_USER_ID,
                cart=cart,
                subtotal=subtotal,
                tax=tax,
                total=total,
            )
            update_session(session_id, {"state": DialogueState.DONE, "cart": []})
            response_text = get_template("order_placed", language)
        else:
            update_session(session_id, {"state": DialogueState.CONFIRMING})
            response_text = get_template("no_pos_session", language)

    elif intent == Intent.CONFIRM_ORDER:
        response_text = get_template(Intent.CONFIRM_ORDER, language)

    elif intent == Intent.CANCEL_ORDER:
        update_session(session_id, {"cart": [], "state": DialogueState.DONE})
        cart = []
        response_text = get_template(Intent.CANCEL_ORDER, language)

    # ── 8. LLM fallback (VIEW_MENU / ENQUIRE_PRICE / UNKNOWN) ────────────────
    if response_text is None:
        upsell_hint  = get_upsell_hint(cart, language)
        menu_summary = "\n".join(f"{i['name']} - ₹{i['price']}" for i in menu_items[:25])
        if intent == Intent.VIEW_MENU:
            prompt = build_menu_prompt(language, menu_items)
        else:
            prompt = build_order_prompt(
                language=language,
                cart=cart,
                last_utterance=clean_text,
                intent=intent.value,
                dialogue_state=new_state.value,
                menu_context=menu_summary,
                upsell_hint=upsell_hint,
            )
        response_text = await generate(prompt)

    update_session(session_id, {"last_response": response_text})

    # ── 9. TTS ────────────────────────────────────────────────────────────────
    # Sanitize symbols that Piper / gTTS can't speak cleanly
    tts_text = " ".join(
        response_text.replace("₹", " rupees ").replace("×", " ").replace("*", "").split()
    )
    audio_b64, _ = await text_to_speech_b64_async(tts_text, language)

    # ── 10. Response ──────────────────────────────────────────────────────────
    session     = get_session(session_id)
    safe_lang   = Language(language) if language in Language._value2member_map_ else Language.EN
    final_state = DialogueState(session["state"])

    return VoiceOrderResponse(
        audio_base64=audio_b64,
        transcript=transcript,
        language=safe_lang,
        intent=intent,
        dialogue_state=final_state,
        cart=[CartItem(**item) for item in session["cart"]],
        response_text=response_text,
        session_id=session_id,
    )


@router.post("/reset", response_model=ResetResponse)
async def reset_voice_session(body: ResetRequest):
    reset_session(body.session_id)
    return ResetResponse(success=True, message="Session reset successfully")

    # ── 2. STT ────────────────────────────────────────────────────────────────
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    stt_result   = await transcribe(audio_bytes)
    transcript   = stt_result["transcript"]
    whisper_lang = stt_result["language"]

    # ── 3. Normalise + language detection ─────────────────────────────────────
    clean_text, language = normalise(transcript, whisper_lang)
    session.language = language

    # ── 4. NLU — rule engine first, semantic fallback ─────────────────────────
    intent, entities = classify_intent(clean_text, language)
    if intent == Intent.UNKNOWN:
        intent, _ = semantic_classify(clean_text)

    # ── 5. Dialogue state transition ──────────────────────────────────────────
    session.transition(intent)

    # ── 6. Fetch live menu ────────────────────────────────────────────────────
    menu_items = await fetch_active_menu()

    # ── 7. Intent handlers ────────────────────────────────────────────────────
    if intent == Intent.ADD_ITEM:
        for entity in entities:
            raw_query = entity.get("raw_query", clean_text)
            quantity  = entity.get("quantity", 1)
            session.cart, matched, needs_clarification = await add_to_cart(
                session.cart, raw_query, quantity, menu_items
            )
            if needs_clarification:
                session.state = DialogueState.CLARIFYING
                session.clarification_context = {"raw_query": raw_query, "quantity": quantity}

    elif intent == Intent.REMOVE_ITEM:
        for entity in entities:
            raw_query = entity.get("raw_query", clean_text)
            session.cart, _ = await remove_from_cart(session.cart, raw_query, menu_items)

    elif session.state == DialogueState.PLACING_ORDER:
        if session.cart:
            subtotal, tax, total = get_cart_total(session.cart)
            pos_session_id = await get_open_session_id(_SYSTEM_USER_ID)
            terminal_id    = await get_default_terminal_id()

            if pos_session_id and terminal_id:
                order_number = await generate_order_number()
                await insert_order(
                    order_number=order_number,
                    table_id=table_id,
                    session_id=pos_session_id,
                    terminal_id=terminal_id,
                    user_id=_SYSTEM_USER_ID,
                    cart=session.cart,
                    subtotal=subtotal,
                    tax=tax,
                    total=total,
                )
                session.state = DialogueState.DONE
            else:
                # No open POS session — stay in confirming state, inform customer
                session.state = DialogueState.CONFIRMING

    # ── 8. Upsell hint ────────────────────────────────────────────────────────
    upsell_hint = get_upsell_hint(session.cart, language)

    # ── 9. Build LLM prompt + generate response ───────────────────────────────
    menu_summary = "\n".join(
        f"{item['name']} - ₹{item['price']}" for item in menu_items[:25]
    )

    if intent == Intent.VIEW_MENU:
        # Build a compact menu-focused prompt
        prompt = build_menu_prompt(language, menu_items)
    else:
        prompt = build_order_prompt(
            language=language,
            cart=session.cart,
            last_utterance=clean_text,
            intent=intent.value,
            dialogue_state=session.state.value,
            menu_context=menu_summary,
            upsell_hint=upsell_hint,
        )

    response_text = await generate(prompt)

    # ── 10. TTS ───────────────────────────────────────────────────────────────
    audio_b64, _ = await text_to_speech_b64_async(response_text, language)

    # ── 11. Build response ────────────────────────────────────────────────────
    safe_lang = Language(language) if language in Language._value2member_map_ else Language.EN

    return VoiceOrderResponse(
        audio_base64=audio_b64,
        transcript=transcript,
        language=safe_lang,
        intent=intent,
        dialogue_state=session.state,
        cart=[CartItem(**item) for item in session.cart],
        response_text=response_text,
        session_id=session_id,
    )


@router.post("/reset", response_model=ResetResponse)
async def reset_voice_session(body: ResetRequest):
    reset_session(body.session_id)
    return ResetResponse(success=True, message="Session reset successfully")
