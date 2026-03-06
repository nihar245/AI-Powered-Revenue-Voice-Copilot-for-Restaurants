"""
Speech-to-Text module using Deepgram Nova-3.

Fast, accurate transcription with multi-language support.
Supports English, Hindi, and auto-detection.
"""

import time
import logging
from typing import Optional

from app.config import settings
from app.services.deepgram_client import client as dg_client

logger = logging.getLogger(__name__)

# Exposed for health_routes compatibility
_model = f"deepgram-{settings.deepgram.stt_model}"


def _detect_script_language(text: str) -> str:
    """Detect language from script used in text."""
    if not text:
        return "en"

    devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
    gujarati = sum(1 for ch in text if "\u0A80" <= ch <= "\u0AFF")
    total = sum(1 for ch in text if not ch.isspace())

    if total == 0:
        return "en"
    if gujarati / total > 0.3:
        return "gu"
    if devanagari / total > 0.3:
        return "hi"
    return "en"


async def transcribe_audio(audio_bytes: bytes, language: Optional[str] = None) -> dict:
    """
    Transcribe audio bytes to text using Deepgram Nova-3.

    Args:
        audio_bytes: Raw audio file bytes (WAV, MP3, etc.).
        language: Optional language hint (e.g. 'en', 'hi').

    Returns:
        dict with text, segments, language, duration_ms, confidence.
    """
    start_time = time.perf_counter()

    logger.info("Transcribing audio with Deepgram: %d bytes", len(audio_bytes))

    try:
        kwargs = {
            "request": audio_bytes,
            "model": settings.deepgram.stt_model,
            "smart_format": True,
            "punctuate": True,
        }
        if language:
            kwargs["language"] = language
        else:
            kwargs["detect_language"] = True

        response = dg_client.listen.v1.media.transcribe_file(**kwargs)

        channel = response.results.channels[0]
        alt = channel.alternatives[0] if channel.alternatives else None

        text = alt.transcript if alt else ""
        confidence = alt.confidence if alt else 0.0

        segments = []
        if alt and alt.words:
            segments = [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "confidence": w.confidence,
                }
                for w in alt.words
            ]

        detected_lang = language or "en"
        if hasattr(channel, "detected_language") and channel.detected_language:
            detected_lang = channel.detected_language
        else:
            detected_lang = _detect_script_language(text)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Transcription complete: lang=%s, length=%d chars, confidence=%.2f, time=%.0fms",
            detected_lang, len(text), confidence, elapsed_ms,
        )

        return {
            "text": text,
            "segments": segments,
            "language": detected_lang,
            "duration_ms": round(elapsed_ms, 1),
            "confidence": round(confidence, 3),
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Deepgram STT failed: %s", e)
        return {
            "text": "",
            "segments": [],
            "language": "en",
            "duration_ms": round(elapsed_ms, 1),
            "error": str(e),
        }


def preload_model() -> None:
    """No-op for Deepgram (cloud API, no local model to preload)."""
    logger.info("Deepgram STT — no local model to preload (cloud API).")
