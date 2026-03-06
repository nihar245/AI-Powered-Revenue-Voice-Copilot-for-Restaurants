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


_LANG_NAMES: dict[str, str] = {
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "gu": "Gujarati (ગુજરાતી)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "en": "English",
}


def build_live_system_instruction(
    menu_items: list[dict],
    cart: list[dict],
    upsell_suggestion: str | None = None,
    pending_clarification: str | None = None,
    language: str = "en",
    table_id: str = "",
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
    for item in menu_items[:60]:
        name     = item["name"]
        variants = item.get("variants", [])
        veg_tag  = "[V]" if item.get("is_veg", True) else "[NV]"
        tags     = item.get("tags") or []
        tag_str  = f" ★{','.join(tags)}" if tags else ""

        if len(variants) > 1:
            price_str = " / ".join(
                f"{v['variant_name']} ₹{v['price']:.0f}" for v in variants
            )
        elif len(variants) == 1:
            price_str = f"₹{variants[0]['price']:.0f}"
        else:
            price_str = f"₹{item.get('price', 0):.0f}"

        addons = item.get("addons", [])
        addon_hint = ""
        if addons:
            addon_hint = "  add-ons: " + ", ".join(
                f"{a['addon_name']} +₹{a['price']:.0f}" for a in addons[:4]
            )

        lines.append(f"  {veg_tag} {name}{tag_str} — {price_str}{addon_hint}")
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

    # ── Table section ──
    table_label = f"Table {table_id}" if table_id else "Walk-in / table not set"

    # Language-specific instruction — applied for every language, including English
    lang_name = _LANG_NAMES.get(language, "English")
    lang_hint = (
        f"• LANGUAGE LOCK: The customer's chosen language is {lang_name}. "
        f"You MUST reply in {lang_name} ONLY. "
        f"Do NOT switch to Hindi or any other language, "
        f"even if the customer uses food words from another language.\n"
    )

    return (
        "You are Aria, a warm, efficient multilingual restaurant voice ordering assistant.\n\n"

        "━━ LANGUAGE RULES ━━\n"
        "• Detect the language the customer is speaking and reply in EXACTLY that same language.\n"
        "• English → English. Hindi → pure Hindi. Tamil → pure Tamil. Telugu → pure Telugu.\n"
        f"{lang_hint}"
        "• CRITICAL: When the customer speaks Hindi, Tamil, or Telugu — your SPOKEN AUDIO must be\n"
        "  in that same language so the customer hears a natural reply in their own tongue.\n"
        "  EXCEPTION: the machine tags [CMD:] [ROMAN:] [TRANSCRIPT:] MUST always be Roman/English.\n"
        "• Never switch languages unless the customer does first.\n"
        "• TRANSCRIPTION RULES — strictly follow these for BOTH input and output transcriptions:\n"
        "  1. TRANSLITERATE — do NOT translate. Write each word phonetically in Roman/Latin letters.\n"
        "     Hindi example: customer says 'मुझे एक पनीर टिक्का चाहिए' → transcribe as\n"
        "     'mujhe ek paneer tikka chahiye'  (✔ correct transliteration)\n"
        "     NOT 'I want one paneer tikka'    (✘ wrong — that is a translation)\n"
        "     NOT 'मुझे एक पनीर टिक्ѓा चाहिए'  (✘ wrong — that is native script)\n"
        "  2. Aria's response transcription must also be a Roman transliteration of the audio spoken.\n"
        "     Aria says Hindi audio 'मैंने पनीर टिѓѓा डाल दिया है' → transcribe as\n"
        "     'Maine paneer tikka add kar diya hai'\n"
        "  3. NEVER use native script (Devanagari / Tamil / Telugu) anywhere in transcriptions.\n\n"

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
        "10. After adding an item, if there is an UPSELL OPPORTUNITY, mention it naturally.\n"
        "11. TOTAL: After every add / remove / modify, end your spoken response with\n"
        "    'Your total is ₹X.' using the subtotal in CURRENT ORDER below.\n"
        "    Skip this line only when the cart is empty.\n"
        "12. COMBO SAVINGS: Proactively scan CURRENT ORDER against AVAILABLE COMBO DEALS.\n"
        "    If the cart fully or partially matches a combo, ALWAYS announce it without\n"
        "    being asked: 'Add [item] to unlock the [Combo Name] and save ₹X!'\n"
        "13. CMD TAG — append at the very end of your output_audio_transcription on its own line.\n"
        "    NEVER speak this aloud. Format:\n"
        "    [CMD: <intent> | <ExactMenuName> x<qty> (<key=val, key=val>)]\n"
        "    Use ONLY exact English item names from MENU below. intent values:\n"
        "      add_item | remove_item | modify_item | confirm_order | cancel_order\n"
        "      view_cart | view_menu | enquire_price | greeting | unknown\n"
        "    Examples:\n"
        "      [CMD: add_item | Paneer Tikka x1 (size=full, spice=hot) | Masala Chai x2]\n"
        "      [CMD: remove_item | Veg Biryani x1]\n"
        "      [CMD: confirm_order]\n"
        "      [CMD: greeting]\n"
        "    CRITICAL: This tag MUST be in English/Roman regardless of the language lock.\n"
        "14. ROMAN TAG — on its own line immediately after [CMD:].\n"
        "    [ROMAN: <Aria's full spoken response transliterated into Roman/Latin>]\n"
        "    This is what the UI shows as Aria's response text.\n"
        "    Example (Hindi audio): [ROMAN: Paneer Tikka add kar diya! Aapka total hai Rs.250.]\n"
        "    Example (English audio): [ROMAN: Added Paneer Tikka! Your total is Rs.250.]\n"
        "    CRITICAL: Roman/Latin script ONLY.\n"
        "15. TRANSCRIPT TAG — on its own line after [ROMAN:].\n"
        "    [TRANSCRIPT: <what the customer just said, TRANSLITERATED into Roman/Latin>]\n"
        "    This is what the UI shows as the customer's words.\n"
        "    Example: customer says 'मुझे एक पनीर टिѓѓा डालना है' → [TRANSCRIPT: mujhe ek paneer tikka daalna hai]\n"
        "    Example: customer says in English 'add one veg biryani' → [TRANSCRIPT: add one veg biryani]\n"
        "    CRITICAL: Roman/Latin script ONLY. Transliterate, do NOT translate.\n\n"

        "━━ AVAILABLE COMBO DEALS ━━\n"
        f"{combo_text}\n"
        "  Mention a relevant combo if the customer's order qualifies.\n\n"

        f"━━ TABLE ━━\n{table_label}\n\n"
        f"━━ MENU ━━\n{menu_text}\n\n"
        f"━━ CURRENT ORDER ━━\n{cart_text}\n"
        f"{clarify_section}"
        f"{upsell_section}"
    )

