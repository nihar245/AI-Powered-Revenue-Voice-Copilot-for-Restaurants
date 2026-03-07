"""
Gemini Live API — native audio-in / audio-out voice turn.

Architecture
────────────
1. Convert browser WebM/Opus → raw PCM 16 kHz mono (via bundled ffmpeg)
2. Open a Gemini Live session with:
   • AUDIO response modality only
   • input_audio_transcription  (what the user said)
   • output_audio_transcription (what the model is saying)
   • A system instruction that includes the current menu + cart
3. Stream PCM audio + ActivityEnd into the session
4. Collect: PCM audio output chunks + input/output transcripts
5. Wrap the 24 kHz PCM output in a WAV container
6. Return a plain dict with audio, transcripts, and detected language

No separate STT step. No separate TTS step. Everything is one Live session.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import struct
import subprocess
import traceback

from fastapi import HTTPException
from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)


# ─── PCM ↔ WAV helpers ───────────────────────────────────────────────────────

def _pcm_to_wav(pcm: bytes, rate: int = 24_000) -> bytes:
    """Wrap raw signed 16-bit mono PCM in a standard WAV container."""
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))     # PCM format
    buf.write(struct.pack("<H", 1))     # mono
    buf.write(struct.pack("<I", rate))
    buf.write(struct.pack("<I", rate * 2))
    buf.write(struct.pack("<H", 2))     # block align (16-bit mono)
    buf.write(struct.pack("<H", 16))    # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm)))
    buf.write(pcm)
    return buf.getvalue()


def to_pcm16k(audio_bytes: bytes) -> bytes:
    """
    Convert any browser audio (WebM/Opus, WAV, MP3, OGG …) to
    raw signed 16-bit little-endian PCM at 16 kHz mono via bundled ffmpeg.

    Gemini Live requires: mime_type="audio/pcm;rate=16000"
    """
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error",
        "-i",  "pipe:0",
        "-f",  "s16le",
        "-ar", "16000",
        "-ac", "1",
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, input=audio_bytes, capture_output=True, timeout=30)
    except FileNotFoundError:
        raise HTTPException(500, "ffmpeg binary not found — run: pip install imageio-ffmpeg")

    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace")[:300]
        raise HTTPException(500, f"Audio conversion failed (ffmpeg): {detail}")

    return result.stdout


# ─── Language heuristic ───────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """Detect language from the native script of the transcript."""
    if not text:
        return "en"
    devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097F")  # Hindi/Marathi
    gujarati   = sum(1 for c in text if "\u0A80" <= c <= "\u0AFF")
    gurmukhi   = sum(1 for c in text if "\u0A00" <= c <= "\u0A7F")  # Punjabi
    tamil      = sum(1 for c in text if "\u0B80" <= c <= "\u0BFF")
    telugu     = sum(1 for c in text if "\u0C00" <= c <= "\u0C7F")
    # Pick the dominant non-ASCII script
    scores = {
        "hi": devanagari,
        "gu": gujarati,
        "pa": gurmukhi,
        "ta": tamil,
        "te": telugu,
    }
    best_lang, best_count = max(scores.items(), key=lambda x: x[1])
    if best_count >= 3:
        return best_lang
    return "en"


# ─── Response tag parser ─────────────────────────────────────────────────────

def _parse_response_tags(text: str) -> tuple[str, list[str], str, str]:
    """
    Extract [CMD:], [ROMAN:] and [TRANSCRIPT:] tags from Gemini's output_audio_transcription.
    Returns (clean_response, cmd_hints_list, roman_display, transcript_display).

    Supports multiple [CMD:] tags per turn (compound intents like modify + remove).
    Tags are stripped so they are never shown to the user or spoken aloud.
    """
    cmd_hints    = [m.group(1).strip() for m in re.finditer(r'\[CMD:\s*(.*?)\]', text, re.DOTALL | re.IGNORECASE)]
    roman_m      = re.search(r'\[ROMAN:\s*(.*?)\]',      text, re.DOTALL | re.IGNORECASE)
    transcript_m = re.search(r'\[TRANSCRIPT:\s*(.*?)\]', text, re.DOTALL | re.IGNORECASE)
    roman_text        = roman_m.group(1).strip()      if roman_m      else ""
    transcript_roman  = transcript_m.group(1).strip() if transcript_m else ""
    clean = re.sub(r'\[CMD:.*?\]',        '', text,  flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'\[ROMAN:.*?\]',      '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'\[TRANSCRIPT:.*?\]', '', clean, flags=re.DOTALL | re.IGNORECASE).strip()
    return clean, cmd_hints, roman_text, transcript_roman


# ─── Live session ─────────────────────────────────────────────────────────────

async def voice_turn(
    audio_bytes: bytes,
    system_instruction: str,
    voice_name: str = "Aoede",
) -> dict:
    """
    Execute one push-to-talk turn via Gemini Live Native Audio.

    Returns
    -------
    dict with keys:
        audio_b64     : base64-encoded WAV (24 kHz PCM mono), or "" on silence
        audio_mime    : "audio/wav"
        transcript    : what the user said  (input_audio_transcription)
        response_text : what the model said (output_audio_transcription)
        language      : "en" | "hi" | "gu"
    """
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    # Convert browser audio → PCM 16 kHz (required by Gemini Live).
    # Run in a thread so the blocking ffmpeg subprocess does not stall the event loop.
    loop = asyncio.get_event_loop()
    pcm_input = await loop.run_in_executor(None, to_pcm16k, audio_bytes)

    client = genai.Client(api_key=settings.gemini_api_key)

    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription={},
        output_audio_transcription={},
        # Push-to-talk: disable automatic VAD so we can send explicit
        # ActivityStart / ActivityEnd without getting error 1007.
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=True
            )
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
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

            # PTT sequence: mark start → stream PCM → mark end
            await session.send_realtime_input(activity_start=types.ActivityStart())
            await session.send_realtime_input(
                audio=types.Blob(data=pcm_input, mime_type="audio/pcm;rate=16000")
            )
            await session.send_realtime_input(activity_end=types.ActivityEnd())

            # Collect audio output + transcripts
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

                in_tr = getattr(sc, "input_transcription", None)
                if in_tr:
                    input_transcript += getattr(in_tr, "text", "") or ""

                out_tr = getattr(sc, "output_transcription", None)
                if out_tr:
                    output_transcript += getattr(out_tr, "text", "") or ""

                if getattr(sc, "turn_complete", False):
                    break

        # Gemini Live sometimes delivers the final input_transcription fragment
        # AFTER turn_complete.  Drain with a short deadline to capture it.
        async def _drain_late_transcript() -> None:
            nonlocal input_transcript
            async for late_resp in session.receive():
                lsc = getattr(late_resp, "server_content", None)
                if not lsc:
                    break
                in_tr = getattr(lsc, "input_transcription", None)
                if in_tr:
                    input_transcript += getattr(in_tr, "text", "") or ""
        try:
            await asyncio.wait_for(_drain_late_transcript(), timeout=0.8)
        except Exception:
            pass  # asyncio.TimeoutError or session already closed — both expected

    except HTTPException:
        raise
    except Exception as exc:
        # ── Print full API error to server stdout so it appears in uvicorn logs ──
        logger.error(
            "\n━━━ Gemini Live ERROR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Exception type : %s\n"
            "Exception repr : %r\n"
            "Model used     : %s\n"
            "━━━ Traceback ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n%s"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            type(exc).__name__,
            exc,
            settings.gemini_audio_model,
            traceback.format_exc(),
        )
        # Also print directly so it's visible even if logging isn't configured
        print(
            f"\n━━━ Gemini Live ERROR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Type   : {type(exc).__name__}\n"
            f"Detail : {exc!r}\n"
            f"Model  : {settings.gemini_audio_model}\n"
            f"{traceback.format_exc()}"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            flush=True,
        )
        msg = str(exc).lower()
        if any(k in msg for k in ("quota", "resource_exhausted", "429", "rate limit")):
            raise HTTPException(429, "Gemini rate limit — please wait a moment and try again.")
        if any(k in msg for k in ("not found", "not supported", "invalid argument", "unknown model")):
            raise HTTPException(
                502,
                f"Model {settings.gemini_audio_model!r} unavailable. "
                f"Raw error: {exc!r}. Check GEMINI_AUDIO_MODEL in .env.",
            )
        raise HTTPException(502, f"Gemini Live error [{type(exc).__name__}]: {exc!r}")

    pcm_out   = b"".join(audio_chunks)
    audio_b64 = base64.b64encode(_pcm_to_wav(pcm_out)).decode() if pcm_out else ""

    clean_response, cmd_hints, roman_display, transcript_roman = _parse_response_tags(output_transcript)

    # Prefer TRANSCRIPT tag (Gemini's own transliteration) over raw input_transcript
    # which may still arrive in native script despite the instruction.
    transcript_display = transcript_roman or input_transcript.strip()

    return {
        "audio_b64":           audio_b64,
        "audio_mime":          "audio/wav",
        "transcript":          input_transcript.strip(),   # raw STT (may be native script)
        "transcript_display":  transcript_display,          # Roman transliteration → shown in UI
        "response_text":       clean_response,              # clean native-script response
        "response_display":    roman_display or clean_response,  # Roman transliteration → shown in UI
        "cmd_hints":           cmd_hints,                   # list of [CMD:] tag values (may be multiple)
        "cmd_hint":            cmd_hints[0] if cmd_hints else "",  # backward compat
        "language":            _detect_language(input_transcript),
    }


# ─── Persistent per-call session ─────────────────────────────────────────────

class GeminiCallSession:
    """
    Persistent Gemini Live WebSocket session for the full duration of one phone call.

    Why this exists
    ───────────────
    Opening a new Gemini Live WebSocket on every utterance triggered TLS + WebSocket
    handshake overhead (~2–3 s) that exceeded Twilio's audio delivery rate, causing
    "timed out during opening handshake" errors on the very first turn.

    With this class the connection is established ONCE when the call begins and reused
    for every subsequent turn.  Gemini natively maintains the full conversation context
    inside the session's context window — no external history injection is needed.

    Per-turn dynamic state (current cart, turn number, awaiting-confirmation flag) is
    delivered via a short text snippet injected with send_realtime_input(text=…) BEFORE
    the audio.  With PTT mode (automatic_activity_detection=disabled) the text is
    batched as context and does NOT trigger a premature response — the model replies
    only after ActivityEnd.

    Usage
    ─────
        session = GeminiCallSession()
        await session.open(system_instruction)      # once
        result  = await session.send_turn(audio)    # once per utterance
        await session.close()                       # once at call end
    """

    def __init__(self) -> None:
        self._client: genai.Client | None = None
        self._session = None   # live session object returned by context-manager __aenter__
        self._cm      = None   # the async context manager itself
        self.connected: bool = False

    async def open(self, system_instruction: str, voice_name: str = "Aoede") -> None:
        """Open the Gemini Live connection.  Must be called exactly once per call."""
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")

        self._client = genai.Client(api_key=settings.gemini_api_key)

        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription={},
            output_audio_transcription={},
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
            system_instruction=system_instruction,
        )

        self._cm      = self._client.aio.live.connect(
            model=settings.gemini_audio_model,
            config=live_config,
        )
        self._session = await self._cm.__aenter__()
        self.connected = True
        logger.info("[GeminiCallSession] opened  model=%s", settings.gemini_audio_model)

    async def close(self) -> None:
        """Close the Gemini Live session cleanly."""
        if self._cm and self.connected:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("[GeminiCallSession] close error (ignored): %s", exc)
        self.connected = False
        self._session  = None
        logger.info("[GeminiCallSession] closed")

    async def send_turn(
        self,
        audio_bytes:    bytes,
        context_update: str | None = None,
    ) -> dict:
        """
        Process one customer utterance and return Gemini's audio + text response.

        Parameters
        ----------
        audio_bytes    : Raw audio (WAV or μ-law). Converted to PCM 16 kHz internally.
        context_update : Short text injected BEFORE the audio conveying current cart
                         state, turn number, and any special state (greeting, awaiting
                         kitchen confirmation, etc.).

        Returns
        -------
        Same dict shape as voice_turn():
            audio_b64, audio_mime, transcript, transcript_display,
            response_text, response_display, cmd_hints, cmd_hint, language
        """
        if not self._session or not self.connected:
            raise RuntimeError("Gemini session is not open — call open() first.")

        # Run ffmpeg conversion in a thread to avoid blocking the event loop.
        loop = asyncio.get_event_loop()
        pcm_input = await loop.run_in_executor(None, to_pcm16k, audio_bytes)

        # Inject per-turn context before the audio.  With PTT mode the model will
        # not respond to the text alone — it waits until ActivityEnd.
        if context_update:
            await self._session.send_realtime_input(text=context_update)

        await self._session.send_realtime_input(activity_start=types.ActivityStart())
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm_input, mime_type="audio/pcm;rate=16000")
        )
        await self._session.send_realtime_input(activity_end=types.ActivityEnd())

        audio_chunks:     list[bytes] = []
        input_transcript  = ""
        output_transcript = ""

        async for response in self._session.receive():
            sc = getattr(response, "server_content", None)
            if not sc:
                continue

            model_turn = getattr(sc, "model_turn", None)
            if model_turn:
                for part in getattr(model_turn, "parts", []):
                    idata = getattr(part, "inline_data", None)
                    if idata and getattr(idata, "data", None):
                        audio_chunks.append(idata.data)

            in_tr = getattr(sc, "input_transcription", None)
            if in_tr:
                input_transcript += getattr(in_tr, "text", "") or ""

            out_tr = getattr(sc, "output_transcription", None)
            if out_tr:
                output_transcript += getattr(out_tr, "text", "") or ""

            if getattr(sc, "turn_complete", False):
                break

        raw_pcm   = b"".join(audio_chunks)
        audio_b64 = base64.b64encode(_pcm_to_wav(raw_pcm)).decode() if raw_pcm else ""

        clean_response, cmd_hints, roman_display, transcript_roman = _parse_response_tags(output_transcript)
        transcript_display = transcript_roman or input_transcript.strip()

        return {
            "audio_b64":           audio_b64,
            "audio_mime":          "audio/wav",
            "transcript":          input_transcript.strip(),
            "transcript_display":  transcript_display,
            "response_text":       clean_response,
            "response_display":    roman_display or clean_response,
            "cmd_hints":           cmd_hints,
            "cmd_hint":            cmd_hints[0] if cmd_hints else "",
            "language":            _detect_language(input_transcript),
        }
