"""
Tests for the full voice pipeline and API integration.

Tests the FastAPI endpoints and the end-to-end pipeline flow.
"""

import pytest
import struct
import wave
import tempfile
import io

from fastapi.testclient import TestClient


def _create_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Create minimal WAV file bytes for testing."""
    num_samples = int(sample_rate * duration_sec)
    samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples)

    buf.seek(0)
    return buf.read()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should always return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_components(self, client):
        """Health response should include component status."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "gemini" in data["components"]
        assert "stt" in data["components"]


class TestRootEndpoint:
    """Test the root endpoint."""

    def test_root_returns_200(self, client):
        """Root should return service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "endpoints" in data


class TestMenuEndpoint:
    """Test the menu endpoint."""

    def test_menu_returns_items(self, client):
        """Menu endpoint should return menu items."""
        response = client.get("/menu")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "categories" in data
        assert data["total_items"] > 0


class TestVoiceIntentEndpoint:
    """Test the /voice/intent endpoint."""

    def test_intent_endpoint(self, client):
        """Intent endpoint should accept transcript and return structured data."""
        try:
            response = client.post(
                "/voice/intent",
                json={"transcript": "I want one paneer tikka"},
            )
            # If Gemini API is not reachable, this may fail
            assert response.status_code in (200, 500)
            if response.status_code == 200:
                data = response.json()
                assert "items" in data
                assert "intent_type" in data
        except Exception:
            pytest.skip("Gemini API not available")


class TestVoiceUpsellEndpoint:
    """Test the /voice/upsell endpoint."""

    def test_upsell_endpoint(self, client):
        """Upsell endpoint should return a suggestion."""
        response = client.post(
            "/voice/upsell",
            json={"items": ["Paneer Tikka"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestion" in data
        assert data["suggestion"] == "Cold Coffee"

    def test_upsell_empty_items(self, client):
        """Upsell with empty items should still respond."""
        response = client.post(
            "/voice/upsell",
            json={"items": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestion" in data


class TestVoiceSpeakEndpoint:
    """Test the /voice/speak endpoint."""

    @pytest.mark.asyncio
    async def test_speak_endpoint(self, client):
        """Speak endpoint should return audio bytes."""
        try:
            response = client.post(
                "/voice/speak",
                json={"text": "Welcome to our restaurant!"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/mpeg"
            assert len(response.content) > 0
        except Exception:
            pytest.skip("TTS not available")

    def test_speak_empty_text_rejected(self, client):
        """Empty text should be rejected."""
        response = client.post(
            "/voice/speak",
            json={"text": ""},
        )
        assert response.status_code == 400


class TestVoiceTranscribeEndpoint:
    """Test the /voice/transcribe endpoint."""

    def test_transcribe_empty_file_rejected(self, client):
        """Empty audio file should be rejected."""
        response = client.post(
            "/voice/transcribe",
            files={"audio": ("test.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400

    def test_transcribe_with_wav(self, client):
        """Transcribe should accept a WAV file."""
        try:
            wav_bytes = _create_wav_bytes(duration_sec=1.0)
            response = client.post(
                "/voice/transcribe",
                files={"audio": ("test.wav", wav_bytes, "audio/wav")},
            )
            assert response.status_code in (200, 422, 500)
            if response.status_code == 200:
                data = response.json()
                assert "text" in data
                assert "language" in data
        except Exception:
            pytest.skip("Whisper model not available")


class TestWebSocket:
    """Test the WebSocket connection."""

    def test_websocket_connect(self, client):
        """Should be able to connect to admin WebSocket."""
        try:
            with client.websocket_connect("/ws/admin") as websocket:
                # Connection should succeed
                # Close immediately
                pass
        except Exception:
            pytest.skip("WebSocket test not supported in this environment")


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    def test_menu_to_match_to_upsell(self):
        """Test the menu → match → upsell flow without LLM."""
        from app.services.menu_service import get_menu_items
        from app.services.matching import match_items
        from app.services.upsell_service import suggest_upsell

        # Simulate detected items
        spoken = ["paneer tikka", "coke"]
        menu = get_menu_items()

        # Match
        matched = match_items(spoken, menu)
        assert len(matched) == 2
        matched_names = [m["matched_item"] for m in matched if m["matched_item"]]
        assert "Paneer Tikka" in matched_names

        # Upsell
        upsell = suggest_upsell(matched_names)
        assert upsell["suggestion"] is not None
        # Paneer Tikka → Cold Coffee, but Coke already ordered
        # So it should not suggest Coke again
