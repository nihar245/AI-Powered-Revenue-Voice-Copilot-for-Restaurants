"""
Fuzzy matching module using RapidFuzz.

Maps spoken/transcribed item names to actual menu items,
handling mispronunciations, accents, partial matches,
and multilingual aliases (Hindi/Hinglish/Gujarati → English).

Optimized for large menus via:
  - Pre-built search index with aliases
  - LRU caching of recent lookups
  - Category-scoped matching
"""

import logging
from typing import Optional
from functools import lru_cache

from rapidfuzz import fuzz, process

from app.config import settings
from app.services.menu_service import get_menu_items, get_menu_items_detailed

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multilingual alias map: spoken name → canonical English menu name
# Covers Hindi, Hinglish, and Gujarati common equivalents.
# ---------------------------------------------------------------------------
_ITEM_ALIASES: dict[str, str] = {
    # Hindi / Hinglish aliases
    "paneer tikka": "Paneer Tikka",
    "tikka paneer": "Paneer Tikka",
    "chicken biryani": "Chicken Biryani",
    "murgh biryani": "Chicken Biryani",
    "biryani": "Chicken Biryani",
    "butter naan": "Butter Naan",
    "makhan naan": "Butter Naan",
    "naan": "Butter Naan",
    "dal makhani": "Dal Makhani",
    "daal makhani": "Dal Makhani",
    "daal": "Dal Makhani",
    "raita": "Raita",
    "gulab jamun": "Gulab Jamun",
    "meetha": "Gulab Jamun",
    "mango lassi": "Mango Lassi",
    "lassi": "Mango Lassi",
    "aam lassi": "Mango Lassi",
    "sweet lassi": "Sweet Lassi",
    "garlic naan": "Garlic Naan",
    "lehsun naan": "Garlic Naan",
    "roti": "Tandoori Roti",
    "chapati": "Tandoori Roti",
    "phulka": "Tandoori Roti",
    "fulka": "Tandoori Roti",
    "tandoori roti": "Tandoori Roti",
    "paratha": "Paratha",
    # Mains
    "butter chicken": "Butter Chicken",
    "murgh makhani": "Butter Chicken",
    "shahi paneer": "Shahi Paneer",
    "palak paneer": "Palak Paneer",
    "saag paneer": "Palak Paneer",
    "mutton rogan josh": "Mutton Rogan Josh",
    "rogan josh": "Mutton Rogan Josh",
    "chicken kadai": "Chicken Kadai",
    "kadai chicken": "Chicken Kadai",
    "rajma": "Rajma Masala",
    "rajma masala": "Rajma Masala",
    "chana masala": "Chana Masala",
    "chole": "Chana Masala",
    # Starters
    "dal shorba": "Dal Shorba",
    "shorba": "Dal Shorba",
    "seekh kebab": "Seekh Kebab",
    "seekh": "Seekh Kebab",
    "shammi kebab": "Veg Shammi Kebab",
    "chicken 65": "Chicken 65",
    # Rice
    "veg biryani": "Veg Biryani",
    "mutton biryani": "Mutton Biryani",
    "jeera rice": "Jeera Rice",
    "zeera rice": "Jeera Rice",
    # Drinks
    "masala chai": "Masala Chai",
    "chai": "Masala Chai",
    "tea": "Masala Chai",
    "lime soda": "Fresh Lime Soda",
    "nimbu pani": "Fresh Lime Soda",
    # Desserts
    "rasgulla": "Rasgulla",
    "kheer": "Kheer",
    "gajar halwa": "Gajar Halwa",
    "halwa": "Gajar Halwa",
    # Gujarati aliases
    "rotli": "Tandoori Roti",
    "rotla": "Tandoori Roti",
    "shaak": "Dal Makhani",
}


# ---------------------------------------------------------------------------
# Cached index — rebuilt only when menu changes
# ---------------------------------------------------------------------------
_cached_search_list: list[str] | None = None
_cached_alias_map: dict[str, str] | None = None


