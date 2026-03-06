"""
AI Voice Copilot — FastAPI Application Entry Point.

Initializes the FastAPI app, registers routers, mounts the WebSocket
endpoint, and configures startup/shutdown events.
"""

import logging
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.api.voice_routes import router as voice_router
from app.api.health_routes import router as health_router
from app.api.conversation_routes import router as conversation_router
from app.api.call_routes import router as call_router
from app.websocket.manager import ws_manager, EventType

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Silence noisy websockets debug logs (Gemini Live API internals)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("websockets.client").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — runs on startup and shutdown."""
    logger.info("======================================")
    logger.info("  %s v%s  — starting up", settings.app_name, settings.version)
    logger.info("======================================")

    # Verify Groq LLM connectivity
    try:
        from app.services.groq_client import async_client as groq_test
        resp = await groq_test.chat.completions.create(
            model=settings.groq.model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        logger.info("Groq LLM connected ✓  Model: %s", settings.groq.model)
    except Exception as e:
        logger.warning("Groq LLM not reachable: %s", e)

    # Verify Deepgram connectivity
    try:
        from app.services.deepgram_client import client as dg_test
        # Quick TTS test (tiny text)
        audio_iter = dg_test.speak.v1.audio.generate(
            text="ok",
            model=settings.deepgram.tts_model,
            encoding="linear16",
            container="wav",
            sample_rate=settings.deepgram.tts_sample_rate,
        )
        _ = b"".join(audio_iter)
        logger.info("Deepgram API connected ✓  STT: %s, TTS: %s", settings.deepgram.stt_model, settings.deepgram.tts_model)
    except Exception as e:
        logger.warning("Deepgram API not reachable: %s", e)

    # Fetch live menu from DB first, then backend API, then hardcoded fallback
    try:
        from app.services.menu_service import refresh_menu_from_db, fetch_menu_from_backend
        db_fetched = await refresh_menu_from_db()
        if not db_fetched:
            logger.info("DB menu fetch failed — trying backend API...")
            fetched = await fetch_menu_from_backend()
            if not fetched:
                logger.info("Using fallback hardcoded menu (DB and backend unavailable)")
            else:
                logger.info("✅ Menu loaded from backend API")
        else:
            logger.info("✅ Menu loaded from PostgreSQL DB")
    except Exception as e:
        logger.info("Menu fetch skipped: %s (using fallback)", e)

    # Warm up edge-tts (first call creates WebSocket to Microsoft, ~5-8s)
    try:
        from app.voice.tts import synthesize_speech as _warm_tts
        logger.info("Warming up edge-tts (Hindi voice)...")
        await _warm_tts("नमस्ते", language="hi")
        logger.info("Edge-TTS warmed up ✓  Hindi voice ready")
    except Exception as e:
        logger.warning("Edge-TTS warmup failed (will retry on first request): %s", e)

    yield  # App is running

    logger.info("Shutting down %s...", settings.app_name)


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "NLP & Voice AI pipeline for restaurant ordering. "
        "Processes voice input, extracts order intent, suggests upsells, "
        "and generates spoken responses."
    ),
    lifespan=lifespan,
)

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(voice_router)
app.include_router(health_router)
app.include_router(conversation_router)
app.include_router(call_router)

# Mount static files (browser call UI)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/admin")
async def admin_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for the admin dashboard.

    Streams real-time pipeline events:
    - call_started
    - transcript_received
    - items_detected
    - upsell_suggested
    - response_generated
    - order_confirmed
    - pipeline_complete
    """
    connected = await ws_manager.connect(websocket)
    if not connected:
        return

    # Send recent events to new connection (catch-up)
    recent = ws_manager.get_recent_events(limit=10)
    for event in recent:
        try:
            import json
            await websocket.send_text(json.dumps(event, default=str))
        except Exception:
            break

    try:
        while True:
            # Keep connection alive; listen for client messages
            data = await websocket.receive_text()
            # Future: handle admin commands (e.g., confirm order, override)
            logger.debug("Admin WS received: %s", data[:100])
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("Admin WebSocket disconnected")
    except Exception as e:
        ws_manager.disconnect(websocket)
        logger.warning("Admin WebSocket error: %s", e)


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/call")
async def call_page():
    """Serve the browser-based voice call UI."""
    html_path = Path(__file__).parent / "static" / "call.html"
    return FileResponse(str(html_path), media_type="text/html")


@app.get("/")
async def root():
    """Root endpoint — service info."""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "call_ui": "/call",
        "endpoints": {
            "transcribe": "POST /voice/transcribe",
            "intent": "POST /voice/intent",
            "upsell": "POST /voice/upsell",
            "speak": "POST /voice/speak",
            "full_pipeline": "POST /voice/full-pipeline",
            "health": "GET /health",
            "menu": "GET /menu",
            "admin_ws": "WS /ws/admin",
            "conversation_ws": "WS /ws/conversation",
            "call_ui": "GET /call",
        },
    }
