"""
Menu Resolver — maps raw spoken entity text to real menu items.

Pipeline position:
    NLU (raw entity text)  →  menu_resolver  →  order_builder (structured cart item)

Strategy (in order of speed):
  1. Exact name match (case-insensitive)          — O(n), ~0ms
  2. Partial / contains match                     — O(n), ~0ms
  3. Semantic embedding similarity (threshold 0.50) — ~50ms (cached embeddings)
"""

from __future__ import annotations

from difflib import SequenceMatcher

from services.nlu.intent_classifier import find_best_menu_match_async

# Minimum similarity scores
_EXACT_THRESHOLD   = 1.0
_PARTIAL_THRESHOLD = 0.6   # difflib ratio
_SEMANTIC_THRESHOLD = 0.50  # cosine similarity


def _normalise(text: str) -> str:
    return text.lower().strip()


def _difflib_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _exact_or_partial_match(query: str, menu_items: list[dict]) -> dict | None:
    """Fast string-based matching — no model needed."""
    q = _normalise(query)

    # Pass 1: exact match
    for item in menu_items:
        if _normalise(item["name"]) == q:
            return item

    # Pass 2: query is contained in item name or vice versa
    for item in menu_items:
        name = _normalise(item["name"])
        if q in name or name in q:
            return item

    # Pass 3: difflib fuzzy ratio
    best_item  = None
    best_score = 0.0
    for item in menu_items:
        score = _difflib_ratio(q, _normalise(item["name"]))
        if score > best_score:
            best_score = score
            best_item  = item

    if best_score >= _PARTIAL_THRESHOLD:
        return best_item

    return None


async def resolve_menu_item(
    query: str,
    menu_items: list[dict],
) -> tuple[dict | None, bool]:
    """
    Resolves a spoken entity string to a menu item dict.

    Args:
        query:       Raw spoken text, e.g. "paneer tikka pizza"
        menu_items:  List of active menu item dicts from fetch_active_menu()

    Returns:
        (menu_item_dict, needs_clarification)
        - menu_item_dict contains: product_id, name, price, tax, category_name, ...
        - needs_clarification=True when no confident match is found
    """
    if not menu_items:
        return None, True

    # Fast path: string matching
    match = _exact_or_partial_match(query, menu_items)
    if match:
        return match, False

    # Slow path: semantic similarity
    names = [item["name"] for item in menu_items]
    idx, score = await find_best_menu_match_async(query, names)

    if score >= _SEMANTIC_THRESHOLD:
        return menu_items[idx], False

    return None, True


async def resolve_multiple(
    entities: list[dict],
    menu_items: list[dict],
) -> list[tuple[dict, int, bool]]:
    """
    Resolves a list of NLU entities to (menu_item, quantity, needs_clarification) tuples.

    Args:
        entities:   List of dicts with keys: raw_query, quantity
        menu_items: Active menu items from DB

    Returns:
        List of (menu_item_or_None, quantity, needs_clarification)
    """
    results = []
    for entity in entities:
        raw_query = entity.get("raw_query", "")
        quantity  = entity.get("quantity", 1)
        item, needs_clarification = await resolve_menu_item(raw_query, menu_items)
        results.append((item, quantity, needs_clarification))
    return results
