"""
Real-time voice conversation via Deepgram STT + Groq LLM + Deepgram TTS.

Pipeline per turn:
  1. Browser sends audio (WAV) or text
  2. Audio → Deepgram STT (Nova-3) → transcript
  3. Build chat messages (system prompt + full history)
  4. Groq LLM (Llama 3.3 70B) → response text
  5. Deepgram TTS (Aura-2) → WAV audio
  6. Send text + audio back to browser

Protocol (browser-facing):
─────────────────────────────────────────────────
Client → Server:
  {"type": "start"}                    → Start new session
  {"type": "audio", "data": "<b64>"}   → Send recorded audio
  {"type": "text",  "data": "..."}     → Send typed text
  {"type": "end"}                      → End call

Server → Client:
  {"type": "session_started", "session_id": "..."}
  {"type": "response", "agent_text": "...", "audio_base64": "...", ...}
  {"type": "session_ended",  "summary": {...}}
  {"type": "error",   "message": "..."}
─────────────────────────────────────────────────
"""

import json
import time
import base64
import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.nlp.prompts import CONVERSATION_SYSTEM_PROMPT
from app.services.menu_service import get_menu_items, get_menu_items_detailed, get_combos_for_context
from app.services.conversation import session_store, ConversationSession
from app.websocket.manager import ws_manager, EventType
from app.services.groq_client import async_client as groq_client
from app.services.deepgram_client import client as dg_client
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["conversation"])


# ──────────────────── helpers ────────────────────

def _build_system_prompt(session: ConversationSession) -> str:
    """Build the system prompt with current menu (including prices) and order state."""
    menu_detailed = get_menu_items_detailed()
    menu_lines = get_menu_items()
    combos = get_combos_for_context()
    
    menu_str = "\n".join(f"  - {item}" for item in menu_lines)
    if combos:
        menu_str += "\n\nCOMBO MEALS (special price when ordered as combo):\n"
        menu_str += "\n".join(f"  - {c}" for c in combos)

    order = session.get_order_summary()
    if order["items"]:
        order_lines = []
        for item in order["items"]:
            line = f"  - {item['quantity']}x {item['name']} (₹{item['subtotal']})"
            if item.get("modifications"):
                line += f" [{', '.join(item['modifications'])}]"
            order_lines.append(line)
        order_lines.append(f"  Total: ₹{order['total']}")
        order_str = "\n".join(order_lines)
    else:
        order_str = "  (empty — customer hasn't ordered yet)"

    return CONVERSATION_SYSTEM_PROMPT.format(
        menu_items=menu_str,
        current_order=order_str,
    )


def _parse_order_from_response(raw_text: str) -> tuple[str, dict | None]:
    """
    Extract conversational text and structured order JSON from LLM response.
    
    The LLM is instructed to append:
        |||ORDER_JSON||| { ... } |||END_ORDER|||
    
    Returns:
        (clean_text, order_dict_or_None)
    """
    # Try to extract the JSON block
    pattern = r'\|\|\|ORDER_JSON\|\|\|\s*(.*?)\s*\|\|\|END_ORDER\|\|\|'
    match = re.search(pattern, raw_text, re.DOTALL)
    
    if match:
        clean_text = raw_text[:match.start()].strip()
        json_str = match.group(1).strip()
        try:
            order_data = json.loads(json_str)
            return clean_text, order_data
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse order JSON from LLM: %s", e)
            return clean_text, None
    
    # Fallback: try to find JSON block at the end (sometimes LLM omits markers)
    # Look for a JSON object at the end of the text
    json_pattern = r'\{[^{}]*"items"\s*:\s*\[.*?\]\s*,\s*"total"\s*:\s*[\d.]+.*?\}'
    json_match = re.search(json_pattern, raw_text, re.DOTALL)
    if json_match:
        clean_text = raw_text[:json_match.start()].strip()
        try:
            order_data = json.loads(json_match.group(0))
            return clean_text, order_data
        except json.JSONDecodeError:
            pass
    
    return raw_text.strip(), None


