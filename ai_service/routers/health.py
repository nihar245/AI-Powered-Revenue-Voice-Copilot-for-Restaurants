from fastapi import APIRouter

from models.schemas import HealthResponse
from services.database.connection import get_pool
from services.stt.whisper_engine import is_loaded as whisper_loaded
from services.nlu.intent_classifier import is_loaded as classifier_loaded
from services.llm.qwen_client import check_ollama_health

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_ok       = get_pool() is not None
    whisper_ok  = whisper_loaded()
    nlu_ok      = classifier_loaded()
    ollama_ok   = await check_ollama_health()

    components = {
        "database":   "ok" if db_ok      else "unavailable",
        "whisper":    "ok" if whisper_ok  else "not_loaded",
        "nlu":        "ok" if nlu_ok      else "not_loaded",
        "ollama":     "ok" if ollama_ok   else "unavailable",
    }
    overall = "ok" if all([db_ok, whisper_ok, nlu_ok, ollama_ok]) else "degraded"
    return HealthResponse(status=overall, components=components)
