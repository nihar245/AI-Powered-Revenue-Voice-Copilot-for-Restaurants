from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import voice, health, test_pipeline
from services.stt.whisper_engine import load_whisper_model
from services.nlu.intent_classifier import load_classifier
from services.database.connection import connect_db, disconnect_db
from services.llm.qwen_client import load_model, warmup_ollama
from services.tts.gtts_engine import load_piper_voices


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    print("[startup] Connecting to database...")
    await connect_db()

    print("[startup] Loading Whisper model...")
    load_whisper_model()

    print("[startup] Loading NLU classifier...")
    load_classifier()

    print("[startup] Loading phi4-mini (llama-cpp) — this may take 10-30s on first launch…")
    load_model()

    print("[startup] Warming up LLM (first-token pre-heating)...")
    await warmup_ollama()

    print("[startup] Loading Piper TTS voices…")
    load_piper_voices()

    print("[startup] All services ready.")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    await disconnect_db()
    print("[shutdown] Database pool closed.")


app = FastAPI(
    title="AI Voice Receptionist",
    description="Multilingual voice ordering assistant for restaurants",
    version="1.0.0",
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


app.include_router(health.router, tags=["health"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])
app.include_router(test_pipeline.router, tags=["diagnostics"])
