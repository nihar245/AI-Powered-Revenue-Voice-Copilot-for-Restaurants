"""
Text-to-Speech module — smart language routing.

- Hindi / Hinglish → edge-tts (Microsoft Neural Voices) — FREE, fast, great Hindi
- English → Deepgram Aura-2 — low latency, natural English

edge-tts outputs MP3 by default; we convert to WAV for browser playback consistency.
"""

import io
import re
import time
import logging
from typing import Optional

import edge_tts

from app.config import settings
from app.services.deepgram_client import client as dg_client

logger = logging.getLogger(__name__)


# ─── Script / language detection ────────────────────────────────────────────
_DEVANAGARI_RE     = re.compile(r"[\u0900-\u097F]")
_GUJARATI_SCRPT_RE = re.compile(r"[\u0A80-\u0AFF]")
_HINDI_WORDS = {
    "aur", "hai", "ka", "ki", "ke", "mein", "ko", "se", "ye", "wo",
    "haan", "nahi", "chahiye", "kya", "main", "hum", "bhai", "dena",
    "lena", "ek", "do", "teen", "char", "paanch", "rupaye", "order",
    "khana", "peena", "aapka", "mujhe", "toh", "bhi", "naan", "roti",
    "daal", "sabzi", "paneer", "ji", "accha", "theek", "bilkul",
}
_GUJARATI_WORDS = {
    "kem", "chho", "chhe", "nathi", "maro", "tamaro", "avu",
    "java", "karo", "lai", "aao", "tame", "be", "tran",
    "ben", "khavo", "pivo", "joiye", "chalo", "pan", "tamne",
}


def _is_hindi(text: str) -> bool:
    """Detect if text is Hindi/Hinglish (Devanagari or common Hindi words)."""
    if _DEVANAGARI_RE.search(text):
        return True
    words = set(text.lower().split())
    hindi_count = len(words & _HINDI_WORDS)
    return hindi_count >= 2  # at least 2 Hindi words → treat as Hindi


def _is_gujarati(text: str) -> bool:
    """Detect if text is Gujarati (Gujarati script or common Gujarati words)."""
    if _GUJARATI_SCRPT_RE.search(text):
        return True
    words = set(text.lower().split())
    return len(words & _GUJARATI_WORDS) >= 2


# ─── Edge-TTS voices ─────────────────────────────────────────────────────────
EDGE_VOICES = {
    "hi-female": "hi-IN-SwaraNeural",      # Hindi female — excellent quality
    "hi-male":   "hi-IN-MadhurNeural",     # Hindi male
    "gu-female": "gu-IN-DhwaniNeural",     # Gujarati female
    "gu-male":   "gu-IN-NiranjanNeural",   # Gujarati male
    "en-female": "en-IN-NeerjaNeural",     # Indian English female
    "en-male":   "en-IN-PrabhatNeural",    # Indian English male
}


async def _edge_tts_synthesize(text: str, voice: str) -> bytes:
    """Synthesize with edge-tts, returns MP3 bytes."""
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


async def _deepgram_synthesize(text: str, voice: str) -> bytes:
    """Synthesize with Deepgram Aura-2, returns WAV bytes."""
    audio_iter = dg_client.speak.v1.audio.generate(
        text=text,
        model=voice,
        encoding="linear16",
        container="wav",
        sample_rate=settings.deepgram.tts_sample_rate,
    )
    return b"".join(audio_iter)


