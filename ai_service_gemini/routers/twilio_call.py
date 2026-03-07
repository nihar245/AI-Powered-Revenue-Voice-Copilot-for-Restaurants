"""
Twilio phone call integration — inbound AI voice ordering.

Flow
────
1.  Customer calls the Twilio number.
2.  Twilio POSTs to  POST /twilio/incoming
    → we return TwiML that opens a bidirectional Media Stream WebSocket.
3.  Twilio opens  WS /twilio/stream
4.  On "start" message → a pre-recorded gTTS greeting is played directly to
    the caller ("Welcome to Padmavati Bhojanalaya …").  Gemini does NOT do
    the greeting.  The system waits for the customer to speak first.
5.  Customer speaks  → VAD buffers 20 ms μ-law frames  → silence detected
    → raw μ-law segment pushed into queue.
6.  Worker coroutine processes turns sequentially:
      μ-law segment  →  WAV container  →  GeminiCallSession.send_turn()  →  Gemini Live
      Gemini WAV response  →  raw μ-law 8 kHz  →  stream back to Twilio.
    Inbound frames are DROPPED while ai_is_speaking=True to prevent re-greetings.
    If Gemini takes >8 s, "please wait" audio is sent every 8 s.  The wait
    audio task is always cancelled BEFORE Aria's response is streamed to
    prevent interleaving / overlap.
7.  On CONFIRM_ORDER intent  →  order persisted to DB  →  worker sets
    order_done = True  →  WebSocket closes  →  Twilio hangs up.
8.  On CANCEL_ORDER or call disconnect  →  session cleaned up.

All calls are appended to the in-memory _CALL_LOG list (GET /twilio/call-logs).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import traceback as _traceback
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from config import settings
from models.schemas import DialogueState, Intent
from services.audio.live import GeminiCallSession
from services.audio.twilio_bridge import (
    VAD,
    get_greeting_mulaw,
    get_wait_mulaw,
    make_clear_message,
    make_media_message,
    mulaw_to_wav8k,
    wav_to_mulaw8k,
)
from services.database.connection import get_pool
from services.database.queries import (
    fetch_active_combos,
    fetch_active_menu,
    fetch_active_offers,
    generate_order_number,
    insert_order,
)
from services.dialogue.order_builder import get_cart_total
from services.dialogue.session_store import get_session, reset_session, update_session
from services.llm.extract import extract_cart_update
from services.prompts import build_live_system_instruction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["twilio"])

# ── Menu cache ────────────────────────────────────────────────────────────────
_MENU_TTL   = 60.0
_COMBO_TTL  = 120.0
_menu_cache:    list[dict] = []
_menu_cache_ts: float      = 0.0
_combo_cache:   list[dict] = []
_offer_cache:   list[dict] = []
_combo_cache_ts: float     = 0.0


async def _get_menu() -> list[dict]:
    global _menu_cache, _menu_cache_ts
    if _menu_cache and (time.monotonic() - _menu_cache_ts) < _MENU_TTL:
        return _menu_cache
    _menu_cache    = await fetch_active_menu()
    _menu_cache_ts = time.monotonic()
    return _menu_cache


async def _get_combos_and_offers() -> tuple[list[dict], list[dict]]:
    global _combo_cache, _offer_cache, _combo_cache_ts
    if _combo_cache and (time.monotonic() - _combo_cache_ts) < _COMBO_TTL:
        return _combo_cache, _offer_cache
    _combo_cache    = await fetch_active_combos()
    _offer_cache    = await fetch_active_offers()
    _combo_cache_ts = time.monotonic()
    return _combo_cache, _offer_cache


@router.get("/debug/db-status")
async def debug_db_status() -> dict:
    """
    Quick health check: is the database pool alive and can we reach relevant tables?
    Hit GET /twilio/debug/db-status to diagnose DB connectivity issues.
    """
    pool = get_pool()
    if pool is None:
        return {"pool": None, "connected": False, "error": "Pool is None — DB never connected or connection failed at startup"}

    try:
        row = await pool.fetchrow("SELECT COUNT(*)::int AS cnt FROM orders")
        orders_count = row["cnt"]
    except Exception as exc:
        return {"pool": repr(pool), "connected": False, "error": f"Query failed: {exc}",
                "traceback": _traceback.format_exc()}

    try:
        menu_row = await pool.fetchrow("SELECT COUNT(*)::int AS cnt FROM menu_items WHERE is_available=TRUE")
        menu_count = menu_row["cnt"]
    except Exception as exc:
        menu_count = f"ERROR: {exc}"

    try:
        kot_row = await pool.fetchrow("SELECT COUNT(*)::int AS cnt FROM kot")
        kot_count = kot_row["cnt"]
    except Exception as exc:
        kot_count = f"ERROR: {exc}"

    return {
        "connected": True,
        "pool_size":     pool.get_size(),
        "pool_idle":     pool.get_idle_size(),
        "orders_count":  orders_count,
        "menu_items":    menu_count,
        "kot_count":     kot_count,
    }


@router.get("/debug/recent-orders")
async def debug_recent_orders(limit: int = 10) -> dict:
    """
    Return the most recent orders from the DB directly (bypass Node.js backend).
    Useful to confirm whether voice orders are actually being written.
    """
    pool = get_pool()
    if pool is None:
        return {"error": "DB pool is None", "orders": []}
    try:
        rows = await pool.fetch("""
            SELECT o.order_id, o.placed_by, o.channel, o.status,
                   o.subtotal, o.tax_amt, o.total, o.payment_status,
                   o.placed_at,
                   COUNT(oi.line_id) AS item_count
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            GROUP BY o.order_id
            ORDER BY o.placed_at DESC
            LIMIT $1
        """, limit)
        return {"orders": [dict(r) for r in rows]}
    except Exception as exc:
        return {"error": str(exc), "traceback": _traceback.format_exc(), "orders": []}


# ── In-memory call log ────────────────────────────────────────────────────────
_CALL_LOG: list[dict] = []   # newest-first
_CALL_LOG_MAX = 200


def _log_call(entry: dict) -> None:
    _CALL_LOG.insert(0, entry)
    if len(_CALL_LOG) > _CALL_LOG_MAX:
        _CALL_LOG.pop()


# ── External confirm requests ─────────────────────────────────────────────────
# Maps call_sid → asyncio.Event so the HTTP confirm endpoint can signal the WS.
_CONFIRM_REQUESTS: dict[str, asyncio.Event] = {}


# ── Turn queue item ───────────────────────────────────────────────────────────

@dataclass
class _Turn:
    audio:        bytes
    is_pcm_wav:   bool    # True = already a WAV (greeting silence); False = raw μ-law
    is_greeting:  bool    # True = first turn — append phone greeting note to system instr
    turn_number:  int = 0 # 0-based turn counter for the call


# ── TwiML webhook ─────────────────────────────────────────────────────────────

@router.post("/incoming")
async def incoming_call(request: Request) -> Response:
    """
    Twilio calls this HTTP endpoint when an inbound call arrives.
    Returns TwiML that connects the call to our bidirectional Media Stream.

    Configure this URL in the Twilio Console:
      Phone Numbers → Your Number → Voice & Fax → A call comes in → Webhook
      → POST  https://<TWILIO_BASE_URL>/twilio/incoming
    """
    base_url  = settings.twilio_base_url.rstrip("/")
    ws_url    = base_url.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/twilio/stream"

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        "  <Connect>\n"
        f'    <Stream url="{stream_url}" />\n'
        "  </Connect>\n"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def call_status(request: Request) -> Response:
    """Twilio status callback — updates the call log entry with final status."""
    form     = await request.form()
    call_sid = form.get("CallSid", "")
    status   = form.get("CallStatus", "")
    caller   = form.get("From", "")
    logger.info("[twilio] CallSid=%s  Status=%s", call_sid, status)
    for entry in _CALL_LOG:
        if entry.get("call_sid") == call_sid:
            entry["status"] = status
            if status in ("completed", "failed", "busy", "no-answer"):
                entry["end_time"] = datetime.now(timezone.utc).isoformat()
            if caller and not entry.get("caller"):
                entry["caller"] = caller
            break
    return Response(status_code=204)


@router.get("/call-logs")
async def get_call_logs(limit: int = 50) -> list[dict]:
    """Return the most recent call log entries (newest first)."""
    return _CALL_LOG[:max(1, min(limit, _CALL_LOG_MAX))]


@router.get("/active-call")
async def get_active_call() -> dict:
    """
    Return the live state of the currently-active inbound phone call, if any.
    The VoiceOrder page polls this endpoint to show the phone cart in real time.
    Also returns just_confirmed=True for calls confirmed within the last 60 s so
    the frontend can show the Order Confirmed card even after the call ends.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    for entry in _CALL_LOG:
        status = entry.get("status", "")
        sid    = entry.get("call_sid")
        if not sid:
            continue

        # ── Active call ───────────────────────────────────────────────────────
        if status == "in_progress":
            sess     = get_session(sid, table_id="phone")
            cart     = sess.get("cart", [])
            subtotal = sum(c["unit_price"] * c["quantity"] for c in cart)
            tax_amt  = sum(c["unit_price"] * c["quantity"] * c.get("tax_rate", 5.0) / 100 for c in cart)
            return {
                "active":       True,
                "call_sid":     sid,
                "caller":       entry.get("caller", ""),
                "start_time":   entry.get("start_time", ""),
                "turns":        entry.get("turns", 0),
                "cart":         cart,
                "subtotal":     round(subtotal, 2),
                "tax":          round(tax_amt, 2),
                "total":        round(subtotal + tax_amt, 2),
                "state":        sess.get("state", "").value if hasattr(sess.get("state", ""), "value") else str(sess.get("state", "")),
                "transcript":   (entry.get("transcript") or [])[-6:],
                "order_number": entry.get("order_number"),
            }

        # ── Recently confirmed call (within 60 s) — let frontend read order # ─
        if status == "order_confirmed" and entry.get("order_number"):
            end_iso = entry.get("end_time") or entry.get("start_time", "")
            try:
                end_dt = datetime.fromisoformat(end_iso)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                if (now - end_dt) < timedelta(seconds=60):
                    return {
                        "active":         False,
                        "just_confirmed": True,
                        "call_sid":       sid,
                        "caller":         entry.get("caller", ""),
                        "order_number":   entry.get("order_number"),
                        "order_total":    entry.get("order_total"),
                    }
            except Exception:
                pass

    return {"active": False}


