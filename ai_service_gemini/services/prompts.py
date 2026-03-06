"""
System instruction builders for Gemini Live sessions.

The system instruction is injected into every Live session so the model knows
the current menu (with modifiers), cart state, behavioural rules, and
upsell / combo hints — without any extra LLM call.

Combos and upsell pairings are loaded from the DB at startup and refreshed
via ``reload_combos()``.  Fallback static data is used when the DB is
unavailable.
"""

from __future__ import annotations


# ─── Modifier catalogue (used both in prompt and in upsell engine) ─────────────
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

# ─── Dynamic combo deals (loaded from DB, fallback to static) ─────────────────
COMBO_DEALS: list[dict] = []

# ─── Dynamic upsell map (loaded from DB combos, fallback to static) ──────────
UPSELL_MAP: list[tuple[str, str]] = []

# ─── Static fallbacks ────────────────────────────────────────────────────────
_FALLBACK_COMBOS = [
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
]

_FALLBACK_UPSELL: list[tuple[str, str]] = [
    ("Veg Biryani",     "Mango Lassi"),
    ("Butter Chicken",  "Garlic Naan"),
    ("Paneer Tikka",    "Masala Chai"),
    ("Aloo Paratha",    "Masala Chai"),
    ("Dal Makhani",     "Garlic Naan"),
]


async def reload_combos() -> None:
    """
    Load combo deals from ``menu_combos`` + ``combo_items`` and derive
    upsell pairings.  Called on startup and can be called periodically.
    """
    global COMBO_DEALS, UPSELL_MAP

    try:
        from services.database.queries import fetch_active_combos
        db_combos = await fetch_active_combos()
    except Exception:
        db_combos = []

    if db_combos:
        COMBO_DEALS = []
        seen_pairs: set[tuple[str, str]] = set()
        for c in db_combos:
            item_names = [i["item_name"] for i in c["items"]]
            COMBO_DEALS.append({
                "name":        c["name"],
                "items":       item_names,
                "saving":      c.get("saving", 0),
                "description": c.get("description") or (
                    " + ".join(item_names) + f" — save ₹{c.get('saving', 0)}"
                ),
            })
            # Derive pairings: each item triggers suggestion of the others
            for i, trigger in enumerate(item_names):
                for j, target in enumerate(item_names):
                    if i != j:
                        pair = (trigger, target)
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
        UPSELL_MAP = list(seen_pairs)
    else:
        COMBO_DEALS = list(_FALLBACK_COMBOS)
        UPSELL_MAP  = list(_FALLBACK_UPSELL)


def _extract_item_name_from_menu(suggestion_text: str, menu: list[dict]) -> str | None:
    """Pull the item name out of a suggestion / upsell string."""
    text_lower = suggestion_text.lower()
    for m in menu:
        if m["name"].lower() in text_lower:
            return m["name"]
    return None


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
    # ── Menu section (show item + variants) ──
    lines = []
    for item in menu_items[:50]:
        name  = item["name"]
        variants = item.get("variants", [])
        if len(variants) > 1:
            var_strs = [f"{v['variant_name']} ₹{v['price']:.0f}" for v in variants]
            lines.append(f"  {name} — {', '.join(var_strs)}")
        else:
            lines.append(f"  {name} — ₹{item['price']:.0f}")
        veg_tag = " [Veg]" if item.get("is_veg") else " [Non-Veg]"
        lines[-1] += veg_tag
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

