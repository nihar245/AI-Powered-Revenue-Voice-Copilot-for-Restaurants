from models.schemas import Language

# ─── Per-language system personas ────────────────────────────────────────────
_SYSTEM_PROMPTS = {
    Language.EN: (
        "You are a smart, friendly voice ordering assistant for a restaurant.\n"
        "Your job:\n"
        "1. The customer's speech was transcribed by a voice model and MAY contain mishearings or typos "
        "(e.g. 'panettica' means 'Paneer Tikka', 'masla chai' means 'Masala Chai', 'garlic none' means 'Garlic Naan'). "
        "Always find the closest match from the MENU provided below — never say an item is unavailable unless "
        "it genuinely does not exist in the menu after careful fuzzy matching.\n"
        "2. Understand the customer's intent from context (add item, remove item, view cart, confirm, cancel).\n"
        "3. Respond in plain conversational English, max 2 sentences. "
        "Confirm what action was taken (e.g. 'Added Paneer Tikka × 2 to your order.'). "
        "If multiple actions were requested, handle all of them and confirm each briefly.\n"
        "4. Never make up items not in the menu. Suggest the closest real item if unclear."
    ),
    Language.HI: (
        "Aap ek smart, friendly restaurant voice assistant hain.\n"
        "Aapka kaam:\n"
        "1. Customer ki awaaz speech model se transcribe hui hai aur usme galat words ho sakte hain "
        "(e.g. 'panettica' matlab 'Paneer Tikka', 'masla chai' matlab 'Masala Chai'). "
        "Hamesha neeche diye MENU se sabse close match dhundho.\n"
        "2. Customer ka intent samjho (item add karna, hatana, cart dekhna, confirm, cancel).\n"
        "3. Hindi ya Hinglish mein max 2 sentences mein jawab do. \n"
        "Jo action hua usse confirm karo (e.g. 'Paneer Tikka × 2 add ho gaya').\n"
        "4. Menu mein jo nahi hai woh kabhi mat bolein."
    ),
    Language.GU: (
        "Tame ek smart, friendly restaurant voice assistant cho.\n"
        "Tamaro kaam:\n"
        "1. Customer ni awaj speech model e transcribe kari che ane tena ma galat words hoi shake che "
        "(e.g. 'panettica' eno arth 'Paneer Tikka', 'masla chai' eno arth 'Masala Chai'). "
        "Hamesha niche aapela MENU ma thi sabse najik match shodo.\n"
        "2. Customer no intent samjho (item add karvu, hatavvu, cart jovu, confirm, cancel).\n"
        "3. Gujarati ma max 2 sentences ma jawab apo. Jo action thayo te confirm karo.\n"
        "4. Menu ma nathi tema thi koi pan item kabhi bolsho nahi."
    ),
}


def build_order_prompt(
    language: str,
    cart: list[dict],
    last_utterance: str,
    intent: str,
    dialogue_state: str,
    menu_context: str,
    upsell_hint: str = "",
) -> str:
    lang   = Language(language) if language in Language._value2member_map_ else Language.EN
    system = _SYSTEM_PROMPTS[lang]

    cart_lines = "\n".join(
        f"  - {item['name']} x{item['quantity']}  = ₹{item['unit_price'] * item['quantity']:.0f}"
        for item in cart
    ) or "  (empty)"

    subtotal = sum(item["unit_price"] * item["quantity"] for item in cart)

    prompt = (
        f"{system}\n\n"
        f"=== MENU ===\n{menu_context}\n\n"
        f"=== CURRENT CART ===\n{cart_lines}\nCart total: ₹{subtotal:.0f}\n\n"
        f"=== CONVERSATION ===\n"
        f"Dialogue state: {dialogue_state}\n"
        f"Customer said (may contain speech-to-text errors): \"{last_utterance}\"\n"
        f"System detected intent: {intent}\n"
    )

    if upsell_hint:
        prompt += f"Upsell opportunity (use naturally only if relevant): {upsell_hint}\n"

    prompt += (
        "\n=== YOUR RESPONSE ===\n"
        "Interpret any fuzzy/misheared words using the menu above, then respond to the customer "
        "in 1-2 sentences confirming the action taken:\n"
    )
    return prompt


def build_menu_prompt(language: str, menu_items: list[dict]) -> str:
    lang   = Language(language) if language in Language._value2member_map_ else Language.EN
    system = _SYSTEM_PROMPTS[lang]

    # Group items by category_name
    categories: dict[str, list] = {}
    for item in menu_items:
        cat = item.get("category_name", "Other")
        categories.setdefault(cat, []).append(item)

    menu_text = ""
    for cat_name, items in categories.items():
        menu_text += f"\n{cat_name}:\n"
        for item in items:
            menu_text += f"  - {item['name']}: ₹{item['price']}\n"

    lang_label = {"en": "English", "hi": "Hindi/Hinglish", "gu": "Gujarati"}.get(lang, "English")

    prompt = (
        f"{system}\n\n"
        f"Menu:{menu_text}\n"
        f"Give a brief, friendly overview of the menu in {lang_label}. "
        f"Keep it under 4 sentences and highlight a few popular items."
        f"\n\nRespond:"
    )
    return prompt
