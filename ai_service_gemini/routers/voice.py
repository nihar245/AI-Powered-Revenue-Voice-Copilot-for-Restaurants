"""
Production voice ordering endpoint.

Flow per request
────────────────
1. Resolve session + menu (cached 60 s)
2. Build Gemini Live system instruction (menu + cart context + conversation history)
3. Gemini Live voice turn  → audio WAV + input transcript + output transcript + [CMD:] tag
4. Parse [CMD:] tag (primary) or fall back to LLM extractor (with response_text hint)
5. Apply cart mutations (add / remove / confirm / cancel)
6. Persist to DB on confirm_order (if POS session is open)
7. Return VoiceOrderResponse (audio + cart + metadata)
"""

from __future__ import annotations

import re
import time
import uuid
from difflib import SequenceMatcher

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
from services.audio.live import voice_turn
from services.database.queries import (
    fetch_active_menu,
    generate_order_number,
    insert_order,
)
from services.dialogue.order_builder import get_cart_total
from services.dialogue.session_store import get_session, reset_session, update_session
from services.llm.extract import extract_cart_update
from services.prompts import build_live_system_instruction

router = APIRouter()

# ─── Menu cache ───────────────────────────────────────────────────────────────

_menu_cache:    list[dict] = []
_menu_cache_ts: float     = 0.0
_MENU_TTL = 60.0


# ─── CMD tag parser (primary, zero-latency cart update) ─────────────────────────────
# Gemini's system prompt explicitly asks it to append:
#   [CMD: <intent> | <ItemName> x<qty> (<key=val, ...>) | ...]
# to every output_audio_transcription.  Parsing this directly is much more
# reliable than a second LLM call because the transcript text is already
# structured and normalised by Gemini itself.

_INTENT_ALIASES = {
    "add_item":            "add_item",
    "remove_item":         "remove_item",
    "modify_item":         "modify_item",
    "confirm_order":       "confirm_order",
    "cancel_order":        "cancel_order",
    "view_cart":           "view_cart",
    "view_menu":           "view_menu",
    "greeting":            "greeting",
    "enquire_price":       "enquire_price",
    "set_customer_name":   "set_customer_name",
    "unknown":             "unknown",
}


def _fuzzy_name(name: str, menu_items: list[dict]) -> dict | None:
    """Best-effort fuzzy match against the live menu."""
    nl = name.lower().strip()
    for item in menu_items:
        if item["name"].lower() == nl:
            return item
    for item in menu_items:
        if nl in item["name"].lower() or item["name"].lower() in nl:
            return item
    best, best_s = None, 0.0
    for item in menu_items:
        s = SequenceMatcher(None, nl, item["name"].lower()).ratio()
        if s > best_s:
            best_s, best = s, item
    return best if best_s >= 0.55 else None


def _parse_cmd_hint(cmd_hint: str, menu_items: list[dict]) -> dict | None:
    """
    Parse Gemini's [CMD: ...] tag into a structured cart update dict
    identical in shape to what extract_cart_update returns.

    Returns None if cmd_hint is blank / unparseable.
    """
    raw = cmd_hint.strip()
    if not raw:
        return None

    parts   = [p.strip() for p in raw.split("|")]
    intent  = _INTENT_ALIASES.get(parts[0].lower().replace(" ", "_"), "unknown")
    items: list[dict] = []

    for seg in parts[1:]:
        # Pattern: "Item Name x2 (key=val, key2=val2)" or just "Item Name x2"
        m = re.match(
            r'^(.+?)\s+[xX](\d+)\s*(?:\(([^)]*)\))?$', seg.strip()
        )
        if m:
            name_raw = m.group(1).strip()
            qty      = max(1, int(m.group(2)))
            mods_str = m.group(3) or ""
        else:
            # No qty given — accept just a name (qty=1)
            clean = re.sub(r'\s*\([^)]*\)$', '', seg.strip())
            name_raw = clean.strip()
            qty      = 1
            mods_str = ""

        matched = _fuzzy_name(name_raw, menu_items)
        if not matched:
            continue

        mods: dict = {}
        for kv in mods_str.split(","):
            kv = kv.strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                k, v = k.strip(), v.strip()
                if v.lower() not in ("null", "none", ""):
                    mods[k] = v

        items.append({
            "product_id": str(matched["product_id"]),
            "name":       matched["name"],
            "qty":        qty,
            "modifiers":  mods,
            "ambiguous":  False,
        })

    return {
        "intent":                 intent,
        "items":                  items,
        "clarification_needed":  False,
        "clarification_question": None,
    }


async def _get_menu() -> list[dict]:
    global _menu_cache, _menu_cache_ts
    if _menu_cache and (time.monotonic() - _menu_cache_ts) < _MENU_TTL:
        return _menu_cache
    _menu_cache    = await fetch_active_menu()
    _menu_cache_ts = time.monotonic()
    return _menu_cache


# ─── /voice/order ─────────────────────────────────────────────────────────────

