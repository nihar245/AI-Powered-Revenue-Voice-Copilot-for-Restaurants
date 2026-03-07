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

_LANG_NAMES: dict[str, str] = {
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "gu": "Gujarati (ગુજરાતી)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "en": "English",
}


def _build_combo_text(combo_deals: list[dict]) -> str:
    """
    Format DB combos (from fetch_active_combos) into the prompt section.
    Each combo: { name, description, selling_price, items: [{item_name, qty}] }
    """
    if not combo_deals:
        return "  (No active combo deals at the moment)"
    lines = []
    for c in combo_deals:
        item_parts = " + ".join(
            f"{it['item_name']}{' ×' + str(it['qty']) if it['qty'] > 1 else ''}"
            for it in c.get("items", [])
        )
        price_str = f"₹{c['selling_price']:.0f}" if c.get("selling_price") else ""
        desc = c.get("description") or item_parts
        lines.append(f"  • {c['name']} ({item_parts}) — {price_str}  {desc}")
    return "\n".join(lines)


def _build_upsell_hint(combo_deals: list[dict], cart_names: list[str]) -> str:
    """
    Given the current cart item names and DB combos, produce a hint telling
    Aria which combos the customer is one item away from completing.
    """
    if not combo_deals or not cart_names:
        return ""
    cart_lower = {n.lower() for n in cart_names}
    hints = []
    for c in combo_deals:
        combo_item_names = [it["item_name"] for it in c.get("items", [])]
        combo_lower      = {n.lower() for n in combo_item_names}
        missing          = combo_lower - cart_lower
        if missing and len(missing) < len(combo_lower):
            missing_str = " and ".join(m.title() for m in missing)
            hints.append(
                f"Add {missing_str} to complete the '{c['name']}' combo "
                f"(₹{c['selling_price']:.0f} for {' + '.join(combo_item_names)})"
            )
    return "; ".join(hints) if hints else ""


def _build_offers_text(active_offers: list[dict]) -> str:
    """Format active offers (from fetch_active_offers) into a prompt section."""
    if not active_offers:
        return ""
    lines = []
    for o in active_offers:
        if o["type"] == "pct":
            disc = f"{o['discount_value']:.0f}% off"
        elif o["type"] == "flat":
            disc = f"₹{o['discount_value']:.0f} off"
        else:
            disc = f"{o['type'].upper()} deal"
        min_val = f" on orders above ₹{o['min_order_val']:.0f}" if o["min_order_val"] > 0 else ""
        lines.append(f"  • {o['name']}: {disc}{min_val}")
    return "\n".join(lines)


