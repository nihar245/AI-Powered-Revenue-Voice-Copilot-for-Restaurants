import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import voice, health, test_pipeline, twilio_call
from services.database.connection import connect_db, disconnect_db
from services.database.queries import fetch_active_menu, fetch_tables
from services.audio.twilio_bridge import get_greeting_mulaw, get_wait_mulaw


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    print("[startup] Connecting to database...")
    await connect_db()

    # Cache menu + tables so every request has them without a DB hit
    try:
        app.state.menu   = await fetch_active_menu()
        app.state.tables = await fetch_tables()
        print(f"[startup] Cached {len(app.state.menu)} menu items, "
              f"{len(app.state.tables)} tables from DB.")
    except Exception as exc:
        print(f"[startup] WARNING — could not prefetch menu/tables: {exc}")
        app.state.menu   = []
        app.state.tables = []

    # Pre-build gTTS greeting + wait audio in background threads so the first
    # inbound call never blocks the asyncio event loop waiting for gTTS/ffmpeg.
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, get_greeting_mulaw)
        await loop.run_in_executor(None, get_wait_mulaw)
        print("[startup] Pre-built greeting and 'please wait' audio.")
    except Exception as exc:
        print(f"[startup] WARNING — audio pre-build failed (silence fallback will be used): {exc}")

    print("[startup] ai_service_gemini ready  "
          "(Gemini Live API — audio-in/audio-out, no local ML models)")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await disconnect_db()
    print("[shutdown] Database pool closed.")


app = FastAPI(
    title="AI Voice Receptionist — Gemini Live",
    description=(
        "Multilingual restaurant voice ordering assistant powered exclusively by "
        "Gemini Live API (audio-in / audio-out) + Gemini text model for structured "
        "cart extraction. No local ML models required."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


app.include_router(health.router,         tags=["health"])
app.include_router(voice.router,          prefix="/voice",  tags=["voice"])
app.include_router(test_pipeline.router,  tags=["diagnostics"])
app.include_router(twilio_call.router,    tags=["twilio"])
