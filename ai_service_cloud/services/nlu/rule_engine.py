import re

from models.schemas import Intent
from services.nlu.keyword_maps import (
    ADD_KEYWORDS,
    CANCEL_KEYWORDS,
    CONFIRM_KEYWORDS,
    ENQUIRE_PRICE_KEYWORDS,
    GREET_KEYWORDS,
    NUMBER_WORDS,
    REMOVE_KEYWORDS,
    VIEW_CART_KEYWORDS,
    VIEW_MENU_KEYWORDS,
)

# Words to strip before passing to the menu resolver so it gets a clean item name
_STRIP_PATTERN = re.compile(
    r'\b(add|remove|give\s+me|bring|want|get\s+me|order|i\'?d\s+like|'
    r'i\s+would\s+like|can\s+i\s+have|i\'?ll\s+have|i\'?ll\s+take|'
    r'chahiye|dena|lena|lao|laao|hatao|wapas\s+karo|joie|apo|lavo|'
    r'please|also|and|me|a|an|the|my|i|from|in|to|one|two|three|four|five|'
    r'ek|do|teen|char|paanch|be|tran|panch)\b',
    re.IGNORECASE,
)

# Connectors that separate multiple items in one utterance
_CONNECTOR_PATTERN = re.compile(
    r'\b(?:and|also|aur|aur\s+bhi|ane|tatha|pan)\b',
    re.IGNORECASE,
)


def _any_keyword(text: str, keyword_dict: dict) -> bool:
    """
    Returns True if any keyword from the dict appears in text.
    Uses word-boundary matching to prevent short keywords (e.g. 'na', 'ha')
    from falsely matching substrings inside longer words (e.g. 'naan', 'that').
    """
    text_lower = text.lower()
    for keywords in keyword_dict.values():
        for kw in keywords:
            pattern = r'\b' + re.escape(kw.lower()) + r'\b'
            if re.search(pattern, text_lower):
                return True
    return False


def _extract_quantity(text: str) -> int:
    """Extracts the first numeral or number-word found in text."""
    # Digits first
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return min(int(match.group(1)), 20)  # cap at 20 for safety

    # Number words
    text_lower = text.lower()
    for word, num in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            return num

    return 1  # default: one item


def _extract_items(text: str) -> list[dict]:
    """
    Returns a list of entity dicts, one per item.
    Splits on connectors (and/aur/ane) so multi-item utterances like
    '2 paneer tikka and one masala chai' produce two separate entities.
    """
    parts = [p.strip() for p in _CONNECTOR_PATTERN.split(text) if p.strip()]
    items = []
    for part in parts:
        qty     = _extract_quantity(part)
        cleaned = re.sub(r'\b\d+\b', '', _STRIP_PATTERN.sub('', part)).strip()
        raw_query = cleaned if len(cleaned) > 2 else part.strip()
        if raw_query:
            items.append({"raw_query": raw_query, "quantity": qty})
    return items if items else [{"raw_query": text, "quantity": 1}]


def classify_intent(text: str, language: str) -> tuple[Intent, list[dict]]:
    """
    Fast rule-based intent classifier.

    Returns:
        (Intent, entities)
        entities is non-empty only for ADD_ITEM / REMOVE_ITEM.
    """
    if _any_keyword(text, GREET_KEYWORDS):
        return Intent.GREETING, []

    if _any_keyword(text, CONFIRM_KEYWORDS):
        return Intent.CONFIRM_ORDER, []

    if _any_keyword(text, CANCEL_KEYWORDS):
        return Intent.CANCEL_ORDER, []

    if _any_keyword(text, VIEW_MENU_KEYWORDS):
        return Intent.VIEW_MENU, []

    if _any_keyword(text, VIEW_CART_KEYWORDS):
        return Intent.VIEW_CART, []

    if _any_keyword(text, ENQUIRE_PRICE_KEYWORDS):
        return Intent.ENQUIRE_PRICE, []

    # Check remove before add (prevents false add triggers)
    if _any_keyword(text, REMOVE_KEYWORDS):
        return Intent.REMOVE_ITEM, _extract_items(text)

    if _any_keyword(text, ADD_KEYWORDS):
        return Intent.ADD_ITEM, _extract_items(text)

    return Intent.UNKNOWN, []
