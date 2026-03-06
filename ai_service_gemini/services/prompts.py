"""
System instruction builders for Gemini Live sessions.

The system instruction is injected into every Live session so the model knows
the current menu (with modifiers), cart state, behavioural rules, and
upsell / combo hints — without any extra LLM call.
"""

from __future__ import annotations


# ─── Modifier catalogue (used both in prompt and in upsell engine) ─────────────
# When a real DB with product_variants / modifiers table is connected, this
# will be replaced by a DB query.  For now it is keyed by product name (lowercase).
MODIFIER_CATALOGUE: dict[str, dict] = {
    "masala chai":    {"size": ["small", "large"], "extras": ["extra ginger", "less sugar", "extra sweet"]},
    "mango lassi":    {"size": ["small", "large"], "extras": ["less sugar", "extra mango"]},
    "cold coffee":    {"size": ["small", "large"], "extras": ["extra shot", "less sugar", "no ice"]},
    "veg biryani":    {"spice": ["mild", "medium", "hot", "extra hot"], "extras": ["extra raita", "extra salan", "less oil"]},
    "butter chicken": {"spice": ["mild", "medium", "hot", "extra hot"], "extras": ["extra gravy", "less oil"]},
    "dal makhani":    {"spice": ["mild", "medium", "hot"],              "extras": ["extra butter", "less oil"]},
    "paneer tikka":   {"spice": ["mild", "medium", "hot"],              "extras": ["extra chutney"]},
    "garlic naan":    {"extras": ["extra butter", "without garlic"]},
    "aloo paratha":   {"extras": ["extra butter", "extra curd", "without butter"]},
    "gulab jamun":    {"extras": ["warm", "cold", "extra sugar syrup"]},
}

# ─── Combo deals catalogue ────────────────────────────────────────────────────
# Structure: list of {name, items (names), saving, description}
COMBO_DEALS = [
    {
        "name":        "Starter Combo",
        "items":       ["Paneer Tikka", "Masala Chai"],
        "saving":      20,
        "description": "Paneer Tikka + Masala Chai — save ₹20",
    },
    {
        "name":        "Biryani Meal",
        "items":       ["Veg Biryani", "Mango Lassi"],
        "saving":      25,
        "description": "Veg Biryani + Mango Lassi — save ₹25",
    },
    {
        "name":        "Butter Chicken Feast",
        "items":       ["Butter Chicken", "Garlic Naan", "Dal Makhani"],
        "saving":      40,
        "description": "Butter Chicken + Garlic Naan + Dal Makhani — save ₹40",
    },
]

# ─── Upsell map: if X is in cart, suggest Y ──────────────────────────────────
UPSELL_MAP: list[tuple[str, str]] = [
    ("Veg Biryani",     "Mango Lassi"),
    ("Butter Chicken",  "Garlic Naan"),
    ("Butter Chicken",  "Dal Makhani"),
    ("Paneer Tikka",    "Masala Chai"),
    ("Aloo Paratha",    "Masala Chai"),
    ("Aloo Paratha",    "Mango Lassi"),
    ("Gulab Jamun",     "Masala Chai"),
    ("Dal Makhani",     "Garlic Naan"),
]


