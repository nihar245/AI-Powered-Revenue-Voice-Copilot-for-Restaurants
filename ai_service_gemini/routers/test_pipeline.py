"""
Diagnostic / test endpoints — with live DB support.

Architecture: every voice request goes through the full Gemini Live pipeline
(audio-in → audio-out + transcripts → structured JSON extraction → cart update)
and uses the real database for menu, tables, and order creation.

Endpoints
─────────
GET  /test/ping          → liveness probe
GET  /test/services      → service status + model info
GET  /test/menu          → active menu from DB (or fallback)
GET  /test/tables        → active tables from DB (or demo list)
POST /test/voice-chat    → stateful voice turn (used by VoiceLab UI)
GET  /test/voicelab      → VoiceLab HTML UI
"""

import logging
import os
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from config import settings
from models.schemas import DialogueState, Intent, Language
from services.audio.live import voice_turn
from services.database.connection import get_pool
from services.database.queries import (
    fetch_active_menu,
    insert_order,
)
from services.dialogue.order_builder import format_cart_total, get_cart_total
from services.dialogue.session_store import get_session, reset_session, update_session
from services.dialogue.upsell import (
    build_order_summary,
    detect_active_combos,
    get_upsell_suggestion,
)
from services.llm.extract import extract_cart_update
from services.prompts import build_live_system_instruction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test", tags=["diagnostics"])

# ─── Fallbacks (used when DB is unavailable) ──────────────────────────────────
_FALLBACK_MENU = [
    {"product_id": "1",  "item_id": 1,  "name": "Paneer Tikka",   "price": 250.0, "tax": 5.0, "category_name": "Starters",    "is_veg": True,  "variant_id": 1,  "variant_name": "Full", "food_cost": 100.0, "variants": [{"variant_id": 1, "variant_name": "Full", "price": 250.0, "gst_pct": 5.0, "food_cost": 100.0}]},
    {"product_id": "2",  "item_id": 2,  "name": "Masala Chai",     "price": 50.0,  "tax": 0.0, "category_name": "Beverages",   "is_veg": True,  "variant_id": 2,  "variant_name": "Regular", "food_cost": 15.0, "variants": [{"variant_id": 2, "variant_name": "Regular", "price": 50.0, "gst_pct": 0.0, "food_cost": 15.0}]},
    {"product_id": "3",  "item_id": 3,  "name": "Veg Biryani",     "price": 180.0, "tax": 5.0, "category_name": "Main Course", "is_veg": True,  "variant_id": 3,  "variant_name": "Full", "food_cost": 70.0, "variants": [{"variant_id": 3, "variant_name": "Full", "price": 180.0, "gst_pct": 5.0, "food_cost": 70.0}]},
    {"product_id": "4",  "item_id": 4,  "name": "Garlic Naan",     "price": 40.0,  "tax": 5.0, "category_name": "Breads",      "is_veg": True,  "variant_id": 4,  "variant_name": "Regular", "food_cost": 12.0, "variants": [{"variant_id": 4, "variant_name": "Regular", "price": 40.0, "gst_pct": 5.0, "food_cost": 12.0}]},
    {"product_id": "5",  "item_id": 5,  "name": "Mango Lassi",     "price": 80.0,  "tax": 0.0, "category_name": "Beverages",   "is_veg": True,  "variant_id": 5,  "variant_name": "Regular", "food_cost": 25.0, "variants": [{"variant_id": 5, "variant_name": "Regular", "price": 80.0, "gst_pct": 0.0, "food_cost": 25.0}]},
    {"product_id": "6",  "item_id": 6,  "name": "Dal Makhani",     "price": 160.0, "tax": 5.0, "category_name": "Main Course", "is_veg": True,  "variant_id": 6,  "variant_name": "Full", "food_cost": 55.0, "variants": [{"variant_id": 6, "variant_name": "Full", "price": 160.0, "gst_pct": 5.0, "food_cost": 55.0}]},
    {"product_id": "7",  "item_id": 7,  "name": "Gulab Jamun",     "price": 60.0,  "tax": 5.0, "category_name": "Desserts",    "is_veg": True,  "variant_id": 7,  "variant_name": "2 Pcs", "food_cost": 18.0, "variants": [{"variant_id": 7, "variant_name": "2 Pcs", "price": 60.0, "gst_pct": 5.0, "food_cost": 18.0}]},
    {"product_id": "8",  "item_id": 8,  "name": "Aloo Paratha",    "price": 90.0,  "tax": 5.0, "category_name": "Breads",      "is_veg": True,  "variant_id": 8,  "variant_name": "Regular", "food_cost": 30.0, "variants": [{"variant_id": 8, "variant_name": "Regular", "price": 90.0, "gst_pct": 5.0, "food_cost": 30.0}]},
    {"product_id": "9",  "item_id": 9,  "name": "Cold Coffee",     "price": 110.0, "tax": 0.0, "category_name": "Beverages",   "is_veg": True,  "variant_id": 9,  "variant_name": "Regular", "food_cost": 35.0, "variants": [{"variant_id": 9, "variant_name": "Regular", "price": 110.0, "gst_pct": 0.0, "food_cost": 35.0}]},
    {"product_id": "10", "item_id": 10, "name": "Butter Chicken",  "price": 280.0, "tax": 5.0, "category_name": "Main Course", "is_veg": False, "variant_id": 10, "variant_name": "Full", "food_cost": 110.0, "variants": [{"variant_id": 10, "variant_name": "Full", "price": 280.0, "gst_pct": 5.0, "food_cost": 110.0}]},
]

