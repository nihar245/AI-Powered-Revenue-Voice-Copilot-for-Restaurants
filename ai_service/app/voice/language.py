"""
Language detection and translation utilities.

Provides helpers for multilingual support in the voice pipeline.
Supports: English, Hindi, Hinglish (Hindi+English mix), and Gujarati.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported languages — TTS voice mapping
# ---------------------------------------------------------------------------
SUPPORTED_LANGUAGES = {
    "en": {
        "name": "English",
        "whisper_code": "en",
        "tts_voice": "Kore",
    },
    "hi": {
        "name": "Hindi",
        "whisper_code": "hi",
        "tts_voice": "Kore",
    },
    "hinglish": {
        "name": "Hinglish",
        "whisper_code": "hi",
        "tts_voice": "Kore",
    },
    "gu": {
        "name": "Gujarati",
        "whisper_code": "gu",
        "tts_voice": "Kore",
    },
}

# ---------------------------------------------------------------------------
# Hinglish keyword list — common Hindi words written in Latin script
# that signal the customer is speaking Hinglish (mix of Hindi + English).
# Keep lowercase.
# ---------------------------------------------------------------------------
_HINGLISH_KEYWORDS: set[str] = {
    # basics
    "mujhe", "muje", "mereko", "haan", "nahi", "nhi", "aur",
    "bhai", "yaar", "dedo", "dena", "chahiye", "chaiye",
    "kitna", "kitne", "kya", "hai", "hain", "ek", "do", "teen",
    "char", "paanch", "chhe", "saat", "aath", "nau", "das",
    # ordering context
    "khana", "peena", "plate", "glass", "roti", "dal", "sabzi",
    "paneer", "chai", "lassi", "thali", "biryani", "naan",
    "daal", "chawal", "paani", "pani", "meetha", "jeera",
    "zyada", "kam", "thoda", "bahut", "accha", "theek",
    "bhi", "wala", "wali", "karke", "laga", "lagao",
    # polite
    "shukriya", "dhanyavaad", "bhaiya", "didi",
    "ji", "abhi", "bas", "bilkul", "chalo",
}

# ---------------------------------------------------------------------------
# Gujarati keyword list — common Gujarati words in Latin script
# ---------------------------------------------------------------------------
_GUJARATI_KEYWORDS: set[str] = {
    "mane", "mare", "tran",
    "apo", "apjo", "nathi", "chhe", "haa",
    "khavu", "pivu", "rotli", "shaak",
    "shu", "ketla", "kemcho", "majama", "tamne",
    "aapjo", "lavo", "jovo", "biju",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_language_config(language_code: str) -> dict:
    """
    Get language-specific configuration.

    Args:
        language_code: ISO language code ('en', 'hi', 'hinglish', 'gu').

    Returns:
        dict: Language config with whisper_code and tts_voice.
    """
    config = SUPPORTED_LANGUAGES.get(language_code)
    if config is None:
        logger.warning("Unsupported language '%s', falling back to English.", language_code)
        config = SUPPORTED_LANGUAGES["en"]
    return config


def detect_language_from_text(text: str) -> str:
    """
    Detect language from text using script analysis + keyword heuristics.

    Detection order:
      1. Gujarati script (Unicode block 0A80-0AFF)
      2. Devanagari script (Unicode block 0900-097F) → Hindi
      3. Latin script with Hinglish keywords → Hinglish
      4. Latin script with Gujarati keywords → Gujarati
      5. Default → English

    Args:
        text: Input text.

    Returns:
        str: One of 'en', 'hi', 'hinglish', 'gu'.
    """
    if not text or not text.strip():
        return "en"

    # --- Step 1: Script-based detection (most reliable) ---
    devanagari_count = 0
    gujarati_count = 0
    latin_count = 0
    total = 0

    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if "\u0A80" <= ch <= "\u0AFF":
            gujarati_count += 1
        elif "\u0900" <= ch <= "\u097F":
            devanagari_count += 1
        elif ch.isascii() and ch.isalpha():
            latin_count += 1

    if total == 0:
        return "en"

    # If >30% Gujarati script chars → Gujarati
    if gujarati_count / total > 0.3:
        return "gu"

    # If >30% Devanagari script chars → Hindi
    if devanagari_count / total > 0.3:
        return "hi"

    # --- Step 2: Keyword-based detection (for Latin-script input) ---
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))

    hinglish_hits = words & _HINGLISH_KEYWORDS
    gujarati_hits = words & _GUJARATI_KEYWORDS

    # Need at least 2 keyword hits to avoid false positives
    if len(gujarati_hits) >= 2 and len(gujarati_hits) > len(hinglish_hits):
        return "gu"

    if len(hinglish_hits) >= 2:
        return "hinglish"

    # Single keyword + short text (≤5 words) can also trigger
    word_count = len(words)
    if len(hinglish_hits) >= 1 and word_count <= 5:
        return "hinglish"
    if len(gujarati_hits) >= 1 and word_count <= 5:
        return "gu"

    return "en"


def get_tts_voice(language_code: str) -> str:
    """
    Get the appropriate TTS voice for a language.

    Args:
        language_code: ISO language code.

    Returns:
        str: TTS voice identifier string.
    """
    config = get_language_config(language_code)
    return config["tts_voice"]


def whisper_lang_code(detected_lang: str) -> Optional[str]:
    """
    Map our internal language code to Whisper's expected code.
    Returns None for auto-detection.

    Args:
        detected_lang: Our language code.

    Returns:
        Optional[str]: Whisper language code or None.
    """
    config = SUPPORTED_LANGUAGES.get(detected_lang)
    if config:
        return config["whisper_code"]
    return None