@router.post("/confirm-phone-order/{call_sid}")
async def confirm_phone_order(call_sid: str) -> dict:
    """
    Confirm an active phone call's order from the dashboard UI.
    Writes directly to the DB and signals the WebSocket worker to close the call.
    """
    session = get_session(call_sid, table_id="phone")
    cart    = session.get("cart", [])
    if not cart:
        return {"success": False, "error": "Cart is empty"}

    cur_state = session.get("state")
    if cur_state == DialogueState.DONE:
        order_num = session.get("confirmed_order_number", "")
        return {"success": True, "order_number": order_num, "already_confirmed": True}

    subtotal, tax, total = get_cart_total(cart)
    order_number = await generate_order_number()
    try:
        await insert_order(
            order_number=order_number,
            cart=cart,
            subtotal=subtotal,
            tax=tax,
            total=total,
            placed_by="phone_order",
        )
    except Exception as exc:
        logger.error("[twilio] external confirm failed: %s", exc)
        return {"success": False, "error": str(exc)}

    update_session(call_sid, {
        "cart": [],
        "state": DialogueState.DONE,
        "confirmed_order_number": order_number,
    })
    for entry in _CALL_LOG:
        if entry.get("call_sid") == call_sid:
            entry["order_number"] = order_number
            entry["order_total"]  = round(total, 2)
            entry["status"]       = "order_confirmed"
            break

    if call_sid in _CONFIRM_REQUESTS:
        _CONFIRM_REQUESTS[call_sid].set()

    logger.info("[twilio] external confirm  #%s  Rs.%.0f  callSid=%s",
                order_number, total, call_sid[:8])
    return {"success": True, "order_number": order_number, "total": round(total, 2)}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _send_audio(websocket: WebSocket, stream_sid: str, wav_bytes: bytes) -> None:
    """Convert Gemini's WAV response to μ-law 8 kHz and stream it to Twilio."""
    try:
        loop  = asyncio.get_event_loop()
        mulaw = await loop.run_in_executor(None, wav_to_mulaw8k, wav_bytes)
        await websocket.send_text(make_clear_message(stream_sid))
        for i in range(0, len(mulaw), 160):
            await websocket.send_text(
                make_media_message(stream_sid, mulaw[i : i + 160])
            )
        logger.debug("[twilio] streamed %.2f s of audio", len(mulaw) / 8_000)
    except Exception as exc:
        logger.warning("[twilio] _send_audio error: %s", exc)


