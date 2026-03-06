"""
Conversation session manager for real-time multi-turn voice calls.

Maintains per-session chat history, order state, and language
preference so the AI agent remembers all previous exchanges
within a single call.
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OrderItem:
    """A single validated order item."""
    name: str
    quantity: int
    modifications: list[str] = field(default_factory=list)
    price: float = 0.0


@dataclass
class ConversationTurn:
    """One user↔agent exchange in the conversation."""
    role: str           # "customer" or "agent"
    text: str
    timestamp: float = field(default_factory=time.time)
    audio_size: int = 0  # bytes of audio, 0 if text-only


@dataclass
class ConversationSession:
    """
    Represents a single phone-call conversation.

    Stores the full chat history, running order state, 
    detected language, and session metadata.
    """
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    language: str = "en"            # detected from first audio
    status: str = "active"          # active | ended | error
    turns: list[ConversationTurn] = field(default_factory=list)
    current_order: list[OrderItem] = field(default_factory=list)
    upsell_offered: list[str] = field(default_factory=list)
    total_amount: float = 0.0
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # History management
    # ------------------------------------------------------------------ #
    def add_customer_turn(self, text: str, audio_size: int = 0) -> None:
        """Record what the customer said."""
        self.turns.append(ConversationTurn(
            role="customer", text=text, audio_size=audio_size,
        ))

    def add_agent_turn(self, text: str) -> None:
        """Record what the agent responded."""
        self.turns.append(ConversationTurn(role="agent", text=text))

    def get_chat_history(self) -> list[dict]:
        """
        Return chat history formatted for the LLM context window.

        Returns:
            list[dict]: [{"role": "user"/"assistant", "content": str}, ...]
        """
        history = []
        for turn in self.turns:
            role = "user" if turn.role == "customer" else "assistant"
            history.append({"role": role, "content": turn.text})
        return history

    def get_history_text(self) -> str:
        """Plain-text summary of conversation so far."""
        lines = []
        for turn in self.turns:
            prefix = "Customer" if turn.role == "customer" else "Agent"
            lines.append(f"{prefix}: {turn.text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Order management
    # ------------------------------------------------------------------ #
    def update_order(self, items: list[dict]) -> None:
        """
        Merge newly detected items into the running order.

        If a customer says "also add one coke", the coke is added
        to whatever was ordered before in this call.
        """
        for item in items:
            # Check if item already in order
            existing = next(
                (o for o in self.current_order if o.name.lower() == item["name"].lower()),
                None,
            )
            if existing:
                existing.quantity += item.get("quantity", 1)
                existing.modifications.extend(item.get("modifications", []))
            else:
                self.current_order.append(OrderItem(
                    name=item["name"],
                    quantity=item.get("quantity", 1),
                    modifications=item.get("modifications", []),
                    price=item.get("price", 0.0),
                ))
        self._recalculate_total()

    def remove_item(self, item_name: str) -> bool:
        """Remove an item from the order by name."""
        before = len(self.current_order)
        self.current_order = [
            o for o in self.current_order
            if o.name.lower() != item_name.lower()
        ]
        removed = len(self.current_order) < before
        if removed:
            self._recalculate_total()
        return removed

    def clear_order(self) -> None:
        """Clear the entire order."""
        self.current_order.clear()
        self.total_amount = 0.0

    def _recalculate_total(self) -> None:
        self.total_amount = sum(o.price * o.quantity for o in self.current_order)

    def get_order_summary(self) -> dict:
        """Get a serializable order summary."""
        return {
            "items": [
                {
                    "name": o.name,
                    "quantity": o.quantity,
                    "modifications": o.modifications,
                    "price": o.price,
                    "subtotal": o.price * o.quantity,
                }
                for o in self.current_order
            ],
            "total": round(self.total_amount, 2),
            "item_count": sum(o.quantity for o in self.current_order),
        }

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #
    def end_session(self) -> dict:
        """Mark session ended and return final summary."""
        self.status = "ended"
        return {
            "session_id": self.session_id,
            "status": "ended",
            "language": self.language,
            "total_turns": len(self.turns),
            "order": self.get_order_summary(),
            "conversation": self.get_history_text(),
            "duration_seconds": round(
                self.turns[-1].timestamp - self.turns[0].timestamp, 1
            ) if len(self.turns) >= 2 else 0,
        }

    def to_dict(self) -> dict:
        """Full session state as dict."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "status": self.status,
            "language": self.language,
            "turns": len(self.turns),
            "order": self.get_order_summary(),
            "warnings": self.warnings,
        }


# ====================================================================== #
# Session Store (in-memory; replace with Redis for production)
# ====================================================================== #
class SessionStore:
    """
    In-memory store for active conversation sessions.
    
    TODO: Replace with Redis for horizontal scaling.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}

    def create_session(self) -> ConversationSession:
        session = ConversationSession()
        self._sessions[session.session_id] = session
        logger.info("Session created: %s", session.session_id)
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[dict]:
        session = self._sessions.get(session_id)
        if session:
            summary = session.end_session()
            logger.info("Session ended: %s (%d turns)", session_id, len(session.turns))
            return summary
        return None

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def get_active_sessions(self) -> list[dict]:
        return [
            s.to_dict() for s in self._sessions.values()
            if s.status == "active"
        ]

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.status == "active")


# Singleton session store
session_store = SessionStore()