def _get_menu(request: Request) -> list[dict]:
    """Return cached DB menu, falling back to hardcoded list if DB is down."""
    menu = getattr(request.app.state, "menu", [])
    return menu if menu else _FALLBACK_MENU


# ─── /test/ping ───────────────────────────────────────────────────────────────

@router.get("/ping")
async def ping():
    return {"status": "ok", "message": "ai_service_gemini is running (Gemini Live API)"}


# ─── /test/services ───────────────────────────────────────────────────────────

@router.get("/services")
async def service_status(request: Request):
    menu   = _get_menu(request)
    db_ok  = get_pool() is not None
    return {
        "pipeline": {
            "audio_model":  settings.gemini_audio_model,
            "text_model":   settings.gemini_text_model,
            "api_key_set":  bool(settings.gemini_api_key),
            "description":  "Gemini Live (audio-in/audio-out) + fast text extraction",
        },
        "database": {
            "connected":    db_ok,
            "menu_items":   len(menu),
            "source":       "database" if db_ok else "fallback (DB unavailable)",
        },
    }


# ─── /test/menu ───────────────────────────────────────────────────────────────

@router.get("/menu")
async def get_menu(request: Request):
    """Active menu from DB (or fallback list). Grouped by category."""
    menu = _get_menu(request)
    # Group by category
    grouped: dict[str, list] = {}
    for item in menu:
        cat = item.get("category_name") or item.get("category") or "Other"
        grouped.setdefault(cat, []).append({
            "product_id": item["product_id"],
            "name":       item["name"],
            "price":      float(item["price"]),
            "tax":        float(item.get("tax", 0)),
        })
    return {
        "source":     "database" if get_pool() else "fallback",
        "item_count": len(menu),
        "categories": [
            {"name": cat, "items": items}
            for cat, items in grouped.items()
        ],
    }


# ─── /test/voice-chat ─────────────────────────────────────────────────────────

