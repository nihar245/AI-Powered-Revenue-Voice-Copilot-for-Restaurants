"""
Voice API routes.

Implements the core voice pipeline endpoints:
- /voice/transcribe   — Audio → Text
- /voice/intent       — Text → Structured Order
- /voice/upsell       — Order → Upsell Suggestion
- /voice/speak        — Text → Audio
- /voice/full-pipeline — Audio → Full pipeline → Audio Response
"""

import time
import logging
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech
from app.nlp.intent import extract_intent
from app.nlp.response import generate_response
from app.services.matching import match_items
from app.services.upsell_service import suggest_upsell
from app.services.menu_service import get_menu_items
from app.services.validation import validate_order
from app.websocket.manager import ws_manager, EventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class IntentRequest(BaseModel):
    """Request body for /voice/intent."""
    transcript: str


class UpsellRequest(BaseModel):
    """Request body for /voice/upsell."""
    items: list[str]


class SpeakRequest(BaseModel):
    """Request body for /voice/speak."""
    text: str
    voice: Optional[str] = None
    rate: Optional[str] = None
    language: Optional[str] = None  # "hi" for Hindi, "en" for English; auto-detects if omitted
    response_format: Optional[str] = "mp3"  # "mp3" (download) or "json" (base64 in JSON)


class TranscribeResponse(BaseModel):
    """Response for /voice/transcribe."""
    text: str
    segments: list[dict]
    language: str
    duration_ms: float


class IntentResponse(BaseModel):
    """Response for /voice/intent."""
    items: list[dict]
    validated_items: list[dict] = []
    rejected_items: list[dict] = []
    warnings: list[str] = []
    is_valid: bool = True
    intent_type: str
    sentiment: str
    special_requests: Optional[str]
    duration_ms: float


class UpsellResponse(BaseModel):
    """Response for /voice/upsell."""
    suggestion: Optional[str]
    reason: str
    source: str


class PipelineResponse(BaseModel):
    """Metadata returned alongside audio in the full pipeline."""
    transcript: str
    intent: dict
    matched_items: list[dict]
    upsell: dict
    response_text: str
    total_duration_ms: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)):
    """
    Convert uploaded audio to text using Gemini STT.

    Accepts any audio format supported by ffmpeg (wav, mp3, ogg, etc.).
    """
    logger.info("POST /voice/transcribe — file=%s", audio.filename)

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    result = await transcribe_audio(audio_bytes)

    # Broadcast event
    await ws_manager.broadcast(EventType.TRANSCRIPT_RECEIVED, {
        "text": result["text"],
        "language": result["language"],
    })

    return TranscribeResponse(
        text=result["text"],
        segments=result["segments"],
        language=result["language"],
        duration_ms=result["duration_ms"],
    )


@router.post("/intent", response_model=IntentResponse)
async def get_intent(request: IntentRequest):
    """
    Extract structured order intent from a text transcript.

    Uses Google Gemini API to parse natural language into
    a structured order with items, quantities, and modifications.
    """
    logger.info("POST /voice/intent — transcript='%s'", request.transcript[:80])

    result = await extract_intent(request.transcript)

    # Validate order against business rules
    result = validate_order(result)

    # Broadcast event
    await ws_manager.broadcast(EventType.ITEMS_DETECTED, {
        "items": result["validated_items"],
        "intent_type": result["intent_type"],
        "warnings": result.get("warnings", []),
    })

    return IntentResponse(
        items=result["items"],
        validated_items=result.get("validated_items", []),
        rejected_items=result.get("rejected_items", []),
        warnings=result.get("warnings", []),
        is_valid=result.get("is_valid", True),
        intent_type=result["intent_type"],
        sentiment=result["sentiment"],
        special_requests=result.get("special_requests"),
        duration_ms=result["duration_ms"],
    )


@router.post("/upsell", response_model=UpsellResponse)
async def get_upsell(request: UpsellRequest):
    """
    Get an upsell suggestion based on ordered items.

    Uses combo rules and category-based logic to suggest
    a complementary item.
    """
    logger.info("POST /voice/upsell — items=%s", request.items)

    result = suggest_upsell(request.items)

    # Broadcast event
    await ws_manager.broadcast(EventType.UPSELL_SUGGESTED, {
        "suggestion": result["suggestion"],
        "reason": result["reason"],
    })

    return UpsellResponse(**result)


