"""
Order validation module.

Enforces business rules on extracted orders AFTER LLM parsing.
The backend validates — not the LLM.

Handles:
- Items not found in menu
- Invalid/unsupported modifications
- Ambiguous item names
- Empty orders
- Quantity parsing & limits
"""

import logging
from typing import Optional

from app.services.menu_service import get_menu_items, get_menu_item_by_name
from app.services.matching import match_item

logger = logging.getLogger(__name__)

# Allowed modifications (whitelist)
VALID_MODIFICATIONS = {
    "extra spicy", "less spicy", "no spice", "mild",
    "no onions", "extra onions",
    "no cheese", "extra cheese",
    "no ice", "extra ice",
    "half portion", "double portion",
    "no sugar", "less sugar", "extra sugar",
    "extra gravy", "dry",
    "packed", "takeaway", "dine in",
}

MAX_QUANTITY_PER_ITEM = 20
MIN_QUANTITY_PER_ITEM = 1


def validate_order(intent_result: dict) -> dict:
    """
    Validate and sanitize an extracted order intent.

    Applies business rules that the LLM should not be responsible for:
    - Verifies items exist in the menu (fuzzy match if needed)
    - Validates quantities are within limits
    - Filters invalid modifications
    - Flags ambiguous or unrecognized items

    Args:
        intent_result: Raw intent dict from LLM extraction.

    Returns:
        dict: Validated intent with added fields:
            - "validated_items": list of validated items
            - "warnings": list of warning messages
            - "rejected_items": items that couldn't be matched
            - "is_valid": bool indicating if at least one item is valid
    """
    items = intent_result.get("items", [])
    menu_items = get_menu_items()

    validated_items = []
    rejected_items = []
    warnings = []

    # Edge case: empty order
    if not items and intent_result.get("intent_type") == "order":
        warnings.append("No items detected in order. Please specify what you'd like.")
        return {
            **intent_result,
            "validated_items": [],
            "rejected_items": [],
            "warnings": warnings,
            "is_valid": False,
        }

    for item in items:
        item_name = item.get("name", "").strip()
        quantity = item.get("quantity", 1)
        modifications = item.get("modifications", [])

        # --- Validate item name ---
        if not item_name:
            rejected_items.append({"original": item, "reason": "Empty item name"})
            continue

        # Check exact match first
        menu_match = get_menu_item_by_name(item_name)

        if menu_match is None:
            # Try fuzzy matching
            fuzzy_result = match_item(item_name, menu_items, threshold=65)
            if fuzzy_result and fuzzy_result["matched_item"]:
                if fuzzy_result["confidence"] >= 85:
                    # High confidence — auto-correct
                    item_name = fuzzy_result["matched_item"]
                    menu_match = get_menu_item_by_name(item_name)
                    logger.info("Auto-corrected '%s' → '%s'", item.get("name"), item_name)
                elif fuzzy_result["confidence"] >= 65:
                    # Medium confidence — accept but warn
                    item_name = fuzzy_result["matched_item"]
                    menu_match = get_menu_item_by_name(item_name)
                    warnings.append(
                        f"Did you mean '{item_name}'? "
                        f"(heard '{item.get('name')}', confidence: {fuzzy_result['confidence']}%)"
                    )
                else:
                    rejected_items.append({
                        "original": item,
                        "reason": f"'{item.get('name')}' not found in menu",
                    })
                    warnings.append(f"'{item.get('name')}' is not on our menu.")
                    continue
            else:
                rejected_items.append({
                    "original": item,
                    "reason": f"'{item.get('name')}' not found in menu",
                })
                warnings.append(f"'{item.get('name')}' is not on our menu.")
                continue

        # --- Validate quantity ---
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 1
            warnings.append(f"Invalid quantity for {item_name}, defaulting to 1.")

        if quantity < MIN_QUANTITY_PER_ITEM:
            quantity = MIN_QUANTITY_PER_ITEM
            warnings.append(f"Quantity for {item_name} adjusted to minimum ({MIN_QUANTITY_PER_ITEM}).")
        elif quantity > MAX_QUANTITY_PER_ITEM:
            warnings.append(
                f"Quantity {quantity} for {item_name} exceeds maximum ({MAX_QUANTITY_PER_ITEM}). "
                f"Capped at {MAX_QUANTITY_PER_ITEM}."
            )
            quantity = MAX_QUANTITY_PER_ITEM

        # --- Validate modifications ---
        valid_mods = []
        for mod in modifications:
            mod_lower = mod.strip().lower()
            if mod_lower in VALID_MODIFICATIONS:
                valid_mods.append(mod.strip())
            else:
                warnings.append(f"Modification '{mod}' is not supported for {item_name}, ignoring.")

        # --- Build validated item ---
        validated_items.append({
            "name": item_name,
            "quantity": quantity,
            "modifications": valid_mods,
            "price": menu_match["price"] if menu_match else None,
            "category": menu_match["category"] if menu_match else None,
        })

    is_valid = len(validated_items) > 0 or intent_result.get("intent_type") != "order"

    result = {
        **intent_result,
        "validated_items": validated_items,
        "rejected_items": rejected_items,
        "warnings": warnings,
        "is_valid": is_valid,
    }

    logger.info(
        "Validation: %d valid, %d rejected, %d warnings",
        len(validated_items), len(rejected_items), len(warnings),
    )

    return result
