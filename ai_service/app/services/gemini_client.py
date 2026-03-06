"""
Shared Google Gemini client singleton.

Provides a single `google.genai.Client` instance used for
STT, LLM intent/response, conversation, and TTS.
"""

from google import genai
from app.config import settings

# Singleton client — reused everywhere
client = genai.Client(api_key=settings.gemini.api_key)
