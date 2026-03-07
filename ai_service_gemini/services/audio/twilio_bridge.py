"""
Twilio Media Streams — audio conversion utilities and VAD.

Twilio sends:  raw G.711 μ-law 8 kHz, 20 ms frames (160 bytes each)
Gemini needs:  any format that ffmpeg can decode (we wrap mulaw in a WAV container)
Gemini gives:  WAV container, PCM 24 kHz, 16-bit, mono
Twilio wants:  raw G.711 μ-law 8 kHz bytes, base64-encoded in JSON frames
"""

from __future__ import annotations

import base64
import io
import json
import math
import struct
import subprocess
from dataclasses import dataclass
from typing import Optional

# ── VAD tunables ──────────────────────────────────────────────────────────────
SPEECH_RMS_THRESHOLD  = 500    # decoded 16-bit RMS above this = speech
SILENCE_RMS_THRESHOLD = 250    # decoded 16-bit RMS below this = silence
SILENCE_DURATION_MS   = 900    # ms of silence that ends a speech segment
MAX_SEGMENT_MS        = 8_000  # force-flush after this many ms even without silence
_FRAME_MS             = 20     # Twilio sends 20 ms frames → 160 bytes at 8 kHz


# ── μ-law decoder (ITU-T G.711, pure Python — no audioop needed) ──────────────

def _decode_mulaw(byte: int) -> int:
    """Decode a single G.711 μ-law byte to a signed 16-bit PCM sample."""
    byte = (~byte) & 0xFF
    sign = -1 if (byte & 0x80) else 1
    exp  = (byte >> 4) & 0x07
    mant = byte & 0x0F
    linear = ((mant << 1) + 33) << exp
    linear -= 33
    return sign * linear


def chunk_rms(mulaw_bytes: bytes) -> float:
    """Return the RMS energy of a μ-law chunk — used for VAD."""
    if not mulaw_bytes:
        return 0.0
    total = sum(_decode_mulaw(b) ** 2 for b in mulaw_bytes)
    return math.sqrt(total / len(mulaw_bytes))


# ── Audio format converters ───────────────────────────────────────────────────

def mulaw_to_wav8k(mulaw_bytes: bytes) -> bytes:
    """
    Wrap raw G.711 μ-law bytes in a RIFF WAV container
    (format tag 0x0007 = WAVE_FORMAT_MULAW, 8 kHz, 8-bit, mono).

    ffmpeg — which is called by voice_turn() — handles this format natively.
    """
    buf = io.BytesIO()
    n   = len(mulaw_bytes)
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + n))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))       # chunk size
    buf.write(struct.pack("<H", 7))        # WAVE_FORMAT_MULAW
    buf.write(struct.pack("<H", 1))        # channels = mono
    buf.write(struct.pack("<I", 8_000))    # sample rate
    buf.write(struct.pack("<I", 8_000))    # byte rate (1 byte/sample × 8000)
    buf.write(struct.pack("<H", 1))        # block align
    buf.write(struct.pack("<H", 8))        # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", n))
    buf.write(mulaw_bytes)
    return buf.getvalue()


def wav_to_mulaw8k(wav_bytes: bytes) -> bytes:
    """
    Convert any WAV (any sample rate, any encoding) to raw G.711 μ-law 8 kHz
    bytes using the bundled ffmpeg binary.

    Output is *raw* μ-law — no WAV header — ready to base64-encode for Twilio.
    """
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error",
        "-i",      "pipe:0",
        "-ar",     "8000",
        "-ac",     "1",
        "-acodec", "pcm_mulaw",
        "-f",      "mulaw",
        "pipe:1",
    ]
    result = subprocess.run(cmd, input=wav_bytes, capture_output=True, timeout=30)
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")[:300]
        raise RuntimeError(f"ffmpeg mulaw conversion failed: {err}")
    return result.stdout


def make_greeting_wav(duration_ms: int = 500, sample_rate: int = 16_000) -> bytes:
    """
    Return a PCM-WAV file containing silence.

    Sent to voice_turn() as the very first audio of a phone call so that
    Gemini Live (in PTT mode) receives an ActivityEnd signal and generates
    the opening greeting based on the system instruction.
    """
    num_samples = int(sample_rate * duration_ms / 1_000)
    pcm = b"\x00" * (num_samples * 2)  # signed 16-bit → 2 bytes per sample
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))              # PCM
    buf.write(struct.pack("<H", 1))              # mono
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * 2))
    buf.write(struct.pack("<H", 2))              # block align
    buf.write(struct.pack("<H", 16))             # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm)))
    buf.write(pcm)
    return buf.getvalue()


# ── Twilio WebSocket message builders ─────────────────────────────────────────

def make_media_message(stream_sid: str, mulaw_bytes: bytes) -> str:
    """Build the JSON string that sends μ-law audio TO the Twilio caller."""
    return json.dumps({
        "event":     "media",
        "streamSid": stream_sid,
        "media":     {"payload": base64.b64encode(mulaw_bytes).decode()},
    })


def make_clear_message(stream_sid: str) -> str:
    """Build the JSON string that flushes Twilio's audio buffer (interrupts playback)."""
    return json.dumps({"event": "clear", "streamSid": stream_sid})


# ── Voice activity detector ───────────────────────────────────────────────────

@dataclass
class _TurnRequest:
    """Item placed on the internal processing queue."""
    audio: bytes           # raw μ-law bytes (customer speech) OR PCM WAV (greeting)
    is_pcm_wav: bool       # True → already a WAV file; False → raw μ-law
    is_greeting: bool      # True → append phone greeting context to system instruction


