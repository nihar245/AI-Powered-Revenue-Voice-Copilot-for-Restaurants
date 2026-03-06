"""
WebSocket connection manager for real-time event streaming.

Manages admin dashboard connections and broadcasts pipeline events
(call_started, transcript_received, items_detected, etc.).
"""

import json
import time
import logging
from datetime import datetime, timezone
from typing import Any
from enum import Enum

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Pipeline event types broadcast via WebSocket."""
    CALL_STARTED = "call_started"
    TRANSCRIPT_RECEIVED = "transcript_received"
    ITEMS_DETECTED = "items_detected"
    UPSELL_SUGGESTED = "upsell_suggested"
    RESPONSE_GENERATED = "response_generated"
    ORDER_CONFIRMED = "order_confirmed"
    PIPELINE_ERROR = "pipeline_error"
    PIPELINE_COMPLETE = "pipeline_complete"


class ConnectionManager:
    """
    Manages WebSocket connections for the admin dashboard.
    
    Supports multiple concurrent admin connections and broadcasts
    real-time pipeline events to all connected clients.
    """

    def __init__(self, max_connections: int = 50) -> None:
        self._active_connections: list[WebSocket] = []
        self._max_connections = max_connections
        self._event_log: list[dict] = []  # Recent events buffer
        self._max_log_size = 100

    @property
    def active_count(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> bool:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.

        Returns:
            bool: True if connected, False if max connections reached.
        """
        if len(self._active_connections) >= self._max_connections:
            logger.warning("Max WebSocket connections reached (%d)", self._max_connections)
            await websocket.close(code=1013, reason="Max connections reached")
            return False

        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info(
            "WebSocket connected. Active connections: %d",
            len(self._active_connections),
        )
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: The connection to remove.
        """
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        logger.info(
            "WebSocket disconnected. Active connections: %d",
            len(self._active_connections),
        )

    async def broadcast(self, event_type: EventType, data: Any = None) -> None:
        """
        Broadcast an event to all connected admin clients.

        Args:
            event_type: The type of pipeline event.
            data: Event payload (will be JSON serialized).
        """
        event = {
            "event": event_type.value,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Buffer event in log
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        message = json.dumps(event, default=str)

        disconnected = []
        for connection in self._active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning("Failed to send to WebSocket: %s", str(e))
                disconnected.append(connection)

        # Clean up dead connections
        for conn in disconnected:
            self.disconnect(conn)

        logger.debug(
            "Broadcast event '%s' to %d clients",
            event_type.value, len(self._active_connections),
        )

    async def send_personal(self, websocket: WebSocket, event_type: EventType, data: Any = None) -> None:
        """
        Send an event to a specific client.

        Args:
            websocket: Target connection.
            event_type: Event type.
            data: Event payload.
        """
        event = {
            "event": event_type.value,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await websocket.send_text(json.dumps(event, default=str))
        except Exception as e:
            logger.warning("Failed to send personal message: %s", str(e))
            self.disconnect(websocket)

    def get_recent_events(self, limit: int = 20) -> list[dict]:
        """
        Get recent event log (useful for new connections to catch up).

        Args:
            limit: Number of recent events to return.

        Returns:
            list[dict]: Recent events in chronological order.
        """
        return self._event_log[-limit:]


# Singleton instance
ws_manager = ConnectionManager()
