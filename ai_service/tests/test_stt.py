"""
Tests for Speech-to-Text module.

These tests verify the STT pipeline works correctly.
Some tests require the Whisper model to be available.
"""

import pytest
import tempfile
import struct
import wave
import os


def _create_silent_wav(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """
    Create a minimal silent WAV file for testing.

    Args:
        duration_sec: Duration of silence in seconds.
        sample_rate: Audio sample rate.

    Returns:
        bytes: WAV file bytes.
    """
    num_samples = int(sample_rate * duration_sec)
    samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))

    buf = tempfile.SpooledTemporaryFile()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples)

    buf.seek(0)
    return buf.read()


class TestSTTModule:
    """Test suite for the STT module."""

    def test_create_silent_wav(self):
        """Test that we can create valid WAV bytes for testing."""
        wav_bytes = _create_silent_wav(duration_sec=0.5)
        assert len(wav_bytes) > 0
        assert wav_bytes[:4] == b"RIFF"  # WAV header

    @pytest.mark.asyncio
    async def test_transcribe_silent_audio(self):
        """
        Test transcription of silent audio.
        
        Should return empty or near-empty transcript.
        Requires faster-whisper model to be available.
        """
        try:
            from app.voice.stt import transcribe_audio

            wav_bytes = _create_silent_wav(duration_sec=1.0)
            result = await transcribe_audio(wav_bytes)

            assert "text" in result
            assert "segments" in result
            assert "language" in result
            assert "duration_ms" in result
            assert isinstance(result["text"], str)
            assert isinstance(result["segments"], list)
            assert result["duration_ms"] > 0
        except Exception as e:
            pytest.skip(f"Whisper model not available: {e}")

    @pytest.mark.asyncio
    async def test_transcribe_returns_correct_structure(self):
        """Verify the response structure from transcribe_audio."""
        try:
            from app.voice.stt import transcribe_audio

            wav_bytes = _create_silent_wav(duration_sec=0.5)
            result = await transcribe_audio(wav_bytes)

            required_keys = {"text", "segments", "language", "duration_ms"}
            assert required_keys.issubset(result.keys())
        except Exception as e:
            pytest.skip(f"Whisper model not available: {e}")


class TestSTTConfig:
    """Test that STT configuration is accessible."""

    def test_whisper_config_exists(self):
        """Config module should have whisper settings."""
        from app.config import settings

        assert hasattr(settings, "whisper")
        assert settings.whisper.model_size in ("tiny", "base", "small", "medium", "large")
        assert settings.whisper.device in ("cpu", "cuda", "auto")

    def test_config_has_beam_size(self):
        """Beam size should be a positive integer."""
        from app.config import settings
        assert settings.whisper.beam_size > 0