class VAD:
    """
    Simple energy-based Voice Activity Detector for Twilio 20 ms μ-law frames.

    State machine
    ─────────────
    SILENT   →  (frame RMS > SPEECH_RMS_THRESHOLD)   →  SPEAKING
    SPEAKING →  (silence_duration >= SILENCE_DURATION_MS)  →  yield segment
    SPEAKING →  (buffer_ms >= MAX_SEGMENT_MS)              →  yield segment
    """

    def __init__(self) -> None:
        self._buf:       bytearray = bytearray()
        self._speaking:  bool      = False
        self._silent_ms: int       = 0
        self._buf_ms:    int       = 0

    def push_frame(self, mulaw_bytes: bytes) -> Optional[bytes]:
        """
        Feed one 20 ms μ-law frame.
        Returns accumulated μ-law bytes when a complete speech segment ends,
        or None if more audio is needed.
        """
        rms = chunk_rms(mulaw_bytes)

        if self._speaking:
            self._buf.extend(mulaw_bytes)
            self._buf_ms += _FRAME_MS
            if rms < SILENCE_RMS_THRESHOLD:
                self._silent_ms += _FRAME_MS
            else:
                self._silent_ms = 0

            if self._silent_ms >= SILENCE_DURATION_MS or self._buf_ms >= MAX_SEGMENT_MS:
                return self._flush()
        else:
            if rms > SPEECH_RMS_THRESHOLD:
                self._speaking  = True
                self._silent_ms = 0
                self._buf.extend(mulaw_bytes)
                self._buf_ms += _FRAME_MS

        return None

    def flush(self) -> Optional[bytes]:
        """Force-return any buffered audio (called on call end)."""
        if self._buf:
            return self._flush()
        return None

    def reset(self) -> None:
        """Discard buffered audio and reset state — call after each AI turn."""
        self._buf       = bytearray()
        self._speaking  = False
        self._silent_ms = 0
        self._buf_ms    = 0

    def _flush(self) -> bytes:
        segment      = bytes(self._buf)
        self._buf       = bytearray()
        self._speaking  = False
        self._silent_ms = 0
        self._buf_ms    = 0
        return segment


# ── Module-level greeting WAV (generated once at import) ─────────────────────
GREETING_WAV = make_greeting_wav(duration_ms=500)


# ── "Please wait" audio (lazy, generated on first need via gTTS) ──────────────
_WAIT_MULAW: bytes | None = None


def _build_wait_mulaw() -> bytes:
    """Convert a TTS 'please wait' phrase to raw μ-law 8 kHz bytes."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from gtts import gTTS  # type: ignore
        mp3_buf = io.BytesIO()
        gTTS("Please hold the line.", lang="en").write_to_fp(mp3_buf)
        mp3_bytes = mp3_buf.getvalue()

        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"

        result = subprocess.run(
            [
                ffmpeg_exe, "-hide_banner", "-loglevel", "error",
                "-f", "mp3", "-i", "pipe:0",
                "-ar", "8000", "-ac", "1", "-acodec", "pcm_mulaw", "-f", "mulaw", "pipe:1",
            ],
            input=mp3_bytes,
            capture_output=True,
            timeout=20,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        _log.warning("gTTS ffmpeg conversion failed: %s", result.stderr[:200])
    except Exception as exc:
        _log.warning("_build_wait_mulaw failed: %s", exc)

    # Fallback: 1.5 s of μ-law silence (value 0x7F = zero energy)
    return bytes([0x7F] * 12_000)


def get_wait_mulaw() -> bytes:
    """Return cached μ-law bytes for the 'please wait' message."""
    global _WAIT_MULAW
    if _WAIT_MULAW is None:
        _WAIT_MULAW = _build_wait_mulaw()
    return _WAIT_MULAW


# ── Greeting audio (lazy, generated once via gTTS) ────────────────────────────
_GREETING_MULAW: bytes | None = None


def _build_greeting_mulaw() -> bytes:
    """Convert the restaurant's opening greeting to raw μ-law 8 kHz bytes."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from gtts import gTTS  # type: ignore
        mp3_buf = io.BytesIO()
        gTTS(
            "Welcome to Padmavati Bhojanalaya! I am Aria, your voice ordering assistant. "
            "Please go ahead and tell me what you would like to order.",
            lang="en",
        ).write_to_fp(mp3_buf)
        mp3_bytes = mp3_buf.getvalue()

        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"

        result = subprocess.run(
            [
                ffmpeg_exe, "-hide_banner", "-loglevel", "error",
                "-f", "mp3", "-i", "pipe:0",
                "-ar", "8000", "-ac", "1", "-acodec", "pcm_mulaw", "-f", "mulaw", "pipe:1",
            ],
            input=mp3_bytes,
            capture_output=True,
            timeout=20,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        _log.warning("gTTS greeting ffmpeg conversion failed: %s", result.stderr[:200])
    except Exception as exc:
        _log.warning("_build_greeting_mulaw failed: %s", exc)

    # Fallback: 2 s of μ-law silence
    return bytes([0x7F] * 16_000)


def get_greeting_mulaw() -> bytes:
    """Return cached μ-law bytes for the opening restaurant greeting."""
    global _GREETING_MULAW
    if _GREETING_MULAW is None:
        _GREETING_MULAW = _build_greeting_mulaw()
    return _GREETING_MULAW
