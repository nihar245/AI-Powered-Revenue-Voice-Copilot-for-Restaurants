from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/cafe_odoo"

    # Whisper
    whisper_model: str = "small"

    # LLM (llama-cpp-python / phi4-mini GGUF)
    llm_model_path: str = "models/Phi-4-mini-instruct-Q4_K_M.gguf"
    llm_n_gpu_layers: int = -1   # -1 = offload all layers to GPU (Vulkan/CUDA)
    llm_n_ctx: int = 512         # context window — keep small for speed
    llm_n_threads: int = 4       # CPU threads for non-GPU ops

    # Ollama (legacy — kept so old imports don't break)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # TTS — Piper (offline) + gTTS fallback
    piper_voices_dir: str = "models/piper_voices"
    piper_voice_en: str = "en_US-lessac-medium"
    piper_voice_hi: str = "hi_IN-hindi_voices-medium"
    tts_language_default: str = "hi"


settings = Settings()
