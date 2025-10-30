"""Batch operations for handling multiple emails efficiently."""

import asyncio
import logging
from typing import Any, Callable, Optional

from gmail_mcp.config import get_settings
from gmail_mcp.gmail.client import GmailClient
from gmail_mcp.utils.validators import (
    validate_batch_size,
    validate_label_id,
    validate_message_id,
)

logger = logging.getLogger(__name__)


class BatchOperations:
    """Efficient batch operations for Gmail."""

    def __init__(self, client: GmailClient, max_concurrent: int = 5):
        """Initialize batch operations.

        Args:
            client: Gmail API client
            max_concurrent: Maximum concurrent operations
        """
        self.client = client
        self.settings = get_settings()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(
            f"Batch operations initialized: max_concurrent={max_concurrent}"
        )

    async def _execute_with_semaphore(
        self, coro: Callable[[], Any]
    ) -> tuple[bool, Any]:
        """Execute coroutine with semaphore limiting.

        Args:
            coro: Coroutine to execute

        Returns:
            Tuple of (success, result_or_error)
        """
        async with self.semaphore:
            try:
                result = await coro()
                return True, result
            except Exception as e:
                logger.error(f"Batch operation failed: {e}")
                return False, str(e)

    async def batch_read(
        self,
        message_ids: list[str],
        format: str = "metadata",
    ) -> dict[str, Any]:
        """Read multiple emails in parallel.

        Args:
            message_ids: List of message IDs
            format: Response format

        Returns:
            Dictionary with successful and failed reads
        """
        # Validate inputs
        message_ids = [validate_message_id(mid) for mid in message_ids]
        batch_size = len(message_ids)
        validate_batch_size(batch_size)

        logger.info(f"Batch read: {batch_size} messages")

        # Create tasks
        tasks = [
            self._execute_with_semaphore(
                lambda mid=mid: self.client.get_message(mid, format=format)
            )
            for mid in message_ids
        ]

        # Execute in parallel
        results = await asyncio.gather(*tasks)

        # Separate successful and failed
        successful = {}
        failed = {}

        for message_id, (success, result) in zip(message_ids, results):
            if success:
                successful[message_id] = result
            else:
                failed[message_id] = result

        logger.info(
            f"Batch read complete: {len(successful)} successful, {len(failed)} failed"
        )

        return {
            "successful": successful,
            "failed": failed,
            "total": batch_size,
            "success_count": len(successful),
            "failure_count": len(failed),
        }

    async def batch_apply_labels(
        self,
        message_ids: list[str],
        add_label_ids: Optional[list[str]] = None,
        remove_label_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Apply labels to multiple emails.

        Args:
            message_ids: List of message IDs
            add_label_ids: Labels to add
            remove_label_ids: Labels to remove

        Returns:
            Dictionary with operation results
        """
        # Validate inputs
        message_ids = [validate_message_id(mid) for mid in message_ids]
        batch_size = len(message_ids)
        validate_batch_size(batch_size)

        if add_label_ids:
            add_label_ids = [validate_label_id(lid) for lid in add_label_ids]
        if remove_label_ids:
            remove_label_ids = [validate_label_id(lid) for lid in remove_label_ids]

        logger.info(f"Batch label operation: {batch_size} messages")

        # Use Gmail's batchModify API for better efficiency
        try:
            await self.client.batch_modify(
                message_ids=message_ids,
                add_label_ids=add_label_ids,
                remove_label_ids=remove_label_ids,
            )

            return {
                "successful": message_ids,
                "failed": {},
                "total": batch_size,
                "success_count": batch_size,
                "failure_count": 0,
            }

        except Exception as e:
            logger.error(f"Batch modify failed: {e}")
            # Fall back to individual operations
            return await self._fallback_batch_label(
                message_ids, add_label_ids, remove_label_ids
            )

    async def _fallback_batch_label(
        self,
        message_ids: list[str],
        add_label_ids: Optional[list[str]],
        remove_label_ids: Optional[list[str]],
    ) -> dict[str, Any]:
        """Fallback to individual label operations.

        Args:
            message_ids: List of message IDs
            add_label_ids: Labels to add
            remove_label_ids: Labels to remove

        Returns:
            Dictionary with operation results
        """
        logger.info("Using fallback individual label operations")

        tasks = [
            self._execute_with_semaphore(
                lambda mid=mid: self.client.modify_message(
                    mid,
                    add_label_ids=add_label_ids,
                    remove_label_ids=remove_label_ids,
                )
            )
            for mid in message_ids
        ]

        results = await asyncio.gather(*tasks)

        successful = []
        failed = {}

        for message_id, (success, result) in zip(message_ids, results):
            if success:
                successful.append(message_id)
            else:
                failed[message_id] = result

        return {
            "successful": successful,
            "failed": failed,
            "total": len(message_ids),
            "success_count": len(successful),
            "failure_count": len(failed),
        }

    async def batch_mark_as_read(
        self, message_ids: list[str]
    ) -> dict[str, Any]:
        """Mark multiple emails as read.

        Args:
            message_ids: List of message IDs

        Returns:
            Dictionary with operation results
        """
        return await self.batch_apply_labels(
            message_ids=message_ids,
            remove_label_ids=["UNREAD"],
        )

    async def batch_mark_as_unread(
        self, message_ids: list[str]
    ) -> dict[str, Any]:
        """Mark multiple emails as unread.

        Args:
            message_ids: List of message IDs

        Returns:
            Dictionary with operation results
        """
        return await self.batch_apply_labels(
            message_ids=message_ids,
            add_label_ids=["UNREAD"],
        )

    async def batch_archive(
        self, message_ids: list[str]
    ) -> dict[str, Any]:
        """Archive multiple emails.

        Args:
            message_ids: List of message IDs

        Returns:
            Dictionary with operation results
        """
        return await self.batch_apply_labels(
            message_ids=message_ids,
            remove_label_ids=["INBOX"],
        )

    async def batch_move_to_trash(
        self, message_ids: list[str]
    ) -> dict[str, Any]:
        """Move multiple emails to trash.

        Args:
            message_ids: List of message IDs

        Returns:
            Dictionary with operation results
        """
        return await self.batch_apply_labels(
            message_ids=message_ids,
            add_label_ids=["TRASH"],
        )

    async def batch_star(
        self, message_ids: list[str]
    ) -> dict[str, Any]:
        """Star multiple emails.

        Args:
            message_ids: List of message IDs

        Returns:
            Dictionary with operation results
        """
        return await self.batch_apply_labels(
            message_ids=message_ids,
            add_label_ids=["STARRED"],
        )

    async def batch_unstar(
        self, message_ids: list[str]
    ) -> dict[str, Any]:
        """Unstar multiple emails.

        Args:
            message_ids: List of message IDs

        Returns:
            Dictionary with operation results
        """
        return await self.batch_apply_labels(
            message_ids=message_ids,
            remove_label_ids=["STARRED"],
        )

    async def batch_get_headers(
        self,
        message_ids: list[str],
        headers: list[str],
    ) -> dict[str, Any]:
        """Get specific headers from multiple emails.

        Args:
            message_ids: List of message IDs
            headers: List of header names

        Returns:
            Dictionary with header data
        """
        # Read messages with metadata format
        results = await self.batch_read(message_ids, format="metadata")

        # Extract headers from successful reads
        headers_data = {}
        for message_id, message in results["successful"].items():
            payload = message.get("payload", {})
            all_headers = payload.get("headers", [])

            message_headers = {
                h["name"]: h["value"]
                for h in all_headers
                if h["name"] in headers
            }
            headers_data[message_id] = message_headers

        return {
            "headers": headers_data,
            "failed": results["failed"],
            "total": results["total"],
            "success_count": len(headers_data),
            "failure_count": results["failure_count"],
        }

    def get_stats(self) -> dict[str, Any]:
        """Get batch operations statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "max_concurrent": self.max_concurrent,
            "max_batch_size": self.settings.max_batch_size,
        }
