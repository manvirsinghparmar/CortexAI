"""
ConversationManager - In-memory conversation history management with database integration.

Maintains chat history as a list of messages with role/content format.
Supports automatic trimming to prevent context overflow.
Can load conversation history from database for session continuity.
"""

import os
from uuid import UUID

from utils.logger import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    Manages conversation history for multi-turn chat interactions.

    Messages are stored in a standardized format:
    {"role": "system|user|assistant", "content": str}

    Features:
    - Automatic trimming when exceeding max_messages
    - Preserves system prompt at the beginning
    - Thread-safe for single-threaded CLI usage
    """

    def __init__(self, max_messages: int | None = None, system_prompt: str | None = None, db=None):
        """
        Initialize ConversationManager.

        Args:
            max_messages: Maximum number of messages to keep (excluding system prompt).
                         If None, reads from MAX_CONTEXT_MESSAGES env var (default 20).
            system_prompt: Optional system prompt to prepend to all conversations.
            db: Optional database session for loading history from DB.
        """
        if max_messages is None:
            max_messages = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

        self.max_messages = max_messages
        self.system_prompt = system_prompt
        self.messages: list[dict[str, str]] = []
        self.db = db
        self.session_id: UUID | None = None

        # Add system prompt if provided
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})
            logger.info(
                f"Initialized ConversationManager with system prompt (max_messages={max_messages})"
            )
        else:
            logger.info(
                f"Initialized ConversationManager without system prompt (max_messages={max_messages})"
            )

    def add_user(self, text: str) -> None:
        """
        Add a user message to the conversation.

        Args:
            text: The user's message content
        """
        if not text or not text.strip():
            logger.warning("Attempted to add empty user message")
            return

        self.messages.append({"role": "user", "content": text.strip()})
        logger.debug(f"Added user message (total messages: {len(self.messages)})")
        self._auto_trim()

    def add_assistant(self, text: str) -> None:
        """
        Add an assistant message to the conversation.

        Args:
            text: The assistant's response content
        """
        if not text or not text.strip():
            logger.warning("Attempted to add empty assistant message")
            return

        self.messages.append({"role": "assistant", "content": text.strip()})
        logger.debug(f"Added assistant message (total messages: {len(self.messages)})")
        self._auto_trim()

    def add_system(self, text: str) -> None:
        """
        Add a system message to the conversation.

        Note: System messages are typically used at the start of a conversation.
        This adds a system message at the current position.

        Args:
            text: The system message content
        """
        if not text or not text.strip():
            logger.warning("Attempted to add empty system message")
            return

        self.messages.append({"role": "system", "content": text.strip()})
        logger.debug(f"Added system message (total messages: {len(self.messages)})")
        self._auto_trim()

    def get_messages(self) -> list[dict[str, str]]:
        """
        Get all messages in the conversation.

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        return self.messages.copy()

    def pop_last_user(self) -> dict[str, str] | None:
        """
        Remove and return the most recent user message.

        This is useful when a request fails and you want to remove
        the user message that caused the error.

        Returns:
            The removed user message dict, or None if no user message found
        """
        # Find the last user message
        for i in range(len(self.messages) - 1, -1, -1):
            if self.messages[i]["role"] == "user":
                removed = self.messages.pop(i)
                logger.debug(f"Removed last user message (total messages: {len(self.messages)})")
                return removed

        logger.warning("Attempted to pop last user message but none found")
        return None

    def reset(self, keep_system_prompt: bool = True) -> None:
        """
        Clear all conversation history.

        Args:
            keep_system_prompt: If True, preserves the system prompt.
                               If False, clears everything including system prompt.
        """
        if keep_system_prompt and self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
            logger.info("Reset conversation (kept system prompt)")
        else:
            self.messages = []
            logger.info("Reset conversation (cleared all messages)")

    def get_message_count(self) -> int:
        """
        Get the total number of messages (including system prompt).

        Returns:
            Total message count
        """
        return len(self.messages)

    def get_conversation_summary(self, last_n: int = 10) -> str:
        """
        Get a formatted summary of the last N messages.

        Args:
            last_n: Number of recent messages to include

        Returns:
            Formatted string showing the conversation history
        """
        if not self.messages:
            return "No conversation history"

        recent_messages = self.messages[-last_n:] if last_n < len(self.messages) else self.messages

        lines = []
        lines.append(
            f"=== Conversation History (showing last {len(recent_messages)} of {len(self.messages)} messages) ==="
        )

        for i, msg in enumerate(recent_messages, 1):
            role = msg["role"].upper()
            content = msg["content"]

            # Truncate long messages
            if len(content) > 100:
                content = content[:97] + "..."

            lines.append(f"{i}. [{role}] {content}")

        return "\n".join(lines)

    def _auto_trim(self) -> None:
        """
        Automatically trim old messages when exceeding max_messages.

        Preserves the system prompt (if present) and removes oldest messages first.
        System prompt is NOT counted toward max_messages limit.
        """
        # Count non-system messages
        has_system = len(self.messages) > 0 and self.messages[0]["role"] == "system"
        system_offset = 1 if has_system else 0
        non_system_count = len(self.messages) - system_offset

        if non_system_count > self.max_messages:
            # Calculate how many to remove
            to_remove = non_system_count - self.max_messages

            # Remove oldest messages (after system prompt)
            if has_system:
                self.messages = [
                    self.messages[0],
                    *self.messages[system_offset + to_remove :],
                ]
            else:
                self.messages = self.messages[to_remove:]

            logger.info(
                f"Auto-trimmed conversation: removed {to_remove} old messages (current: {len(self.messages)})"
            )

    def set_session(self, session_id: UUID, db) -> None:
        """
        Set the session and load history from database.

        Args:
            session_id: Session ID to load
            db: Database session
        """
        self.session_id = session_id
        self.db = db
        self.load_history_from_db(limit=self.max_messages)

    def load_history_from_db(self, limit: int = 10) -> None:
        """
        Load conversation history from database.

        Args:
            limit: Number of recent messages to load
        """
        if not self.db or not self.session_id:
            logger.debug("Cannot load history: no db session or session_id")
            return

        try:
            from db.repository import get_session_messages

            messages = get_session_messages(self.db, self.session_id, limit=limit)

            # Preserve system prompt if present
            has_system = len(self.messages) > 0 and self.messages[0]["role"] == "system"
            system_msg = self.messages[0] if has_system else None

            # Convert DB messages to conversation manager format
            self.messages = []
            if system_msg:
                self.messages.append(system_msg)

            for msg in messages:
                self.messages.append({"role": msg["role"], "content": msg["content"]})

            logger.info(
                f"Loaded {len(messages)} messages from database for session {self.session_id}"
            )

        except Exception as e:
            logger.error(f"Failed to load conversation history from database: {e}")
            # Continue without history - don't crash the app

    def __repr__(self) -> str:
        """String representation of ConversationManager."""
        return f"ConversationManager(messages={len(self.messages)}, max={self.max_messages})"
