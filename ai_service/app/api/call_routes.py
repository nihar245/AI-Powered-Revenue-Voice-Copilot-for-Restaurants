"""
Twilio SIP Voice Call Integration for Restaurant Voice Copilot.

Handles inbound VoIP calls from SIP softphones (Zoiper, Linphone, etc.)
using the EXISTING pipeline — nothing is changed:

    Deepgram STT (Nova-3) → Groq LLM (Llama 3.3 70B) → TTS
        English → Deepgram Aura-2
        Hindi   → edge-tts (hi-IN-SwaraNeural)

Flow:
  1. Caller dials SIP URI → Twilio sends webhook to /incoming-call
  2. Server answers, generates greeting TTS audio, serves it via <Play>
  3. Server starts <Record> to capture caller speech
  4. Twilio posts recording to /process-recording
  5. Server downloads the recording WAV from Twilio
  6. Audio → existing transcribe_audio() (Deepgram STT)
  7. Transcript → existing Groq LLM pipeline
  8. LLM response → existing synthesize_speech() (Deepgram EN / edge-tts HI)
  9. Generated audio saved to /static/call_audio/, served via <Play>
  10. Loop back to <Record> for next turn

Endpoints:
  POST /api/call/incoming-call     — Twilio SIP webhook (answers + greets + records)
  POST /api/call/process-recording — Download recording → STT → LLM → TTS → <Play>
  POST /api/call/status            — Call status callback
  GET  /api/call/audio/<filename>  — Serve generated TTS audio files
  GET  /api/call/active            — List active call sessions
  GET  /api/call/history           — List all call sessions
  POST /api/call/simulate          — Test pipeline without Twilio (text in → text + order out)

===========================================================================
TWILIO SIP DOMAIN SETUP (step-by-step)
===========================================================================

1. CREATE A TWILIO ACCOUNT
   - Sign up at https://www.twilio.com/
   - Note your Account SID and Auth Token from the dashboard

2. CREATE A SIP DOMAIN
   - Go to: Twilio Console → Voice → SIP Domains
   - URL: https://console.twilio.com/us1/develop/voice/manage/sip-domains
   - Click "Create SIP Domain"
   - Domain name: restaurant-ai  (gives you: restaurant-ai.sip.twilio.com)
   - Voice Configuration:
       Request URL: POST https://YOUR-NGROK-URL/api/call/incoming-call
       Status Callback: POST https://YOUR-NGROK-URL/api/call/status

3. CREATE A CREDENTIAL LIST (for softphone authentication)
   - Go to: SIP Domain → Credential Lists
   - Create new credential list: "restaurant-callers"
   - Add credentials:
       Username: restaurant-ai
       Password: YourSecurePassword123
   - Assign this credential list to your SIP Domain under "Authentication"

4. EXPOSE LOCAL SERVER WITH NGROK
   - Install ngrok: https://ngrok.com/download
   - Run: ngrok http 8001
   - Copy the HTTPS URL (e.g. https://abc123.ngrok.io)
   - Set it as TWILIO_BASE_URL env var, or in config.py

5. CONFIGURE ZOIPER SOFTPHONE
   - Download Zoiper: https://www.zoiper.com/
   - Add a SIP account:
       Username:  restaurant-ai
       Password:  YourSecurePassword123
       Domain:    restaurant-ai.sip.twilio.com
       Auth user: restaurant-ai
   - Dial: sip:restaurant-ai@restaurant-ai.sip.twilio.com
   - The AI assistant will answer and start taking your order!

6. CONFIGURE LINPHONE (alternative)
   - SIP Account → Add
       Username:  restaurant-ai
       SIP Domain: restaurant-ai.sip.twilio.com
       Password: YourSecurePassword123
       Transport: TLS or UDP
   - Call: restaurant-ai@restaurant-ai.sip.twilio.com

ENVIRONMENT VARIABLES:
  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN=79564f53d8d490a0c6784a70c457a3a7
  TWILIO_SIP_DOMAIN=restaurant-ai.sip.twilio.com
  TWILIO_BASE_URL=https://your-ngrok-url.ngrok.io
===========================================================================
"""

import asyncio
import base64
import json
import os
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

# DB URL for persisting call logs
_DB_URL = "postgresql://postgres:12345678@localhost:5432/postgres"

import httpx

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse

from app.config import settings
from app.nlp.prompts import CONVERSATION_SYSTEM_PROMPT
from app.services.menu_service import get_menu_items, get_combos_for_context
from app.services.groq_client import async_client as groq_client
from app.voice.stt import transcribe_audio        # ← EXISTING Deepgram STT
from app.voice.tts import synthesize_speech        # ← EXISTING TTS (Deepgram EN / edge-tts HI)
from app.websocket.manager import ws_manager, EventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/call", tags=["twilio-sip-calls"])

# ─────────────── Audio file storage for <Play> URLs ───────────────
AUDIO_DIR = Path(__file__).parent.parent / "static" / "call_audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _get_base_url() -> str:
    """
    Get the public base URL for serving audio files.
    In production, set TWILIO_BASE_URL env var.
    For local dev, use your ngrok URL.
    """
    url = settings.twilio.base_url or os.getenv("TWILIO_BASE_URL", "")
    if url:
        return url.rstrip("/")
    # Fallback: localhost (won't work with real Twilio, only for testing)
    return f"http://localhost:{settings.port}"


def _save_audio_file(audio_bytes: bytes, audio_format: str, prefix: str = "resp") -> str:
    """
    Save TTS audio bytes to disk and return the public URL.

    Args:
        audio_bytes: Raw audio data from TTS engine.
        audio_format: 'wav' or 'mp3'.
        prefix: Filename prefix.

    Returns:
        Public URL that Twilio can <Play>.
    """
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.{audio_format}"
    filepath = AUDIO_DIR / filename
    filepath.write_bytes(audio_bytes)
    logger.info("💾 Saved TTS audio: %s (%d bytes)", filename, len(audio_bytes))
    return f"{_get_base_url()}/api/call/audio/{filename}"


