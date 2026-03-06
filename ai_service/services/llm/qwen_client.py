"""
LLM client — Ollama HTTP API (fully local, no external APIs).
Model is configured via OLLAMA_MODEL in .env — default: phi4-mini
"""
import httpx

from config import settings

# ── Backward-compat: load_model() is a no-op when using Ollama ───────────────
def load_model() -> None:
    """No-op — Ollama manages model loading. Called from main.py lifespan."""
    print(f"[LLM] Using Ollama model: {settings.ollama_model}  (run 'ollama pull {settings.ollama_model}' if not downloaded)")


async def generate(
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 35,
) -> str:
    """Sends a prompt to Ollama /api/generate and returns the response text."""
    payload = {
        "model":  settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature":   temperature,
            "num_predict":   max_tokens,
            "num_ctx":       512,
            "stop": ["\n\n", "Customer:", "System:", "User:"],
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
    return response.json().get("response", "").strip()


async def warmup_ollama() -> None:
    """Pre-loads model weights so the first real request has no cold-start delay."""
    try:
        await generate("hi", max_tokens=3)
        print("[LLM] Ollama warm-up complete.")
    except Exception as e:
        print(f"[LLM] Ollama warm-up skipped (not reachable yet): {e}")


async def check_ollama_health() -> bool:
    """Returns True if Ollama is running and the configured model is pulled."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            return any(settings.ollama_model.split(":")[0] in m for m in models)
    except Exception:
        return False