async def _periodic_wait(websocket: WebSocket, stream_sid: str) -> None:
    """
    Fires every 8 s while Gemini is processing, streaming a 'please wait' message.
    Cancelled in worker() BEFORE Aria's audio is sent to prevent overlap.
    """
    wait_mulaw = get_wait_mulaw()
    while True:
        await asyncio.sleep(8.0)
        try:
            logger.debug("[twilio] sending 'please wait' interim message")
            for i in range(0, len(wait_mulaw), 160):
                await websocket.send_text(
                    make_media_message(stream_sid, wait_mulaw[i : i + 160])
                )
        except Exception:
            break


def _items_from_cmd_hint(cmd_str: str, menu_items: list[dict]) -> list[dict]:
    """
    Fallback: parse items from Gemini's [CMD: add_item | Item Name x2] tag
    when ``extract_cart_update`` returns no items (e.g. short/non-Latin input).
    """
    part = re.sub(r'^add_item\s*\|?\s*', '', cmd_str, flags=re.IGNORECASE).strip()
    if not part:
        return []
    resolved: list[dict] = []
    for raw in part.split(","):
        raw = raw.strip()
        if not raw:
            continue
        qty = 1
        qm  = re.search(r'\bx\s*(\d+)\b', raw, re.IGNORECASE)
        if qm:
            qty = int(qm.group(1))
            raw = (raw[: qm.start()] + raw[qm.end():]).strip()
        raw = re.sub(r'\(.*?\)', '', raw).strip()
        if not raw:
            continue
        rl      = raw.lower()
        matched = next((m for m in menu_items if m["name"].lower() == rl), None)
        if matched is None:
            matched = next(
                (m for m in menu_items
                 if rl in m["name"].lower() or m["name"].lower() in rl),
                None,
            )
        if matched:
            resolved.append({
                "product_id": str(matched["product_id"]),
                "name":       matched["name"],
                "qty":        qty,
                "modifiers":  {},
                "ambiguous":  False,
            })
    return resolved


