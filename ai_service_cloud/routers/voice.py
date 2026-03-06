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
from services.prompts import build_menu_prompt, build_order_prompt
from services.gemini_pipeline import process_audio_and_reason, generate_speech_b64

router = APIRouter()

_SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

# ─── Menu cache (avoids a DB round-trip on every request) ────────────────────
_menu_cache:    list[dict] = []
_menu_cache_ts: float     = 0.0
_MENU_TTL = 60.0  # seconds


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

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    menu_items = await _get_menu()
    cart: list[dict] = list(session["cart"])
    upsell_hint  = get_upsell_hint(cart, "en")
    menu_summary = "\n".join(f"{i['name']} - ₹{i['price']}" for i in menu_items[:25])
    current_state = DialogueState(session["state"])
    
    context = build_order_prompt(
        language="en",
        cart=cart,
        last_utterance="",
        intent="",
        dialogue_state=current_state.value,
        menu_context=menu_summary,
        upsell_hint=upsell_hint,
    )

    # ── 2. Unified STT + LLM Reasoning ───────────────────────────────────────
    gemini_response = await process_audio_and_reason(audio_bytes, context=context)
    
    transcript = gemini_response.get("transcript", "")
    language = gemini_response.get("language", "en")
    
    raw_intent = gemini_response.get("intent", "UNKNOWN")
    try:
        intent = Intent(raw_intent)
    except ValueError:
        intent = Intent.UNKNOWN

    response_text = gemini_response.get("response_text", "")
    
    # ── 3. Dialogue state transition & Session update ─────────────────────────
    new_state = _state_transition(current_state, intent)
    update_session(session_id, {
        "language":    language,
        "last_intent": intent.value,
        "state":       new_state,
    })
    session    = get_session(session_id)

    # ── 4. Process Cart Updates (from LLM) ────────────────────────────────────
    updates = gemini_response.get("cart_updates", [])
    if updates and isinstance(updates, list):
        for update in updates:
            action = str(update.get("action", "")).lower()
            product_id = str(update.get("product_id", ""))
            qty = int(update.get("quantity", 1))

            if action == "add":
                existing = next((i for i in cart if i["product_id"] == product_id), None)
                if existing:
                    existing["quantity"] += qty
                else:
                    # Resolve product details from menu
                    menu_item = next((m for m in menu_items if str(m["product_id"]) == product_id), None)
                    if menu_item:
                        cart.append({
                            "product_id":   product_id,
                            "name":         menu_item["name"],
                            "quantity":     qty,
                            "unit_price":   float(menu_item["price"]),
                            "tax_rate":     float(menu_item.get("tax", 5.0)),
                            "variant_id":   None,
                            "variant_name": None,
                            "notes":        None,
                        })
            elif action == "remove":
                cart = [i for i in cart if i["product_id"] != product_id]
        
        update_session(session_id, {"cart": cart})

    elif intent == Intent.CONFIRM_ORDER and new_state == DialogueState.PLACING_ORDER:
        subtotal, tax, total = get_cart_total(cart)
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
            if not response_text:
                response_text = get_template("order_placed", language)
        else:
            update_session(session_id, {"state": DialogueState.CONFIRMING})
            if not response_text:
                response_text = get_template("no_pos_session", language)

    elif intent == Intent.CANCEL_ORDER:
        update_session(session_id, {"cart": [], "state": DialogueState.DONE})
        cart = []
        if not response_text:
            response_text = get_template(Intent.CANCEL_ORDER, language)

    update_session(session_id, {"last_response": response_text})

    # ── 6. TTS Generation ───────────────────────────────────────────────────
    if not response_text:
        response_text = "Sorry, I could not understand."
    
    tts_text = " ".join(
        response_text.replace("₹", " rupees ").replace("×", " ").replace("*", "").split()
    )
    audio_b64, _ = await generate_speech_b64(tts_text, language)

    # ── 9. Response ───────────────────────────────────────────────────────────
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
