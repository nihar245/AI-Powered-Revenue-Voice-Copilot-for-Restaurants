from __future__ import annotations

import asyncio

import torch
from sentence_transformers import SentenceTransformer, util

from models.schemas import Intent

_model: SentenceTransformer | None = None
_intent_labels: list[Intent] = []
_intent_embeddings: torch.Tensor | None = None

# ─── Training utterances per intent ──────────────────────────────────────────
_INTENT_EXAMPLES: dict[Intent, list[str]] = {
    Intent.GREETING: [
        "hello", "hi there", "namaste", "good morning", "hey",
        "kem cho", "namaskar", "good evening",
    ],
    Intent.ADD_ITEM: [
        "I want paneer butter masala",
        "ek dosa dena",
        "two pizzas please",
        "mujhe butter naan chahiye",
        "give me idli sambar",
        "order karna chahta hoon",
        "can I have masala dosa",
        "pizza laao",
        "mujhe do chai chahiye",
        "garlic naan de dena",
    ],
    Intent.REMOVE_ITEM: [
        "remove naan",
        "don't want pizza",
        "nahi chahiye dosa",
        "cancel the pasta",
        "hatao pizza",
        "wapas karo naan",
    ],
    Intent.VIEW_MENU: [
        "show me the menu",
        "what do you have",
        "kya kya milta hai",
        "menu dikhao",
        "what can I order",
        "aapke paas kya hai",
    ],
    Intent.VIEW_CART: [
        "what did I order",
        "show my cart",
        "mera order kya hai",
        "total batao",
        "what's in my order",
        "kitna hua",
    ],
    Intent.CONFIRM_ORDER: [
        "yes confirm",
        "that's all",
        "place my order",
        "haan theek hai",
        "bas kar do",
        "confirm order",
        "done",
        "ho gaya",
    ],
    Intent.CANCEL_ORDER: [
        "cancel everything",
        "nahi chahiye kuch bhi",
        "forget it",
        "sab cancel karo",
        "I want to cancel",
        "rehne do",
    ],
    Intent.ENQUIRE_PRICE: [
        "how much is paneer butter masala",
        "price of pizza",
        "kitne ka hai dosa",
        "dosa ka rate kya hai",
        "what does naan cost",
    ],
}


def load_classifier() -> None:
    global _model, _intent_labels, _intent_embeddings
    print("[NLU] Loading sentence-transformer (paraphrase-multilingual-MiniLM-L12-v2)...")
    _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    all_texts: list[str] = []
    for intent, examples in _INTENT_EXAMPLES.items():
        for ex in examples:
            _intent_labels.append(intent)
            all_texts.append(ex)

    # Pre-compute and cache all example embeddings
    _intent_embeddings = _model.encode(all_texts, convert_to_tensor=True)
    print(f"[NLU] Classifier ready — {len(all_texts)} example embeddings cached.")


def is_loaded() -> bool:
    return _model is not None


def classify(text: str, threshold: float = 0.45) -> tuple[Intent, float]:
    """
    Semantic similarity fallback — used when rule_engine returns UNKNOWN.

    Returns:
        (Intent, similarity_score)
    """
    if _model is None or _intent_embeddings is None:
        return Intent.UNKNOWN, 0.0

    query_emb = _model.encode(text, convert_to_tensor=True)
    scores    = util.cos_sim(query_emb, _intent_embeddings)[0]
    best_idx  = int(scores.argmax())
    best_score = float(scores[best_idx])

    if best_score < threshold:
        return Intent.UNKNOWN, best_score

    return _intent_labels[best_idx], best_score


async def find_best_menu_match_async(
    query: str, menu_names: list[str]
) -> tuple[int, float]:
    """
    Finds the best matching menu item for a spoken item name.
    Runs in a thread pool to avoid blocking the event loop.

    Returns:
        (index_of_best_match, similarity_score)
    """
    if _model is None or not menu_names:
        return 0, 0.0

    loop = asyncio.get_event_loop()

    def _encode_and_match() -> tuple[int, float]:
        query_emb = _model.encode(query, convert_to_tensor=True)
        menu_embs = _model.encode(menu_names, convert_to_tensor=True)
        scores    = util.cos_sim(query_emb, menu_embs)[0]
        best_idx  = int(scores.argmax())
        return best_idx, float(scores[best_idx])

    return await loop.run_in_executor(None, _encode_and_match)