async def _process_turn(
    session: ConversationSession,
    user_text: str,
) -> dict:
    """
    Run the LLM + TTS pipeline for one conversation turn.

    Returns the LLM text immediately. TTS audio is generated separately
    so the caller can send text first for instant feedback.

    Args:
        session: Current conversation session (has chat history).
        user_text: What the customer said/typed.

    Returns:
        dict with agent_text, llm_ms (LLM-only time).
    """
    start_time = time.perf_counter()

    # Record customer turn
    session.add_customer_turn(user_text)

    # Build messages for Groq: system + full chat history
    system_prompt = _build_system_prompt(session)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.get_chat_history())

    # ── Groq LLM ──
    llm_response = await groq_client.chat.completions.create(
        model=settings.groq.model,
        messages=messages,
        temperature=0.7,
        max_tokens=500,
    )
    agent_text = (llm_response.choices[0].message.content or "").strip()

    if not agent_text:
        agent_text = "I'm sorry, could you repeat that?"

    # Parse structured order from LLM response
    clean_text, order_data = _parse_order_from_response(agent_text)
    
    # Use clean text (without JSON block) as the conversational response
    agent_text = clean_text if clean_text else agent_text
    
    # Update session order if we got structured data
    if order_data and order_data.get("action") != "none":
        items = order_data.get("items", [])
        if isinstance(items, list):
            # Replace entire order with the LLM's complete view
            session.current_order.clear()
            session.total_amount = 0.0
            if items:
                session.update_order(items)
            logger.info("Order updated: %d items, total=₹%.0f",
                        len(session.current_order), session.total_amount)
    
    # Record agent turn (clean text only)
    session.add_agent_turn(agent_text)

    llm_ms = (time.perf_counter() - start_time) * 1000
    logger.info("LLM done (%.0fms): '%s'", llm_ms, agent_text[:80])

    return {
        "agent_text": agent_text,
        "llm_ms": round(llm_ms, 1),
    }


async def _generate_tts(text: str, language: str = "en") -> dict:
    """Generate TTS audio separately. Returns audio_base64, audio_format, tts_ms."""
    start = time.perf_counter()
    tts_result = await synthesize_speech(text, language=language)
    audio_bytes = tts_result.get("audio_bytes", b"")
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else ""
    tts_ms = (time.perf_counter() - start) * 1000
    logger.info("TTS done (%.0fms, engine=%s)", tts_ms, tts_result.get("engine", "?"))
    return {
        "audio_base64": audio_b64,
        "audio_format": tts_result.get("audio_format", "wav"),
        "tts_ms": round(tts_ms, 1),
    }


# ──────────────────── WebSocket endpoint ────────────────────

