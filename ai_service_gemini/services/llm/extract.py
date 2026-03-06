"""
Transcript → Structured Cart Update Extractor

Uses Gemini text model to parse the customer's transcript into a structured JSON
containing intent, cart items WITH modifiers, ambiguity flags, and any
clarification question the assistant should ask.

Capabilities:
 - Modifier extraction  : size, spice_level, add_ons, special_notes
 - Ambiguity detection  : partial/unclear item names trigger clarify intent
 - Modify intent        : "make it spicy" / "change qty to 2" on existing items
 - All intents          : add, remove, modify, confirm, cancel, view_cart,
                          view_menu, enquire_price, upsell_response, greeting
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from google import genai
from google.genai import types

from config import settings


# ─── Prompt ──────────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """\
You are a restaurant order parser. Extract structured data from the customer's spoken input.

Customer said (transcription — may be in any language/script: English, Hindi, Tamil, Telugu, Gujarati, etc.): "{transcript}"
AI assistant's spoken response (use as a reliable hint for what was understood): "{response_text}"

Available menu items (ONLY use names from this list):
{menu_names}

Return ONLY a single valid JSON object — no markdown, no explanation:
{{
  "intent": "<one of: add_item | remove_item | modify_item | confirm_order | cancel_order | view_cart | view_menu | enquire_price | upsell_response | greeting | clarify | unknown>",
  "items": [
    {{
      "name": "<exact menu name>",
      "qty": 1,
      "modifiers": {{
        "size":        "<small|medium|large|null>",
        "spice_level": "<mild|medium|hot|extra_hot|null>",
        "add_ons":     ["<add-on string>"],
        "notes":       "<free text special request or null>"
      }},
      "ambiguous": false
    }}
  ],
  "clarification_needed": false,
  "clarification_question": null
}}

Rules:
1. Match names EXACTLY from menu list; correct minor mishearings ("masla chai" → "Masala Chai").
2. If customer mentions an item not on the menu, set ambiguous=true and clarification_needed=true.
3. clarification_question: if ambiguous or unclear, write the question Aria should ask.
4. CONFIRM_ORDER: "yes", "confirm", "place it", "order karo", "theek hai", "done", "that's all".
5. CANCEL_ORDER: "cancel", "forget it", "nahi chahiye", "band karo".
6. VIEW_CART: "what did I order", "mera order", "show cart", "total", "kitna hua".
7. modify_item: "make it spicy", "2 kar do", "change quantity", "without onion".
8. upsell_response: customer responds to a recommendation ("yes add it", "no thanks").
9. Extract qty from spoken numbers (default 1).
10. Only set add_ons if explicitly requested (e.g., "extra cheese", "with raita").
11. Set modifiers fields to null if not mentioned — never guess.
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_garbled(text: str) -> bool:
    """Return True when the transcript is empty or written in non-Latin (native) script.
    When the transcript is in Gujarati / Hindi / Tamil / Telugu script the LLM
    extractor cannot do reliable menu matching, so callers should fall back to
    using the AI's English response_text as the primary parse source instead.
    """
    if not text.strip():
        return True
    # If more than 30 % of alphabetic characters are non-ASCII the text contains
    # a substantial amount of native script (Devanagari, Gujarati, Tamil, …).
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return True
    non_latin_ratio = sum(1 for c in alpha if ord(c) > 127) / len(alpha)
    return non_latin_ratio > 0.30


def _fuzzy_match_item(name: str, menu_items: list[dict]) -> dict | None:
    """Best-effort fuzzy match to correct minor model output errors."""
    name_lower = name.lower().strip()
    for item in menu_items:
        if item["name"].lower() == name_lower:
            return item
    for item in menu_items:
        if name_lower in item["name"].lower() or item["name"].lower() in name_lower:
            return item
    best, best_score = None, 0.0
    for item in menu_items:
        score = SequenceMatcher(None, name_lower, item["name"].lower()).ratio()
        if score > best_score:
            best_score, best = score, item
    return best if best_score >= 0.50 else None


