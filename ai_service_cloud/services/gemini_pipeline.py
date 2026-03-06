"""
Unified Gemini 2.5 Pipeline (Option C: STT + LLM (JSON) -> TTS)

1. Takes user audio and menu/cart context.
2. Uses Gemini 2.5 Flash to transcribe and return a JSON structure
   containing the intent, cart updates, and the text response.
3. Uses Gemini Live API (Audio modality) to stream the TTS response.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import struct

import google.generativeai as legacy_genai
from google import genai
from google.genai import types

from config import settings


# ─── 1. STT + Reasoning (LLM) returning JSON  ─────────────────────────────────

_TRANSCRIBE_REASON_PROMPT = """
You are a highly efficient AI voice assistant for a restaurant.
Your objective is to process the customer's audio input, understand their intent, update the cart if necessary, and formulate a conversational text response.

The speaker may use English, Hindi, Gujarati, Hinglish, or code-mixed speech.
Return exactly one valid JSON object with the following fields:
  "transcript": The spoken text verbatim.
  "language":   ISO 639-1 code (e.g., "en", "hi", "gu").
  "intent":     A standard intent string (e.g., "ADD_ITEM", "REMOVE_ITEM", "VIEW_CART", "CONFIRM_ORDER", "CANCEL_ORDER", "GREETING", "VIEW_MENU", "UNKNOWN").
  "cart_updates": A list of items to add or remove if applicable (e.g., [{"product_id": "123", "action": "add", "quantity": 1}]). If none, return [].
  "response_text": The conversational response to the customer.

IMPORTANT: Do NOT wrap the output in markdown fences (like ```json), just output the raw JSON object.
"""

def _process_audio_sync(audio_bytes: bytes, mime_type: str, context: str) -> dict:
    legacy_genai.configure(api_key=settings.gemini_api_key)
    model = legacy_genai.GenerativeModel(settings.gemini_text_model)
    
    prompt = _TRANSCRIBE_REASON_PROMPT
    if context:
        prompt += f"\n\nContext:\n{context}"

    response = model.generate_content(
        [{"mime_type": mime_type, "data": audio_bytes}, prompt],
        generation_config={"temperature": 0.1, "max_output_tokens": 1024},
    )

    text = response.text.strip()
    # Strip markdown code fences if the model wrapped its response
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError:
        # Fallback if Gemini failed to output valid JSON
        return {
            "transcript": "",
            "language": "en",
            "intent": "UNKNOWN",
            "cart_updates": [],
            "response_text": text
        }

async def process_audio_and_reason(audio_bytes: bytes, context: str = "", mime_type: str = "audio/webm") -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_audio_sync, audio_bytes, mime_type, context)


# ─── 2. TTS Generation ───────────────────────────────────────────────────────

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


async def generate_speech_b64(text: str, language: str = "en") -> tuple[str, str]:
    """
    Convert text to speech via Gemini Live API (Audio modality).
    Returns (base64_encoded_wav, mime_type).
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
        await session.send(
            input=types.Content(
                role="user",
                parts=[types.Part(text=text)],
            ),
            end_of_turn=True,
        )

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

async def warmup_gemini():
    """No-op for the new unified api"""
    pass

def check_gemini_health():
    return True
