"""
TTS — Gemini Live Text-to-Speech

Sends text into a Gemini Live session (AUDIO-only modality) and
collects the PCM output, then wraps it in a WAV container.

Same model and API key as the voice-chat endpoint — no extra credentials.
"""

from __future__ import annotations

import base64
import io
import struct

from google import genai
from google.genai import types

from config import settings


def _pcm_to_wav(pcm: bytes, rate: int = 24_000) -> bytes:
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))    # PCM
    buf.write(struct.pack("<H", 1))    # mono
    buf.write(struct.pack("<I", rate))
    buf.write(struct.pack("<I", rate * 2))
    buf.write(struct.pack("<H", 2))    # block align
    buf.write(struct.pack("<H", 16))   # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm)))
    buf.write(pcm)
    return buf.getvalue()


async def text_to_speech_b64_async(text: str, language: str = "en") -> tuple[str, str]:
    """
    Convert text to speech via Gemini Live API.

    Returns:
        (base64_encoded_wav, "audio/wav")
    """
    if not text.strip():
        return "", "audio/wav"
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    client = genai.Client(api_key=settings.gemini_api_key)

    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )

    audio_chunks: list[bytes] = []

    async with client.aio.live.connect(
        model=settings.gemini_audio_model, config=live_config
    ) as session:
        # Send text input and signal end of turn
        await session.send(
            input=types.Content(
                role="user",
                parts=[types.Part(text=text)],
            ),
            end_of_turn=True,
        )

        # Collect PCM audio chunks
        async for response in session.receive():
            sc = getattr(response, "server_content", None)
            if not sc:
                continue
            model_turn = getattr(sc, "model_turn", None)
            if model_turn:
                for part in getattr(model_turn, "parts", []):
                    idata = getattr(part, "inline_data", None)
                    if idata and getattr(idata, "data", None):
                        audio_chunks.append(idata.data)
            if getattr(sc, "turn_complete", False):
                break

    pcm = b"".join(audio_chunks)
    if not pcm:
        return "", "audio/wav"
    return base64.b64encode(_pcm_to_wav(pcm)).decode(), "audio/wav"


def load_piper_voices() -> None:
    """No-op — Gemini Live TTS needs no local voice files."""
    pass
