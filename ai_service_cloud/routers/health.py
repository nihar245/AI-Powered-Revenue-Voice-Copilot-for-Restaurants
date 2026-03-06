from fastapi import APIRouter

from models.schemas import HealthResponse
from services.database.connection import get_pool
from services.stt.whisper_api import is_loaded as whisper_loaded
from services.nlu.intent_classifier import is_loaded as classifier_loaded
from services.llm.gemini_client import check_gemini_health

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_ok      = get_pool() is not None
    whisper_ok = whisper_loaded()
    nlu_ok     = classifier_loaded()
    gemini_ok  = await check_gemini_health()

    components = {
        "database": "ok" if db_ok      else "unavailable",
        "whisper":  "ok" if whisper_ok  else "api_key_missing",
        "nlu":      "ok" if nlu_ok      else "not_loaded",
        "gemini":   "ok" if gemini_ok   else "unavailable",
    }
    overall = "ok" if all([db_ok, whisper_ok, nlu_ok, gemini_ok]) else "degraded"
    return HealthResponse(status=overall, components=components)