async def synthesize_speech(
    text: str,
    voice: Optional[str] = None,
    language: Optional[str] = None,
    rate: Optional[str] = None,
    volume: Optional[str] = None,
) -> dict:
    """
    Smart TTS: routes to edge-tts (Hindi) or Deepgram (English).

    Args:
        text: The text to speak.
        voice: Override voice name. If not set, auto-selects based on language.
        language: Language hint ('hi', 'en'). If not set, auto-detects.

    Returns:
        dict with audio_bytes, duration_ms, voice, text_length, engine.
    """
    start_time = time.perf_counter()

    # Detect language
    is_hindi    = (language or "").startswith("hi") or _is_hindi(text)
    is_gujarati = (language or "").startswith("gu") or _is_gujarati(text)

    # Choose engine + voice — Gujarati > Hindi > English
    if is_gujarati and not is_hindi:
        engine = "edge-tts"
        tts_voice = voice or EDGE_VOICES["gu-female"]
        lang_label = "gu"
    elif is_hindi:
        engine = "edge-tts"
        tts_voice = voice or EDGE_VOICES["hi-female"]
        lang_label = "hi"
    else:
        engine = "deepgram"
        tts_voice = voice or settings.deepgram.tts_model
        lang_label = "en"

    logger.info("TTS [%s]: voice=%s, lang=%s, text_len=%d",
                engine, tts_voice, lang_label, len(text))

    try:
        if engine == "edge-tts":
            audio_bytes = await _edge_tts_synthesize(text, tts_voice)
            audio_format = "mp3"
        else:
            audio_bytes = await _deepgram_synthesize(text, tts_voice)
            audio_format = "wav"

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info("TTS [%s] complete: %d bytes %s, %.0fms",
                     engine, len(audio_bytes), audio_format, elapsed_ms)

        return {
            "audio_bytes": audio_bytes,
            "audio_format": audio_format,
            "duration_ms": round(elapsed_ms, 1),
            "voice": tts_voice,
            "text_length": len(text),
            "engine": engine,
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error("TTS [%s] failed: %s — trying fallback", engine, e)

        # Fallback: if primary fails, try the other engine
        try:
            if engine == "edge-tts":
                audio_bytes = await _deepgram_synthesize(text, settings.deepgram.tts_model)
                audio_format = "wav"
                fallback_voice = settings.deepgram.tts_model
            else:
                fb_voice = EDGE_VOICES["en-female"]
                audio_bytes = await _edge_tts_synthesize(text, fb_voice)
                audio_format = "mp3"
                fallback_voice = fb_voice

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info("TTS fallback complete: %d bytes, %.0fms", len(audio_bytes), elapsed_ms)

            return {
                "audio_bytes": audio_bytes,
                "audio_format": audio_format,
                "duration_ms": round(elapsed_ms, 1),
                "voice": fallback_voice,
                "text_length": len(text),
                "engine": "fallback",
            }
        except Exception as e2:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error("TTS fallback also failed: %s", e2)
            return {
                "audio_bytes": b"",
                "audio_format": "wav",
                "duration_ms": round(elapsed_ms, 1),
                "voice": tts_voice,
                "text_length": len(text),
                "error": str(e),
            }


async def list_voices(language: str = "en") -> list[dict]:
    """List available TTS voices across both engines."""
    voices = [
        # Edge-TTS Hindi voices (FREE)
        {"name": "hi-IN-SwaraNeural", "gender": "Female", "locale": "hi-IN", "engine": "edge-tts"},
        {"name": "hi-IN-MadhurNeural", "gender": "Male", "locale": "hi-IN", "engine": "edge-tts"},
        # Edge-TTS Indian English voices (FREE)
        {"name": "en-IN-NeerjaNeural", "gender": "Female", "locale": "en-IN", "engine": "edge-tts"},
        {"name": "en-IN-PrabhatNeural", "gender": "Male", "locale": "en-IN", "engine": "edge-tts"},
        # Deepgram Aura-2 English voices
        {"name": "aura-2-asteria-en", "gender": "Female", "locale": "en", "engine": "deepgram"},
        {"name": "aura-2-luna-en", "gender": "Female", "locale": "en", "engine": "deepgram"},
        {"name": "aura-2-orion-en", "gender": "Male", "locale": "en", "engine": "deepgram"},
        {"name": "aura-2-arcas-en", "gender": "Male", "locale": "en", "engine": "deepgram"},
    ]
    if language.startswith("hi"):
        return [v for v in voices if v["locale"].startswith("hi") or v["locale"].startswith("en-IN")]
    return voices
