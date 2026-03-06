# ─── Curated upsell pairs (item name substring → suggestions) ─────────────────
_UPSELL_PAIRS: dict[str, list[str]] = {
    # North Indian mains → breads / rice
    "paneer butter masala": ["Butter Naan", "Jeera Rice", "Dal Makhani"],
    "dal makhani":          ["Garlic Naan", "Jeera Rice"],
    "palak paneer":         ["Butter Naan", "Jeera Rice"],
    "chole bhature":        ["Lassi", "Gulab Jamun"],
    "veg biryani":          ["Raita", "Gulab Jamun"],
    "rajma chawal":         ["Papad", "Lassi"],

    # South Indian
    "masala dosa":          ["Filter Coffee", "Medu Vada (2 pcs)"],
    "plain dosa":           ["Filter Coffee", "Idli Sambar (3 pcs)"],
    "idli sambar":          ["Filter Coffee", "Medu Vada (2 pcs)"],
    "uttapam":              ["Filter Coffee"],

    # Italian
    "margherita pizza":     ["Cheese Garlic Bread", "Cold Coffee"],
    "farmhouse pizza":      ["Cheese Garlic Bread", "Virgin Mojito"],
    "pasta alfredo":        ["Bruschetta", "Virgin Mojito"],
    "pasta arrabiata":      ["Cheese Garlic Bread"],

    # Mexican
    "veg burrito":          ["Nachos Supreme", "Virgin Mojito"],
    "quesadilla":           ["Nachos Supreme"],

    # Chinese
    "veg fried rice":       ["Veg Manchurian", "Spring Rolls (3 pcs)"],
    "veg noodles":          ["Veg Manchurian"],
}

_UPSELL_TEMPLATES = {
    "en": "Would you also like to try {item}?",
    "hi": "Kya aap {item} bhi try karna chahenge?",
    "gu": "Shya tame {item} pan try karva mango cho?",
}


def get_upsell_hint(cart: list[dict], language: str) -> str:
    """
    Returns a natural language upsell suggestion or an empty string.
    Only suggests items not already in the cart.
    """
    if not cart:
        return ""

    cart_names_lower = {item["name"].lower() for item in cart}

    for cart_item in cart:
        name_lower = cart_item["name"].lower()
        for key, suggestions in _UPSELL_PAIRS.items():
            if key in name_lower:
                available = [s for s in suggestions if s.lower() not in cart_names_lower]
                if available:
                    template = _UPSELL_TEMPLATES.get(language, _UPSELL_TEMPLATES["en"])
                    return template.format(item=available[0])

    return ""
