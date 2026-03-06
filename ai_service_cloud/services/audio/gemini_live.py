"""
Gemini Live Audio — Native audio-in / audio-out.

Audio format requirements (Gemini Live API):
  Input : raw 16-bit PCM, little-endian, 16 kHz, mono  →  mime "audio/pcm;rate=16000"
  Output: raw 16-bit PCM, little-endian, 24 kHz, mono  (wrapped in WAV for the browser)

This module:
  1. Converts browser WebM/Opus → PCM 16kHz via ffmpeg subprocess
  2. Sends it to Gemini Live via send_realtime_input()
  3. Collects PCM audio chunks + transcripts (input & output) from the response stream
  4. Returns WAV audio + transcripts (cart management is handled by the caller)
"""

from __future__ import annotations

import base64
import io
import struct
import subprocess

from fastapi import HTTPException
from google import genai
from google.genai import types

from config import settings



# ─── Audio helpers ────────────────────────────────────────────────────────────

def _pcm_to_wav(pcm: bytes, rate: int = 24_000) -> bytes:
    """Wrap raw signed 16-bit mono PCM in a WAV container (24kHz for Gemini output)."""
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))        # chunk size
    buf.write(struct.pack("<H", 1))         # PCM
    buf.write(struct.pack("<H", 1))         # mono
    buf.write(struct.pack("<I", rate))
    buf.write(struct.pack("<I", rate * 2))  # byte rate
    buf.write(struct.pack("<H", 2))         # block align
    buf.write(struct.pack("<H", 16))        # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm)))
    buf.write(pcm)
    return buf.getvalue()


def _to_pcm16k(audio_bytes: bytes) -> bytes:
    """
    Convert any browser audio (WebM/Opus, WAV, MP3, OGG…) to
    raw signed-16-bit little-endian PCM at 16 kHz mono via ffmpeg.

    Uses the bundled ffmpeg from imageio-ffmpeg (pip package — no system install needed).
    Gemini Live API requires: audio/pcm;rate=16000 (16-bit, 16kHz, mono, LE).
    """
    # Get the bundled ffmpeg binary from imageio-ffmpeg package
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"  # last-resort: try system PATH

    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error",
        "-i",  "pipe:0",
        "-f",  "s16le",    # raw signed 16-bit little-endian PCM
        "-ar", "16000",    # 16 kHz — required by Gemini Live input
        "-ac", "1",        # mono
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, input=audio_bytes, capture_output=True, timeout=30)
    except FileNotFoundError:
        raise HTTPException(
            500,
            "ffmpeg binary not found. Run: pip install imageio-ffmpeg",
        )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace")[:300]
        raise HTTPException(500, f"Audio conversion failed (ffmpeg): {detail}")
    return result.stdout


def _detect_language(text: str) -> str:
    """Heuristic: detect Hindi/Gujarati by Unicode range, else English."""
    if not text:
        return "en"
    devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    gujarati   = sum(1 for c in text if "\u0A80" <= c <= "\u0AFF")
    if gujarati > 2:
        return "gu"
    if devanagari > 2:
        return "hi"
    return "en"


# ─── Live session ─────────────────────────────────────────────────────────────

