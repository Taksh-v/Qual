"""
intelligence/session_memory.py
-------------------------------
V6.0 Lightweight Conversation Memory.

Maintains a rolling window of the last N query/response pairs per session.
This allows follow-up questions ("Tell me more about point 3") to work
naturally by injecting prior conversation context into the AnalystAgent.

Architecture:
  - In-memory dict keyed by session_id (no persistence).
  - Ring buffer of max 3 turns per session.
  - Thread-safe via Lock.
  - Auto-expires sessions after 30 minutes of inactivity.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_TURNS_PER_SESSION = 3
SESSION_EXPIRY_SECONDS = 1800  # 30 minutes


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    """A single query/response pair."""
    query: str
    response_summary: str  # First 500 chars of the response
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """A conversation session with a rolling turn history."""
    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

    def add_turn(self, query: str, response: str) -> None:
        """Add a turn, evicting the oldest if at capacity."""
        self.turns.append(ConversationTurn(
            query=query,
            response_summary=response[:500],
        ))
        if len(self.turns) > MAX_TURNS_PER_SESSION:
            self.turns.pop(0)
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > SESSION_EXPIRY_SECONDS

    def format_context(self) -> str:
        """Format prior turns into a prompt-injectable string."""
        if not self.turns:
            return ""
        parts = []
        for i, turn in enumerate(self.turns):
            parts.append(
                f"[Prior Turn {i+1}]\n"
                f"User asked: {turn.query}\n"
                f"System responded: {turn.response_summary}\n"
            )
        return "### 💬 CONVERSATION HISTORY (prior turns)\n" + "\n".join(parts)


# ── Global Session Store ──────────────────────────────────────────────────────

_sessions: dict[str, Session] = {}
_lock = Lock()


def get_session(session_id: str) -> Session:
    """Get or create a session."""
    with _lock:
        _cleanup_expired()
        if session_id not in _sessions:
            _sessions[session_id] = Session(session_id=session_id)
        return _sessions[session_id]


def record_turn(session_id: str, query: str, response: str) -> None:
    """Record a completed query/response turn."""
    session = get_session(session_id)
    session.add_turn(query, response)
    logger.debug("[SessionMemory] Recorded turn for session %s (total: %d)", session_id[:8], len(session.turns))


def get_conversation_context(session_id: str) -> str:
    """Get formatted prior conversation context for prompt injection."""
    session = get_session(session_id)
    return session.format_context()


def _cleanup_expired() -> None:
    """Remove expired sessions (called under lock)."""
    expired = [sid for sid, s in _sessions.items() if s.is_expired()]
    for sid in expired:
        del _sessions[sid]
    if expired:
        logger.debug("[SessionMemory] Cleaned up %d expired sessions.", len(expired))