def _build_context_update(
    turn:      _Turn,
    cart:      list[dict],
    cur_state: DialogueState,
    cust_name: str | None,
) -> str:
    """
    Build a compact per-turn text block injected into the persistent Gemini session
    BEFORE the audio.  Gives Gemini current cart state and turn-specific instructions
    without reopening the session.  With PTT mode (automatic_activity_detection=disabled)
    the text is batched as context and will NOT trigger a premature response.
    """
    lines = [f"[TURN {turn.turn_number}]"]

    if cart:
        grand_total = 0.0
        cart_lines  = []
        for c in cart:
            line_total = c["unit_price"] * c["quantity"] * (1 + c.get("tax_rate", 5.0) / 100)
            grand_total += line_total
            cart_lines.append(f"  {c['name']} ×{c['quantity']} = ₹{line_total:.0f} (incl. tax)")
        lines.append("CURRENT CART:")
        lines.extend(cart_lines)
        lines.append(f"  Grand Total: ₹{grand_total:.0f}")
    else:
        lines.append("CURRENT CART: empty")

    if cust_name:
        lines.append(f"Customer name: {cust_name}")

    if cur_state == DialogueState.AWAITING_KITCHEN_CONFIRM:
        lines.append(
            "STATE: AWAITING KITCHEN CONFIRMATION. "
            "The customer is responding to 'Shall I send this order to the kitchen?' "
            "Handle YES → [CMD: confirm_order], NO → [CMD: cancel_order]."
        )
    else:
        lines.append(
            f"Turn {turn.turn_number}. A pre-recorded greeting has already been played "
            "by the system. Do NOT greet. Respond directly to the customer's request."
        )

    return "\n".join(lines)


