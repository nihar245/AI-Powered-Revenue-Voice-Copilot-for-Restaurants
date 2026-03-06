"""
Shared Deepgram client singleton.

Provides a single ``DeepgramClient`` instance used for STT and TTS.
"""

from deepgram import DeepgramClient
from app.config import settings

# Singleton client — reused everywhere
client = DeepgramClient(api_key=settings.deepgram.api_key)
