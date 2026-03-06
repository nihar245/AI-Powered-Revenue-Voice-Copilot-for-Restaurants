from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Server
    host: str = "0.0.0.0"
    port: int = 8001   # Different port so both services can run side-by-side

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/cafe_odoo"

    # Gemini — single API key for all services
    gemini_api_key: str = "AIzaSyBuZZ2lcO3Yx9ql7syb_bQGhNBPakWW0i0"

    # Text model: LLM responses + standalone STT transcription (generate_content)
    gemini_text_model: str = "gemini-2.5-flash"

    # Audio model: Gemini Live API — voice chat STT + TTS in one call
    gemini_audio_model: str = "gemini-2.5-flash"


settings = Settings()
print("Using audio model:", settings.gemini_audio_model)