@router.websocket("/conversation")
async def conversation_websocket(websocket: WebSocket):
    """
    Real-time voice conversation.

    Pipeline: Deepgram STT → Groq LLM → Deepgram TTS.
    Each user message is processed sequentially (request-response).
    """
    await websocket.accept()
    logger.info("Conversation WebSocket connected")

    session: ConversationSession | None = None

    try:
        # ── Wait for the START message ──
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                continue

            if msg.get("type") == "start":
                break

            await websocket.send_text(json.dumps({
                "type": "error",
                "message": 'Send {"type": "start"} first.',
            }))

        # ── Create session & notify ──
        session = session_store.create_session()
        await websocket.send_text(json.dumps({
            "type": "session_started",
            "session_id": session.session_id,
            "message": "Call started. Speak or type your order!",
        }))
        await ws_manager.broadcast(EventType.CALL_STARTED, {
            "session_id": session.session_id,
        })

        # ── Main conversation loop ──
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", "message": "Invalid JSON",
                }))
                continue

            msg_type = msg.get("type", "")

            # ── AUDIO ──
            if msg_type == "audio":
                audio_b64 = msg.get("data", "")
                if not audio_b64:
                    await websocket.send_text(json.dumps({
                        "type": "error", "message": "No audio data",
                    }))
                    continue
                try:
                    wav_bytes = base64.b64decode(audio_b64)
                except Exception:
                    await websocket.send_text(json.dumps({
                        "type": "error", "message": "Invalid base64 audio",
                    }))
                    continue

                logger.info("Received %d bytes audio (session %s)", len(wav_bytes), session.session_id)

                # Deepgram STT
                stt_result = await transcribe_audio(wav_bytes)
                transcript = stt_result.get("text", "").strip()

                if not transcript:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Could not understand audio. Please try again.",
                    }))
                    continue

                # Update session language from STT
                detected_lang = stt_result.get("language", "en")
                if detected_lang and detected_lang != "en":
                    session.language = detected_lang

                logger.info("STT transcript: '%s' (lang=%s)", transcript[:80], detected_lang)

                # Step 1: LLM → send text response IMMEDIATELY
                result = await _process_turn(session, transcript)
                order_summary = session.get_order_summary()
                lang = session.language
                turn_num = len(session.turns)

                await websocket.send_text(json.dumps({
                    "type": "response",
                    "session_id": session.session_id,
                    "transcript": transcript,
                    "agent_text": result["agent_text"],
                    "audio_base64": "",
                    "audio_format": "wav",
                    "duration_ms": result["llm_ms"],
                    "order": order_summary,
                    "language": lang,
                    "turn_number": turn_num,
                }, default=str))

                # Step 2: TTS → send audio as follow-up
                tts = await _generate_tts(result["agent_text"], lang)
                if tts["audio_base64"]:
                    await websocket.send_text(json.dumps({
                        "type": "audio_ready",
                        "session_id": session.session_id,
                        "audio_base64": tts["audio_base64"],
                        "audio_format": tts["audio_format"],
                        "tts_ms": tts["tts_ms"],
                    }))

            # ── TEXT ──
            elif msg_type == "text":
                text = msg.get("data", "").strip()
                if not text:
                    continue

                logger.info("Text input: '%s' (session %s)", text[:80], session.session_id)

                # Step 1: LLM → send text response IMMEDIATELY
                result = await _process_turn(session, text)
                order_summary = session.get_order_summary()
                lang = session.language
                turn_num = len(session.turns)

                await websocket.send_text(json.dumps({
                    "type": "response",
                    "session_id": session.session_id,
                    "agent_text": result["agent_text"],
                    "audio_base64": "",
                    "audio_format": "wav",
                    "duration_ms": result["llm_ms"],
                    "order": order_summary,
                    "language": lang,
                    "turn_number": turn_num,
                }, default=str))

                # Step 2: TTS → send audio as follow-up
                tts = await _generate_tts(result["agent_text"], lang)
                if tts["audio_base64"]:
                    await websocket.send_text(json.dumps({
                        "type": "audio_ready",
                        "session_id": session.session_id,
                        "audio_base64": tts["audio_base64"],
                        "audio_format": tts["audio_format"],
                        "tts_ms": tts["tts_ms"],
                    }))

            # ── END ──
            elif msg_type == "end":
                break

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown type: {msg_type}",
                }))

        # ── Session ended normally ──
        if session:
            summary = session_store.end_session(session.session_id)
            await websocket.send_text(json.dumps({
                "type": "session_ended",
                "summary": summary,
            }, default=str))
            await ws_manager.broadcast(EventType.ORDER_CONFIRMED, summary)

    except WebSocketDisconnect:
        logger.info("Conversation WebSocket disconnected")
        if session and session.status == "active":
            session_store.end_session(session.session_id)

    except Exception as e:
        logger.error("Conversation WebSocket error: %s", e)
        if session and session.status == "active":
            session_store.end_session(session.session_id)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except Exception:
            pass