def _build_search_index() -> tuple[list[str], dict[str, str]]:
    """
    Build a combined search index: real menu names + aliases.
    Each alias maps back to the canonical menu name.
    Cached at module level.
    """
    global _cached_search_list, _cached_alias_map
    if _cached_search_list is not None:
        return _cached_search_list, _cached_alias_map

    menu_names = get_menu_items()

    # Start with real menu names (identity mapping)
    alias_map: dict[str, str] = {}
    for name in menu_names:
        alias_map[name.lower()] = name

    # Add multilingual aliases (only if target exists in menu)
    menu_set = set(menu_names)
    for alias, canonical in _ITEM_ALIASES.items():
        if canonical in menu_set:
            alias_map[alias.lower()] = canonical

    search_list = list(alias_map.keys())

    _cached_search_list = search_list
    _cached_alias_map = alias_map

    logger.info("Search index built: %d entries (%d menu + %d aliases)",
                len(search_list), len(menu_names), len(search_list) - len(menu_names))

    return search_list, alias_map


def invalidate_search_cache() -> None:
    """Call this when the menu changes to rebuild the search index."""
    global _cached_search_list, _cached_alias_map
    _cached_search_list = None
    _cached_alias_map = None
    match_item_cached.cache_clear()


# ---------------------------------------------------------------------------
# LRU-cached match for repeated lookups (e.g., "biryani" asked 100 times)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=512)
def match_item_cached(spoken_item: str, threshold: int) -> Optional[tuple]:
    """
    Cached version of fuzzy match. Returns (canonical_name, score) or None.
    """
    search_list, alias_map = _build_search_index()

    result = process.extractOne(
        spoken_item.strip().lower(),
        search_list,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )

    if result is None:
        return None

    matched_key, score, _index = result
    canonical = alias_map[matched_key]
    return (canonical, int(score))


def match_item(
    spoken_item: str,
    menu_items: Optional[list[str]] = None,
    threshold: Optional[int] = None,
) -> Optional[dict]:
    """
    Match a single spoken item name to the closest menu item.

    Uses token_sort_ratio for robustness against word order differences
    (e.g., "tikka paneer" vs "paneer tikka").

    Leverages LRU-cached alias-aware index for speed on large menus.

    Args:
        spoken_item: The item name as spoken/transcribed by the customer.
        menu_items: Optional list of valid menu item names (ignored when
                    using the cached index path; kept for backward compat).
        threshold: Minimum confidence score (0-100) to accept a match.

    Returns:
        Optional[dict]: {
            "matched_item": str,   # Best matching menu item
            "confidence": int,     # Match score (0-100)
            "spoken_as": str       # Original spoken text
        } or None if no match meets threshold.
    """
    if threshold is None:
        threshold = settings.fuzzy.score_threshold

    if not spoken_item or not spoken_item.strip():
        return None

    # Fast path: use cached alias-aware index
    cached = match_item_cached(spoken_item.strip(), threshold)

    if cached is None:
        logger.info("No match for '%s' above threshold %d", spoken_item, threshold)
        return None

    matched_name, score = cached

    logger.info(
        "Matched '%s' → '%s' (confidence: %d%%)",
        spoken_item, matched_name, score,
    )

    return {
        "matched_item": matched_name,
        "confidence": score,
        "spoken_as": spoken_item,
    }


def match_items(
    spoken_items: list[str],
    menu_items: Optional[list[str]] = None,
    threshold: Optional[int] = None,
) -> list[dict]:
    """
    Match multiple spoken item names to menu items.

    Args:
        spoken_items: List of item names as spoken by the customer.
        menu_items: Optional list of valid menu item names.
        threshold: Minimum confidence score (0-100).

    Returns:
        list[dict]: List of match results. Unmatched items are included
                    with matched_item=None.
    """
    results = []
    for spoken in spoken_items:
        match = match_item(spoken, menu_items, threshold)
        if match:
            results.append(match)
        else:
            results.append({
                "matched_item": None,
                "confidence": 0,
                "spoken_as": spoken,
            })

    return results


def find_top_matches(
    spoken_item: str,
    menu_items: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Get top N matches for a spoken item (useful for disambiguation).
    Uses the alias-expanded search index.

    Args:
        spoken_item: The spoken item name.
        menu_items: Optional list of valid menu items.
        limit: Number of top matches to return.

    Returns:
        list[dict]: Top matches sorted by confidence descending.
    """
    if limit is None:
        limit = settings.fuzzy.limit

    search_list, alias_map = _build_search_index()

    results = process.extract(
        spoken_item.strip().lower(),
        search_list,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
    )

    return [
        {
            "matched_item": alias_map[key],
            "confidence": int(score),
            "spoken_as": spoken_item,
        }
        for key, score, _index in results
    ]
