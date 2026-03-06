"""
Upsell service module.

Determines the best upsell/cross-sell suggestion based on the
customer's current order, combo rules, and menu availability.
"""

import logging
from typing import Optional

from app.services.menu_service import get_menu_items, get_combo_rules
from app.services.matching import match_item

logger = logging.getLogger(__name__)


def suggest_upsell(
    ordered_items: list[str],
    menu_items: Optional[list[str]] = None,
    combo_rules: Optional[dict[str, str]] = None,
) -> dict:
    """
    Suggest an upsell item based on current order.

    Strategy:
    1. Check combo rules first (highest priority).
    2. If no combo rule applies, suggest a beverage if none ordered.
    3. If no beverage suggestion, suggest a dessert.
    4. Avoid suggesting items already in the order.

    Args:
        ordered_items: List of item names the customer has ordered.
        menu_items: Optional full menu list.
        combo_rules: Optional combo pairing rules.

    Returns:
        dict: {
            "suggestion": str | None,   # Suggested item name
            "reason": str,              # Why this was suggested
            "source": str               # "combo_rule" | "category" | "none"
        }
    """
    if menu_items is None:
        menu_items = get_menu_items()

    if combo_rules is None:
        combo_rules = get_combo_rules()

    ordered_lower = {item.lower() for item in ordered_items}

    # Strategy 1: Check combo rules
    for ordered in ordered_items:
        if ordered in combo_rules:
            suggestion = combo_rules[ordered]
            if suggestion.lower() not in ordered_lower:
                logger.info(
                    "Upsell (combo rule): '%s' → '%s'",
                    ordered, suggestion,
                )
                return {
                    "suggestion": suggestion,
                    "reason": f"{suggestion} pairs great with {ordered}",
                    "source": "combo_rule",
                }

    # Strategy 2: Suggest a beverage if none ordered
    from app.services.menu_service import get_menu_items_detailed
    detailed_items = get_menu_items_detailed()

    ordered_categories = set()
    for item in detailed_items:
        if item["name"].lower() in ordered_lower:
            ordered_categories.add(item["category"])

    if "beverages" not in ordered_categories:
        beverages = [
            item["name"] for item in detailed_items
            if item["category"] == "beverages" and item["name"].lower() not in ordered_lower
        ]
        if beverages:
            suggestion = beverages[0]
            logger.info("Upsell (category): suggesting beverage '%s'", suggestion)
            return {
                "suggestion": suggestion,
                "reason": f"How about a {suggestion} to go with your meal?",
                "source": "category",
            }

    # Strategy 3: Suggest a dessert if none ordered
    if "desserts" not in ordered_categories:
        desserts = [
            item["name"] for item in detailed_items
            if item["category"] == "desserts" and item["name"].lower() not in ordered_lower
        ]
        if desserts:
            suggestion = desserts[0]
            logger.info("Upsell (category): suggesting dessert '%s'", suggestion)
            return {
                "suggestion": suggestion,
                "reason": f"Would you like to finish with a {suggestion}?",
                "source": "category",
            }

    logger.info("No upsell suggestion available")
    return {
        "suggestion": None,
        "reason": "No suitable upsell found",
        "source": "none",
    }
