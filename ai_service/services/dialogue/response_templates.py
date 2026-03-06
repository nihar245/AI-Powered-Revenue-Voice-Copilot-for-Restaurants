"""
Response Templates — fast deterministic responses for common intents.

The state machine checks this before ever calling the LLM.
LLM is only invoked when no template matches (complex / ambiguous turns).

All templates support EN / HI / GU.
"""

from models.schemas import DialogueState, Intent, Language

# fmt: off
TEMPLATES: dict[str, dict[str, str]] = {

    # ── Greeting ──────────────────────────────────────────────────────────────
    Intent.GREETING: {
        Language.EN: "Welcome! What would you like to order today?",
        Language.HI: "Swagat hai! Aaj aap kya order karna chahenge?",
        Language.GU: "Swagat che! Aaj tame shu order karva mango cho?",
    },

    # ── Item added successfully ───────────────────────────────────────────────
    "add_item_ok": {
        Language.EN: "Added {item} × {qty} to your order.",
        Language.HI: "{item} × {qty} aapke order mein add ho gaya.",
        Language.GU: "{item} × {qty} tamara order ma add thai gayu.",
    },

    # ── Item not found / needs clarification ─────────────────────────────────
    "add_item_clarify": {
        Language.EN: "Sorry, I didn't find '{query}' on the menu. Could you say it again?",
        Language.HI: "Maafi kijiye, '{query}' menu mein nahi mila. Kya aap dobara bol sakte hain?",
        Language.GU: "Mafi karo, '{query}' menu ma nathi malyu. Fari thi kaho?",
    },

    # ── Item removed ─────────────────────────────────────────────────────────
    "remove_item_ok": {
        Language.EN: "Removed {item} from your order.",
        Language.HI: "{item} aapke order se hata diya gaya.",
        Language.GU: "{item} tamara order ma thi hatavi devayu.",
    },

    # ── Cart view ─────────────────────────────────────────────────────────────
    "view_cart": {
        Language.EN: "Your cart: {cart_lines}. Total: ₹{total}.",
        Language.HI: "Aapka cart: {cart_lines}. Kul: ₹{total}.",
        Language.GU: "Tamaro cart: {cart_lines}. Kul: ₹{total}.",
    },

    "view_cart_empty": {
        Language.EN: "Your cart is empty. What would you like to order?",
        Language.HI: "Aapka cart khali hai. Aap kya order karna chahenge?",
        Language.GU: "Tamaro cart khali che. Tame shu order karva mango cho?",
    },

    # ── Confirm order ─────────────────────────────────────────────────────────
    Intent.CONFIRM_ORDER: {
        Language.EN: "Got it! Shall I place the order? Say yes to confirm.",
        Language.HI: "Samajh gaya! Kya main order place kar dun? Confirm karne ke liye 'haan' bolein.",
        Language.GU: "Samjhi gayu! Shu hun order place kari du? Confirm karva 'ha' kaho.",
    },

    # ── Order placed successfully ─────────────────────────────────────────────
    "order_placed": {
        Language.EN: "Your order has been placed! The kitchen will prepare it shortly.",
        Language.HI: "Aapka order place ho gaya! Kitchen jald hi tayaar karega.",
        Language.GU: "Tamaro order place thai gayu! Kitchen jaldi tayar karsh.",
    },

    # ── Cancel ───────────────────────────────────────────────────────────────
    Intent.CANCEL_ORDER: {
        Language.EN: "Order cancelled. Let me know if you'd like to start a new order.",
        Language.HI: "Order cancel ho gaya. Naya order shuru karne ke liye batayein.",
        Language.GU: "Order cancel thai gayu. Navo order shuru karva kaho.",
    },

    # ── No open POS session ───────────────────────────────────────────────────
    "no_pos_session": {
        Language.EN: "Sorry, the POS is not open right now. Please ask a staff member for help.",
        Language.HI: "Maafi kijiye, abhi POS khulli nahi hai. Kripaya staff se madad maangein.",
        Language.GU: "Mafi karo, haju POS khuli nathi. Kripaya staff ne puchho.",
    },
}
# fmt: on


def get_template(
    key: str | Intent,
    language: str,
    **kwargs: str,
) -> str | None:
    """
    Returns a formatted template string, or None if no template exists for key.

    Args:
        key:      Intent enum value or custom string key (e.g. "add_item_ok")
        language: "en" | "hi" | "gu"
        **kwargs: Substitution variables (e.g. item="Paneer Butter Masala", qty="2")
    """
    lang = Language(language) if language in Language._value2member_map_ else Language.EN
    template_map = TEMPLATES.get(key)
    if template_map is None:
        return None
    text = template_map.get(lang) or template_map.get(Language.EN, "")
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass   # Return unformatted if placeholder is missing
    return text