def build_live_system_instruction(
    menu_items: list[dict],
    cart: list[dict],
    upsell_suggestion: str | None = None,
    pending_clarification: str | None = None,
    language: str = "en",
    table_id: str = "",
    customer_name: str | None = None,
    awaiting_kitchen_confirm: bool = False,
    conversation_history: list[dict] | None = None,
    combo_deals: list[dict] | None = None,
    active_offers: list[dict] | None = None,
) -> str:
    """
    Build the full system instruction for a Gemini Live voice turn.
    """
    # ── Menu section ──
    lines = []
    for item in menu_items[:60]:
        name     = item["name"]
        variants = item.get("variants", [])
        veg_tag  = "[V]" if item.get("is_veg", True) else "[NV]"
        tags     = item.get("tags") or []
        tag_str  = f" ★{','.join(tags)}" if tags else ""

        tax_rate = float(item.get("tax", 5.0))
        tax_mult = 1 + tax_rate / 100
        if len(variants) > 1:
            price_str = " / ".join(
                f"{v['variant_name']} ₹{v['price'] * tax_mult:.0f}" for v in variants
            )
        elif len(variants) == 1:
            price_str = f"₹{variants[0]['price'] * tax_mult:.0f}"
        else:
            price_str = f"₹{item.get('price', 0) * tax_mult:.0f}"

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
            line_tax    = c.get("tax_rate", 5.0) / 100
            line_total  = c["unit_price"] * c["quantity"] * (1 + line_tax)
            cart_lines.append(f"  {c['name']}{mod_str} ×{c['quantity']} = ₹{line_total:.0f} (incl. tax)")
        subtotal_val = sum(c["unit_price"] * c["quantity"] for c in cart)
        tax_val      = sum(c["unit_price"] * c["quantity"] * c.get("tax_rate", 5.0) / 100 for c in cart)
        grand_total  = round(subtotal_val + tax_val, 2)
        cart_text = "\n".join(cart_lines) + (
            f"\n  Grand Total (incl. 5% tax): ₹{grand_total:.0f}"
        )
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

    # ── Upsell section (explicit suggestion + combo-based hint) ──
    upsell_section = ""
    combo_upsell_hint = _build_upsell_hint(combo_deals or [], [c["name"] for c in cart])
    if upsell_suggestion or combo_upsell_hint:
        hints = []
        if upsell_suggestion:
            hints.append(f"Suggest: \"{upsell_suggestion}\"")
        if combo_upsell_hint:
            hints.append(f"Combo opportunity: {combo_upsell_hint}")
        upsell_section = (
            "\nUPSELL OPPORTUNITY:\n"
            + "\n".join(f"  {h}" for h in hints)
            + "\n  Work this naturally into your response after confirming the last action.\n"
        )

    # ── Combo section (from DB) ──
    combo_text = _build_combo_text(combo_deals or [])

    # ── Offers section (from DB) ──
    offers_text = _build_offers_text(active_offers or [])
    offers_section = (
        f"\n━━ ACTIVE PROMOTIONS / OFFERS ━━\n{offers_text}\n"
        "  Mention the most relevant offer naturally when it applies to the customer's order.\n"
    ) if offers_text else ""

    # ── Table section ──
    table_label = f"Table {table_id}" if table_id else "Walk-in / phone order"

    # ── Customer name section ──
    name_label = customer_name if customer_name else "not yet asked"

    # Language-specific instruction
    lang_name = _LANG_NAMES.get(language, "English")
    lang_hint = (
        f"• LANGUAGE LOCK: The customer's chosen language is {lang_name}. "
        f"You MUST reply in {lang_name} ONLY. "
        f"Do NOT switch to Hindi or any other language, "
        f"even if the customer uses food words from another language.\n"
    )

    # ── Awaiting kitchen confirmation block ──
    kitchen_confirm_section = ""
    if awaiting_kitchen_confirm:
        kitchen_confirm_section = (
            "\n━━ AWAITING KITCHEN CONFIRMATION ━━\n"
            "The customer has finished ordering. You have ALREADY read back the full order and total.\n"
            "The customer is now replying to: 'Shall I send this order to the kitchen?'\n"
            "• If they say YES / confirm / go ahead / haan / ha → use [CMD: confirm_order]\n"
            "  Then say: 'Perfect! Your order has been sent to the kitchen. Thank you, <customer_name>! "
            "Have a wonderful meal. Goodbye!' (replace <customer_name> with the actual name if known)\n"
            "• If they say NO / cancel / nahi / hold on → use [CMD: cancel_order]\n"
            "  Then ask what they'd like to change.\n"
            "• If they want to add/remove items → use the appropriate intent and go back to taking order.\n\n"
        )

    # ── Conversation history section ──
    history_section = ""
    if conversation_history:
        history_lines = "\n".join(
            f"  Turn {h.get('turn', i)}: Customer: \"{h.get('customer', '')[:150]}\""
            f" | Aria: \"{h.get('aria', '')[:200]}\""
            for i, h in enumerate(conversation_history)
        )
        history_section = (
            "\n━━ CONVERSATION HISTORY (prior turns) ━━\n"
            f"{history_lines}\n"
            "Reference this history to maintain context and avoid re-greeting or repeating yourself.\n"
        )

    return (
        "You are Aria, a warm, efficient multilingual restaurant voice ordering assistant "
        "at Padmavati Bhojanalaya.\n\n"

        "━━ LANGUAGE RULES ━━\n"
        "• Detect the language the customer is speaking and reply in EXACTLY that same language.\n"
        "• English → English. Hindi → pure Hindi. Tamil → pure Tamil. Telugu → pure Telugu.\n"
        f"{lang_hint}"
        "• CRITICAL: When the customer speaks Hindi, Tamil, Telugu, Gujarati — your SPOKEN AUDIO must be\n"
        "  in that same language so the customer hears a natural reply in their own tongue.\n"
        "  EXCEPTION: the machine tags [CMD:] [ROMAN:] [TRANSCRIPT:] MUST always be in Roman/English.\n"
        "  The language lock applies ONLY to your spoken audio and its transliteration — NEVER to the\n"
        "  machine tags. The machine tags are MANDATORY in every single turn, regardless of language.\n"
        "• Never switch languages unless the customer does first.\n"
        "• TRANSCRIPTION RULES — strictly follow these for BOTH input and output transcriptions:\n"
        "  1. TRANSLITERATE — do NOT translate. Write each word phonetically in Roman/Latin letters.\n"
        "     Hindi example: customer says 'मुझे एक पनीर टिक्का चाहिए' → transcribe as\n"
        "     'mujhe ek paneer tikka chahiye'  (correct transliteration)\n"
        "  2. Aria's response transcription must also be a Roman transliteration of the audio spoken.\n"
        "  3. NEVER use native script (Devanagari / Tamil / Telugu) anywhere in transcriptions.\n\n"

        "━━ BEHAVIOUR RULES ━━\n"
        "1. Keep replies to 1–2 short, natural sentences. Be warm and restaurant-pace.\n"
        "2. A pre-recorded greeting has already introduced you as Aria from Padmavati Bhojanalaya.\n"
        "   Do NOT greet again. Respond directly to the customer's first request.\n"
        "3. Once you have the customer's name, use it occasionally for warmth.\n"
        "   Tag the name: [NAME: <first name only>]\n"
        "4. Confirm every cart action — 'Added Paneer Tikka (hot, extra chutney) to your order!'\n"
        "5. If customer asks for an unknown item, say you don't have it and suggest the closest.\n"
        "6. When ambiguous ('something spicy'), ask a specific clarifying question.\n"
        "7. DONE ORDERING — when the customer says 'that's all', 'no more', 'bas itna hi', 'done',\n"
        "   'koi aur nahi', 'nothing else', 'that's everything', 'I'm done', etc.:\n"
        "   a) Read back the COMPLETE order: every item, quantity, modifiers, and Grand Total.\n"
        "   b) Ask: 'Shall I send this order to the kitchen?'\n"
        "   c) Use [CMD: done_ordering]\n"
        "8. On CONFIRM_ORDER (only after done_ordering read-back): insert order, then say:\n"
        "   'Your order has been sent to the kitchen! Thank you, <name>! Enjoy your meal. Goodbye!'\n"
        "9. On CANCEL_ORDER, say: 'No problem! Your order has been cancelled. Have a great day!'\n"
        "10. On VIEW_CART / bill questions, read the cart and total clearly.\n"
        "11. For modifier requests ('make it spicy', 'large size'), confirm the change.\n"
        "12. Never mention items not on the MENU below.\n"
        "13. After adding an item, if there is an UPSELL OPPORTUNITY, mention it naturally.\n"
        "14. PRICING — CRITICAL: ALL prices are already tax-inclusive (incl. 5% GST).\n"
        "    Always quote the tax-inclusive price. NEVER say the pre-tax price.\n"
        "15. TOTAL: After every add/remove/modify, end with 'Your total is Rs.X.'\n"
        "    Skip this only when the cart is empty.\n"
        "16. COMBO SAVINGS: If the cart matches a combo deal, always announce it proactively.\n"
        "17. CMD TAG — MANDATORY every single turn, no exceptions.\n"
        "    Append at the very end of your output_audio_transcription on its own line.\n"
        "    NEVER speak this aloud. Format:\n"
        "    [CMD: <intent> | <ExactMenuName> x<qty> (<key=val>)]\n"
        "    intent values:\n"
        "      add_item | remove_item | modify_item | done_ordering | confirm_order | cancel_order\n"
        "      view_cart | view_menu | enquire_price | greeting | unknown\n"
        "    Examples:\n"
        "      [CMD: add_item | Paneer Tikka x1 (spice=hot)]\n"
        "      [CMD: done_ordering]\n"
        "      [CMD: confirm_order]\n"
        "      [CMD: greeting]\n"
        "    CRITICAL: Always in English/Roman. Never omit the tag.\n"
        "18. NAME TAG — when you learn the customer's name, add on its own line:\n"
        "    [NAME: <first name>]\n"
        "    Only include this tag the FIRST TIME you hear their name.\n"
        "19. ROMAN TAG — MANDATORY. On its own line immediately after [CMD:].\n"
        "    [ROMAN: <Aria's full spoken response transliterated into Roman/Latin>]\n"
        "20. TRANSCRIPT TAG — MANDATORY. On its own line after [ROMAN:].\n"
        "    [TRANSCRIPT: <what the customer just said, transliterated into Roman/Latin>]\n\n"

        "━━ AVAILABLE COMBO DEALS ━━\n"
        f"{combo_text}\n\n"

        f"{offers_section}"
        f"━━ CUSTOMER ━━\nName: {name_label}\n\n"
        f"━━ TABLE ━━\n{table_label}\n\n"
        f"━━ MENU ━━\n{menu_text}\n\n"
        f"━━ CURRENT ORDER ━━\n{cart_text}\n"
        f"{kitchen_confirm_section}"
        f"{clarify_section}"
        f"{upsell_section}"
        f"{history_section}"
    )