def _clean_modifiers(raw: dict | None) -> dict:
    """Normalize modifiers dict; strip all-null entries."""
    if not raw or not isinstance(raw, dict):
        return {}
    out: dict = {}
    if raw.get("size") and str(raw["size"]).lower() not in ("null", "none", ""):
        out["size"] = raw["size"]
    if raw.get("spice_level") and str(raw["spice_level"]).lower() not in ("null", "none", ""):
        out["spice_level"] = raw["spice_level"]
    add_ons = [s for s in (raw.get("add_ons") or []) if s and str(s).lower() not in ("null", "none")]
    if add_ons:
        out["add_ons"] = add_ons
    notes = raw.get("notes")
    if notes and str(notes).lower() not in ("null", "none", ""):
        out["notes"] = str(notes)
    return out


# ─── Main extractor ───────────────────────────────────────────────────────────

_INTENT_MAP = {
    "ADD_ITEM":        "add_item",
    "REMOVE_ITEM":     "remove_item",
    "MODIFY_ITEM":     "modify_item",
    "VIEW_CART":       "view_cart",
    "CONFIRM_ORDER":   "confirm_order",
    "CANCEL_ORDER":    "cancel_order",
    "GREETING":        "greeting",
    "VIEW_MENU":       "view_menu",
    "ENQUIRE_PRICE":   "enquire_price",
    "UPSELL_RESPONSE": "upsell_response",
    "CLARIFY":         "clarify",
    "UNKNOWN":         "unknown",
}


async def extract_cart_update(
    transcript: str,
    menu_items: list[dict],
    response_text: str = "",
) -> dict:
    """
    Parse transcript into structured update.

    Returns:
    {
      "intent": str,
      "items": [{"product_id", "name", "qty", "modifiers": {...}, "ambiguous": bool}],
      "clarification_needed": bool,
      "clarification_question": str | None,
    }
    """
    # When transcript is blank, fall back to parsing the AI's spoken response.
    garbled = not transcript.strip()
    if garbled and not response_text.strip():
        return _safe_default()
    if not settings.gemini_api_key:
        return _safe_default()

    parse_text    = transcript.strip() if not garbled else response_text.strip()
    response_hint = response_text.strip() if response_text else "(not available)"

    menu_names = " | ".join(item["name"] for item in menu_items)
    prompt = _EXTRACT_PROMPT.format(
        transcript=parse_text,
        response_text=response_hint,
        menu_names=menu_names,
    )

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = await client.aio.models.generate_content(
            model=settings.gemini_text_model,
            contents=prompt,
            config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=512,
            response_mime_type="application/json",
        ),
        )
        text = (resp.text or "").strip()
    except Exception:
        return _safe_default()

    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _safe_default()

    raw_intent = str(data.get("intent", "UNKNOWN")).upper()
    intent     = _INTENT_MAP.get(raw_intent, "unknown")

    # Resolve items
    resolved: list[dict] = []
    for raw in data.get("items", []):
        raw_name  = str(raw.get("name", "")).strip()
        qty       = max(1, int(raw.get("qty", 1)))
        ambiguous = bool(raw.get("ambiguous", False))
        modifiers = _clean_modifiers(raw.get("modifiers"))
        matched   = _fuzzy_match_item(raw_name, menu_items)
        if matched:
            resolved.append({
                "product_id": str(matched["product_id"]),
                "name":       matched["name"],
                "qty":        qty,
                "modifiers":  modifiers,
                "ambiguous":  ambiguous,
            })
        elif raw_name:
            # Unmatched — keep with ambiguous flag so caller can clarify
            resolved.append({
                "product_id": "",
                "name":       raw_name,
                "qty":        qty,
                "modifiers":  modifiers,
                "ambiguous":  True,
            })

    clarification_needed   = bool(data.get("clarification_needed", False))
    clarification_question = data.get("clarification_question") or None
    # Auto-set clarification if any item is ambiguous
    if any(i.get("ambiguous") for i in resolved):
        clarification_needed = True

    return {
        "intent":                  intent,
        "items":                   resolved,
        "clarification_needed":    clarification_needed,
        "clarification_question":  clarification_question,
    }


def _safe_default() -> dict:
    return {
        "intent":                 "unknown",
        "items":                  [],
        "clarification_needed":   False,
        "clarification_question": None,
    }

