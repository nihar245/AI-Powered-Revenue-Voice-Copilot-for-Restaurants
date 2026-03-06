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
import re
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
    fetch_tables,
    generate_order_number,
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
    {"product_id": "1",  "name": "Paneer Tikka",   "price": 250.0, "tax": 5.0, "category_name": "Starters"},
    {"product_id": "2",  "name": "Masala Chai",     "price": 50.0,  "tax": 0.0, "category_name": "Beverages"},
    {"product_id": "3",  "name": "Veg Biryani",     "price": 180.0, "tax": 5.0, "category_name": "Main Course"},
    {"product_id": "4",  "name": "Garlic Naan",     "price": 40.0,  "tax": 5.0, "category_name": "Breads"},
    {"product_id": "5",  "name": "Mango Lassi",     "price": 80.0,  "tax": 0.0, "category_name": "Beverages"},
    {"product_id": "6",  "name": "Dal Makhani",     "price": 160.0, "tax": 5.0, "category_name": "Main Course"},
    {"product_id": "7",  "name": "Gulab Jamun",     "price": 60.0,  "tax": 5.0, "category_name": "Desserts"},
    {"product_id": "8",  "name": "Aloo Paratha",    "price": 90.0,  "tax": 5.0, "category_name": "Breads"},
    {"product_id": "9",  "name": "Cold Coffee",     "price": 110.0, "tax": 0.0, "category_name": "Beverages"},
    {"product_id": "10", "name": "Butter Chicken",  "price": 280.0, "tax": 5.0, "category_name": "Main Course"},
]
_FALLBACK_TABLES = [
    {"table_id": "demo-t1", "table_number": "T-1", "seats": 4, "status": "available"},
    {"table_id": "demo-t2", "table_number": "T-2", "seats": 4, "status": "available"},
    {"table_id": "demo-t3", "table_number": "T-3", "seats": 2, "status": "available"},
]

def _get_menu(request: Request) -> list[dict]:
    """Return cached DB menu, falling back to hardcoded list if DB is down."""
    menu = getattr(request.app.state, "menu", [])
    return menu if menu else _FALLBACK_MENU


def _get_tables(request: Request) -> list[dict]:
    tables = getattr(request.app.state, "tables", [])
    return tables if tables else _FALLBACK_TABLES


def _resolve_variant(
    menu_item: dict, modifiers: dict | None
) -> tuple[int | None, str | None, float, float]:
    """
    Pick the best variant for a menu item based on modifier hints.
    Returns (variant_id, variant_name, unit_price, tax_rate).
    Falls back to the first (cheapest) variant.
    """
    variants = menu_item.get("variants", [])
    if not variants:
        return None, None, float(menu_item.get("price", 0)), float(menu_item.get("tax", 5.0))

    size_hint = ""
    if modifiers:
        size_hint = (
            modifiers.get("size") or
            modifiers.get("variant") or
            modifiers.get("portion") or ""
        ).lower()

    if size_hint:
        for v in variants:
            if size_hint in v["variant_name"].lower():
                return v["variant_id"], v["variant_name"], float(v["price"]), float(v["gst_pct"])

    v = variants[0]
    return v["variant_id"], v["variant_name"], float(v["price"]), float(v["gst_pct"])


# ─── /test/ping ───────────────────────────────────────────────────────────────

@router.get("/ping")
async def ping():
    return {"status": "ok", "message": "ai_service_gemini is running (Gemini Live API)"}


# ─── /test/services ───────────────────────────────────────────────────────────

@router.get("/services")
async def service_status(request: Request):
    menu   = _get_menu(request)
    tables = _get_tables(request)
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
            "tables":       len(tables),
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
        variants = item.get("variants", [])
        grouped.setdefault(cat, []).append({
            "product_id": item["product_id"],
            "name":       item["name"],
            "price":      float(item["price"]),
            "tax":        float(item.get("tax", 0)),
            "is_veg":     item.get("is_veg", True),
            "tags":       item.get("tags") or [],
            "variants":   [
                {
                    "variant_id":   v["variant_id"],
                    "variant_name": v["variant_name"],
                    "price":        float(v["price"]),
                }
                for v in variants
            ],
        })
    return {
        "source":     "database" if get_pool() else "fallback",
        "item_count": len(menu),
        "categories": [
            {"name": cat, "items": items}
            for cat, items in grouped.items()
        ],
    }


# ─── /test/tables ─────────────────────────────────────────────────────────────

