from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import voice, health, test_pipeline
from services.database.connection import connect_db, disconnect_db
from services.gemini_pipeline import check_gemini_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] Connecting to database...")
    await connect_db()

    print("[startup] Checking Gemini API key for Audio Pipeline...")
    if not check_gemini_health():
        print("[WARNING] Gemini API key not set or invalid.")

    print("[startup] All services ready.")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    await disconnect_db()
    print("[shutdown] Database pool closed.")


app = FastAPI(
    title="AI Voice Receptionist — Cloud APIs",
    description="Multilingual voice ordering assistant using OpenAI + Gemini APIs",
    version="2.0.0",
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
