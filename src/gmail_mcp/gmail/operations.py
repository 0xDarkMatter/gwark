"""High-level Gmail operations with caching and pagination support."""

import logging
from typing import Any, Optional

from gmail_mcp.cache import EmailCache, PaginationManager
from gmail_mcp.config import get_settings
from gmail_mcp.gmail.client import GmailClient
from gmail_mcp.utils.validators import (
    validate_label_id,
    validate_message_id,
    validate_page_size,
)

logger = logging.getLogger(__name__)


class GmailOperations:
    """High-level Gmail operations with caching and smart pagination."""

    def __init__(
        self,
        client: GmailClient,
        cache: Optional[EmailCache] = None,
        pagination_manager: Optional[PaginationManager] = None,
    ):
        """Initialize Gmail operations.

        Args:
            client: Gmail API client
            cache: Email cache instance
            pagination_manager: Pagination manager
        """
        self.client = client
        self.settings = get_settings()

        # Initialize cache if enabled
        if self.settings.cache_enabled:
            self.cache = cache or EmailCache()
        else:
            self.cache = None

        self.pagination_manager = pagination_manager or PaginationManager()

        logger.info(f"Gmail operations initialized for account: {client.account_id}")

    async def search_emails(
        self,
        query: str,
        max_results: Optional[int] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Search emails with pagination support.

        Args:
            query: Gmail search query
            max_results: Maximum total results to return
            page_size: Results per page
            page_token: Page token for pagination
            use_cache: Whether to use cache

        Returns:
            Dictionary with messages, nextPageToken, and metadata
        """
        page_size = validate_page_size(page_size or self.settings.default_page_size)

        # Limit max_results
        if max_results and max_results > self.settings.max_results_per_search:
            max_results = self.settings.max_results_per_search
            logger.warning(
                f"max_results capped at {self.settings.max_results_per_search}"
            )

        # Execute search
        response = await self.client.list_messages(
            query=query,
            max_results=page_size,
            page_token=page_token,
        )

        messages = response.get("messages", [])
        next_page_token = response.get("nextPageToken")
        result_size_estimate = response.get("resultSizeEstimate", 0)

        # Enhance messages with cached metadata if available
        if use_cache and self.cache:
            enhanced_messages = []
            for msg in messages:
                message_id = msg["id"]
                cached = await self.cache.get_metadata(
                    self.client.account_id, message_id
                )
                if cached:
                    enhanced_messages.append(cached)
                else:
                    enhanced_messages.append(msg)
            messages = enhanced_messages

        return {
            "messages": messages,
            "nextPageToken": next_page_token,
            "resultSizeEstimate": result_size_estimate,
            "pageSize": page_size,
            "query": query,
        }

    async def read_email(
        self,
        message_id: str,
        format: str = "full",
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Read a specific email.

        Args:
            message_id: Gmail message ID
            format: Response format (full, metadata, minimal)
            use_cache: Whether to use cache

        Returns:
            Email message data
        """
        message_id = validate_message_id(message_id)

        # Check cache first
        if use_cache and self.cache:
            if format == "full":
                cached = await self.cache.get_content(
                    self.client.account_id, message_id
                )
            else:
                cached = await self.cache.get_metadata(
                    self.client.account_id, message_id
                )

            if cached:
                logger.debug(f"Cache hit for message {message_id}")
                return cached

        # Fetch from API
        message = await self.client.get_message(message_id, format=format)

        # Cache the result
        if use_cache and self.cache:
            if format == "full":
                await self.cache.set_content(
                    self.client.account_id, message_id, message
                )
            else:
                await self.cache.set_metadata(
                    self.client.account_id, message_id, message
                )

        return message

    async def get_email_headers(
        self,
        message_id: str,
        headers: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """Get specific headers from an email.

        Args:
            message_id: Gmail message ID
            headers: List of header names to retrieve

        Returns:
            Dictionary of header name -> value
        """
        message = await self.read_email(message_id, format="metadata")

        payload = message.get("payload", {})
        all_headers = payload.get("headers", [])

        if headers:
            header_dict = {
                h["name"]: h["value"]
                for h in all_headers
                if h["name"] in headers
            }
        else:
            header_dict = {h["name"]: h["value"] for h in all_headers}

        return header_dict

    async def apply_labels(
        self,
        message_id: str,
        label_ids: list[str],
        remove_labels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Apply labels to an email.

        Args:
            message_id: Gmail message ID
            label_ids: Label IDs to add
            remove_labels: Label IDs to remove

        Returns:
            Modified message
        """
        message_id = validate_message_id(message_id)
        label_ids = [validate_label_id(lid) for lid in label_ids]

        if remove_labels:
            remove_labels = [validate_label_id(lid) for lid in remove_labels]

        result = await self.client.modify_message(
            message_id=message_id,
            add_label_ids=label_ids if label_ids else None,
            remove_label_ids=remove_labels,
        )

        # Invalidate cache
        if self.cache:
            await self.cache.delete_metadata(self.client.account_id, message_id)
            await self.cache.delete_content(self.client.account_id, message_id)

        return result

    async def remove_labels(
        self,
        message_id: str,
        label_ids: list[str],
    ) -> dict[str, Any]:
        """Remove labels from an email.

        Args:
            message_id: Gmail message ID
            label_ids: Label IDs to remove

        Returns:
            Modified message
        """
        return await self.apply_labels(
            message_id=message_id,
            label_ids=[],
            remove_labels=label_ids,
        )

    async def mark_as_read(self, message_id: str) -> dict[str, Any]:
        """Mark an email as read.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return await self.remove_labels(message_id, ["UNREAD"])

    async def mark_as_unread(self, message_id: str) -> dict[str, Any]:
        """Mark an email as unread.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return await self.apply_labels(message_id, ["UNREAD"])

    async def archive(self, message_id: str) -> dict[str, Any]:
        """Archive an email (remove from INBOX).

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return await self.remove_labels(message_id, ["INBOX"])

    async def move_to_trash(self, message_id: str) -> dict[str, Any]:
        """Move email to trash.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return await self.apply_labels(message_id, ["TRASH"])

    async def star(self, message_id: str) -> dict[str, Any]:
        """Star an email.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return await self.apply_labels(message_id, ["STARRED"])

    async def unstar(self, message_id: str) -> dict[str, Any]:
        """Unstar an email.

        Args:
            message_id: Gmail message ID

        Returns:
            Modified message
        """
        return await self.remove_labels(message_id, ["STARRED"])

    async def list_labels(self) -> list[dict[str, Any]]:
        """List all labels for the account.

        Returns:
            List of label dictionaries
        """
        response = await self.client.list_labels()
        return response.get("labels", [])

    async def get_label(self, label_id: str) -> dict[str, Any]:
        """Get details about a specific label.

        Args:
            label_id: Label ID

        Returns:
            Label details
        """
        label_id = validate_label_id(label_id)
        return await self.client.get_label(label_id)

    async def get_profile(self) -> dict[str, Any]:
        """Get user profile information.

        Returns:
            User profile
        """
        return await self.client.get_profile()

    async def close(self) -> None:
        """Close operations and cleanup resources."""
        await self.client.close()

        if self.cache:
            await self.cache.close()

        logger.info("Gmail operations closed")
