"""
Health check and system status routes.

Provides endpoints for monitoring service health,
model readiness, and WebSocket connection status.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str
    timestamp: str
    components: dict


class MenuInfoResponse(BaseModel):
    """Menu information response."""
    total_items: int
    categories: list[str]
    items: list[dict]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Service health check endpoint.

    Returns overall service status and component health.
    """
    # Check Groq LLM connectivity
    groq_status = "unknown"
    try:
        from app.services.groq_client import client as groq_sync
        resp = groq_sync.chat.completions.create(
            model=settings.groq.model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        groq_status = "connected"
    except Exception:
        groq_status = "disconnected"

    # Check Deepgram connectivity
    deepgram_status = "unknown"
    try:
        from app.services.deepgram_client import client as dg_health
        audio_iter = dg_health.speak.v1.audio.generate(
            text="ok",
            model=settings.deepgram.tts_model,
            encoding="linear16",
            container="wav",
            sample_rate=settings.deepgram.tts_sample_rate,
        )
        _ = b"".join(audio_iter)
        deepgram_status = "connected"
    except Exception:
        deepgram_status = "disconnected"

    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components={
            "groq": {
                "status": groq_status,
                "model": settings.groq.model,
            },
            "deepgram": {
                "status": deepgram_status,
                "stt_model": settings.deepgram.stt_model,
                "tts_model": settings.deepgram.tts_model,
            },
            "conversation": {
                "engine": "Deepgram STT → Groq LLM → Deepgram TTS",
                "mode": "sequential pipeline per turn",
            },
            "websocket": {
                "active_connections": ws_manager.active_count,
            },
        },
    )


@router.get("/menu", response_model=MenuInfoResponse)
async def get_menu():
    """
    Get current menu information.

    Returns all available menu items and categories.
    Useful for testing and admin dashboard display.
    """
    from app.services.menu_service import get_menu_items_detailed, get_categories

    items = get_menu_items_detailed()
    categories = get_categories()

    return MenuInfoResponse(
        total_items=len(items),
        categories=categories,
        items=items,
    )