@router.post("/speak")
async def speak(request: SpeakRequest):
    """
    Convert text to speech audio.

    Set `response_format` to:
    - **"mp3"** (default) → returns downloadable MP3 file
    - **"json"** → returns base64-encoded audio in JSON (visible in Swagger)
    """
    logger.info("POST /voice/speak — text_len=%d, format=%s", len(request.text), request.response_format)

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = await synthesize_speech(
        text=request.text,
        voice=request.voice,
        language=request.language,
        rate=request.rate,
    )

    audio_fmt = result.get("audio_format", "wav")  # edge-tts → mp3, deepgram → wav
    mime = "audio/mpeg" if audio_fmt == "mp3" else "audio/wav"

    # JSON format: return base64 audio (works in Swagger UI)
    if request.response_format == "json":
        import base64
        audio_b64 = base64.b64encode(result["audio_bytes"]).decode("utf-8")
        return {
            "audio_base64": audio_b64,
            "format": audio_fmt,
            "size_bytes": len(result["audio_bytes"]),
            "duration_ms": result["duration_ms"],
            "voice": result["voice"],
            "engine": result.get("engine", "deepgram"),
            "text_length": len(request.text),
            "instructions": f"Decode audio_base64 from base64 to get {audio_fmt.upper()} bytes",
        }

    # Default: return raw audio as downloadable file
    ext = "mp3" if audio_fmt == "mp3" else "wav"
    return Response(
        content=result["audio_bytes"],
        media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename=speech.{ext}",
            "X-Duration-Ms": str(result["duration_ms"]),
            "X-Voice": result["voice"],
            "X-Engine": result.get("engine", "deepgram"),
        },
    )


@router.post("/full-pipeline")
async def full_pipeline(audio: UploadFile = File(...)):
    """
    Execute the complete voice ordering pipeline.

    Pipeline: Audio → STT → Intent → Match → Upsell → Response → TTS

    Returns the audio response as MP3  with pipeline metadata in headers.
    """
    pipeline_start = time.perf_counter()
    logger.info("POST /voice/full-pipeline — file=%s", audio.filename)

    # Broadcast: pipeline started
    await ws_manager.broadcast(EventType.CALL_STARTED, {
        "filename": audio.filename,
    })

    # Step 1: Read audio
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Step 2: Speech-to-Text
    stt_result = await transcribe_audio(audio_bytes)
    transcript = stt_result["text"]

    await ws_manager.broadcast(EventType.TRANSCRIPT_RECEIVED, {
        "text": transcript,
        "language": stt_result["language"],
        "stt_ms": stt_result["duration_ms"],
    })

    if not transcript.strip():
        raise HTTPException(status_code=422, detail="Could not transcribe audio")

    # Step 3: Intent Extraction
    intent_result = await extract_intent(transcript)

    # Step 3b: Validate order
    intent_result = validate_order(intent_result)

    await ws_manager.broadcast(EventType.ITEMS_DETECTED, {
        "items": intent_result["validated_items"],
        "intent_type": intent_result["intent_type"],
        "warnings": intent_result.get("warnings", []),
        "intent_ms": intent_result["duration_ms"],
    })

    # Step 4: Fuzzy Match items to menu (use validated items)
    matched_names = [item["name"] for item in intent_result.get("validated_items", [])]

    # Step 5: Upsell Suggestion
    upsell_result = suggest_upsell(matched_names)

    await ws_manager.broadcast(EventType.UPSELL_SUGGESTED, {
        "suggestion": upsell_result["suggestion"],
        "reason": upsell_result["reason"],
    })

    # Step 6: Generate Response
    response_result = await generate_response(
        order_json=intent_result,
        upsell_suggestion=upsell_result.get("suggestion"),
    )
    response_text = response_result["response_text"]

    await ws_manager.broadcast(EventType.RESPONSE_GENERATED, {
        "text": response_text,
    })

    # Step 7: Text-to-Speech
    tts_result = await synthesize_speech(response_text)

    total_ms = (time.perf_counter() - pipeline_start) * 1000

    # Broadcast: pipeline complete
    await ws_manager.broadcast(EventType.PIPELINE_COMPLETE, {
        "transcript": transcript,
        "items": intent_result.get("validated_items", []),
        "warnings": intent_result.get("warnings", []),
        "upsell": upsell_result["suggestion"],
        "response": response_text,
        "total_ms": round(total_ms, 1),
    })

    logger.info(
        "Full pipeline complete: items=%d, upsell=%s, total=%.0fms",
        len(intent_result.get("validated_items", [])),
        upsell_result["suggestion"],
        total_ms,
    )

    # Build metadata as JSON for the X-Pipeline-Result header
    import json
    pipeline_meta = {
        "transcript": transcript,
        "intent": {
            "items": intent_result.get("validated_items", []),
            "intent_type": intent_result["intent_type"],
            "sentiment": intent_result["sentiment"],
            "warnings": intent_result.get("warnings", []),
            "rejected_items": intent_result.get("rejected_items", []),
        },
        "matched_items": matched_names,
        "upsell": upsell_result,
        "response_text": response_text,
        "total_duration_ms": round(total_ms, 1),
    }

    return Response(
        content=tts_result["audio_bytes"],
        media_type="audio/wav",
        headers={
            "X-Pipeline-Result": json.dumps(pipeline_meta, default=str),
            "X-Total-Duration-Ms": str(round(total_ms, 1)),
        },
    )