# ─────────────── In-memory call session store ───────────────

@dataclass
class CallSession:
    """Tracks conversation state for a single phone call."""
    call_sid: str
    phone_number: str
    started_at: float = field(default_factory=time.time)
    language: str = "hi"  # Default Hindi for Indian restaurant
    turns: list = field(default_factory=list)  # [{role, text, ts}]
    order_items: list = field(default_factory=list)
    total: float = 0.0
    status: str = "active"  # active | ended
    pending_cancel: Optional[dict] = None  # set when waiting for cancel confirmation
    customer_name: str = ""  # captured during call when Gemini asks for name

    def add_turn(self, role: str, text: str):
        self.turns.append({"role": role, "text": text, "ts": time.time()})

    def get_chat_history(self) -> list[dict]:
        """Format turns as OpenAI-style messages for the LLM."""
        return [
            {"role": "user" if t["role"] == "customer" else "assistant", "content": t["text"]}
            for t in self.turns
        ]

    def get_order_summary_text(self) -> str:
        if not self.order_items:
            return "  (empty — customer hasn't ordered yet)"
        lines = [
            f"  - {it.get('quantity', 1)}x {it['name']} (₹{it.get('subtotal', it.get('price', 0))})"
            for it in self.order_items
        ]
        lines.append(f"  Total: ₹{self.total}")
        return "\n".join(lines)


_call_sessions: dict[str, CallSession] = {}

# ─────────────── Pending AI responses (background processing) ───────────────
# When Twilio POSTs a recording, we kick off the pipeline in the background
# and return a "please hold" TwiML immediately.  A polling endpoint checks
# whether the result is ready so we never exceed Twilio's 15-second webhook
# timeout.
#
# Structure:  { task_key: { "event": asyncio.Event, "twiml": str | None } }
_pending_responses: dict[str, dict] = {}


def _get_or_create_session(call_sid: str, phone: str = "") -> CallSession:
    if call_sid not in _call_sessions:
        _call_sessions[call_sid] = CallSession(call_sid=call_sid, phone_number=phone)
        logger.info("📞 New call session: %s from %s", call_sid, phone)
        # Persist new call to DB asynchronously (fire-and-forget)
        asyncio.create_task(_upsert_call_log(call_sid, phone, status="active"))
    return _call_sessions[call_sid]


async def _upsert_call_log(
    call_sid: str,
    phone: str = "",
    status: str = "active",
    session: Optional["CallSession"] = None,
) -> None:
    """
    INSERT or UPDATE a call_logs row for this call.
    Safe to call multiple times — uses ON CONFLICT DO UPDATE.
    """
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_DB_URL, timeout=5.0)
        try:
            order_items_json = None
            total_val        = 0.0
            turn_count       = 0
            duration_sec     = None
            ended_at         = None
            language         = "hi"
            transcript_json  = None

            if session:
                order_items_json = json.dumps(session.order_items) if session.order_items else None
                total_val        = session.total
                turn_count       = len(session.turns)
                language         = session.language
                started          = session.started_at
                ended_at         = time.time() if status == "ended" else None
                duration_sec     = int(ended_at - started) if ended_at else None
                transcript_json  = json.dumps(session.turns) if session.turns else None

            await conn.execute("""
                INSERT INTO call_logs
                    (call_sid, phone_number, status, turn_count, language,
                     order_items, total, full_transcript, ended_at, duration_sec)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::jsonb, $9, $10)
                ON CONFLICT (call_sid) DO UPDATE SET
                    status          = EXCLUDED.status,
                    turn_count      = EXCLUDED.turn_count,
                    language        = EXCLUDED.language,
                    order_items     = EXCLUDED.order_items,
                    total           = EXCLUDED.total,
                    full_transcript = EXCLUDED.full_transcript,
                    ended_at        = EXCLUDED.ended_at,
                    duration_sec    = EXCLUDED.duration_sec
            """,
                call_sid,
                phone or None,
                status,
                turn_count,
                language,
                order_items_json,
                total_val,
                transcript_json,
                ended_at,
                duration_sec,
            )
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Failed to persist call log for %s: %s", call_sid, e)