async def _run_turn(
    websocket:      WebSocket,
    stream_sid:     str,
    session_id:     str,
    turn:           _Turn,
    menu_items:     list[dict],
    call_log_ref:   dict,
    gemini_session: GeminiCallSession,
) -> tuple[bool, bytes | None]:
    """
    Process one conversational turn on the persistent Gemini Live session.
    Returns (call_done, wav_bytes).  The caller (worker) cancels the wait-audio
    task and then sends wav_bytes so the two audio streams never interleave.
    """
    session   = get_session(session_id, table_id="phone")
    cart      = list(session["cart"])
    cur_state = session.get("state", DialogueState.GREETING)
    cust_name = session.get("customer_name")

    context_update   = _build_context_update(turn, cart, cur_state, cust_name)
    audio_for_gemini = turn.audio if turn.is_pcm_wav else mulaw_to_wav8k(turn.audio)

    try:
        result = await gemini_session.send_turn(audio_for_gemini, context_update)
    except Exception as exc:
        logger.error("[twilio] send_turn error: %s", exc)
        return False, None

    transcript    = result.get("transcript", "")
    response_text = result.get("response_text", "")
    audio_b64     = result.get("audio_b64", "")
    wav_out       = base64.b64decode(audio_b64) if audio_b64 else None

    # ── Extract NAME tag from Aria's response ─────────────────────────────────
    name_match = re.search(r"\[NAME:\s*([^\]]+)\]", response_text, re.IGNORECASE)
    if name_match and not cust_name:
        extracted_name = name_match.group(1).strip()
        if extracted_name:
            cust_name = extracted_name
            update_session(session_id, {"customer_name": cust_name})
            logger.info("[twilio] customer name captured: %r  session=%s", cust_name, session_id[:8])

    # Pass Aria's response text so the extractor can use it as a fallback hint
    # (critical when the customer speaks in native script and transcript is empty).
    update_data = await extract_cart_update(transcript, menu_items, response_text)
    intent_str  = update_data.get("intent", "unknown")
    items_data  = update_data.get("items", [])

    # ── Trust Gemini's own [CMD:] tag for high-level call-flow intents ─────────
    # extract_cart_update may mis-classify short affirmations ("yes", "haan",
    # "go ahead") as unknown.  Aria's [CMD:] tag is authoritative for these.
    full_cmd   = result.get("cmd_hint", "")
    gemini_cmd = full_cmd.split("|")[0].strip().lower().replace(" ", "_")
    if gemini_cmd in ("confirm_order", "done_ordering", "cancel_order", "greeting"):
        intent_str = gemini_cmd
        logger.info("[twilio] intent overridden by cmd_hint: %r  session=%s", intent_str, session_id[:8])
    elif gemini_cmd == "add_item" and not items_data:
        # extract_cart_update found no items; fall back to parsing from cmd_hint
        fallback = _items_from_cmd_hint(full_cmd, menu_items)
        if fallback:
            intent_str = "add_item"
            items_data = fallback
            logger.info(
                "[twilio] add_item items from cmd_hint fallback: %r  session=%s",
                full_cmd[:80], session_id[:8],
            )

    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.UNKNOWN

    # ── Apply cart mutations ──────────────────────────────────────────────────
    if intent == Intent.ADD_ITEM:
        for item_data in items_data:
            pid  = str(item_data.get("product_id", ""))
            qty  = int(item_data.get("qty", 1))
            name = item_data.get("name", "")
            existing = next((c for c in cart if c["product_id"] == pid), None)
            if existing:
                existing["quantity"] += qty
            else:
                mi = next((m for m in menu_items if str(m["product_id"]) == pid), None)
                if mi:
                    mods     = item_data.get("modifiers") or {}
                    variants = mi.get("variants", [])
                    vid = vname = None
                    uprice = float(mi.get("price", 0))
                    tax_r  = float(mi.get("tax", 5.0))
                    if variants:
                        size_hint = (mods.get("size") or mods.get("variant") or "").lower()
                        chosen = next(
                            (v for v in variants if size_hint and size_hint in v["variant_name"].lower()),
                            variants[0],
                        )
                        vid    = chosen["variant_id"]
                        vname  = chosen["variant_name"]
                        uprice = float(chosen["price"])
                        tax_r  = float(chosen["gst_pct"])
                    cart.append({
                        "product_id":  pid,
                        "name":        mi["name"],
                        "quantity":    qty,
                        "unit_price":  uprice,
                        "tax_rate":    tax_r,
                        "variant_id":  vid,
                        "variant_name": vname,
                        "notes":       mods.get("notes"),
                        "modifiers":   {k: v for k, v in mods.items() if v and k != "notes"} or None,
                    })
                    logger.info("[twilio] +%d %s  session=%s", qty, name, session_id[:8])
        update_session(session_id, {"cart": cart})

    elif intent == Intent.REMOVE_ITEM:
        for item_data in items_data:
            pid  = str(item_data.get("product_id", ""))
            cart = [c for c in cart if c["product_id"] != pid]
        update_session(session_id, {"cart": cart})

    elif intent == Intent.CANCEL_ORDER:
        update_session(session_id, {"cart": [], "state": DialogueState.DONE})

    elif intent == Intent.DONE_ORDERING:
        # Customer says "that's all / no more" — transition to awaiting kitchen confirm.
        # Aria has already read back the order and asked "Shall I send to kitchen?"
        # (handled by the AWAITING_KITCHEN_CONFIRM block in the system instruction)
        update_session(session_id, {"state": DialogueState.AWAITING_KITCHEN_CONFIRM})
        logger.info("[twilio] state → AWAITING_KITCHEN_CONFIRM  session=%s", session_id[:8])

    elif intent == Intent.CONFIRM_ORDER:
        # ── DEBUG: log everything about this confirmation attempt ──────────────────
        _pool_obj = get_pool()
        print(
            f"\n[DEBUG CONFIRM ORDER] ================================================",
            flush=True,
        )
        print(f"[DEBUG CONFIRM ORDER] session_id    = {session_id}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] cur_state     = {cur_state}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] cart_len      = {len(cart)}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] cart_contents = {cart}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] cmd_hint raw  = {full_cmd!r}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] gemini_cmd    = {gemini_cmd!r}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] intent_str    = {intent_str!r}", flush=True)
        print(f"[DEBUG CONFIRM ORDER] DB pool       = {_pool_obj!r}", flush=True)
        logger.info(
            "[twilio][CONFIRM_DEBUG] CONFIRM_ORDER triggered  cart_len=%d  state=%s  "
            "pool=%r  session=%s",
            len(cart), cur_state, _pool_obj, session_id,
        )

        # Accept confirm_order if cart is non-empty regardless of current dialogue state.
        # Gemini's [CMD: confirm_order] tag is authoritative — no extra state guard needed.
        if cart:
            subtotal, tax, total = get_cart_total(cart)
            order_number = await generate_order_number()
            print(
                f"[DEBUG CONFIRM ORDER] order_number={order_number}  "
                f"subtotal={subtotal:.2f}  tax={tax:.2f}  total={total:.2f}",
                flush=True,
            )
            logger.info(
                "[twilio][CONFIRM_DEBUG] Calling insert_order  order_number=%s  "
                "total=%.2f  items=%s",
                order_number, total,
                [(c.get('name'), c.get('quantity'), c.get('unit_price')) for c in cart],
            )
            try:
                _order_id = await insert_order(
                    order_number=order_number,
                    cart=cart,
                    subtotal=subtotal,
                    tax=tax,
                    total=total,
                    placed_by="phone_order",
                    channel="phone",
                )
                print(
                    f"[DEBUG CONFIRM ORDER] ✅ insert_order SUCCESS  "
                    f"order_id={_order_id}  order_number={order_number}",
                    flush=True,
                )
                logger.info(
                    "[twilio][CONFIRM_DEBUG] ✅ insert_order SUCCESS  "
                    "order_id=%s  order_number=%s  session=%s",
                    _order_id, order_number, session_id,
                )
            except Exception as _db_exc:
                _tb_str = _traceback.format_exc()
                print(f"[DEBUG CONFIRM ORDER] ❌ insert_order FAILED!", flush=True)
                print(f"[DEBUG CONFIRM ORDER] Exception type : {type(_db_exc).__name__}", flush=True)
                print(f"[DEBUG CONFIRM ORDER] Exception msg  : {_db_exc}", flush=True)
                print(f"[DEBUG CONFIRM ORDER] Full traceback :\n{_tb_str}", flush=True)
                print(f"[DEBUG CONFIRM ORDER] cart at failure: {cart}", flush=True)
                print(f"[DEBUG CONFIRM ORDER] DB pool at fail: {get_pool()!r}", flush=True)
                logger.error(
                    "[twilio][CONFIRM_DEBUG] ❌ insert_order FAILED  session=%s\n"
                    "Exception: %s\nTraceback:\n%s",
                    session_id, _db_exc, _tb_str,
                )
                # Still hang up and play audio so the call doesn't freeze.
                # The operator can re-confirm via POST /twilio/confirm-phone-order/{sid}.
                call_log_ref["status"] = "order_db_failed"
                call_log_ref["error"]  = f"{type(_db_exc).__name__}: {_db_exc}"
                call_log_ref["turns"]  = turn.turn_number + 1
                call_log_ref.setdefault("transcript", []).append({
                    "turn":     turn.turn_number,
                    "customer": transcript[:200] if transcript else "",
                    "aria":     response_text[:200] if response_text else "",
                    "intent":   intent.value,
                })
                return True, wav_out

            logger.info(
                "[twilio] ORDER CONFIRMED  #%s  Rs.%.0f  session=%s",
                order_number, total, session_id[:8],
            )
            call_log_ref["order_number"] = order_number
            call_log_ref["order_total"]  = round(total, 2)
            call_log_ref["status"]       = "order_confirmed"
            update_session(session_id, {"cart": [], "state": DialogueState.DONE})

            # Log this final turn then signal call end
            call_log_ref["turns"] = turn.turn_number + 1
            call_log_ref.setdefault("transcript", []).append({
                "turn":     turn.turn_number,
                "customer": transcript[:200] if transcript else "",
                "aria":     response_text[:200] if response_text else "",
                "intent":   intent.value,
            })
            return True, wav_out
        else:
            print(
                f"[DEBUG CONFIRM ORDER] ⚠️  CONFIRM_ORDER intent but CART IS EMPTY!  "
                f"session={session_id}  state={cur_state}",
                flush=True,
            )
            logger.warning(
                "[twilio][CONFIRM_DEBUG] ⚠️  CONFIRM_ORDER but cart is EMPTY  "
                "session=%s  state=%s",
                session_id, cur_state,
            )

    # Update call log transcript
    call_log_ref["turns"] = turn.turn_number + 1
    call_log_ref.setdefault("transcript", []).append({
        "turn":     turn.turn_number,
        "customer": transcript[:200] if transcript else "",
        "aria":     response_text[:200] if response_text else "",
        "intent":   intent.value,
    })

    update_session(session_id, {
        "last_intent":   intent.value,
        "last_response": response_text,
        "turn":          session.get("turn", 0) + 1,
    })
    logger.info(
        "[twilio] turn done  intent=%-18s  transcript=%r  session=%s",
        intent.value, transcript[:80], session_id[:8],
    )
    return False, wav_out