@router.post("/voice-chat")
async def voice_chat(
    request:    Request,
    audio:      UploadFile = File(...),
    session_id: str        = Form(default=""),
    language:   str        = Form(default="en"),
):
    """
    Full stateful voice turn for VoiceLab.

    1. Gemini Live: audio → audio (WAV) + transcripts
    2. Gemini text: transcript → intent + cart items
    3. Apply cart mutation (add / remove / cancel / confirm)
    4. On confirm_order: write real order to DB (if connected)
    5. Return VoiceLab-compatible JSON
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    menu      = _get_menu(request)
    session   = get_session(session_id)
    cart: list[dict] = list(session["cart"])
    turn_num  = session.get("turn", 0) + 1

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")

    # Pull per-session upsell/clarification state
    upsells_shown   = list(session.get("upsells_shown", []))
    combos_shown    = list(session.get("combos_shown", []))
    pending_clarif  = session.get("pending_clarification")
    pending_upsell  = session.get("pending_upsell")

    # ── Step 1: Gemini Live voice turn ────────────────────────────────────────
    system_instr = build_live_system_instruction(
        menu_items             = menu,
        cart                   = cart,
        upsell_suggestion      = session.get("pending_upsell"),
        pending_clarification  = pending_clarif,
    )
    t0 = time.perf_counter()
    turn = await voice_turn(audio_bytes, system_instr)
    live_ms = round((time.perf_counter() - t0) * 1000)

    transcript    = turn["transcript"]
    response_text = turn["response_text"]
    detected_lang = turn["language"]
    audio_b64     = turn["audio_b64"]

    # ── Step 2: Extract structured update from transcript ─────────────────────
    t1 = time.perf_counter()
    update_data  = await extract_cart_update(transcript, menu, response_text=response_text)
    extract_ms   = round((time.perf_counter() - t1) * 1000)

    intent_str            = update_data.get("intent", "unknown")
    items_to_act          = update_data.get("items", [])
    clarification_needed  = update_data.get("clarification_needed", False)
    clarification_question = update_data.get("clarification_question")

    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.UNKNOWN

    # ── Step 3: Apply cart mutations ──────────────────────────────────────────
    cart_events:  list[str]      = []
    order_number: str | None     = None
    new_clarification: str | None = None
    new_pending_upsell: str | None = pending_upsell  # carry forward unless resolved

    if intent == Intent.ADD_ITEM:
        for item_data in items_to_act:
            pid      = str(item_data.get("product_id", ""))
            qty      = int(item_data.get("qty", 1))
            name     = item_data.get("name", "")
            mods     = item_data.get("modifiers") or {}
            ambig    = item_data.get("ambiguous", False)

            if ambig or not pid:
                # Don't add to cart yet; ask for clarification
                new_clarification = clarification_question or f"Which {name} did you mean?"
                session["pending_ambiguous_item"] = item_data
                cart_events.append(f"? Clarifying: {name}")
                continue

            existing = next((c for c in cart if c["product_id"] == pid), None)
            if existing:
                existing["quantity"] += qty
                # Merge modifiers if present
                if mods:
                    existing.setdefault("modifiers", {})
                    existing["modifiers"].update({k: v for k, v in mods.items() if v})
                cart_events.append(f"+{qty}× {name}")
            else:
                mi = next((m for m in menu if str(m["product_id"]) == pid), None)
                if mi:
                    cart.append({
                        "product_id":   pid,
                        "item_id":      mi.get("item_id", int(pid)),
                        "name":         mi["name"],
                        "quantity":     qty,
                        "unit_price":   float(mi["price"]),
                        "tax_rate":     float(mi.get("tax", 5.0)),
                        "variant_id":   mi.get("variant_id"),
                        "variant_name": mi.get("variant_name"),
                        "food_cost":    float(mi.get("food_cost", 0)),
                        "notes":        mods.get("notes"),
                        "modifiers":    {k: v for k, v in mods.items() if v} or None,
                    })
                    cart_events.append(f"+{qty}× {mi['name']}")

        # Trigger upsell suggestion after adding items
        upsell_text = get_upsell_suggestion(cart, upsells_shown + combos_shown, menu)
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
            else:
                cart_events.append(f"? {name} not in cart to modify")

    elif intent == Intent.REMOVE_ITEM:
        for item_data in items_to_act:
            pid  = str(item_data.get("product_id", ""))
            name = item_data.get("name", "")
            before = len(cart)
            cart = [c for c in cart if c["product_id"] != pid]
            if len(cart) < before:
                cart_events.append(f"−{name} removed")

    elif intent == Intent.UPSELL_RESPONSE:
        # Customer said "yes" to a pending upsell
        if pending_upsell:
            # Parse item name out of suggestion text
            suggested_name = _extract_item_name_from_upsell(pending_upsell, menu)
            if suggested_name:
                mi = next(
                    (m for m in menu if m["name"].lower() == suggested_name.lower()),
                    None,
                )
                if mi and not any(c["product_id"] == str(mi["product_id"]) for c in cart):
                    cart.append({
                        "product_id":   str(mi["product_id"]),
                        "item_id":      mi.get("item_id", int(mi["product_id"])),
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

    elif intent == Intent.CLARIFY:
        # Customer is answering a previous clarification question
        new_clarification = None
        session["pending_ambiguous_item"] = None

    elif intent == Intent.CANCEL_ORDER:
        cart = []
        new_pending_upsell = None
        new_clarification  = None
        cart_events.append("Order cancelled")

    elif intent == Intent.CONFIRM_ORDER:
        if cart:
            subtotal, tax_total, grand_total = get_cart_total(cart)
            order_summary = build_order_summary(cart, subtotal, tax_total, grand_total)
            try:
                order_id = await insert_order(
                    cart=cart,
                    subtotal=subtotal,
                    tax=tax_total,
                    total=grand_total,
                )
                cart_events.append(f"✅ Order #{order_id} placed — ₹{grand_total:.0f}")
                order_number = str(order_id)
            except Exception as exc:
                logger.error("Order write failed: %s", exc)
                cart_events.append(f"Order confirmed — ₹{grand_total:.0f} (DB write failed)")
            cart = []
            new_pending_upsell = None
            new_clarification  = None

    # Update clarification state: set new one if needed, or clear if answered
    if intent not in (Intent.ADD_ITEM, Intent.MODIFY_ITEM):
        # Other intents count as implicitly resolving pending clarification
        if intent not in (Intent.CLARIFY, Intent.UNKNOWN, Intent.GREETING):
            new_clarification = None

    # ── Step 4: Persist session ───────────────────────────────────────────────
    if new_pending_upsell and new_pending_upsell not in upsells_shown:
        upsells_shown.append(new_pending_upsell)

    update_session(session_id, {
        "cart":                   cart,
        "language":               detected_lang,
        "last_intent":            intent.value,
        "last_response":          response_text,
        "turn":                   turn_num,
        "pending_clarification":  new_clarification,
        "pending_upsell":         new_pending_upsell,
        "upsells_shown":          upsells_shown,
        "combos_shown":           combos_shown,
    })

    # ── Step 5: Build response ────────────────────────────────────────────────
    _, _, total   = get_cart_total(cart)
    active_combos = detect_active_combos(cart)

    # Build upsell chips for the UI — chip per suggestion not yet shown
    upsell_chips: list[dict] = []
    if new_pending_upsell:
        item_name = _extract_item_name_from_upsell(new_pending_upsell, menu)
        if item_name:
            mi = next((m for m in menu if m["name"].lower() == item_name.lower()), None)
            if mi:
                upsell_chips.append({
                    "label":      f"+ Add {mi['name']} ₹{mi['price']:.0f}",
                    "item_name":  mi["name"],
                    "product_id": str(mi["product_id"]),
                    "price":      float(mi["price"]),
                    "suggestion": new_pending_upsell,
                })

    return {
        "session_id":            session_id,
        "turn":                  turn_num,
        "transcript":            transcript,
        "clean_text":            transcript,
        "language":              detected_lang,
        "intent":                intent.value,
        "response_text":         response_text,
        "audio_base64":          audio_b64,
        "audio_mime":            "audio/wav",
        "cart":                  cart,
        "cart_total":            f"₹{total:.0f}",
        "cart_events":           cart_events,
        "order_number":          order_number,
        "upsell_suggestion":     new_pending_upsell,
        "upsell_chips":          upsell_chips,
        "pending_clarification": new_clarification,
        "active_combos":         active_combos,
        "timings_ms": {
            "gemini_live_ms": live_ms,
            "extract_ms":     extract_ms,
        },
    }


def _extract_item_name_from_upsell(suggestion_text: str, menu: list[dict]) -> str | None:
    """
    Pull the item name out of a suggestion string like
    'Would you like to add Mango Lassi? It pairs great with Veg Biryani!'
    or 'Add Garlic Naan to complete the Biryani Meal and save ₹25!'
    """
    text_lower = suggestion_text.lower()
    for m in menu:
        if m["name"].lower() in text_lower:
            # Make sure it's a suggestion target (appears before "pairs" or right after "add")
            return m["name"]
    return None


# ─── /test/add-item (quick-add via upsell chip) ──────────────────────────────

@router.post("/add-item")
async def add_item_direct(
    request:    Request,
    session_id: str = Form(...),
    product_id: str = Form(...),
    item_name:  str = Form(...),
    quantity:   int = Form(default=1),
):
    """
    Directly add an item to the cart without a voice turn.
    Used by upsell chips in the VoiceLab UI.
    """
    menu    = _get_menu(request)
    session = get_session(session_id)
    cart    = list(session["cart"])

    mi = next((m for m in menu if str(m["product_id"]) == product_id), None)
    if not mi:
        raise HTTPException(404, f"product_id {product_id!r} not in menu")

    existing = next((c for c in cart if c["product_id"] == product_id), None)
    if existing:
        existing["quantity"] += quantity
    else:
        cart.append({
            "product_id":   product_id,
            "name":         mi["name"],
            "quantity":     quantity,
            "unit_price":   float(mi["price"]),
            "tax_rate":     float(mi.get("tax", 5.0)),
            "item_id":      mi.get("item_id"),
            "variant_id":   mi.get("variant_id"),
            "variant_name": mi.get("variant_name"),
            "food_cost":    float(mi.get("food_cost", 0)),
            "notes":        None,
            "modifiers":    None,
        })

    upsells_shown = list(session.get("upsells_shown", []))
    upsell_text   = get_upsell_suggestion(cart, upsells_shown, menu)
    if upsell_text:
        upsells_shown.append(upsell_text)

    update_session(session_id, {
        "cart":          cart,
        "upsells_shown": upsells_shown,
        "pending_upsell": upsell_text,
    })

    _, _, total   = get_cart_total(cart)
    active_combos = detect_active_combos(cart)

    upsell_chips: list[dict] = []
    if upsell_text:
        name = _extract_item_name_from_upsell(upsell_text, menu)
        if name:
            m2 = next((m for m in menu if m["name"].lower() == name.lower()), None)
            if m2:
                upsell_chips.append({
                    "label":      f"Add {m2['name']} ₹{m2['price']:.0f}",
                    "item_name":  m2["name"],
                    "product_id": str(m2["product_id"]),
                    "price":      float(m2["price"]),
                    "suggestion": upsell_text,
                })

    return {
        "cart":                  cart,
        "cart_total":            f"₹{total:.0f}",
        "cart_events":           [f"+{quantity}× {mi['name']}"],
        "upsell_chips":          upsell_chips,
        "active_combos":         active_combos,
        "pending_clarification": session.get("pending_clarification"),
    }


# ─── /test/session/:session_id ────────────────────────────────────────────────

@router.get("/session/{session_id}")
async def get_session_data(session_id: str):
    session = get_session(session_id)
    return session


# ─── /test/voicelab ──────────────────────────────────────────────────────────

@router.get("/voicelab", response_class=HTMLResponse)
async def voicelab():
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "voicelab.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


