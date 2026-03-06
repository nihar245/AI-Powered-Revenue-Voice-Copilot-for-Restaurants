"""
Configuration module for the AI Voice Copilot service.

All settings are centralized here for easy modification.
Database connection strings will be added here when PostgreSQL is integrated.
"""

from dataclasses import dataclass, field
import os


@dataclass
class DeepgramConfig:
    """Configuration for Deepgram STT & TTS."""
    api_key: str = "762976aed83b77276c042838bf558122e26ee03f"
    stt_model: str = "nova-3"
    tts_model: str = "aura-2-asteria-en"
    tts_sample_rate: int = 24000


@dataclass
class GroqConfig:
    """Configuration for Groq LLM (Llama 3.3 70B)."""
    api_key: str = "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"
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.3
    max_tokens: int = 512


@dataclass
class GeminiConfig:
    """Configuration for Google Gemini API (kept for Live API fallback)."""
    api_key: str = "AIzaSyBSqvU6uDtHeFX5hKGUjHKcPOE69j1g-ms"
    model: str = "gemini-2.5-flash"
    live_model: str = "gemini-2.5-flash-native-audio-latest"
    temperature: float = 0.3
    max_tokens: int = 512


@dataclass
class TTSConfig:
    """General TTS settings."""
    voice: str = "aura-2-asteria-en"
    output_format: str = "wav"


@dataclass
class FuzzyMatchConfig:
    """Configuration for RapidFuzz menu matching."""
    score_threshold: int = 70
    limit: int = 3


@dataclass
class TwilioConfig:
    """
    Configuration for Twilio SIP voice call integration.

    Setup:
      1. Create Twilio account → get Account SID + Auth Token
      2. Create SIP Domain: restaurant-ai.sip.twilio.com
      3. Create Credential List with username/password for softphone auth
      4. Set Voice URL on SIP Domain to: https://your-ngrok-url/api/call/incoming-call
      5. Configure Zoiper: SIP account → restaurant-ai@restaurant-ai.sip.twilio.com
    """
    account_sid: str = "AC4ce9e3c154d923319e55be34f4c74f97"
    auth_token: str = "79564f53d8d490a0c6784a70c457a3a7"
    phone_number: str = "+15705651315"   # Twilio PSTN number — call this from iPhone!
    sip_domain: str = "restaurant-ai-demo.sip.twilio.com"
    base_url: str = "https://nonreformational-criselda-inconclusively.ngrok-free.dev"


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket event streaming."""
    max_connections: int = 50
    ping_interval: int = 30


@dataclass
class AppConfig:
    """Root application configuration."""
    app_name: str = "AI Voice Copilot"
    restaurant_name: str = "Spice Garden"  # Change this to your restaurant's name
    version: str = "0.2.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8001

    # Sub-configs
    deepgram: DeepgramConfig = field(default_factory=DeepgramConfig)
    groq: GroqConfig = field(default_factory=GroqConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    fuzzy: FuzzyMatchConfig = field(default_factory=FuzzyMatchConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    twilio: TwilioConfig = field(default_factory=TwilioConfig)

    # Future: database config
    # database_url: str = "postgresql://user:pass@localhost:5432/restaurant_db"


def get_config() -> AppConfig:
    """
    Factory function to create application config.
    Reads from environment variables with sensible defaults.
    """
    config = AppConfig(
        debug=os.getenv("DEBUG", "true").lower() == "true",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8001")),
    )

    # Deepgram settings
    config.deepgram.api_key = os.getenv("DEEPGRAM_API_KEY", config.deepgram.api_key)
    config.deepgram.stt_model = os.getenv("DEEPGRAM_STT_MODEL", config.deepgram.stt_model)
    config.deepgram.tts_model = os.getenv("DEEPGRAM_TTS_MODEL", config.deepgram.tts_model)

    # Groq settings
    config.groq.api_key = os.getenv("GROQ_API_KEY", config.groq.api_key)
    config.groq.model = os.getenv("GROQ_MODEL", config.groq.model)

    # Gemini settings (kept for Live API fallback)
    config.gemini.api_key = os.getenv("GEMINI_API_KEY", config.gemini.api_key)
    config.gemini.live_model = os.getenv("GEMINI_LIVE_MODEL", config.gemini.live_model)

    # Override TTS voice from env
    config.tts.voice = os.getenv("TTS_VOICE", config.tts.voice)

    # Twilio settings
    config.twilio.account_sid = os.getenv("TWILIO_ACCOUNT_SID", config.twilio.account_sid)
    config.twilio.auth_token = os.getenv("TWILIO_AUTH_TOKEN", config.twilio.auth_token)
    config.twilio.phone_number = os.getenv("TWILIO_PHONE_NUMBER", config.twilio.phone_number)
    config.twilio.sip_domain = os.getenv("TWILIO_SIP_DOMAIN", config.twilio.sip_domain)
    config.twilio.base_url = os.getenv("TWILIO_BASE_URL", config.twilio.base_url)

    return config


# Singleton config instance
settings = get_config()


# Singleton config instance
settings = get_config()