@router.get("/tables")
async def get_tables(request: Request):
    """Active tables from DB (or demo table list)."""
    tables = _get_tables(request)
    return {
        "source": "database" if get_pool() else "fallback",
        "tables": tables,
    }


# ─── /test/voice-chat ─────────────────────────────────────────────────────────

@router.post("/voice-chat")
async def voice_chat(
    request:    Request,
    audio:      UploadFile = File(...),
    session_id: str        = Form(default=""),
    language:   str        = Form(default="en"),
    table_id:   str        = Form(default=""),
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
    session   = get_session(session_id, table_id or "demo-table")
    cart: list[dict] = list(session["cart"])
    turn_num  = session.get("turn", 0) + 1

    if table_id:
        session["table_id"] = table_id

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
        language               = language,
        table_id               = table_id,
    )
    t0 = time.perf_counter()
    turn = await voice_turn(audio_bytes, system_instr)
    live_ms = round((time.perf_counter() - t0) * 1000)

    transcript       = turn["transcript"]
    response_text    = turn["response_text"]
    response_display = turn.get("response_display") or response_text
    cmd_hint         = turn.get("cmd_hint", "")
    detected_lang    = turn["language"]
    audio_b64        = turn["audio_b64"]

    # ── Step 2: Extract structured update ─────────────────────────────────────
    # Primary: parse Gemini's own [CMD:] tag (English, structured, no extra LLM call).
    # Fallback: send transcript to Gemini text model if CMD tag is absent or malformed.
    t1 = time.perf_counter()
    cmd_parsed  = _apply_cmd_hint(cmd_hint, menu) if cmd_hint else None
    update_data = (
        cmd_parsed
        if (cmd_parsed and cmd_parsed["intent"] != "unknown")
        else await extract_cart_update(transcript, menu, response_text=response_text)
    )
    extract_ms = round((time.perf_counter() - t1) * 1000)

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
                    vid, vname, uprice, tax_r = _resolve_variant(mi, mods)
                    cart.append({
                        "product_id":   pid,
                        "name":         mi["name"],
                        "quantity":     qty,
                        "unit_price":   uprice,
                        "tax_rate":     tax_r,
                        "variant_id":   vid,
                        "variant_name": vname,
                        "notes":        mods.get("notes") if mods else None,
                        "modifiers":    {k: v for k, v in mods.items() if v and k != "notes"} or None if mods else None,
                    })
                    label = f"+{qty}× {mi['name']}"
                    if vname:
                        label += f" ({vname})"
                    cart_events.append(label)

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
                    vid, vname, uprice, tax_r = _resolve_variant(mi, None)
                    cart.append({
                        "product_id":   str(mi["product_id"]),
                        "name":         mi["name"],
                        "quantity":     1,
                        "unit_price":   uprice,
                        "tax_rate":     tax_r,
                        "variant_id":   vid,
                        "variant_name": vname,
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
            try:
                order_number = await _write_order_to_db(
                    session_data=session,
                    table_id=table_id,
                    cart=cart,
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=grand_total,
                    cart_events=cart_events,
                )
            except Exception as exc:
                logger.error("Order write failed: %s", exc)
                order_number = f"VO-{uuid.uuid4().hex[:6].upper()}"
                cart_events.append(f"✅ Order #{order_number} confirmed — ₹{grand_total:.0f} (DB error)")
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
        "table_id":               table_id or session.get("table_id", ""),
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
        "response_display":      response_display,
        "audio_base64":          audio_b64,
        "audio_mime":            "audio/wav",
        "cart":                  cart,
        "cart_total":            f"₹{total:.0f}",
        "cart_total_amount":     round(total, 2),
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


def _apply_cmd_hint(cmd_hint: str, menu: list[dict]) -> dict | None:
    """
    Parse Gemini's [CMD: ...] tag directly into the same dict format as extract_cart_update().
    This bypasses the text LLM entirely — Gemini Live already understood the order and
    produced a structured English extraction tag as part of its response transcription.

    Format: <intent> | <ExactMenuName> x<qty> (<key=val, key=val>)
    Example: add_item | Paneer Tikka x1 (size=full, spice=hot) | Masala Chai x2

    Returns None if the hint is empty or malformed.
    """
    if not cmd_hint.strip():
        return None
    try:
        parts  = [p.strip() for p in cmd_hint.split("|")]
        intent = parts[0].lower().strip()
        _VALID_INTENTS = {
            "add_item", "remove_item", "modify_item", "confirm_order", "cancel_order",
            "view_cart", "view_menu", "enquire_price", "greeting", "unknown",
            "upsell_response", "clarify",
        }
        if intent not in _VALID_INTENTS:
            return None

        items: list[dict] = []
        for part in parts[1:]:
            part = part.strip()
            m = re.match(r'^(.+?)\s+x(\d+)(?:\s*\(([^)]*)\))?$', part, re.IGNORECASE)
            if not m:
                continue
            name, qty, mods_s = m.group(1).strip(), int(m.group(2)), m.group(3) or ""
            # Exact name match first, then partial
            mi = next(
                (item for item in menu if item["name"].lower() == name.lower()), None
            ) or next(
                (item for item in menu if name.lower() in item["name"].lower()), None
            )
            if not mi:
                continue
            mods: dict = {}
            for kv in mods_s.split(","):
                kv = kv.strip()
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k and v:
                        mods[k] = v
            items.append({
                "product_id": str(mi["product_id"]),
                "name":       mi["name"],
                "qty":        qty,
                "modifiers":  mods or None,
                "ambiguous":  False,
            })

        return {
            "intent":                 intent,
            "items":                  items,
            "clarification_needed":   False,
            "clarification_question": None,
        }
    except Exception:
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
        vid, vname, uprice, tax_r = _resolve_variant(mi, None)
        cart.append({
            "product_id":   product_id,
            "name":         mi["name"],
            "quantity":     quantity,
            "unit_price":   uprice,
            "tax_rate":     tax_r,
            "variant_id":   vid,
            "variant_name": vname,
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


# ─── /test/voicelab ──────────────────────────────────────────────────────────

@router.get("/voicelab", response_class=HTMLResponse)
async def voicelab():
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "voicelab.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ─── Internal: DB order writer ───────────────────────────────────────────────

async def _write_order_to_db(
    session_data: dict,
    table_id: str,
    cart: list[dict],
    subtotal: float,
    tax_total: float,
    grand_total: float,
    cart_events: list[str],
) -> str:
    """
    Write a confirmed order to the database.
    Appends a status string to cart_events.
    Returns the order_number (always, even in demo/fallback mode).
    """
    pool = get_pool()
    if pool is None:
        fallback_num = f"VO-{uuid.uuid4().hex[:6].upper()}"
        cart_events.append(f"✅ Order #{fallback_num} confirmed — ₹{grand_total:.0f} (demo mode)")
        return fallback_num

    order_num = await generate_order_number()
    await insert_order(
        order_number=order_num,
        cart=cart,
        subtotal=subtotal,
        tax=tax_total,
        total=grand_total,
    )
    cart_events.append(f"✅ Order #{order_num} placed — ₹{grand_total:.0f}")
    logger.info("Order %s written to DB (total=%.0f)", order_num, grand_total)
    return order_num


# ─── /test/confirm-order (button-triggered from Node.js backend) ─────────────

@router.post("/confirm-order")
async def confirm_order_button(session_id: str = Form(...)):
    """
    Button-triggered order confirmation. Writes the cart to DB and clears the session.
    Called by Node.js backend when the user presses the Confirm button in the UI.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    cart = session.get("cart", [])
    if not cart:
        return {"order_number": None, "cart_events": ["Cart is empty"], "message": "Cart is empty"}

    cart_events: list[str] = []
    subtotal, tax_total, grand_total = get_cart_total(cart)

    order_number = await _write_order_to_db(
        session_data=session,
        table_id=session.get("table_id", ""),
        cart=cart,
        subtotal=subtotal,
        tax_total=tax_total,
        grand_total=grand_total,
        cart_events=cart_events,
    )

    update_session(session_id, {"cart": [], "last_intent": "confirm_order"})

    return {
        "order_number": order_number,
        "cart_events":  cart_events,
        "message":      f"Order confirmed — ₹{grand_total:.0f}",
    }


# ─── /test/session/{session_id} (read session state for Node.js proxy) ───────

@router.get("/session/{session_id}")
async def get_session_state(session_id: str):
    """Return the current voice session state for a given session_id."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _, _, total = get_cart_total(session.get("cart", []))
    return {
        "session_id":            session_id,
        "cart":                  session.get("cart", []),
        "cart_total":            f"Rs.{total:.0f}",
        "language":              session.get("language", "en"),
        "turn":                  session.get("turn", 0),
        "last_intent":           session.get("last_intent", ""),
        "table_id":              session.get("table_id", ""),
        "pending_clarification": session.get("pending_clarification"),
        "pending_upsell":        session.get("pending_upsell"),
    }