# ── WebSocket stream handler ──────────────────────────────────────────────────

@router.websocket("/stream")
async def twilio_stream(websocket: WebSocket) -> None:
    """
    Handles the Twilio bidirectional Media Stream WebSocket.

    One asyncio.Queue feeds a single worker coroutine so that voice turns are
    processed sequentially — no two Gemini Live sessions overlap.

    Key behaviours:
    - ai_is_speaking=True while the worker is active → inbound frames are dropped
      to prevent noise/echo from triggering a re-greeting.
    - vad.reset() after every turn discards stale buffered audio.
    - A 10-second periodic task streams "please wait" if Gemini is slow.
    - Every call is logged to _CALL_LOG for the /twilio/call-logs endpoint.
    """
    await websocket.accept()

    stream_sid:   str | None = None
    call_sid:     str | None = None
    session_id:   str | None = None
    menu_items:   list[dict] = []
    combo_deals:  list[dict] = []
    active_offers: list[dict] = []
    turn_counter: int        = 0

    # Shared flag — safe because asyncio is single-threaded (no preemption between awaits)
    ai_is_speaking = False

    queue: asyncio.Queue[_Turn | None] = asyncio.Queue()
    order_done  = False
    call_done_event = asyncio.Event()   # set when order confirmed → closes WS
    call_log_entry: dict = {}
    external_confirm_task: asyncio.Task | None = None

    async def _watch_external_confirm(ev: asyncio.Event) -> None:
        """Close the call when the dashboard UI confirms the order."""
        await ev.wait()
        call_done_event.set()

    # ── Worker: process turns one at a time on a single persistent Gemini session ─
    async def worker() -> None:
        nonlocal order_done, ai_is_speaking

        gemini_session: GeminiCallSession | None = None
        try:
            while True:
                item = await queue.get()
                if item is None:
                    queue.task_done()
                    break

                # Open the Gemini Live session once before the first turn.
                # By this point, menu_items is populated by the "start" event handler.
                if gemini_session is None:
                    gemini_session = GeminiCallSession()
                    try:
                        static_instr = build_live_system_instruction(
                            menu_items, [],
                            combo_deals=combo_deals,
                            active_offers=active_offers,
                        )
                        await gemini_session.open(static_instr)
                    except Exception as exc:
                        logger.error("[twilio] Failed to open Gemini session: %s", exc)
                        queue.task_done()
                        order_done = True
                        break

                wait_task: asyncio.Task | None = None
                done    = False
                wav_out: bytes | None = None
                try:
                    ai_is_speaking = True
                    wait_task = asyncio.create_task(
                        _periodic_wait(websocket, stream_sid)
                    )
                    done, wav_out = await _run_turn(
                        websocket, stream_sid, session_id,
                        item, menu_items, call_log_entry, gemini_session,
                    )
                except Exception as exc:
                    _exc_tb = _traceback.format_exc()
                    print(
                        f"[DEBUG WORKER] ❌ _run_turn EXCEPTION  "
                        f"session={session_id}  turn={item.turn_number}\n"
                        f"Exception: {type(exc).__name__}: {exc}\n"
                        f"Traceback:\n{_exc_tb}",
                        flush=True,
                    )
                    logger.exception(
                        "[twilio][WORKER_DEBUG] ❌ _run_turn raised  "
                        "session=%s  turn=%s\nTraceback:\n%s",
                        session_id, item.turn_number, _exc_tb,
                    )
                finally:
                    # Cancel the wait-audio task BEFORE sending Aria's response
                    # to prevent the two streams from interleaving / overlapping.
                    if wait_task:
                        wait_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await wait_task
                    if wav_out:
                        await _send_audio(websocket, stream_sid, wav_out)
                    if done:
                        order_done = True
                        call_done_event.set()   # will close the WS from the closer task
                    ai_is_speaking = False
                    vad.reset()   # discard audio captured while AI was speaking
                    queue.task_done()

                if order_done:
                    break
        finally:
            if gemini_session and gemini_session.connected:
                await gemini_session.close()

    worker_task = asyncio.create_task(worker())
    vad = VAD()

    # Closes the WebSocket once the order is confirmed so Twilio hangs up.
    async def _hangup_when_done() -> None:
        await call_done_event.wait()
        await asyncio.sleep(0.5)  # brief pause so final audio finishes streaming
        with suppress(Exception):
            await websocket.close(1000)
    hangup_task = asyncio.create_task(_hangup_when_done())

    async def _play_greeting() -> None:
        """Play the pre-recorded restaurant greeting directly to Twilio.
        Blocks inbound VAD frames during playback so the customer's
        background noise does not trigger a premature order turn."""
        nonlocal ai_is_speaking
        ai_is_speaking = True
        try:
            gm = get_greeting_mulaw()
            for i in range(0, len(gm), 160):
                await websocket.send_text(make_media_message(stream_sid, gm[i : i + 160]))
            await asyncio.sleep(0.4)   # brief pause before accepting customer speech
        except Exception as exc:
            logger.warning("[twilio] greeting playback error: %s", exc)
        finally:
            ai_is_speaking = False
            vad.reset()

    try:
        async for raw in websocket.iter_text():
            if order_done:
                break

            try:
                msg = json.loads(raw)
            except Exception:
                continue

            event = msg.get("event")

            if event == "connected":
                logger.debug("[twilio] connected message received")
                continue

            # ── Stream start ──────────────────────────────────────────────────
            if event == "start":
                start_info  = msg.get("start", {})
                stream_sid  = start_info.get("streamSid") or msg.get("streamSid", "")
                call_sid    = start_info.get("callSid",   "unknown")
                caller      = start_info.get("customParameters", {}).get("From", "")
                session_id  = call_sid
                menu_items  = await _get_menu()
                combo_deals, active_offers = await _get_combos_and_offers()
                turn_counter = 0

                call_log_entry.update({
                    "call_sid":     call_sid,
                    "caller":       caller,
                    "start_time":   datetime.now(timezone.utc).isoformat(),
                    "end_time":     None,
                    "status":       "in_progress",
                    "turns":        0,
                    "order_number": None,
                    "order_total":  None,
                    "transcript":   [],
                })
                _log_call(call_log_entry)

                # Register external-confirm event so the UI can trigger order placement
                _ce = asyncio.Event()
                _CONFIRM_REQUESTS[call_sid] = _ce
                external_confirm_task = asyncio.create_task(_watch_external_confirm(_ce))

                logger.info(
                    "[twilio] stream START  callSid=%s  streamSid=%s",
                    call_sid, stream_sid,
                )
                # Play the pre-recorded gTTS greeting directly; no Gemini turn needed.
                # Customer speaks first; Gemini processes from turn 1 onward.
                asyncio.create_task(_play_greeting())
                turn_counter = 1

            # ── Inbound audio frames ──────────────────────────────────────────
            elif event == "media":
                if not session_id:
                    continue
                # Drop frames while AI is speaking to prevent re-greeting
                if ai_is_speaking:
                    continue
                payload = msg.get("media", {}).get("payload", "")
                if not payload:
                    continue
                mulaw_frame = base64.b64decode(payload)
                segment = vad.push_frame(mulaw_frame)
                if segment:
                    await queue.put(_Turn(
                        audio=segment,
                        is_pcm_wav=False,
                        is_greeting=False,
                        turn_number=turn_counter,
                    ))
                    turn_counter += 1

            # ── Stream stop ───────────────────────────────────────────────────
            elif event == "stop":
                logger.info("[twilio] stream STOP  callSid=%s", call_sid)
                leftover = vad.flush()
                if leftover:
                    await queue.put(_Turn(
                        audio=leftover,
                        is_pcm_wav=False,
                        is_greeting=False,
                        turn_number=turn_counter,
                    ))
                    turn_counter += 1
                break

    except WebSocketDisconnect:
        logger.info("[twilio] WebSocket disconnected  callSid=%s", call_sid)
    except Exception as exc:
        logger.exception("[twilio] stream error  callSid=%s  %s", call_sid, exc)
    finally:
        if external_confirm_task:
            external_confirm_task.cancel()
            with suppress(asyncio.CancelledError):
                await external_confirm_task
        if call_sid:
            _CONFIRM_REQUESTS.pop(call_sid, None)
        hangup_task.cancel()
        with suppress(asyncio.CancelledError):
            await hangup_task
        await queue.put(None)
        await worker_task
        if call_log_entry:
            if not call_log_entry.get("end_time"):
                call_log_entry["end_time"] = datetime.now(timezone.utc).isoformat()
            if call_log_entry.get("status") == "in_progress":
                call_log_entry["status"] = "completed"
        if session_id:
            reset_session(session_id)
            logger.info("[twilio] session cleared  callSid=%s", call_sid)
