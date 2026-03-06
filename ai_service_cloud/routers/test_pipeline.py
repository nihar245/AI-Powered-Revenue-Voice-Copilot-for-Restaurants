"""
Diagnostic / test endpoints — zero database dependency.
Cloud version: uses Gemini 2.5 Flash Native Audio logic.

Endpoints
---------
GET  /test/ping                 → API alive check
GET  /test/services             → Status of every service
POST /test/pipeline             → Audio → Gemini 2.5 Unified Pipe → TTS
GET  /test/voicelab             → VoiceLab HTML UI
"""

import os
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from services.gemini_pipeline import check_gemini_health, process_audio_and_reason, generate_speech_b64
from services.dialogue.session_store import update_session, get_session
from services.prompts import build_order_prompt

router = APIRouter(prefix="/test", tags=["diagnostics"])

# ─── Dummy menu (no DB) ────────────────────────────────────────────────────────
DUMMY_MENU = [
    {"product_id": "1",  "name": "Paneer Tikka",  "price": 250.0, "tax": 5.0, "category": "Starters"},
    {"product_id": "2",  "name": "Masala Chai",    "price": 50.0,  "tax": 0.0, "category": "Beverages"},
    {"product_id": "3",  "name": "Veg Biryani",    "price": 180.0, "tax": 5.0, "category": "Main Course"},
    {"product_id": "10", "name": "Butter Chicken", "price": 280.0, "tax": 5.0, "category": "Main Course"},
]

@router.get("/ping")
async def ping():
    return {"status": "ok", "message": "AI Voice Receptionist (Cloud API) is running"}

@router.get("/services")
async def service_status():
    gemini_ready = check_gemini_health()
    from config import settings as _s
    return {
        "gemini":   {"reachable": gemini_ready, "model":  f"{_s.gemini_audio_model} (Native Audio)"},
        "database": {"note": "skipped in test endpoints — uses dummy menu"},
    }

@router.post("/pipeline")
async def test_pipeline(
    audio: UploadFile = File(..., description="Audio file from microphone"),
):
    """Full end-to-end pipeline test using the unified Gemini 2.5 Flash API."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")

    menu_summary = "\n".join(f"{i['name']} - ₹{i['price']}" for i in DUMMY_MENU)
    context = build_order_prompt(
        language="en",
        cart=[],
        last_utterance="",
        intent="",
        dialogue_state="taking_order",
        menu_context=menu_summary,
        upsell_hint="",
    )

    t0 = time.perf_counter()
    gemini_response = await process_audio_and_reason(audio_bytes, context=context)
    gemini_ms = round((time.perf_counter() - t0) * 1000)

    response_text = gemini_response.get("response_text", "Sorry, I could not understand.")
    tts_text = " ".join(response_text.replace("₹", " rupees ").split())

    t0 = time.perf_counter()
    audio_b64, audio_mime = await generate_speech_b64(tts_text)
    tts_ms = round((time.perf_counter() - t0) * 1000)

    return {
        "gemini_json": gemini_response,
        "audio_base64": audio_b64,
        "audio_mime": audio_mime,
        "timings_ms": {"gemini_api_ms": gemini_ms, "tts_ms": tts_ms},
    }

@router.get("/voicelab", response_class=HTMLResponse)
async def voicelab_ui():
    html_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "static", "voicelab.html")
    )
    if not os.path.exists(html_path):
        raise HTTPException(404, "voicelab.html not found in static/")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