@router.post("/order", response_model=VoiceOrderResponse)
async def voice_order(
    audio:      UploadFile = File(..., description="Audio file from browser microphone"),
    table_id:   str        = Form(..., description="UUID of the table placing the order"),
    session_id: str        = Form(default="", description="Dialogue session ID (auto-generated if empty)"),
):
    # ── 1. Session ────────────────────────────────────────────────────────────
    if not session_id:
        session_id = str(uuid.uuid4())
    session = get_session(session_id, table_id)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    menu_items = await _get_menu()
    cart: list[dict] = list(session["cart"])

    # ── 2. Gemini Live voice turn (STT + reasoning + TTS in one session) ──────
    system_instr = build_live_system_instruction(
        menu_items,
        cart,
        language=session.get("language", "en"),
        turns=session.get("turns", []),
    )
    turn = await voice_turn(audio_bytes, system_instr)

    transcript    = turn["transcript"]
    response_text = turn["response_text"]
    language      = turn["language"]
    audio_b64     = turn["audio_b64"]
    cmd_hint      = turn.get("cmd_hint", "")

    # ── 3. Resolve intent + cart items ─────────────────────────────────────────────
    # Primary: parse Gemini's own [CMD:] tag  (no extra LLM call, 0 ms latency)
    # Fallback: call LLM extractor with BOTH transcript AND response_text as hint
    update_data = _parse_cmd_hint(cmd_hint, menu_items)
    if not update_data or update_data.get("intent") == "unknown":
        update_data = await extract_cart_update(
            transcript, menu_items, response_text=response_text
        )
    intent_str   = update_data.get("intent", "unknown")
    items_to_act = update_data.get("items", [])

    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.UNKNOWN

    # ── 4. Apply cart mutations ───────────────────────────────────────────────
    cart_events: list[str] = []

    if intent == Intent.ADD_ITEM:
        for item_data in items_to_act:
            pid  = str(item_data.get("product_id", ""))
            qty  = int(item_data.get("qty", 1))
            name = item_data.get("name", "")

            existing = next((c for c in cart if c["product_id"] == pid), None)
            if existing:
                existing["quantity"] += qty
                cart_events.append(f"+{qty} {name}")
            else:
                menu_item = next(
                    (m for m in menu_items if str(m["product_id"]) == pid), None
                )
                if menu_item:
                    mods     = item_data.get("modifiers") or {}
                    variants = menu_item.get("variants", [])
                    vid, vname, uprice, tax_r = None, None, float(menu_item.get("price", 0)), float(menu_item.get("tax", 5.0))
                    if variants:
                        size_hint = (mods.get("size") or mods.get("variant") or "").lower()
                        chosen = next(
                            (v for v in variants if size_hint and size_hint in v["variant_name"].lower()),
                            variants[0],
                        )
                        vid, vname, uprice, tax_r = chosen["variant_id"], chosen["variant_name"], float(chosen["price"]), float(chosen["gst_pct"])
                    cart.append({
                        "product_id":   pid,
                        "name":         menu_item["name"],
                        "quantity":     qty,
                        "unit_price":   uprice,
                        "tax_rate":     tax_r,
                        "variant_id":   vid,
                        "variant_name": vname,
                        "notes":        mods.get("notes"),
                        "modifiers":    {k: v for k, v in mods.items() if v and k != "notes"} or None,
                    })
                    label = f"+{qty} {menu_item['name']}"
                    if vname:
                        label += f" ({vname})"
                    cart_events.append(label)

        update_session(session_id, {"cart": cart})

    elif intent == Intent.REMOVE_ITEM:
        for item_data in items_to_act:
            pid  = str(item_data.get("product_id", ""))
            name = item_data.get("name", "")
            before = len(cart)
            cart = [c for c in cart if c["product_id"] != pid]
            if len(cart) < before:
                cart_events.append(f"−{name}")
        update_session(session_id, {"cart": cart})

    elif intent == Intent.CANCEL_ORDER:
        cart = []
        cart_events.append("Order cancelled")
        update_session(session_id, {"cart": [], "state": DialogueState.DONE})

    elif intent_str == "set_customer_name":
        # Customer told us their name; store it without touching cart
        raw_name = parts[1].strip() if (parts := [p.strip() for p in cmd_hint.split("|")]) and len(parts) > 1 else ""
        if raw_name:
            update_session(session_id, {"customer_name": raw_name})
            cart_events.append(f"name:{raw_name}")

    elif intent == Intent.CONFIRM_ORDER and cart:
        subtotal, tax, total = get_cart_total(cart)
        new_state = DialogueState.PLACING_ORDER

        order_number = await generate_order_number()
        await insert_order(
            order_number=order_number,
            cart=cart,
            subtotal=subtotal,
            tax=tax,
            total=total,
        )
        cart_events.append(f"Order #{order_number} placed — ₹{total:.0f}")
        new_state = DialogueState.DONE
        cart = []

        update_session(session_id, {"cart": cart, "state": new_state})

    # ── 5. Update session metadata ────────────────────────────────────────────
    # Build conversation turns so next turn's system prompt includes this exchange
    saved_turns = list(session.get("turns", []))
    if transcript:
        saved_turns.append({"role": "user",  "text": transcript})
    if response_text:
        saved_turns.append({"role": "agent", "text": response_text})
    if len(saved_turns) > 14:   # keep last 7 exchange pairs
        saved_turns = saved_turns[-14:]

    session = update_session(session_id, {
        "language":     language,
        "last_intent":  intent.value,
        "last_response": response_text,
        "turn":         session.get("turn", 0) + 1,
        "turns":        saved_turns,
    })

    # ── 6. Build response ─────────────────────────────────────────────────────
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
        customer_name=session.get("customer_name", ""),
    )


# ─── /voice/reset ─────────────────────────────────────────────────────────────

@router.post("/reset", response_model=ResetResponse)
async def reset_voice_session(body: ResetRequest):
    reset_session(body.session_id)
    return ResetResponse(success=True, message="Session reset successfully")
