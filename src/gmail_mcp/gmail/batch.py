"""Batch operations for handling multiple emails efficiently."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from gmail_mcp.config import get_settings
from gmail_mcp.gmail.client import GmailClient
from gmail_mcp.utils.validators import (
    validate_batch_size,
    validate_label_id,
    validate_message_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP Batch Fetcher - Native Gmail batch API for maximum throughput
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    """Result of batch operation."""

    successful: dict[str, Any] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Total number of items processed."""
        return len(self.successful) + len(self.failed)

    @property
    def success_rate(self) -> float:
        """Percentage of successful operations."""
        return len(self.successful) / self.total if self.total else 0.0


class HttpBatchFetcher:
    """Native Gmail HTTP batch API for maximum throughput.

    Uses google-api-python-client's BatchHttpRequest to combine
    multiple requests into a single HTTP round-trip.

    Example:
        >>> fetcher = HttpBatchFetcher(lambda: get_gmail_service())
        >>> result = fetcher.fetch_messages(message_ids, format="full")
        >>> print(f"Fetched {len(result.successful)} emails")

    Why this is faster:
        - Individual requests: 100 × 50ms latency = 5000ms
        - Batch request: 1 × 50ms + processing = ~500ms
        - Result: ~5-10x less network overhead

    Note: Gmail enforces per-user rate limits even within batch requests.
    Failed requests are retried with exponential backoff by the caller.
    """

    BATCH_SIZE = 100  # Gmail API limit per batch
    INTER_BATCH_DELAY = 0.1  # Small delay between batches to avoid rate limits

    def __init__(self, service_factory: Callable[[], Any]):
        """Initialize batch fetcher.

        Args:
            service_factory: Callable that returns a Gmail service instance.
                           Called fresh for each batch to ensure thread safety.
        """
        self.service_factory = service_factory

    def fetch_messages(
        self,
        message_ids: list[str],
        format: str = "full",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchResult:
        """Fetch messages using HTTP batch API.

        Args:
            message_ids: List of Gmail message IDs to fetch
            format: Response format (full, metadata, minimal, raw)
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            BatchResult with successful (id -> data) and failed (id -> error)
        """
        if not message_ids:
            return BatchResult()

        all_successful: dict[str, Any] = {}
        all_failed: dict[str, str] = {}
        total = len(message_ids)

        import time

        # Process in chunks of BATCH_SIZE
        for i in range(0, total, self.BATCH_SIZE):
            chunk = message_ids[i : i + self.BATCH_SIZE]
            chunk_num = i // self.BATCH_SIZE + 1
            total_chunks = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            logger.debug(f"Batch {chunk_num}/{total_chunks}: {len(chunk)} messages")

            result = self._fetch_batch(chunk, format)
            all_successful.update(result.successful)
            all_failed.update(result.failed)

            if progress_callback:
                progress_callback(len(all_successful) + len(all_failed), total)

            # Small delay between batches to avoid rate limits
            if i + self.BATCH_SIZE < total:
                time.sleep(self.INTER_BATCH_DELAY)

        logger.info(
            f"Batch fetch complete: {len(all_successful)}/{total} successful "
            f"({len(all_failed)} failed)"
        )

        return BatchResult(successful=all_successful, failed=all_failed)

    def _fetch_batch(self, message_ids: list[str], format: str) -> BatchResult:
        """Fetch a single batch via HTTP batch API.

        Args:
            message_ids: IDs for this batch (max 100)
            format: Response format

        Returns:
            BatchResult for this batch
        """
        service = self.service_factory()
        successful: dict[str, Any] = {}
        failed: dict[str, str] = {}

        def callback(request_id: str, response: Any, exception: Exception) -> None:
            """Callback invoked for each request in the batch."""
            if exception:
                failed[request_id] = str(exception)
                logger.debug(f"Batch item {request_id} failed: {exception}")
            else:
                successful[request_id] = response

        # Create batch request
        batch = service.new_batch_http_request(callback=callback)

        # Add all message requests to batch
        for msg_id in message_ids:
            request = service.users().messages().get(
                userId="me",
                id=msg_id,
                format=format,
            )
            batch.add(request, request_id=msg_id)

        # Execute batch (single HTTP round-trip)
        batch.execute()

        return BatchResult(successful=successful, failed=failed)


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
        fields: Optional[str] = None,
    ) -> dict[str, Any]:
        """Read multiple emails in parallel.

        Args:
            message_ids: List of message IDs
            format: Response format
            fields: Partial response field mask (e.g., "metadata", "summary", "full")
                   Reduces payload size by 40-70%

        Returns:
            Dictionary with successful and failed reads

        Examples:
            >>> # Batch read with minimal payload
            >>> result = await batch_ops.batch_read(ids, format="metadata", fields="summary")
        """
        # Validate inputs
        message_ids = [validate_message_id(mid) for mid in message_ids]
        batch_size = len(message_ids)
        validate_batch_size(batch_size)

        logger.info(f"Batch read: {batch_size} messages with field mask: {fields or 'none'}")

        # Create tasks
        tasks = [
            self._execute_with_semaphore(
                lambda mid=mid: self.client.get_message(mid, format=format, fields=fields)
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
        # Read messages with metadata format and headers field mask for efficiency
        results = await self.batch_read(message_ids, format="metadata", fields="headers")

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
