# AI Voice Copilot — NLP & Voice Microservice

> Restaurant ordering assistant powered by local AI models.  
> Converts voice input → structured orders → upsell suggestions → spoken responses.

## Architecture

```
Audio Input
    ↓
Speech-to-Text (faster-whisper)
    ↓
Intent Extraction (llama3 via Ollama)
    ↓
Menu Matching (RapidFuzz)
    ↓
Upsell Suggestion (Rule engine)
    ↓
Response Generation (llama3 via Ollama)
    ↓
Text-to-Speech (edge-tts)
    ↓
Audio Output
```

Real-time pipeline events stream to admin dashboards via **WebSocket**.

## Tech Stack

| Component        | Technology       |
|-----------------|-----------------|
| API Framework    | FastAPI          |
| Speech-to-Text   | faster-whisper   |
| Local LLM        | llama3 (Ollama)  |
| Fuzzy Matching   | RapidFuzz        |
| Text-to-Speech   | edge-tts         |
| Real-time        | WebSockets       |
| Testing          | pytest           |

## Folder Structure

```
ai_service/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py             # Centralized configuration
│   ├── voice/
│   │   ├── stt.py            # Speech-to-Text (Whisper)
│   │   ├── tts.py            # Text-to-Speech (edge-tts)
│   │   └── language.py       # Language detection/config
│   ├── nlp/
│   │   ├── intent.py         # Intent extraction (llama3)
│   │   ├── response.py       # Response generation (llama3)
│   │   └── prompts.py        # LLM prompt templates
│   ├── services/
│   │   ├── menu_service.py   # Menu data (stub → PostgreSQL later)
│   │   ├── upsell_service.py # Upsell logic
│   │   ├── matching.py       # Fuzzy menu matching
│   │   └── validation.py     # Order validation & edge cases
│   ├── websocket/
│   │   └── manager.py        # WebSocket connection manager
│   └── api/
│       ├── voice_routes.py   # Voice pipeline endpoints
│       └── health_routes.py  # Health check & menu endpoints
├── tests/
│   ├── test_stt.py
│   ├── test_intent.py
│   └── test_pipeline.py
├── scripts/
│   └── demo_call.py          # Pipeline demo script
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Prerequisites

1. **Python 3.11+**
2. **Ollama** installed and running ([install guide](https://ollama.ai))
3. **FFmpeg** installed (required by faster-whisper)

## Setup

```bash
# 1. Navigate to the ai_service directory
cd ai_service

# 2. Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the llama3 model
ollama pull llama3
```

## Running the Service

```bash
cd ai_service
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the interactive API docs at: **http://localhost:8000/docs**

## API Endpoints

| Method | Endpoint              | Description                          |
|--------|-----------------------|--------------------------------------|
| GET    | `/`                   | Service info                         |
| GET    | `/health`             | Health check with component status   |
| GET    | `/menu`               | Current menu items                   |
| POST   | `/voice/transcribe`   | Audio → Text (Whisper STT)           |
| POST   | `/voice/intent`       | Text → Structured order intent       |
| POST   | `/voice/upsell`       | Items → Upsell suggestion            |
| POST   | `/voice/speak`        | Text → Audio (TTS)                   |
| POST   | `/voice/full-pipeline`| Audio → Full pipeline → Audio        |
| WS     | `/ws/admin`           | Real-time pipeline events            |

### Example: Full Pipeline

```bash
curl -X POST http://localhost:8000/voice/full-pipeline \
  -F "audio=@test_audio.wav" \
  --output response.mp3
```

### Example: Get Upsell

```bash
curl -X POST http://localhost:8000/voice/upsell \
  -H "Content-Type: application/json" \
  -d '{"items": ["Paneer Tikka", "Chicken Biryani"]}'
```

### Example: Text to Speech

```bash
curl -X POST http://localhost:8000/voice/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Welcome! Your order is ready."}' \
  --output welcome.mp3
```

## WebSocket Events

Connect to `ws://localhost:8000/ws/admin` to receive real-time events:

| Event                  | Description                    |
|------------------------|--------------------------------|
| `call_started`         | New voice call initiated       |
| `transcript_received`  | STT transcription complete     |
| `items_detected`       | Order items extracted          |
| `upsell_suggested`     | Upsell recommendation made     |
| `response_generated`   | AI response text created       |
| `pipeline_complete`    | Full pipeline finished         |
| `pipeline_error`       | Error in pipeline              |

## Running Tests

```bash
cd ai_service
pytest -v
```

Tests are organized into:
- **test_stt.py** — Speech-to-Text module tests
- **test_intent.py** — Intent extraction, fuzzy matching, upsell tests
- **test_pipeline.py** — API endpoint and integration tests

> Tests that require Ollama or Whisper models will auto-skip if unavailable.

## Running the Demo

```bash
cd ai_service
python -m scripts.demo_call
```

This runs through each pipeline step and prints results to the console.

## Database Integration (Future)

The service uses **stub functions** in `app/services/menu_service.py`.  
When PostgreSQL is ready, replace the stubs with actual queries:

```python
# Before (stub):
def get_menu_items() -> list[str]:
    return ["Paneer Tikka", "Chicken Biryani", ...]

# After (PostgreSQL):
async def get_menu_items(db: AsyncSession) -> list[str]:
    result = await db.execute(select(MenuItem.name).where(MenuItem.available == True))
    return result.scalars().all()
```

## Environment Variables

| Variable         | Default                   | Description                |
|-----------------|---------------------------|----------------------------|
| `DEBUG`          | `true`                    | Enable debug logging       |
| `HOST`           | `0.0.0.0`                | Server bind host           |
| `PORT`           | `8000`                    | Server bind port           |
| `OLLAMA_BASE_URL`| `http://localhost:11434`  | Ollama API URL             |
| `OLLAMA_MODEL`   | `llama3`                  | LLM model name             |
| `WHISPER_MODEL`  | `base`                    | Whisper model size         |
| `WHISPER_DEVICE` | `cpu`                     | Whisper compute device     |
| `TTS_VOICE`      | `en-US-JennyNeural`      | TTS voice identifier       |

## Performance

Target: **< 2 seconds** end-to-end latency for the full pipeline.

Optimization strategies:
- Whisper model pre-loaded at startup
- VAD filtering to skip silence
- Compact LLM prompts
- Streaming TTS audio generation