async def live_voice_turn(
    audio_bytes: bytes,
    cart: list[dict],
    menu_items: list[dict],
    mime_type: str = "audio/webm",
) -> dict:
    """
    One PTT (push-to-talk) turn via Gemini 2.5 Flash Native Audio Dialogue.

    Flow:
        1. Convert browser WebM/Opus → PCM 16kHz (ffmpeg)
        2. Send to Gemini Live as audio/pcm;rate=16000 via send_realtime_input
        3. Collect: PCM audio chunks + input transcript + output transcript
        4. Wrap PCM output (24kHz) in WAV

    Returns dict:
        audio_b64     : base64 WAV or None
        audio_mime    : "audio/wav"
        transcript    : user's words (from input_audio_transcription)
        response_text : model's spoken reply (from output_audio_transcription)
        language      : "en" | "hi" | "gu"

    NOTE: Cart management is handled by the caller (test_pipeline.py)
    using local NLU on the returned transcript.
    """
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    # 1. Convert browser WebM → PCM 16kHz (Gemini Live input requirement)
    pcm_input = _to_pcm16k(audio_bytes)

    # 2. Context-aware system instruction (menu + cart state for natural responses)
    menu_lines = "\n".join(f"  {i['name']} ₹{i['price']}" for i in menu_items)
    cart_str   = (
        ", ".join(f"{c['name']} x{c['quantity']}" for c in cart)
        if cart else "empty"
    )
    system_instruction = (
        "You are a friendly restaurant voice ordering assistant. "
        "The customer may speak English, Hindi, Gujarati, or Hinglish (code-mixed). "
        "Always reply in the SAME language the customer used. "
        "Keep replies to 1-2 short, warm, natural sentences. "
        "Never refuse — always acknowledge and help.\n\n"
        f"MENU:\n{menu_lines}\n\n"
        f"CURRENT ORDER: {cart_str}"
    )

    client = genai.Client(api_key=settings.gemini_api_key)

    # 3. AUDIO-only modality + input/output transcription channels
    #    (response_modalities must be ["AUDIO"] — TEXT and AUDIO cannot be combined)
    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription={},   # transcribe what the user said
        output_audio_transcription={},  # transcribe what the model says
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
        system_instruction=system_instruction,
    )

    audio_chunks:     list[bytes] = []
    input_transcript  = ""
    output_transcript = ""

    try:
        async with client.aio.live.connect(
            model=settings.gemini_audio_model,
            config=live_config,
        ) as session:

            # Send complete PTT recording as PCM 16kHz (required mime type)
            await session.send_realtime_input(
                audio=types.Blob(data=pcm_input, mime_type="audio/pcm;rate=16000")
            )

            # Explicitly signal end of PTT turn.
            # Falls back gracefully to server-side VAD if SDK version differs.
            try:
                await session.send_realtime_input(activity_end=types.ActivityEnd())
            except (AttributeError, TypeError, Exception):
                pass  # VAD handles turn detection in older SDK versions

            # Collect streamed response until turn_complete
            async for response in session.receive():
                sc = getattr(response, "server_content", None)
                if not sc:
                    continue

                # Audio PCM chunks (24 kHz, mono, s16le)
                model_turn = getattr(sc, "model_turn", None)
                if model_turn:
                    for part in getattr(model_turn, "parts", []):
                        idata = getattr(part, "inline_data", None)
                        if idata and getattr(idata, "data", None):
                            audio_chunks.append(idata.data)

                # User speech transcript (input_audio_transcription channel)
                in_tr = getattr(sc, "input_transcription", None)
                if in_tr:
                    input_transcript += getattr(in_tr, "text", "") or ""

                # Model speech transcript (output_audio_transcription channel)
                out_tr = getattr(sc, "output_transcription", None)
                if out_tr:
                    output_transcript += getattr(out_tr, "text", "") or ""

                # Stop when model turn is complete
                if getattr(sc, "turn_complete", False):
                    break

    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if any(k in msg for k in ("quota", "resource_exhausted", "429", "rate limit")):
            raise HTTPException(429, "Gemini rate limit — please wait a moment and try again.")
        if "not found" in msg or "not supported" in msg:
            raise HTTPException(
                502,
                f"Model {settings.gemini_audio_model!r} not available. "
                f"Check GEMINI_AUDIO_MODEL in .env (current: {settings.gemini_audio_model!r}).",
            )
        raise HTTPException(502, f"Gemini Live error: {exc}")

    # 4. Wrap PCM output (24kHz) in WAV container
    pcm_out   = b"".join(audio_chunks)
    audio_b64 = base64.b64encode(_pcm_to_wav(pcm_out)).decode() if pcm_out else None

    return {
        "audio_b64":     audio_b64,
        "audio_mime":    "audio/wav",
        "transcript":    input_transcript.strip(),
        "response_text": output_transcript.strip(),
        "language":      _detect_language(input_transcript),
    }
