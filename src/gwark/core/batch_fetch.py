"""Elegant batch email fetching with progress and retry.

This module provides a high-level interface for fetching emails using
Gmail's native HTTP batch API, which combines up to 100 requests into
a single HTTP round-trip for ~2-3x faster fetching.

Example:
    >>> from gwark.core.batch_fetch import fetch_emails_batch
    >>> result = fetch_emails_batch(message_ids, detail_level="full")
    >>> print(f"Fetched {len(result.emails)} emails ({result.success_rate:.0%} success)")
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from gmail_mcp.auth import get_gmail_service
from gmail_mcp.gmail import HttpBatchFetcher
from gwark.core.email_utils import extract_email_details


@dataclass
class FetchResult:
    """Result of batch fetch with extracted email details.

    Attributes:
        emails: List of extracted email dictionaries
        failed_ids: List of message IDs that failed to fetch
        total: Total number of messages attempted
    """

    emails: list[dict[str, Any]] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    total: int = 0

    @property
    def success_count(self) -> int:
        """Number of successfully fetched emails."""
        return len(self.emails)

    @property
    def failure_count(self) -> int:
        """Number of failed fetches."""
        return len(self.failed_ids)

    @property
    def success_rate(self) -> float:
        """Success rate as a decimal (0.0 to 1.0)."""
        return self.success_count / self.total if self.total else 0.0


def fetch_emails_batch(
    message_ids: list[str],
    detail_level: str = "full",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_retries: int = 3,
) -> FetchResult:
    """Fetch emails using Gmail HTTP batch API with automatic retry.

    This function uses Gmail's native batch API to fetch up to 100 messages
    per HTTP request, resulting in ~2-3x faster fetching compared to
    individual requests.

    Args:
        message_ids: List of Gmail message IDs to fetch
        detail_level: Level of detail to extract:
            - "summary": Headers + snippet only (fastest)
            - "metadata": Headers only
            - "full": Complete email with body (default)
        progress_callback: Optional callback(completed, total) for progress updates
        max_retries: Retry attempts for rate-limited messages (default: 3)

    Returns:
        FetchResult containing extracted emails and any failed IDs

    Example:
        >>> # Basic usage
        >>> result = fetch_emails_batch(message_ids)
        >>> for email in result.emails:
        ...     print(f"{email['subject']} from {email['from']}")

        >>> # With progress callback
        >>> def on_progress(done, total):
        ...     print(f"Progress: {done}/{total}")
        >>> result = fetch_emails_batch(ids, progress_callback=on_progress)
    """
    if not message_ids:
        return FetchResult(total=0)

    # Map detail_level to Gmail API format
    format_map = {
        "summary": "metadata",
        "metadata": "metadata",
        "full": "full",
    }
    api_format = format_map.get(detail_level, "full")

    # Create fetcher with service factory
    fetcher = HttpBatchFetcher(service_factory=get_gmail_service)

    # First pass: fetch all messages
    result = fetcher.fetch_messages(
        message_ids,
        format=api_format,
        progress_callback=progress_callback,
    )

    # Retry failed messages with exponential backoff
    import time

    failed_ids = list(result.failed.keys())
    for attempt in range(max_retries):
        if not failed_ids:
            break

        # Exponential backoff before retry: 0.5s, 1s, 2s, ...
        backoff = 0.5 * (2 ** attempt)
        time.sleep(backoff)

        retry_result = fetcher.fetch_messages(failed_ids, format=api_format)

        # Merge successful retries
        result.successful.update(retry_result.successful)

        # Update failed list
        failed_ids = list(retry_result.failed.keys())

    # Extract email details from raw responses
    emails: list[dict[str, Any]] = []
    extraction_failed: list[str] = []

    for msg_id, raw_data in result.successful.items():
        try:
            details = extract_email_details(raw_data, detail_level=detail_level)
            emails.append(details)
        except Exception:
            extraction_failed.append(msg_id)

    # Combine all failed IDs
    all_failed = failed_ids + extraction_failed

    return FetchResult(
        emails=emails,
        failed_ids=all_failed,
        total=len(message_ids),
    )


def fetch_emails_batch_sorted(
    message_ids: list[str],
    detail_level: str = "full",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_retries: int = 2,
    sort_by: str = "date",
    reverse: bool = True,
) -> FetchResult:
    """Fetch emails and sort by specified field.

    Same as fetch_emails_batch but sorts results before returning.

    Args:
        message_ids: List of Gmail message IDs to fetch
        detail_level: Level of detail ("summary", "metadata", "full")
        progress_callback: Optional progress callback
        max_retries: Retry attempts for failed messages
        sort_by: Field to sort by ("date", "subject", "from")
        reverse: Sort in descending order (default: True for newest first)

    Returns:
        FetchResult with sorted emails
    """
    result = fetch_emails_batch(
        message_ids,
        detail_level=detail_level,
        progress_callback=progress_callback,
        max_retries=max_retries,
    )

    # Sort emails
    sort_keys = {
        "date": lambda e: e.get("date_timestamp", 0),
        "subject": lambda e: e.get("subject", "").lower(),
        "from": lambda e: e.get("from", "").lower(),
    }

    if sort_by in sort_keys:
        result.emails.sort(key=sort_keys[sort_by], reverse=reverse)

    return result
