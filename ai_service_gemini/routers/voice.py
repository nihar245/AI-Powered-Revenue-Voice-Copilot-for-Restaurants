"""
Production voice ordering endpoint.

Flow per request
────────────────
1. Resolve session + menu (cached 60 s)
2. Build Gemini Live system instruction (menu + cart context)
3. Gemini Live voice turn  → audio WAV + input transcript + output transcript
4. Extract structured update → intent + cart items  (fast text call, ~80 ms)
5. Apply cart mutations (add / remove / confirm / cancel)
6. Persist to DB on confirm_order (if POS session is open)
7. Return VoiceOrderResponse (audio + cart + metadata)
"""

from __future__ import annotations

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
    system_instr = build_live_system_instruction(menu_items, cart)
    turn = await voice_turn(audio_bytes, system_instr)

    transcript    = turn["transcript"]
    response_text = turn["response_text"]
    language      = turn["language"]
    audio_b64     = turn["audio_b64"]

    # ── 3. Extract intent + cart items from transcript (fast text call) ───────
    update_data  = await extract_cart_update(transcript, menu_items)
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
    session = update_session(session_id, {
        "language":     language,
        "last_intent":  intent.value,
        "last_response": response_text,
        "turn":         session.get("turn", 0) + 1,
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
    )


# ─── /voice/reset ─────────────────────────────────────────────────────────────

@router.post("/reset", response_model=ResetResponse)
async def reset_voice_session(body: ResetRequest):
    reset_session(body.session_id)
    return ResetResponse(success=True, message="Session reset successfully")
