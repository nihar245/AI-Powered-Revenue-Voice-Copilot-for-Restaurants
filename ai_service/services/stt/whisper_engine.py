import asyncio
import os
import tempfile

from faster_whisper import WhisperModel

_model: WhisperModel | None = None


def load_whisper_model() -> None:
    global _model
    from config import settings
    print(f"[Whisper] Loading '{settings.whisper_model}' model (faster-whisper, CPU int8)...")
    _model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type="int8",   # most efficient on CPU
    )
    print("[Whisper] Model ready.")


def is_loaded() -> bool:
    return _model is not None


async def transcribe(audio_bytes: bytes) -> dict:
    """
    Transcribes audio bytes using faster-whisper (auto-detects language).

    Returns:
        {
          "transcript": str,
          "language": str,          # e.g. "en", "hi", "gu"
          "language_probability": float
        }

    Inference is offloaded to a thread pool so it doesn't block the event loop.
    """
    if _model is None:
        raise RuntimeError("Whisper model not loaded — call load_whisper_model() first")

    # faster-whisper needs a file path, not raw bytes
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        loop = asyncio.get_event_loop()

        def _run() -> dict:
            segments, info = _model.transcribe(
                tmp_path,
                language=None,      # auto-detect
                task="transcribe",
                beam_size=5,
            )
            transcript = " ".join(seg.text.strip() for seg in segments)
            return {
                "transcript":           transcript.strip(),
                "language":             info.language,
                "language_probability": info.language_probability,
            }

        result = await loop.run_in_executor(None, _run)
    finally:
        os.unlink(tmp_path)

    return result
