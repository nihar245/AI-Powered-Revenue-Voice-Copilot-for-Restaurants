"""
Intent extraction module using Groq (Llama 3.3 70B).

Parses customer speech transcripts into structured order intents.
Uses Groq's ultra-fast inference (~200-300ms).
"""

import json
import time
import logging
import re
from typing import Optional

from app.config import settings
from app.nlp.prompts import INTENT_EXTRACTION_PROMPT
from app.services.menu_service import get_menu_items
from app.services.groq_client import async_client

logger = logging.getLogger(__name__)


def _clean_json_response(raw: str) -> str:
    """
    Extract JSON from LLM response, handling markdown code fences
    and extraneous text.
    """
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        return match.group(1).strip()

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        return match.group(0).strip()

    return raw.strip()


async def extract_intent(transcript: str, menu_items: Optional[list[str]] = None) -> dict:
    """
    Extract structured order intent from a customer transcript.

    Uses Groq (Llama 3.3 70B) for blazing-fast JSON extraction.

    Args:
        transcript: The customer's speech as text.
        menu_items: Optional list of menu item names.

    Returns:
        dict with items, intent_type, sentiment, special_requests, raw_response, duration_ms.
    """
    start_time = time.perf_counter()

    if menu_items is None:
        menu_items = get_menu_items()

    menu_str = "\n".join(f"- {item}" for item in menu_items)

    prompt = INTENT_EXTRACTION_PROMPT.format(
        menu_items=menu_str,
        transcript=transcript,
    )

    logger.info("Extracting intent from: '%s'", transcript[:100])

    try:
        response = await async_client.chat.completions.create(
            model=settings.groq.model,
            messages=[
                {"role": "system", "content": "You are a precise JSON extraction assistant. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.groq.temperature,
            max_tokens=settings.groq.max_tokens,
        )

        raw_text = response.choices[0].message.content or ""
        cleaned = _clean_json_response(raw_text)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON output: %s", cleaned[:200])
            parsed = {
                "items": [],
                "intent_type": "unknown",
                "sentiment": "neutral",
                "special_requests": None,
            }

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        result = {
            "items": parsed.get("items", []),
            "intent_type": parsed.get("intent_type", "unknown"),
            "sentiment": parsed.get("sentiment", "neutral"),
            "special_requests": parsed.get("special_requests"),
            "raw_response": raw_text,
            "duration_ms": round(elapsed_ms, 1),
        }

        logger.info(
            "Intent extracted: type=%s, items=%d, time=%.0fms",
            result["intent_type"], len(result["items"]), elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Intent extraction failed: %s", str(e))
        return {
            "items": [],
            "intent_type": "error",
            "sentiment": "neutral",
            "special_requests": None,
            "raw_response": str(e),
            "duration_ms": round(elapsed_ms, 1),
            "error": str(e),
        }
