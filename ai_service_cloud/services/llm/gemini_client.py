"""
LLM — Google Gemini 2.0 Flash

Replaces local Ollama + phi4-mini with the Gemini API.
Latency: ~200-500ms vs ~2000-5000ms on CPU locally.
Free tier: 15 RPM / 1M tokens per day on gemini-2.0-flash.
"""

import asyncio

import google.generativeai as genai

from config import settings

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel(settings.gemini_text_model)
    return _model


async def generate(
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 80,
) -> str:
    """
    Sends a prompt to Gemini and returns the response text.
    Runs the blocking SDK call in a thread pool to avoid blocking the event loop.
    """
    model = _get_model()
    loop  = asyncio.get_event_loop()

    def _call() -> str:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text.strip()

    return await loop.run_in_executor(None, _call)


async def check_gemini_health() -> bool:
    """Quick liveness check — returns False if API key missing or unreachable."""
    if not settings.gemini_api_key:
        return False
    try:
        resp = await generate("Reply with: ok", max_tokens=5)
        return bool(resp)
    except Exception:
        return False


async def warmup_gemini() -> None:
    """Fire one request at startup so the first real request isn't cold."""
    print("[LLM] Warming up Gemini API...")
    try:
        await generate("Reply with: ready", max_tokens=5)
        print("[LLM] Gemini warm-up complete.")
    except Exception as e:
        print(f"[LLM] Gemini warm-up failed: {e}  (check GEMINI_API_KEY in .env)")


# Backward-compat shim so main.py can call load_model() without branching
def load_model() -> None:
    key_status = "set" if settings.gemini_api_key else "MISSING"
    print(f"[LLM] Gemini API mode — key: {key_status}, model: {settings.gemini_text_model}")
