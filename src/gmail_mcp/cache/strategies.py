"""Cache invalidation strategies."""

import logging
from enum import Enum
from typing import Set

logger = logging.getLogger(__name__)


class InvalidationStrategy(Enum):
    """Cache invalidation strategies."""

    TTL = "ttl"  # Time-based expiration
    LABEL_CHANGE = "label_change"  # Invalidate when labels change
    MANUAL = "manual"  # Manual invalidation only


class CacheInvalidator:
    """Manages cache invalidation based on different strategies."""

    def __init__(self):
        """Initialize cache invalidator."""
        self.tracked_messages: dict[str, Set[str]] = {}  # account_id -> set of message_ids
        logger.info("Cache invalidator initialized")

    async def track_message(self, account_id: str, message_id: str) -> None:
        """Track a message for potential invalidation.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID
        """
        if account_id not in self.tracked_messages:
            self.tracked_messages[account_id] = set()

        self.tracked_messages[account_id].add(message_id)

    async def should_invalidate_on_label_change(
        self, account_id: str, message_id: str, old_labels: list[str], new_labels: list[str]
    ) -> bool:
        """Check if cache should be invalidated due to label changes.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID
            old_labels: Previous labels
            new_labels: New labels

        Returns:
            True if cache should be invalidated
        """
        # Invalidate if labels changed
        if set(old_labels) != set(new_labels):
            logger.debug(f"Labels changed for {message_id}, invalidating cache")
            return True

        return False

    async def invalidate_search_results_on_label_change(
        self, account_id: str, label_id: str
    ) -> list[str]:
        """Get search queries that should be invalidated when a label changes.

        Args:
            account_id: Account identifier
            label_id: Gmail label ID that changed

        Returns:
            List of query hashes to invalidate
        """
        # In a real implementation, we would track which queries involve which labels
        # For now, we'll just return an empty list
        # Future enhancement: track query -> label dependencies
        logger.debug(f"Label {label_id} changed for {account_id}")
        return []

    def get_tracked_count(self, account_id: str) -> int:
        """Get number of tracked messages for an account.

        Args:
            account_id: Account identifier

        Returns:
            Number of tracked messages
        """
        return len(self.tracked_messages.get(account_id, set()))

    def clear_tracked(self, account_id: str) -> None:
        """Clear tracked messages for an account.

        Args:
            account_id: Account identifier
        """
        if account_id in self.tracked_messages:
            del self.tracked_messages[account_id]
            logger.debug(f"Cleared tracked messages for {account_id}")
