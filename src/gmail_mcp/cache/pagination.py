"""Pagination state management for large email result sets."""

import asyncio
import logging
from typing import Any, Optional

from gmail_mcp.config import get_settings
from gmail_mcp.config.constants import DEFAULT_PAGE_SIZE

logger = logging.getLogger(__name__)


class PaginationState:
    """Represents the state of a pagination cursor."""

    def __init__(
        self,
        query: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        page_token: Optional[str] = None,
        total_results: Optional[int] = None,
    ):
        """Initialize pagination state.

        Args:
            query: Gmail search query
            page_size: Number of results per page
            page_token: Current page token
            total_results: Total number of results (estimated)
        """
        self.query = query
        self.page_size = page_size
        self.page_token = page_token
        self.total_results = total_results
        self.fetched_count = 0
        self.current_page = 0

    def update(
        self,
        page_token: Optional[str],
        fetched_count: int,
        total_results: Optional[int] = None,
    ) -> None:
        """Update pagination state after fetching a page.

        Args:
            page_token: Next page token
            fetched_count: Number of results fetched in this page
            total_results: Updated total results estimate
        """
        self.page_token = page_token
        self.fetched_count += fetched_count
        self.current_page += 1
        if total_results is not None:
            self.total_results = total_results

    def has_more(self) -> bool:
        """Check if there are more pages to fetch.

        Returns:
            True if more pages exist
        """
        return self.page_token is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "query": self.query,
            "page_size": self.page_size,
            "page_token": self.page_token,
            "total_results": self.total_results,
            "fetched_count": self.fetched_count,
            "current_page": self.current_page,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaginationState":
        """Create PaginationState from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            PaginationState instance
        """
        state = cls(
            query=data["query"],
            page_size=data["page_size"],
            page_token=data.get("page_token"),
            total_results=data.get("total_results"),
        )
        state.fetched_count = data.get("fetched_count", 0)
        state.current_page = data.get("current_page", 0)
        return state


class PaginationManager:
    """Manages pagination state for multiple concurrent searches."""

    def __init__(self):
        """Initialize pagination manager."""
        self.states: dict[str, PaginationState] = {}
        self._lock = asyncio.Lock()
        self.settings = get_settings()
        logger.info("Pagination manager initialized")

    def _generate_state_key(self, account_id: str, query: str) -> str:
        """Generate a unique key for a pagination state.

        Args:
            account_id: Account identifier
            query: Search query

        Returns:
            Unique state key
        """
        # Use hash of query to create a unique key
        query_hash = str(hash(query))
        return f"{account_id}:{query_hash}"

    async def create_state(
        self,
        account_id: str,
        query: str,
        page_size: Optional[int] = None,
    ) -> str:
        """Create a new pagination state.

        Args:
            account_id: Account identifier
            query: Gmail search query
            page_size: Results per page

        Returns:
            State key for tracking
        """
        page_size = page_size or self.settings.default_page_size
        state_key = self._generate_state_key(account_id, query)

        async with self._lock:
            state = PaginationState(query=query, page_size=page_size)
            self.states[state_key] = state

        logger.debug(f"Created pagination state: {state_key}")
        return state_key

    async def get_state(self, state_key: str) -> Optional[PaginationState]:
        """Get pagination state by key.

        Args:
            state_key: State key

        Returns:
            PaginationState or None if not found
        """
        async with self._lock:
            return self.states.get(state_key)

    async def update_state(
        self,
        state_key: str,
        page_token: Optional[str],
        fetched_count: int,
        total_results: Optional[int] = None,
    ) -> None:
        """Update pagination state after fetching results.

        Args:
            state_key: State key
            page_token: Next page token
            fetched_count: Number of results fetched
            total_results: Total results estimate
        """
        async with self._lock:
            if state_key in self.states:
                self.states[state_key].update(page_token, fetched_count, total_results)
                logger.debug(f"Updated pagination state: {state_key}")

    async def delete_state(self, state_key: str) -> None:
        """Delete pagination state.

        Args:
            state_key: State key
        """
        async with self._lock:
            if state_key in self.states:
                del self.states[state_key]
                logger.debug(f"Deleted pagination state: {state_key}")

    async def clear_account_states(self, account_id: str) -> None:
        """Clear all pagination states for an account.

        Args:
            account_id: Account identifier
        """
        async with self._lock:
            # Find all states for this account
            keys_to_delete = [
                key for key in self.states.keys() if key.startswith(f"{account_id}:")
            ]

            for key in keys_to_delete:
                del self.states[key]

            if keys_to_delete:
                logger.info(f"Cleared {len(keys_to_delete)} pagination states for {account_id}")

    async def get_stats(self) -> dict[str, Any]:
        """Get pagination statistics.

        Returns:
            Dictionary with stats
        """
        async with self._lock:
            total_states = len(self.states)
            active_states = sum(1 for state in self.states.values() if state.has_more())

            return {
                "total_states": total_states,
                "active_states": active_states,
                "inactive_states": total_states - active_states,
            }

    async def cleanup_completed(self) -> int:
        """Remove completed pagination states (no more pages).

        Returns:
            Number of states removed
        """
        async with self._lock:
            keys_to_delete = [
                key for key, state in self.states.items() if not state.has_more()
            ]

            for key in keys_to_delete:
                del self.states[key]

            if keys_to_delete:
                logger.info(f"Cleaned up {len(keys_to_delete)} completed pagination states")

            return len(keys_to_delete)


class PaginationHelper:
    """Helper utilities for working with paginated results."""

    @staticmethod
    def calculate_pages(total_results: int, page_size: int) -> int:
        """Calculate number of pages needed.

        Args:
            total_results: Total number of results
            page_size: Results per page

        Returns:
            Number of pages
        """
        return (total_results + page_size - 1) // page_size

    @staticmethod
    def get_page_range(page: int, page_size: int) -> tuple[int, int]:
        """Get result range for a specific page.

        Args:
            page: Page number (0-indexed)
            page_size: Results per page

        Returns:
            Tuple of (start_index, end_index)
        """
        start = page * page_size
        end = start + page_size
        return start, end

    @staticmethod
    def create_pagination_metadata(
        current_page: int,
        page_size: int,
        total_results: Optional[int],
        has_more: bool,
    ) -> dict[str, Any]:
        """Create pagination metadata for responses.

        Args:
            current_page: Current page number
            page_size: Results per page
            total_results: Total number of results
            has_more: Whether more pages exist

        Returns:
            Pagination metadata dictionary
        """
        metadata = {
            "current_page": current_page,
            "page_size": page_size,
            "has_more": has_more,
        }

        if total_results is not None:
            metadata["total_results"] = total_results
            metadata["total_pages"] = PaginationHelper.calculate_pages(
                total_results, page_size
            )

        return metadata
