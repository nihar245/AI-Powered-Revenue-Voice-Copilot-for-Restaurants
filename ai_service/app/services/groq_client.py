"""
Shared Groq client singleton.

Provides a single ``Groq`` / ``AsyncGroq`` instance used for LLM
intent extraction and response generation (Llama 3.3 70B).
"""

from groq import Groq, AsyncGroq
from app.config import settings

# Synchronous client (used where needed)
client = Groq(api_key=settings.groq.api_key)

# Async client (preferred for FastAPI)
async_client = AsyncGroq(api_key=settings.groq.api_key)