def build_live_system_instruction(
    menu_items: list[dict],
    cart: list[dict],
    upsell_suggestion: str | None = None,
    pending_clarification: str | None = None,
) -> str:
    """
    Build the full system instruction for a Gemini Live voice turn.

    Includes:
    - Persona + language rules
    - Full menu with prices + available modifiers
    - Current cart with modifiers display
    - Pending clarification question (if any)
    - Upsell / combo suggestion (if any)
    """
    # ── Menu section ──
    lines = []
    for item in menu_items[:50]:
        name  = item["name"]
        price = item["price"]
        lines.append(f"  {name} — ₹{price}")
    menu_text = "\n".join(lines)

    # ── Cart section ──
    if cart:
        cart_lines = []
        for c in cart:
            mods = c.get("modifiers") or {}
            mod_str = ""
            if mods:
                parts = []
                if mods.get("size"):        parts.append(mods["size"])
                if mods.get("spice_level"): parts.append(mods["spice_level"])
                if mods.get("add_ons"):     parts.extend(mods["add_ons"])
                if mods.get("notes"):       parts.append(mods["notes"])
                mod_str = f" ({', '.join(parts)})"
            subtotal = c["unit_price"] * c["quantity"]
            cart_lines.append(f"  {c['name']}{mod_str} ×{c['quantity']} = ₹{subtotal:.0f}")
        subtotal_val = sum(c["unit_price"] * c["quantity"] for c in cart)
        cart_text = "\n".join(cart_lines) + f"\n  Subtotal: ₹{subtotal_val:.0f}"
    else:
        cart_text = "  (empty)"

    # ── Clarification section ──
    clarify_section = ""
    if pending_clarification:
        clarify_section = (
            f"\nPENDING CLARIFICATION:\n"
            f"  You asked: \"{pending_clarification}\"\n"
            f"  The customer's next reply answers this question. Handle it accordingly.\n"
        )

    # ── Upsell section ──
    upsell_section = ""
    if upsell_suggestion:
        upsell_section = (
            f"\nUPSELL OPPORTUNITY:\n"
            f"  Suggest: \"{upsell_suggestion}\"\n"
            f"  Work this naturally into your response after confirming the last action.\n"
        )

    # ── Combo section ──
    combo_lines = [f"  • {c['description']}" for c in COMBO_DEALS]
    combo_text = "\n".join(combo_lines)

    return (
        "You are Aria, a warm, efficient multilingual restaurant voice ordering assistant.\n\n"

        "━━ LANGUAGE RULES ━━\n"
        "• Always reply in EXACTLY the same language the customer used.\n"
        "• English → English. Hindi → Hindi. Gujarati → Gujarati.\n"
        "• Hinglish (mixed) → match the mix naturally.\n"
        "• Never switch languages unless the customer does.\n"
        "• TRANSCRIPTION: Always output the customer's speech as English Latin-script text\n"
        "  (romanised/transliterated). NEVER use Devanagari, Gujarati, Gurmukhi, or any\n"
        "  non-Latin script in the input transcription — even if the customer speaks Hindi,\n"
        "  Gujarati, or Punjabi. Your own spoken response may be in any language, but the\n"
        "  written transcription must always be readable English/Roman characters.\n\n"

        "━━ BEHAVIOUR RULES ━━\n"
        "1. Keep replies to 1–2 short, natural sentences. Be warm and restaurant-pace.\n"
        "2. Confirm every action — 'Added Paneer Tikka (hot, extra chutney) to your order!'\n"
        "3. If customer asks for an unknown item, say you don't have it and suggest the closest.\n"
        "4. When ambiguous ('something spicy'), ask a specific clarifying question:\n"
        "   e.g. 'Did you mean Paneer Tikka or Dal Makhani?'\n"
        "5. On CONFIRM_ORDER ('yes/confirm/place it'), read back the full order and total,\n"
        "   then say: 'Perfect! Your order has been placed. Enjoy your meal!'\n"
        "6. On CANCEL_ORDER, say: 'No problem! Your order has been cancelled.'\n"
        "7. On VIEW_CART / bill questions, read the cart and total clearly.\n"
        "8. For modifier requests ('make it spicy', 'large size'), confirm the change.\n"
        "9. Never mention items not on the MENU below.\n"
        "10. After adding an item, if there is an UPSELL OPPORTUNITY, mention it naturally.\n\n"

        "━━ AVAILABLE COMBO DEALS ━━\n"
        f"{combo_text}\n"
        "  Mention a relevant combo if the customer's order qualifies.\n\n"

        f"━━ MENU ━━\n{menu_text}\n\n"
        f"━━ CURRENT ORDER ━━\n{cart_text}\n"
        f"{clarify_section}"
        f"{upsell_section}"
    )