async def _lookup_latest_order_by_phone(phone: str) -> Optional[dict]:
    """Find latest placed/preparing order for a phone number WITHOUT cancelling."""
    if not phone or phone in ("simulator", "unknown", ""):
        return None
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_DB_URL, timeout=5.0)
        try:
            customer = await conn.fetchrow(
                "SELECT customer_id FROM customers WHERE phone = $1", phone
            )
            if not customer:
                return None
            cid = customer["customer_id"]
            order = await conn.fetchrow("""
                SELECT o.order_id, o.total, o.status,
                       json_agg(json_build_object('name', mi.name, 'qty', oi.qty)
                                ORDER BY oi.line_id) AS items
                FROM orders o
                LEFT JOIN order_items oi ON oi.order_id = o.order_id
                LEFT JOIN menu_items mi ON mi.item_id = oi.item_id
                WHERE o.customer_id = $1
                  AND o.status IN ('placed','preparing')
                  AND o.placed_at > NOW() - INTERVAL '24 hours'
                GROUP BY o.order_id
                ORDER BY o.placed_at DESC
                LIMIT 1
            """, cid)
            if not order:
                return None
            return {
                "order_id": order["order_id"],
                "total":    float(order["total"]),
                "status":   order["status"],
                "items":    order["items"] or [],
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Failed to lookup order for phone %s: %s", phone, e)
        return None


async def _cancel_latest_order_by_phone(phone: str) -> Optional[dict]:
    """
    Find the most recent non-cancelled order for a phone number and cancel it.
    Returns order info dict if cancelled, None if no order found.
    """
    if not phone or phone in ("simulator", "unknown", ""):
        return None
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_DB_URL, timeout=5.0)
        try:
            # Find customer by phone
            customer = await conn.fetchrow(
                "SELECT customer_id FROM customers WHERE phone = $1", phone
            )
            if not customer:
                return None
            cid = customer["customer_id"]

            # Find latest placed order for this customer (within 24h)
            order = await conn.fetchrow("""
                SELECT order_id, total, status, placed_at
                FROM orders
                WHERE customer_id = $1
                  AND status IN ('placed','preparing')
                  AND placed_at > NOW() - INTERVAL '24 hours'
                ORDER BY placed_at DESC
                LIMIT 1
            """, cid)

            if not order:
                return None

            order_id = order["order_id"]
            await conn.execute(
                "UPDATE orders SET status = 'cancelled' WHERE order_id = $1",
                order_id,
            )
            logger.info("✅ Cancelled order #%d for phone %s", order_id, phone)
            return {
                "order_id": order_id,
                "total":    float(order["total"]),
                "status":   "cancelled",
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Failed to cancel order for phone %s: %s", phone, e)
        return None


# ─────────────── LLM Processing (uses EXISTING Groq pipeline) ───────────────

def _build_call_system_prompt(session: CallSession) -> str:
    """Build the system prompt with live menu data and current order."""
    menu_lines = get_menu_items()
    combos = get_combos_for_context()

    menu_str = "\n".join(f"  - {item}" for item in menu_lines)
    if combos:
        menu_str += "\n\nCOMBO MEALS (special price when ordered as combo):\n"
        menu_str += "\n".join(f"  - {c}" for c in combos)

    return CONVERSATION_SYSTEM_PROMPT.format(
        menu_items=menu_str,
        current_order=session.get_order_summary_text(),
    )


async def _process_call_turn(session: CallSession, customer_text: str) -> str:
    """
    Process one conversation turn through the EXISTING LLM pipeline.

    1. Add customer text to session history
    2. Send full history + system prompt to Groq LLM
    3. Parse order JSON from response (if present)
    4. Return clean agent text for TTS
    """
    session.add_turn("customer", customer_text)

    system_prompt = _build_call_system_prompt(session)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.get_chat_history())

    start = time.perf_counter()
    llm_response = await groq_client.chat.completions.create(
        model=settings.groq.model,
        messages=messages,
        temperature=0.7,
        max_tokens=500,
    )
    agent_text = (llm_response.choices[0].message.content or "").strip()
    llm_ms = (time.perf_counter() - start) * 1000
    logger.info("📞 LLM response (%.0fms): %s", llm_ms, agent_text[:100])

    if not agent_text:
        agent_text = "Sorry, could you please repeat that?"

    # Extract order JSON markers (|||ORDER_JSON|||...|||END_ORDER|||)
    pattern = r'\|\|\|ORDER_JSON\|\|\|\s*(.*?)\s*\|\|\|END_ORDER\|\|\|'
    match = re.search(pattern, agent_text, re.DOTALL)
    if match:
        clean_text = agent_text[:match.start()].strip()
        try:
            order_data = json.loads(match.group(1).strip())
            if order_data.get("items"):
                session.order_items = order_data["items"]
                session.total = order_data.get("total", 0)
                logger.info("📞 Order updated: %d items, ₹%.0f",
                            len(session.order_items), session.total)
        except json.JSONDecodeError:
            pass
        agent_text = clean_text or agent_text

    session.add_turn("agent", agent_text)
    return agent_text


# ─────────────── TwiML Helpers ───────────────

def _twiml(content: str) -> Response:
    """Return a TwiML XML response."""
    return Response(content=content, media_type="application/xml")


def _escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))


# ─────────────── Audio download from Twilio ───────────────

async def _download_twilio_recording(recording_url: str) -> bytes:
    """
    Download a recording from Twilio's servers.

    Twilio provides RecordingUrl without .wav extension —
    append .wav to get the audio file.
    Uses HTTP Basic Auth with Account SID + Auth Token.
    """
    if recording_url.startswith("/"):
        recording_url = f"https://api.twilio.com{recording_url}"

    wav_url = f"{recording_url}.wav"
    logger.info("📞 Downloading recording: %s", wav_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            wav_url,
            auth=(settings.twilio.account_sid, settings.twilio.auth_token),
        )
        response.raise_for_status()
        logger.info("📞 Recording downloaded: %d bytes", len(response.content))
        return response.content


# ─────────────── Gemini Live proxy ───────────────

_GEMINI_SERVICE_URL = "http://localhost:8002"


