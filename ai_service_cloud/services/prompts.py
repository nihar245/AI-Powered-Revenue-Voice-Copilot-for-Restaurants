"""
Prompt builders for Gemini LLM.
"""

def build_menu_prompt(language: str, menu_items: list[dict]) -> str:
    """Prompt to summarize the menu."""
    menu_str = "\n".join(f"- {i['name']} (₹{i['price']})" for i in menu_items)
    return (
        f"You are a helpful restaurant voice assistant. The user wants to hear the menu. "
        f"Summarize the following menu in a friendly, conversational way, in {language}.\n\n"
        f"Menu:\n{menu_str}\n\n"
        f"Do not read every single item if it's too long, just highlight a few popular options and ask what they'd like."
    )

def build_order_prompt(
    language: str,
    cart: list[dict],
    last_utterance: str,
    intent: str,
    dialogue_state: str,
    menu_context: str,
    upsell_hint: str,
) -> str:
    """Prompt to handle the main ordering conversation."""
    
    cart_str = "\n".join(f"- {i['quantity']}x {i['name']}" for i in cart) if cart else "Empty"
    
    sys_prompt = f"""You are a helpful and polite voice AI taking orders for a restaurant. 
Respond naturally and concisely (1-2 sentences) in {language}. 
Do not use markdown formatting or special characters since your response will be spoken aloud by a TTS engine.

Current State: {dialogue_state}
Current Cart: 
{cart_str}

Menu Context:
{menu_context}

Upsell Suggestion (use naturally if appropriate): {upsell_hint}
"""

    return sys_prompt
