"""
Session Store — single source of truth for dialogue state across turns.

Replaces the ad-hoc session dict in state_machine.py with a clean
get / update / reset interface that state_machine.py delegates to.
"""

from __future__ import annotations

from models.schemas import DialogueState, Intent

# ─── Session schema ────────────────────────────────────────────────────────────
# Each session is a plain dict (easy to serialise to Redis later if needed).
#
# {
#   "session_id":              str,
#   "table_id":                str,
#   "state":                   DialogueState (str enum value),
#   "cart":                    list[dict],
#   "language":                str,
#   "last_intent":             str | None,
#   "last_response":           str,
#   "clarification_context":   dict,
# }

_store: dict[str, dict] = {}


def _default_session(session_id: str, table_id: str = "") -> dict:
    return {
        "session_id":            session_id,
        "table_id":              table_id,
        "state":                 DialogueState.GREETING,
        "cart":                  [],
        "language":              "en",
        "last_intent":           None,
        "last_response":         "",
        "clarification_context": {},
    }


# ─── Public API ────────────────────────────────────────────────────────────────

def get_session(session_id: str, table_id: str = "") -> dict:
    """Returns existing session or creates a new one."""
    if session_id not in _store:
        _store[session_id] = _default_session(session_id, table_id)
    return _store[session_id]


def update_session(session_id: str, data: dict) -> dict:
    """
    Merges `data` into the existing session and returns the updated session.
    Creates the session if it does not exist.
    """
    session = get_session(session_id)
    session.update(data)
    return session


def reset_session(session_id: str) -> None:
    """Resets session to initial GREETING state, clearing the cart."""
    if session_id in _store:
        table_id = _store[session_id].get("table_id", "")
        _store[session_id] = _default_session(session_id, table_id)


def delete_session(session_id: str) -> None:
    """Removes session entirely (use after order is placed)."""
    _store.pop(session_id, None)


def all_sessions() -> dict[str, dict]:
    """Returns a shallow copy of the full store (for debugging / health checks)."""
    return dict(_store)
