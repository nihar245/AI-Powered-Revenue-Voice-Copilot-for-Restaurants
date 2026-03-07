from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Server
    host: str = "0.0.0.0"
    port: int = 8002   # sits alongside 8001 (ai_service_cloud)

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/cafe_odoo"

    # Gemini — single API key for all services
    gemini_api_key: str = ""

    # gemini-2.0-flash (or gemini-2.5-flash) for fast JSON extraction from transcript
    gemini_text_model: str = "gemini-2.0-flash"

    # gemini-2.5-flash-native-audio-preview-* for Gemini Live audio-in / audio-out
    gemini_audio_model: str = "gemini-2.5-flash-native-audio-latest"

    # ── Twilio phone call integration ─────────────────────────────────────────
    twilio_account_sid:  str = ""
    twilio_auth_token:   str = ""
    twilio_phone_number: str = ""
    twilio_sip_domain:   str = ""
    # Public-facing HTTPS URL of THIS server — used to build the Media Stream
    # WebSocket URL returned in TwiML.  Examples:
    #   https://abc123.ngrok.io        (local dev via ngrok)
    #   https://api.yourrestaurant.com (production)
    twilio_base_url: str = ""


settings = Settings()
