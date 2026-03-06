"""
Response generation module using Groq (Llama 3.3 70B).

Generates natural, conversational responses for the voice assistant.
Uses Groq's ultra-fast inference.
"""

import time
import logging
from typing import Optional

from app.config import settings
from app.nlp.prompts import RESPONSE_GENERATION_PROMPT
from app.services.groq_client import async_client

logger = logging.getLogger(__name__)


async def generate_response(
    order_json: dict,
    upsell_suggestion: Optional[str] = None,
) -> dict:
    """
    Generate a natural language response for the customer.

    Uses Groq (Llama 3.3 70B) for fast, natural responses.

    Args:
        order_json: Structured order intent from intent extraction.
        upsell_suggestion: Optional upsell item name to weave into response.

    Returns:
        dict with response_text and duration_ms.
    """
    start_time = time.perf_counter()

    upsell_text = upsell_suggestion or "No upsell suggestion"

    prompt = RESPONSE_GENERATION_PROMPT.format(
        order_json=str(order_json),
        upsell_suggestion=upsell_text,
    )

    logger.info("Generating response for intent_type=%s", order_json.get("intent_type", "unknown"))

    try:
        response = await async_client.chat.completions.create(
            model=settings.groq.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a warm, friendly restaurant assistant. "
                        "Keep responses concise (2-3 sentences max). "
                        "Sound natural and human-like."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=150,
        )

        response_text = (response.choices[0].message.content or "").strip()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Response generated: length=%d chars, time=%.0fms",
            len(response_text), elapsed_ms,
        )

        return {
            "response_text": response_text,
            "duration_ms": round(elapsed_ms, 1),
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Response generation failed: %s", str(e))

        # Fallback response
        items = order_json.get("items", [])
        if items:
            item_names = ", ".join(item.get("name", "item") for item in items)
            fallback = f"Got it! I've noted down {item_names} for you."
            if upsell_suggestion:
                fallback += f" Would you also like to add {upsell_suggestion}?"
        else:
            fallback = "Welcome! What can I get for you today?"

        return {
            "response_text": fallback,
            "duration_ms": round(elapsed_ms, 1),
            "fallback": True,
        }
