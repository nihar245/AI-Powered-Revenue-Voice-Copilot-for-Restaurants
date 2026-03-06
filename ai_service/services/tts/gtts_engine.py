"""
TTS engine — Piper (offline, fast) with gTTS as internet fallback.

Piper voice coverage:
  EN  → en_US-lessac-medium      (offline)
  HI  → hi_IN-hindi_voices-medium (offline)
  GU  → gTTS fallback             (needs internet — no official Piper GU voice yet)

Voice files must be placed in the directory specified by settings.piper_voices_dir:
  models/piper_voices/en_US-lessac-medium.onnx
  models/piper_voices/en_US-lessac-medium.onnx.json
  models/piper_voices/hi_IN-hindi_voices-medium.onnx
  models/piper_voices/hi_IN-hindi_voices-medium.onnx.json

Download command (run once):
  python -c "
  from huggingface_hub import hf_hub_download; import shutil, pathlib
  d = pathlib.Path('models/piper_voices'); d.mkdir(parents=True, exist_ok=True)
  for f in ['en_US-lessac-medium.onnx','en_US-lessac-medium.onnx.json',
            'hi_IN-hindi_voices-medium.onnx','hi_IN-hindi_voices-medium.onnx.json']:
      lang = f[:2]; country = f[3:5].lower()
      src = hf_hub_download('rhasspy/piper-voices',
            filename=f'{lang}/{lang}_{country.upper()}/{f.split(\"-\")[1]}/medium/{f}')
      shutil.copy(src, d / f)
  "
"""
import asyncio
import base64
import io
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from config import settings
from models.schemas import Language

if TYPE_CHECKING:
    from piper.voice import PiperVoice as _PiperVoiceT

# ─── Piper (offline) ──────────────────────────────────────────────────────────
_piper_voices: dict[str, "_PiperVoiceT"] = {}

# Maps language code → voice filename stem
_PIPER_VOICE_MAP = {
    "en": settings.piper_voice_en,
    "hi": settings.piper_voice_hi,
}


def load_piper_voices() -> None:
    """
    Called once at startup to load voice models into memory.
    Missing or uninstalled voices are silently skipped (gTTS fallback used).
    """
    try:
        from piper.voice import PiperVoice
    except ImportError:
        print("[Piper] piper-tts not installed — pip install piper-tts")
        return

    voices_dir = Path(settings.piper_voices_dir)
    for lang, stem in _PIPER_VOICE_MAP.items():
        onnx = voices_dir / f"{stem}.onnx"
        cfg  = voices_dir / f"{stem}.onnx.json"
        if onnx.exists() and cfg.exists():
            try:
                _piper_voices[lang] = PiperVoice.load(str(onnx), config_path=str(cfg))
                print(f"[Piper] '{lang}' voice loaded: {stem}")
            except Exception as e:
                print(f"[Piper] Failed to load '{lang}' voice: {e}")
        else:
            print(f"[Piper] Voice file not found for '{lang}': {onnx}  (will use gTTS)")


def _piper_synth(text: str, lang: str) -> bytes | None:
    """Returns raw WAV bytes for the given language, or None if unavailable."""
    voice = _piper_voices.get(lang)
    if voice is None:
        return None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize(text, wf)
    return buf.getvalue()


# ─── gTTS fallback (needs internet) ───────────────────────────────────────────
_GTTS_LANG_MAP = {Language.EN: "en", Language.HI: "hi", Language.GU: "gu"}


def _gtts_synth(text: str, language: str) -> bytes:
    from gtts import gTTS
    lang_enum = Language(language) if language in Language._value2member_map_ else Language.EN
    tts = gTTS(text=text, lang=_GTTS_LANG_MAP.get(lang_enum, "en"), slow=False)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


# ─── Public API ───────────────────────────────────────────────────────────────

def text_to_speech_b64(text: str, language: str) -> tuple[str, str]:
    """
    Synthesizes speech and returns (base64_audio, mime_type).
    Tries Piper first (offline, fast); falls back to gTTS (online).
    mime_type is 'audio/wav' for Piper, 'audio/mpeg' for gTTS.
    """
    wav_bytes = _piper_synth(text, language)
    if wav_bytes:
        return base64.b64encode(wav_bytes).decode(), "audio/wav"

    # gTTS fallback
    try:
        mp3_bytes = _gtts_synth(text, language)
        return base64.b64encode(mp3_bytes).decode(), "audio/mpeg"
    except Exception as e:
        print(f"[TTS] gTTS also failed: {e}")
        return "", "audio/mpeg"


async def text_to_speech_b64_async(text: str, language: str) -> tuple[str, str]:
    """Async wrapper — runs synthesis in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, text_to_speech_b64, text, language)