async def _gemini_voice_turn(call_sid: str, audio_bytes: bytes) -> dict:
    """
    Proxy one Twilio call turn to the Gemini Live service (port 8002).

    Replaces 3 sequential API calls (Deepgram STT → Groq LLM → Deepgram TTS)
    with ONE Gemini Live session that does audio-in → audio-out natively.

    The Gemini service:
      - Fetches the live menu directly from PostgreSQL
      - Runs Gemini Live native audio (STT + reasoning + TTS in one session)
      - Maintains per-call cart state via session_id = call_sid
      - Returns: audio_base64 (WAV), transcript, response_text, cart, dialogue_state

    Latency: ~2-4 sec vs ~8-15 sec for the 3-step pipeline.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        files = {"audio": ("call.wav", audio_bytes, "audio/wav")}
        data  = {"session_id": call_sid, "table_id": "twilio"}
        resp  = await client.post(
            f"{_GEMINI_SERVICE_URL}/voice/order",
            files=files,
            data=data,
        )
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/incoming-call")
async def incoming_call(request: Request):
    """
    Twilio SIP webhook — called when a VoIP call arrives.

    Flow:
      1. Extract caller info from Twilio form data
      2. Create a call session
      3. Generate greeting audio using EXISTING TTS pipeline
         (Hindi → edge-tts hi-IN-SwaraNeural)
      4. Return TwiML:  <Play greeting>  then  <Record caller speech>

    Twilio Config:
      Set your SIP Domain's Voice URL to:
        POST https://your-ngrok-url/api/call/incoming-call
    """
    form = await request.form()
    call_sid = form.get("CallSid", f"unknown-{int(time.time())}")
    caller = form.get("From", "unknown")
    called = form.get("To", "unknown")

    logger.info("═══════════════════════════════════════")
    logger.info("📞 INCOMING SIP CALL")
    logger.info("   From: %s", caller)
    logger.info("   To:   %s", called)
    logger.info("   SID:  %s", call_sid)
    logger.info("═══════════════════════════════════════")

    session = _get_or_create_session(call_sid, caller)

    # Broadcast to admin dashboard
    await ws_manager.broadcast(EventType.CALL_STARTED, {
        "call_sid": call_sid,
        "caller": caller,
        "type": "sip_call",
    })

    # ─── Generate bilingual greeting (English + Hindi + Gujarati hint so caller can
    # respond in any of the three; Gemini detects language from turn 1 onwards)  ───
    rname = settings.restaurant_name
    # Bilingual greeting: English base + Hindi + Gujarati welcome so caller can
    # naturally respond in whichever language they prefer (Gemini detects it from turn 1).
    greeting_text = (
        f"Welcome to {rname}! "
        "Namaste! Aap kya order karna chahenge? "
        "Kem cho? Tamne shu joiye chhe? "
        "You can speak in English, Hindi, or Gujarati."
    )
    session.add_turn("agent", greeting_text)

    tts_result = await synthesize_speech(greeting_text, language="en")
    greeting_url = _save_audio_file(
        tts_result["audio_bytes"],
        tts_result["audio_format"],
        prefix="greet",
    )
    logger.info("📞 Greeting TTS: engine=%s, format=%s, %d bytes",
                tts_result["engine"], tts_result["audio_format"],
                len(tts_result["audio_bytes"]))

    # ─── TwiML: Play greeting → Record caller speech ───
    base = _get_base_url()
    twiml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{greeting_url}</Play>
    <Record
        action="{base}/api/call/process-recording"
        method="POST"
        maxLength="45"
        playBeep="false"
        trim="trim-silence"
        timeout="10"
        transcribe="false"
    />
    <Say voice="Polly.Aditi" language="hi-IN">Kya aap order dena chahte hain? Abhi boliye please. Are you there? Please tell us your order.</Say>
    <Record
        action="{base}/api/call/process-recording"
        method="POST"
        maxLength="45"
        playBeep="false"
        trim="trim-silence"
        timeout="10"
        transcribe="false"
    />
    <Hangup/>
</Response>"""

    return _twiml(twiml_xml)


@router.post("/process-recording")
async def process_recording(request: Request):
    """
    Receive a recorded speech segment from the caller.

    Instead of running the full pipeline synchronously (which can exceed
    Twilio's ~15-second webhook timeout), this endpoint:
      1. Validates the recording metadata
      2. Kicks off the AI pipeline in a background asyncio task
      3. Immediately returns TwiML with a "please hold" message
         and a <Redirect> to the polling endpoint /check-response/{key}

    The background task stores its TwiML result in _pending_responses
    and signals the asyncio.Event so the polling endpoint can return it.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    recording_url = form.get("RecordingUrl", "")
    recording_sid = form.get("RecordingSid", "")
    recording_duration = form.get("RecordingDuration", "0")

    logger.info("📞 Recording received [%s]: SID=%s, dur=%ss, URL=%s",
                call_sid, recording_sid, recording_duration, recording_url)

    session = _get_or_create_session(call_sid)

    # ─── Skip very short recordings (silence / noise) ───
    if int(recording_duration or 0) < 1:
        logger.warning("📞 Recording too short (%ss), asking to repeat", recording_duration)
        retry_text = "Sorry, mujhe kuch sunai nahi diya. Kya aap dubara bol sakte hain?"
        tts_result = await synthesize_speech(retry_text, language="hi")
        retry_url = _save_audio_file(
            tts_result["audio_bytes"], tts_result["audio_format"], prefix="retry"
        )
        base = _get_base_url()
        return _twiml(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{retry_url}</Play>
    <Record
        action="{base}/api/call/process-recording"
        method="POST"
        maxLength="45"
        playBeep="false"
        trim="trim-silence"
        timeout="10"
        transcribe="false"
    />
    <Hangup/>
</Response>""")

    if not recording_url:
        logger.error("📞 No RecordingUrl in request!")
        return _twiml("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">Sorry, there was an error. Goodbye.</Say>
    <Hangup/>
</Response>""")

    # ─── Kick off the full pipeline in the background ───
    task_key = f"{call_sid}_{recording_sid or int(time.time()*1000)}"
    event = asyncio.Event()
    _pending_responses[task_key] = {"event": event, "twiml": None}

    asyncio.create_task(
        _run_pipeline_background(task_key, call_sid, recording_url, session)
    )

    # ─── Return immediate hold message + redirect to polling endpoint ───
    base = _get_base_url()
    # Use language detected in previous turn (defaults to "hi" on first turn)
    if session.language == "en":
        hold_say = '<Say voice="Polly.Matthew" language="en-US">One moment, processing your order.</Say>'
    elif session.language == "gu":
        hold_say = '<Say voice="Polly.Matthew" language="en-US">Ek kshan, tamaroo order process thayu chhe.</Say>'
    else:  # hi / default
        hold_say = '<Say voice="Polly.Aditi" language="hi-IN">Ek second, main aapka order process kar rahi hoon.</Say>'
    return _twiml(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    {hold_say}
    <Redirect method="POST">{base}/api/call/check-response/{task_key}</Redirect>
</Response>""")


