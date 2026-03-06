"""
Production voice ordering endpoint.

Flow per request
────────────────
1. Resolve session + menu (cached 60 s)
2. Build Gemini Live system instruction (menu + cart context)
3. Gemini Live voice turn  → audio WAV + input transcript + output transcript
4. Extract structured update → intent + cart items  (fast text call, ~80 ms)
5. Apply cart mutations (add / remove / confirm / cancel)
6. Persist to DB on confirm_order
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
    insert_order,
)
from services.dialogue.order_builder import get_cart_total
from services.dialogue.session_store import get_session, reset_session, update_session
from services.dialogue.upsell import get_upsell_suggestion, detect_active_combos
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
    session_id: str        = Form(default="", description="Dialogue session ID (auto-generated if empty)"),
    channel:    str        = Form(default="dine_in", description="Order channel"),
):
    # ── 1. Session ────────────────────────────────────────────────────────────
    if not session_id:
        session_id = str(uuid.uuid4())
    session = get_session(session_id)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    menu_items = await _get_menu()
    cart: list[dict] = list(session["cart"])

    # Pull upsell/clarification state
    upsells_shown  = list(session.get("upsells_shown", []))
    pending_upsell = session.get("pending_upsell")
    pending_clarif = session.get("pending_clarification")

    # ── 2. Gemini Live voice turn (STT + reasoning + TTS in one session) ──────
    system_instr = build_live_system_instruction(
        menu_items=menu_items,
        cart=cart,
        upsell_suggestion=pending_upsell,
        pending_clarification=pending_clarif,
    )
    t0 = time.perf_counter()
    turn = await voice_turn(audio_bytes, system_instr)
    live_ms = round((time.perf_counter() - t0) * 1000)

    transcript    = turn["transcript"]
    response_text = turn["response_text"]
    language      = turn["language"]
    audio_b64     = turn["audio_b64"]

    # ── 3. Extract intent + cart items from transcript (fast text call) ───────
    t1 = time.perf_counter()
    update_data  = await extract_cart_update(transcript, menu_items, response_text=response_text)
    extract_ms   = round((time.perf_counter() - t1) * 1000)

    intent_str   = update_data.get("intent", "unknown")
    items_to_act = update_data.get("items", [])

    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.UNKNOWN

    # ── 4. Apply cart mutations ───────────────────────────────────────────────
    cart_events: list[str] = []
    new_pending_upsell = pending_upsell
    new_clarification  = pending_clarif
    order_id_result    = None

    if intent == Intent.ADD_ITEM:
        for item_data in items_to_act:
            pid  = str(item_data.get("product_id", ""))
            qty  = int(item_data.get("qty", 1))
            name = item_data.get("name", "")
            mods = item_data.get("modifiers") or {}
            ambig = item_data.get("ambiguous", False)

            if ambig or not pid:
                new_clarification = (
                    update_data.get("clarification_question")
                    or f"Which {name} did you mean?"
                )
                cart_events.append(f"? Clarifying: {name}")
                continue

            existing = next((c for c in cart if c["product_id"] == pid), None)
            if existing:
                existing["quantity"] += qty
                if mods:
                    existing.setdefault("modifiers", {})
                    existing["modifiers"].update({k: v for k, v in mods.items() if v})
                cart_events.append(f"+{qty}× {name}")
            else:
                menu_item = next(
                    (m for m in menu_items if str(m["product_id"]) == pid), None
                )
                if menu_item:
                    cart.append({
                        "product_id":   pid,
                        "item_id":      menu_item["item_id"],
                        "name":         menu_item["name"],
                        "quantity":     qty,
                        "unit_price":   float(menu_item["price"]),
                        "tax_rate":     float(menu_item.get("tax", 5.0)),
                        "variant_id":   menu_item.get("variant_id"),
                        "variant_name": menu_item.get("variant_name"),
                        "food_cost":    float(menu_item.get("food_cost", 0)),
                        "notes":        mods.get("notes"),
                        "modifiers":    {k: v for k, v in mods.items() if v} or None,
                    })
                    cart_events.append(f"+{qty}× {menu_item['name']}")

        # Trigger upsell after adding items
        upsell_text = get_upsell_suggestion(cart, upsells_shown, menu_items)
        if upsell_text:
            new_pending_upsell = upsell_text

    elif intent == Intent.MODIFY_ITEM:
        for item_data in items_to_act:
            pid  = str(item_data.get("product_id", ""))
            name = item_data.get("name", "")
            mods = item_data.get("modifiers") or {}
            target = next((c for c in cart if c["product_id"] == pid), None)
            if target and mods:
                target.setdefault("modifiers", {})
                target["modifiers"].update({k: v for k, v in mods.items() if v})
                target["notes"] = mods.get("notes", target.get("notes"))
                mod_desc = ", ".join(f"{k}={v}" for k, v in mods.items() if v)
                cart_events.append(f"✏ {name} modified ({mod_desc})")

    elif intent == Intent.REMOVE_ITEM:
        for item_data in items_to_act:
            pid  = str(item_data.get("product_id", ""))
            name = item_data.get("name", "")
            before = len(cart)
            cart = [c for c in cart if c["product_id"] != pid]
            if len(cart) < before:
                cart_events.append(f"−{name} removed")

    elif intent == Intent.UPSELL_RESPONSE:
        if pending_upsell:
            from services.prompts import _extract_item_name_from_menu
            suggested_name = _extract_item_name_from_menu(pending_upsell, menu_items)
            if suggested_name:
                mi = next(
                    (m for m in menu_items if m["name"].lower() == suggested_name.lower()),
                    None,
                )
                if mi and not any(c["product_id"] == str(mi["product_id"]) for c in cart):
                    cart.append({
                        "product_id":   str(mi["product_id"]),
                        "item_id":      mi["item_id"],
                        "name":         mi["name"],
                        "quantity":     1,
                        "unit_price":   float(mi["price"]),
                        "tax_rate":     float(mi.get("tax", 5.0)),
                        "variant_id":   mi.get("variant_id"),
                        "variant_name": mi.get("variant_name"),
                        "food_cost":    float(mi.get("food_cost", 0)),
                        "notes":        None,
                        "modifiers":    None,
                    })
                    cart_events.append(f"+1× {mi['name']} (upsell accepted)")
            upsells_shown.append(pending_upsell)
            new_pending_upsell = None

    elif intent == Intent.CANCEL_ORDER:
        cart = []
        new_pending_upsell = None
        new_clarification  = None
        cart_events.append("Order cancelled")

    elif intent == Intent.CONFIRM_ORDER and cart:
        subtotal, tax_total, total = get_cart_total(cart)
        try:
            order_id_result = await insert_order(
                cart=cart,
                subtotal=subtotal,
                tax=tax_total,
                total=total,
                channel=channel,
            )
            cart_events.append(f"Order #{order_id_result} placed — ₹{total:.0f}")
            cart = []
            new_pending_upsell = None
            new_clarification  = None
        except Exception as exc:
            cart_events.append(f"Order confirmed — ₹{total:.0f} (DB write failed: {exc})")

    # Clear clarification if a non-add/non-clarify intent
    if intent not in (Intent.ADD_ITEM, Intent.MODIFY_ITEM, Intent.CLARIFY,
                      Intent.UNKNOWN, Intent.GREETING):
        new_clarification = None

    # ── 5. Update session ─────────────────────────────────────────────────────
    if new_pending_upsell and new_pending_upsell not in upsells_shown:
        upsells_shown.append(new_pending_upsell)

    update_session(session_id, {
        "cart":                   cart,
        "language":               language,
        "last_intent":            intent.value,
        "last_response":          response_text,
        "turn":                   session.get("turn", 0) + 1,
        "pending_clarification":  new_clarification,
        "pending_upsell":         new_pending_upsell,
        "upsells_shown":          upsells_shown,
    })

    # ── 6. Build response ─────────────────────────────────────────────────────
    safe_lang   = Language(language) if language in Language._value2member_map_ else Language.EN
    state = session.get("state", DialogueState.GREETING)
    if cart:
        state = DialogueState.TAKING_ORDER
    if intent == Intent.CONFIRM_ORDER:
        state = DialogueState.DONE
    if intent == Intent.CANCEL_ORDER:
        state = DialogueState.DONE

    _, _, total_val = get_cart_total(cart)
    active_combos = detect_active_combos(cart)

    # Build upsell chips
    upsell_chips: list[dict] = []
    if new_pending_upsell:
        from services.prompts import _extract_item_name_from_menu
        item_name = _extract_item_name_from_menu(new_pending_upsell, menu_items)
        if item_name:
            mi = next((m for m in menu_items if m["name"].lower() == item_name.lower()), None)
            if mi:
                upsell_chips.append({
                    "label":      f"+ Add {mi['name']} ₹{mi['price']:.0f}",
                    "item_name":  mi["name"],
                    "product_id": str(mi["product_id"]),
                    "price":      float(mi["price"]),
                    "suggestion": new_pending_upsell,
                })

    return VoiceOrderResponse(
        audio_base64=audio_b64,
        transcript=transcript,
        language=safe_lang,
        intent=intent,
        dialogue_state=state,
        cart=[CartItem(**{k: v for k, v in item.items()
                         if k in CartItem.model_fields}) for item in cart],
        response_text=response_text,
        session_id=session_id,
        upsell_suggestion=new_pending_upsell,
        upsell_chips=upsell_chips,
        pending_clarification=new_clarification,
        active_combos=active_combos,
    )


# ─── /voice/reset ─────────────────────────────────────────────────────────────

@router.post("/reset", response_model=ResetResponse)
async def reset_voice_session(body: ResetRequest):
    reset_session(body.session_id)
    return ResetResponse(success=True, message="Session reset successfully")
