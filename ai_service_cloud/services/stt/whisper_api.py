"""
STT — Gemini multimodal audio transcription

Uses Gemini 2.0 Flash's native audio understanding instead of a dedicated
STT API.  Same GEMINI_API_KEY already in .env — no extra credentials needed.

Free tier: 15 RPM / 1 500 RPD — no billing required.
Supports: English, Hindi, Gujarati, Hinglish, and code-mixed speech natively.
"""

from __future__ import annotations

import asyncio
import json
import re

import google.generativeai as genai
from fastapi import HTTPException

from config import settings

_TRANSCRIBE_PROMPT = (
    "Transcribe the following audio precisely. "
    "The speaker may use English, Hindi, Gujarati, Hinglish, or code-mixed speech. "
    "Return ONLY valid JSON with exactly two keys — no markdown fences, no explanation:\n"
    '  "transcript": the spoken text verbatim\n'
    '  "language":   ISO 639-1 code — one of: "en", "hi", or "gu"\n'
    'If the audio is silent or inaudible return: {"transcript": "", "language": "en"}'
)


def _transcribe_sync(audio_bytes: bytes, mime_type: str) -> dict:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_text_model)

    response = model.generate_content(
        [{"mime_type": mime_type, "data": audio_bytes}, _TRANSCRIBE_PROMPT],
        generation_config={"temperature": 0, "max_output_tokens": 512},
    )

    text = response.text.strip()
    # Strip markdown code fences if the model wrapped its response
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(text)
        lang = str(data.get("language", "en")).lower()[:2]
        return {
            "transcript": str(data.get("transcript", "")).strip(),
            "language":   lang if lang in ("en", "hi", "gu") else "en",
        }
    except json.JSONDecodeError:
        # Gemini returned plain text (rare) — treat whole response as transcript
        return {"transcript": text, "language": "en"}


async def transcribe(audio_bytes: bytes, mime_type: str = "audio/webm") -> dict:
    """
    Transcribes audio using Gemini 2.0 Flash multimodal.
    Returns {"transcript": str, "language": str}.
    """
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _transcribe_sync, audio_bytes, mime_type)
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if any(k in msg for k in ("quota", "rate", "429", "resource_exhausted")):
            raise HTTPException(
                status_code=429,
                detail="Gemini STT rate limit — please wait a moment and try again.",
            )
        if "api_key" in msg or ("invalid" in msg and "key" in msg):
            raise HTTPException(status_code=401, detail="Invalid GEMINI_API_KEY — check your .env file.")
        raise HTTPException(status_code=502, detail=f"Gemini STT error: {exc}")


def is_loaded() -> bool:
    """True when a Gemini API key is present."""
    return bool(settings.gemini_api_key)


def load_whisper_model() -> None:
    """No-op shim — Gemini STT needs no local model."""
    key_status = "set" if settings.gemini_api_key else "MISSING"
    print(f"[STT] Gemini multimodal STT ({settings.gemini_text_model}) — API key: {key_status}")