# ═══════════════════════════════════════════════════════════════════════════
#  BACKGROUND PIPELINE — runs the full AI pipeline asynchronously
# ═══════════════════════════════════════════════════════════════════════════

async def _run_pipeline_background(
    task_key: str,
    call_sid: str,
    recording_url: str,
    session: CallSession,
) -> None:
    """
    Run the AI pipeline in the background using Gemini Live (single API call).

    ─── OLD pipeline (3 sequential network calls, ~8-15 sec) ───
      Download WAV → Deepgram STT → Groq LLM → Deepgram/edge-tts TTS

    ─── NEW pipeline (1 network call, ~2-4 sec) ─────────────────
      Download WAV → Gemini Live (STT + reasoning + TTS in one session)

    The Gemini service (port 8002) also reads the menu LIVE from PostgreSQL
    (not from hardcoded fallback data).

    Stores the resulting TwiML in _pending_responses[task_key]["twiml"]
    and signals the asyncio.Event so the polling endpoint can return it.
    """
    base = _get_base_url()
    try:
        # ═══ STEP 1: Download recording from Twilio ═══
        audio_bytes = await _download_twilio_recording(recording_url)

        # ═══ STEP 2: Gemini Live — STT + LLM reasoning + TTS in one call ═══
        #
        #   Sends the WAV audio to ai_service_gemini (port 8002) which:
        #     • Converts audio → PCM 16 kHz (ffmpeg)
        #     • Opens a Gemini Live session with live DB menu as context
        #     • Streams audio → Gemini → gets audio response back
        #     • Returns: audio_base64 (WAV 24kHz), transcript, response_text,
        #                cart state, dialogue_state
        #
        gemini_start = time.perf_counter()
        try:
            gemini_data = await _gemini_voice_turn(call_sid, audio_bytes)
        except Exception as gemini_err:
            logger.error("📞 Gemini Live failed (%s). Falling back to Groq pipeline.", gemini_err)
            # ── Graceful fallback: Deepgram STT → Groq LLM → edge-tts TTS ──
            stt_result    = await transcribe_audio(audio_bytes)
            transcript    = stt_result.get("text", "").strip()
            agent_response = await _process_call_turn(session, transcript) if transcript else \
                "Sorry, mujhe samajh nahi aaya. Kya aap dubara bol sakte hain?"
            tts_result    = await synthesize_speech(agent_response, language=session.language)
            audio_url     = _save_audio_file(
                tts_result["audio_bytes"], tts_result["audio_format"], prefix="resp"
            )
            # ── Broadcast to admin dashboard (same as Gemini path) ──
            if transcript:
                await ws_manager.broadcast(EventType.TRANSCRIPT_RECEIVED, {
                    "call_sid": call_sid, "transcript": transcript,
                    "language": session.language, "confidence": 0.9, "stt_ms": 0,
                })
            await ws_manager.broadcast(EventType.RESPONSE_GENERATED, {
                "call_sid": call_sid, "response_text": agent_response,
                "tts_engine": "edge-tts", "stt_engine": "deepgram", "total_ms": 0,
                "order": {"items": session.order_items, "total": session.total},
            })
            # ── Check end-of-call so confirm+hangup works even without Gemini ──
            fb_end_kws = [
                "goodbye", "bye", "alvida", "dhanyavaad", "thank you",
                "order confirmed", "order placed", "order complete",
                "has been placed", "enjoy your meal", "aapka order",
                "order thayu", "aavjo",
            ]
            if any(kw in agent_response.lower() for kw in fb_end_kws):
                session.status = "ended"
                if session.order_items:
                    await ws_manager.broadcast(EventType.ORDER_CONFIRMED, {
                        "call_sid": call_sid, "phone": session.phone_number,
                        "items": session.order_items, "total": session.total,
                        "customer_name": session.customer_name,
                    })
                _set_pending_result(task_key, f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Pause length="1"/>
    <Hangup/>
</Response>""")
            else:
                _set_pending_result(task_key, _build_continue_twiml(base, audio_url, session.language))
            return

        gemini_ms      = (time.perf_counter() - gemini_start) * 1000
        transcript     = gemini_data.get("transcript", "").strip()
        agent_response = gemini_data.get("response_text", "").strip()
        detected_lang  = (gemini_data.get("language") or "en").value \
            if hasattr(gemini_data.get("language"), "value") else \
            str(gemini_data.get("language", "en"))
        # ── Persist detected language in session for next turn's hold message ──
        session.language = detected_lang
        # ── Propagate customer name if Gemini captured it this turn ──
        cname = (gemini_data.get("customer_name") or "").strip()
        if cname:
            session.customer_name = cname
        dialogue_state = gemini_data.get("dialogue_state", "") or ""
        # dialogue_state may be an enum value string or object
        dialogue_state_str = str(dialogue_state.value if hasattr(dialogue_state, "value") else dialogue_state)
        cart           = gemini_data.get("cart") or []

        logger.info("📞 Gemini Live [%.0fms]: '%s' → '%s...' (state=%s)",
                    gemini_ms, transcript[:60], agent_response[:60], dialogue_state_str)

        # ── Sync call session order_items from Gemini's cart ──
        if cart:
            session.order_items = [
                {
                    "name":     (ci.get("name") or (ci.get("product_id") or "item")),
                    "quantity": ci.get("quantity", 1),
                    "price":    ci.get("unit_price", 0),
                    "subtotal": round(
                        ci.get("unit_price", 0) * ci.get("quantity", 1), 2
                    ),
                }
                for ci in (cart if isinstance(cart, list) else [])
            ]
            session.total = sum(
                ci.get("unit_price", 0) * ci.get("quantity", 1)
                for ci in (cart if isinstance(cart, list) else [])
            )

        # Broadcast transcript to admin dashboard
        await ws_manager.broadcast(EventType.TRANSCRIPT_RECEIVED, {
            "call_sid":   call_sid,
            "transcript": transcript,
            "language":   detected_lang,
            "confidence": 1.0,
            "stt_ms":     round(gemini_ms),
        })

        # ── Handle silence / empty response ──
        audio_b64 = gemini_data.get("audio_base64", "")
        if not transcript and not audio_b64:
            logger.warning("📞 Gemini returned silence — asking to repeat")
            if detected_lang == "en":
                retry_text = "Sorry, I didn't hear you. Could you please repeat that?"
                retry_lang = "en"
            elif detected_lang == "gu":
                retry_text = "Sorry, mane sambhalayu nahi. Krupaya pharthi bolo?"
                retry_lang = "gu"
            else:
                retry_text = "Sorry, mujhe sunai nahi diya. Kya aap dubara bol sakte hain?"
                retry_lang = "hi"
            tts_result = await synthesize_speech(retry_text, language=retry_lang)
            retry_url  = _save_audio_file(
                tts_result["audio_bytes"], tts_result["audio_format"], prefix="retry"
            )
            _set_pending_result(task_key, f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{retry_url}</Play>
    <Record
        action="{base}/api/call/process-recording"
        method="POST"
        maxLength="45"
        playBeep="false"
        trim="trim-silence"
        timeout="10"
        transcribe="false"
    />
    <Hangup/>
</Response>""")
            return

        # ── Decode Gemini audio WAV ──
        if audio_b64:
            raw_wav   = base64.b64decode(audio_b64)
            audio_url = _save_audio_file(raw_wav, "wav", prefix="resp")
        else:
            # Gemini gave text but no audio — fallback TTS for the response
            logger.warning("📞 Gemini returned no audio — using fallback TTS")
            tts_result = await synthesize_speech(agent_response)
            audio_url  = _save_audio_file(
                tts_result["audio_bytes"], tts_result["audio_format"], prefix="resp"
            )

        # Broadcast response to admin dashboard
        await ws_manager.broadcast(EventType.RESPONSE_GENERATED, {
            "call_sid":     call_sid,
            "response_text": agent_response,
            "tts_engine":   "gemini-live",
            "stt_engine":   "gemini-live",
            "total_ms":     round(gemini_ms),
            "order":        {"items": session.order_items, "total": session.total},
            "customer_name": session.customer_name,
        })

        # ═══ STEP 3: Check for end-of-conversation ═══
        #   Gemini sets dialogue_state = 'done' when order is confirmed / call ends
        #   Also check common end phrases as a secondary signal
        end_keywords = [
            "goodbye", "bye", "alvida", "dhanyavaad", "thank you",
            "order confirmed", "order placed", "order complete",
            "has been placed", "enjoy your meal", "shubh bhojan",
            "order aa gaya", "order ho gaya", "order lag gaya",
            "order thayu", "aavjo", "subh bhojan",
        ]

        # ── Cancel-with-confirmation two-turn flow ──
        #
        # Turn 1: caller says cancel keywords → find order, ASK for confirmation
        # Turn 2: caller says yes/haan/ha → execute cancel   |   no/nahi → abort
        cancel_db_keywords = [
            "cancel my order", "cancel order", "order cancel", "mera order cancel",
            "order cancel karo", "order band karo", "cancel kar do", "delete order",
            "mera order delete", "order delete karo",
        ]
        yes_words = ["yes", "haan", "ha", "han", "theek hai", "ok", "okay",
                     "confirm", "karo", "kar do", "bilkul", "zarur"]
        no_words  = ["no", "nahi", "na", "mat karo", "rehne do", "band karo",
                     "cancel nahi", "don't cancel"]

        # ── Turn 2: confirmation response to a pending cancel ──
        if session.pending_cancel is not None:
            pending = session.pending_cancel
            tlow = transcript.lower()
            if any(w in tlow for w in yes_words):
                # Execute cancel
                cancelled = await _cancel_latest_order_by_phone(session.phone_number)
                if cancelled:
                    done_msg = (
                        f"Aapka order #{cancelled['order_id']} successfully cancel ho gaya. "
                        f"₹{cancelled['total']:.0f} ka order band kar diya gaya hai. Dhanyavaad!"
                    )
                else:
                    done_msg = "Sorry, aapka order cancel nahi ho saka. Shayad woh pehle hi complete ho gaya tha."
                session.pending_cancel = None
                tts_r = await synthesize_speech(done_msg, language="hi")
                url   = _save_audio_file(tts_r["audio_bytes"], tts_r["audio_format"], prefix="cancel")
                session.status = "ended"
                asyncio.create_task(_upsert_call_log(call_sid, session.phone_number, status="ended", session=session))
                _set_pending_result(task_key, f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{url}</Play>
    <Pause length="1"/>
    <Hangup/>
</Response>""")
                return
            elif any(w in tlow for w in no_words):
                session.pending_cancel = None
                keep_msg = "That's alright, your order was not cancelled. Anything else?" if detected_lang == "en" \
                    else "Theek hai, aapka order cancel nahi kiya gaya. Kya aur kuch chahiye?"
                tts_r = await synthesize_speech(keep_msg, language=detected_lang)
                url   = _save_audio_file(tts_r["audio_bytes"], tts_r["audio_format"], prefix="keep")
                _set_pending_result(task_key, _build_continue_twiml(base, url, detected_lang))
                return
            # else ambiguous — fall through to normal Gemini response

        # ── Turn 1: detect cancel intent for a previously placed order ──
        is_cancel_request = (
            not session.order_items  # no items in current call cart
            and session.pending_cancel is None
            and any(kw in transcript.lower() for kw in cancel_db_keywords)
        )
        if is_cancel_request:
            # Look up latest order but DON'T cancel yet — ask first
            order_info = await _lookup_latest_order_by_phone(session.phone_number)
            if order_info:
                session.pending_cancel = order_info
                ask_msg = (
                    f"Aapka order #{order_info['order_id']} hai — "
                    + ", ".join(f"{it['name']}" for it in (order_info.get('items') or [])) + " — "
                    f"total ₹{order_info['total']:.0f}. "
                    f"Kya aap sach mein yeh order cancel karna chahte hain? Haan ya Nahi?"
                )
            else:
                ask_msg = "Sorry, pichle 24 ghante mein aapka koi active order nahi mila. Kya aur kuch chahiye?"
                session.pending_cancel = None
            tts_r = await synthesize_speech(ask_msg, language="hi")
            url   = _save_audio_file(tts_r["audio_bytes"], tts_r["audio_format"], prefix="ask_cancel")
            _set_pending_result(task_key, _build_continue_twiml(base, url, "hi"))
            return

        is_ending = (
            dialogue_state_str in ("done", "placing_order")
            or any(kw in agent_response.lower() for kw in end_keywords)
        )

        if is_ending:
            session.status = "ended"
            if session.order_items:
                await ws_manager.broadcast(EventType.ORDER_CONFIRMED, {
                    "call_sid": call_sid,
                    "phone":    session.phone_number,
                    "items":    session.order_items,
                    "total":    session.total,
                    "customer_name": session.customer_name,
                })
            _set_pending_result(task_key, f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Pause length="1"/>
    <Hangup/>
</Response>""")
            return

        # ═══ STEP 4: Continue conversation — Play + Record next turn ═══
        _set_pending_result(task_key, _build_continue_twiml(base, audio_url, detected_lang))

    except Exception as e:
        logger.error("📞 Background pipeline error: %s", e, exc_info=True)
        try:
            if session.language == "en":
                error_text = "Sorry, something went wrong. Please try again."
                error_lang = "en"
            elif session.language == "gu":
                error_text = "Sorry, koi gadbad thai. Meherbani kari pharthi try karo."
                error_lang = "gu"
            else:
                error_text = "Sorry, kuch gadbad ho gayi. Please dubara try karein."
                error_lang = "hi"
            tts_result = await synthesize_speech(error_text, language=error_lang)
            error_url  = _save_audio_file(
                tts_result["audio_bytes"], tts_result["audio_format"], prefix="error"
            )
            _set_pending_result(task_key, _build_continue_twiml(base, error_url, session.language))
        except Exception:
            _set_pending_result(task_key, f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">Sorry, kuch gadbad ho gayi. Goodbye.</Say>
    <Hangup/>
</Response>""")


def _set_pending_result(task_key: str, twiml: str) -> None:
    """Store the finished TwiML and signal the polling endpoint."""
    entry = _pending_responses.get(task_key)
    if entry:
        entry["twiml"] = twiml
        entry["event"].set()
    else:
        logger.warning("📞 task_key %s not found in _pending_responses", task_key)


def _build_continue_twiml(base: str, audio_url: str, language: str = "hi") -> str:
    """Build the standard 'Play response then Record next turn' TwiML."""
    if language == "en":
        fallback_say = '<Say voice="Polly.Matthew" language="en-US">Would you like to order anything else?</Say>'
    else:
        fallback_say = '<Say voice="Polly.Aditi" language="hi-IN">Kya aap kuch aur order karna chahte hain?</Say>'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Record
        action="{base}/api/call/process-recording"
        method="POST"
        maxLength="45"
        playBeep="false"
        trim="trim-silence"
        timeout="10"
        transcribe="false"
    />
    {fallback_say}
    <Record
        action="{base}/api/call/process-recording"
        method="POST"
        maxLength="45"
        playBeep="false"
        trim="trim-silence"
        timeout="10"
        transcribe="false"
    />
    <Hangup/>
</Response>"""


# ═══════════════════════════════════════════════════════════════════════════
#  POLLING ENDPOINT — Twilio <Redirect> loops here until the result is ready
# ═══════════════════════════════════════════════════════════════════════════

_MAX_POLL_WAIT = 10.0  # seconds to wait per poll before redirecting again


@router.post("/check-response/{task_key}")
async def check_response(task_key: str):
    """
    Twilio redirects here while the AI pipeline runs in the background.

    Behaviour:
      • Wait up to _MAX_POLL_WAIT seconds for the background task to finish.
      • If the result arrives in time → return the real TwiML (<Play> + <Record>).
      • If still processing → return <Pause 1s> + <Redirect> back here.
      • If the task_key is unknown (stale/expired) → hang up gracefully.

    This keeps every HTTP response well under Twilio's 15-second timeout.
    """
    entry = _pending_responses.get(task_key)

    if entry is None:
        # task_key expired or never existed — hang up gracefully
        logger.warning("📞 check-response: unknown task_key %s", task_key)
        return _twiml("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">Sorry, kuch gadbad ho gayi. Goodbye.</Say>
    <Hangup/>
</Response>""")

    event: asyncio.Event = entry["event"]

    try:
        await asyncio.wait_for(event.wait(), timeout=_MAX_POLL_WAIT)
    except asyncio.TimeoutError:
        # Still processing — redirect back for another poll cycle
        base = _get_base_url()
        logger.info("📞 check-response: still waiting for %s, redirecting", task_key)
        return _twiml(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="1"/>
    <Redirect method="POST">{base}/api/call/check-response/{task_key}</Redirect>
</Response>""")

    # ─── Result is ready — return the real TwiML ───
    twiml = entry.get("twiml")
    _pending_responses.pop(task_key, None)  # cleanup

    if twiml:
        logger.info("📞 check-response: returning result for %s", task_key)
        return _twiml(twiml)

    # Shouldn't happen, but safety net
    return _twiml("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">Sorry, kuch gadbad ho gayi. Goodbye.</Say>
    <Hangup/>
</Response>""")


# ─────────────── Audio serving endpoint ───────────────

@router.get("/audio/{filename}")
async def serve_audio(filename: str):
    """
    Serve generated TTS audio files for Twilio <Play>.

    Twilio fetches these URLs to play audio to the caller.
    Files live in: ai_service/app/static/call_audio/
    """
    safe_name = Path(filename).name  # Sanitize
    filepath = AUDIO_DIR / safe_name

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    ext = filepath.suffix.lower()
    content_types = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}
    return FileResponse(str(filepath), media_type=content_types.get(ext, "audio/wav"))


# ─────────────── Call status callback ───────────────

@router.post("/status")
async def call_status(request: Request):
    """
    Twilio call status callback.

    Set this as the Status Callback URL on your SIP Domain:
      POST https://your-ngrok-url/api/call/status
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    call_status = form.get("CallStatus", "unknown")
    duration = form.get("CallDuration", "0")

    logger.info("📞 Call status [%s]: %s (duration: %ss)", call_sid, call_status, duration)

    if call_sid in _call_sessions:
        session = _call_sessions[call_sid]
        session.status = "ended"

        # Persist final call data to DB
        asyncio.create_task(_upsert_call_log(call_sid, session.phone_number, status="ended", session=session))

        await ws_manager.broadcast(EventType.PIPELINE_COMPLETE, {
            "call_sid": call_sid,
            "status": call_status,
            "duration": duration,
            "turns": len(session.turns),
            "order": {"items": session.order_items, "total": session.total},
        })

    return PlainTextResponse("OK")


# ─────────────── Active calls / history ───────────────

@router.get("/active")
async def active_calls():
    """List all active phone call sessions."""
    return [
        {
            "call_sid": s.call_sid,
            "phone": s.phone_number,
            "started_at": s.started_at,
            "turns": len(s.turns),
            "order_items": len(s.order_items),
            "total": s.total,
            "status": s.status,
            "language": s.language,
        }
        for s in _call_sessions.values()
        if s.status == "active"
    ]


@router.get("/history")
async def call_history():
    """List all call sessions — in-memory (current session) + DB (persisted history)."""
    # In-memory sessions (current server run)
    memory_sessions = [
        {
            "call_sid":   s.call_sid,
            "phone":      s.phone_number,
            "started_at": s.started_at,
            "duration":   round(time.time() - s.started_at, 1),
            "turns":      len(s.turns),
            "status":     s.status,
            "language":   s.language,
            "order":      {"items": s.order_items, "total": s.total},
            "source":     "memory",
        }
        for s in sorted(
            _call_sessions.values(), key=lambda x: x.started_at, reverse=True
        )
    ]

    # DB-persisted sessions (survive restarts)
    db_sessions = []
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_DB_URL, timeout=5.0)
        try:
            rows = await conn.fetch("""
                SELECT call_sid, phone_number, started_at, ended_at, duration_sec,
                       turn_count, language, status, order_items, total, full_transcript
                FROM call_logs
                ORDER BY started_at DESC
                LIMIT 200
            """)
            known_sids = {s["call_sid"] for s in memory_sessions}
            for r in rows:
                if r["call_sid"] not in known_sids:  # don't duplicate
                    items = json.loads(r["order_items"]) if r["order_items"] else []
                    db_sessions.append({
                        "call_sid":   r["call_sid"],
                        "phone":      r["phone_number"] or "",
                        "started_at": r["started_at"].timestamp() if r["started_at"] else 0,
                        "duration":   r["duration_sec"] or 0,
                        "turns":      r["turn_count"],
                        "status":     r["status"],
                        "language":   r["language"] or "hi",
                        "order":      {"items": items, "total": float(r["total"] or 0)},
                        "source":     "db",
                    })
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Could not fetch call history from DB: %s", e)

    return memory_sessions + db_sessions


# ─────────────── Simulator (test without Twilio) ───────────────

@router.post("/simulate")
async def simulate_call(request: Request):
    """
    Simulate a phone call turn for testing WITHOUT Twilio.

    Send:    {"text": "mujhe ek butter chicken chahiye", "call_sid": "test-123"}
    Returns: agent response text, audio URL, order state

    Uses the REAL LLM→TTS pipeline (minus STT since you send text directly).
    """
    body = await request.json()
    text = body.get("text", "").strip()
    call_sid = body.get("call_sid", f"sim-{int(time.time())}")

    if not text:
        raise HTTPException(status_code=400, detail="'text' is required")

    session = _get_or_create_session(call_sid, "simulator")

    # First turn: add greeting
    if not session.turns:
        rname = settings.restaurant_name
        greeting = f"नमस्ते! {rname} में आपका स्वागत है। आप क्या order करना चाहेंगे?"
        session.add_turn("agent", greeting)

    # Process through EXISTING LLM
    agent_response = await _process_call_turn(session, text)

    # Generate TTS audio via EXISTING pipeline
    tts_result = await synthesize_speech(agent_response)
    audio_url = _save_audio_file(
        tts_result["audio_bytes"], tts_result["audio_format"], prefix="sim"
    )

    return {
        "call_sid": call_sid,
        "agent_text": agent_response,
        "audio_url": audio_url,
        "tts_engine": tts_result["engine"],
        "order": {"items": session.order_items, "total": session.total},
        "turns": len(session.turns),
    }


# ─────────────── Utility: clean up old audio files ───────────────

async def cleanup_old_audio(max_age_seconds: int = 3600):
    """Remove TTS audio files older than max_age_seconds (default 1 hour)."""
    now = time.time()
    removed = 0
    for f in AUDIO_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > max_age_seconds:
            f.unlink()
            removed += 1
    if removed:
        logger.info("🧹 Cleaned up %d old audio files", removed)
