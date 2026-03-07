"""
In-memory session store for dialogue state.

Keyed by session_id (UUID string). Each session holds:
  - cart:           list of cart item dicts
  - state:          DialogueState enum value
  - language:       "en" | "hi" | "gu"
  - last_intent:    str | None
  - last_response:  str
  - turn:           int  (incremented each voice turn)
  - table_id:       str
"""

from __future__ import annotations

from models.schemas import DialogueState

_store: dict[str, dict] = {}


def _default(session_id: str, table_id: str = "") -> dict:
    return {
        "session_id":   session_id,
        "table_id":     table_id,
        "state":        DialogueState.GREETING,
        "cart":         [],
        "language":     "en",
        "last_intent":  None,
        "last_response": "",
        "turn":         0,
        # ── Customer info ────────────────────────────────────────────────────
        "customer_name": None,  # str | None — collected during greeting turn
        # ── Clarification state ──────────────────────────────────────────────
        "pending_clarification": None,   # str | None — question awaiting answer
        "pending_ambiguous_item": None,  # dict | None — item that triggered clarification
        # ── Upsell / combo tracking ──────────────────────────────────────────
        "pending_upsell":   None,   # str | None — item name currently being offered
        "upsells_shown":    [],     # list[str]  — upsell texts already shown
        "combos_shown":     [],     # list[str]  — combo names already announced
        # ── Order tracking ───────────────────────────────────────────────────
        "confirmed_order_number": None,  # str | None — last confirmed order number
    }


def get_session(session_id: str, table_id: str = "") -> dict:
    if session_id not in _store:
        _store[session_id] = _default(session_id, table_id)
    return _store[session_id]


def update_session(session_id: str, data: dict) -> dict:
    session = get_session(session_id)
    session.update(data)
    return session


def reset_session(session_id: str) -> None:
    if session_id in _store:
        table_id = _store[session_id].get("table_id", "")
        _store[session_id] = _default(session_id, table_id)


def delete_session(session_id: str) -> None:
    _store.pop(session_id, None)
