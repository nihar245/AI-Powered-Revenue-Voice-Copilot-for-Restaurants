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
    gemini_audio_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"


settings = Settings()
