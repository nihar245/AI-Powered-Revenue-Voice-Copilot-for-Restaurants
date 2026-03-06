import re

# Unicode ranges
_DEVANAGARI = r"\u0900-\u097F"   # Hindi
_GUJARATI   = r"\u0A80-\u0AFF"   # Gujarati

_SUPPORTED = {"en", "hi", "gu"}


def normalise(transcript: str, whisper_lang: str) -> tuple[str, str]:
    """
    Cleans the raw Whisper transcript and resolves the language code.

    Uses Whisper's own language detection directly — avoids running a
    separate langdetect model, saving ~50ms per request.

    Args:
        transcript:   Raw text from Whisper.
        whisper_lang: Language code Whisper detected (e.g. "en", "hi", "gu").

    Returns:
        (cleaned_text, language_code)
        language_code is one of: "en" | "hi" | "gu"
    """
    text = transcript.strip()

    # Strip characters outside printable ASCII + Devanagari + Gujarati ranges
    text = re.sub(
        rf"[^\w\s{_DEVANAGARI}{_GUJARATI}.,?!'\"()-]",
        " ",
        text,
        flags=re.UNICODE,
    )
    text = re.sub(r"\s+", " ", text).strip()

    # Trust Whisper's built-in language detection
    # Whisper already runs language detection as part of transcription at no
    # extra cost — no need for a second pass with langdetect.
    language = whisper_lang if whisper_lang in _SUPPORTED else "en"

    return text, language
