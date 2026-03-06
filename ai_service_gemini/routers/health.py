from fastapi import APIRouter

from models.schemas import HealthResponse
from services.database.connection import get_pool
from config import settings

router = APIRouter()


async def _check_gemini() -> bool:
    """Quick liveness check — tries a tiny generate_content call."""
    if not settings.gemini_api_key:
        return False
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = await client.aio.models.generate_content(
            model=settings.gemini_text_model,
            contents="Reply: ok",
            config=types.GenerateContentConfig(max_output_tokens=5),
        )
        return bool(resp.text)
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_ok     = get_pool() is not None
    gemini_ok = await _check_gemini()

    components = {
        "database":    "ok" if db_ok     else "unavailable",
        "gemini_live": "ok" if bool(settings.gemini_api_key) else "api_key_missing",
        "gemini_text": "ok" if gemini_ok else "unavailable",
    }
    overall = "ok" if (db_ok and gemini_ok) else "degraded"
    return HealthResponse(status=overall, components=components)
