"""Input validation utilities."""

import logging
import re
from datetime import datetime
from typing import Optional

from gmail_mcp.config import get_settings
from gmail_mcp.config.constants import (
    MAX_BATCH_SIZE,
    MAX_PAGE_SIZE,
    MAX_RESULTS_PER_SEARCH,
    MIN_BATCH_SIZE,
    MIN_PAGE_SIZE,
    QUERY_OPERATORS,
)

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Custom exception for validation errors."""

    pass


def validate_email_query(query: str, max_length: int = 500) -> str:
    """Validate Gmail search query.

    Args:
        query: Gmail search query string
        max_length: Maximum query length

    Returns:
        Validated and sanitized query

    Raises:
        ValidationError: If query is invalid
    """
    if not query:
        raise ValidationError("Query cannot be empty")

    if not isinstance(query, str):
        raise ValidationError("Query must be a string")

    query = query.strip()

    if len(query) > max_length:
        raise ValidationError(f"Query too long (max {max_length} characters)")

    # Check for potential injection attempts (basic validation)
    # Gmail query syntax is safe, but we still validate
    if query.count('"') % 2 != 0:
        raise ValidationError("Unbalanced quotes in query")

    return query


def validate_page_size(page_size: int) -> int:
    """Validate pagination size.

    Args:
        page_size: Requested page size

    Returns:
        Validated page size

    Raises:
        ValidationError: If page size is invalid
    """
    if not isinstance(page_size, int):
        raise ValidationError("Page size must be an integer")

    if page_size < MIN_PAGE_SIZE:
        raise ValidationError(f"Page size must be at least {MIN_PAGE_SIZE}")

    if page_size > MAX_PAGE_SIZE:
        raise ValidationError(f"Page size cannot exceed {MAX_PAGE_SIZE}")

    return page_size


def validate_batch_size(batch_size: int) -> int:
    """Validate batch operation size.

    Args:
        batch_size: Requested batch size

    Returns:
        Validated batch size

    Raises:
        ValidationError: If batch size is invalid
    """
    if not isinstance(batch_size, int):
        raise ValidationError("Batch size must be an integer")

    if batch_size < MIN_BATCH_SIZE:
        raise ValidationError(f"Batch size must be at least {MIN_BATCH_SIZE}")

    if batch_size > MAX_BATCH_SIZE:
        raise ValidationError(f"Batch size cannot exceed {MAX_BATCH_SIZE}")

    return batch_size


def validate_message_id(message_id: str) -> str:
    """Validate Gmail message ID.

    Args:
        message_id: Gmail message ID

    Returns:
        Validated message ID

    Raises:
        ValidationError: If message ID is invalid
    """
    if not message_id:
        raise ValidationError("Message ID cannot be empty")

    if not isinstance(message_id, str):
        raise ValidationError("Message ID must be a string")

    message_id = message_id.strip()

    # Gmail message IDs are alphanumeric with some special chars
    if not re.match(r"^[a-zA-Z0-9_-]+$", message_id):
        raise ValidationError("Invalid message ID format")

    return message_id


def validate_label_id(label_id: str) -> str:
    """Validate Gmail label ID.

    Args:
        label_id: Gmail label ID

    Returns:
        Validated label ID

    Raises:
        ValidationError: If label ID is invalid
    """
    if not label_id:
        raise ValidationError("Label ID cannot be empty")

    if not isinstance(label_id, str):
        raise ValidationError("Label ID must be a string")

    label_id = label_id.strip()

    # Gmail label IDs can be system labels (INBOX, SENT) or custom IDs
    if not re.match(r"^[a-zA-Z0-9_-]+$", label_id):
        raise ValidationError("Invalid label ID format")

    return label_id


def validate_account_id(account_id: str) -> str:
    """Validate account ID.

    Args:
        account_id: Account identifier

    Returns:
        Validated account ID

    Raises:
        ValidationError: If account ID is invalid
    """
    if not account_id:
        raise ValidationError("Account ID cannot be empty")

    if not isinstance(account_id, str):
        raise ValidationError("Account ID must be a string")

    account_id = account_id.strip()

    # Account IDs should be alphanumeric with hyphens and underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", account_id):
        raise ValidationError("Invalid account ID format")

    settings = get_settings()
    if len(account_id) > 100:
        raise ValidationError("Account ID too long (max 100 characters)")

    return account_id


def validate_date_string(date_str: str, format: str = "%Y/%m/%d") -> datetime:
    """Validate and parse date string.

    Args:
        date_str: Date string
        format: Expected date format

    Returns:
        Parsed datetime object

    Raises:
        ValidationError: If date string is invalid
    """
    try:
        return datetime.strptime(date_str, format)
    except ValueError as e:
        raise ValidationError(f"Invalid date format: {e}")


def validate_max_results(max_results: Optional[int]) -> Optional[int]:
    """Validate maximum results parameter.

    Args:
        max_results: Maximum number of results

    Returns:
        Validated max results

    Raises:
        ValidationError: If max results is invalid
    """
    if max_results is None:
        return None

    if not isinstance(max_results, int):
        raise ValidationError("Max results must be an integer")

    if max_results < 1:
        raise ValidationError("Max results must be at least 1")

    if max_results > MAX_RESULTS_PER_SEARCH:
        raise ValidationError(f"Max results cannot exceed {MAX_RESULTS_PER_SEARCH}")

    return max_results


def build_query_from_filters(
    from_email: Optional[str] = None,
    to_email: Optional[str] = None,
    subject: Optional[str] = None,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    has_attachment: Optional[bool] = None,
    is_unread: Optional[bool] = None,
    label: Optional[str] = None,
    **kwargs,
) -> str:
    """Build Gmail query string from individual filters.

    Args:
        from_email: Sender email filter
        to_email: Recipient email filter
        subject: Subject filter
        after_date: After date (YYYY/MM/DD)
        before_date: Before date (YYYY/MM/DD)
        has_attachment: Filter for messages with attachments
        is_unread: Filter for unread messages
        label: Label filter
        **kwargs: Additional query operators

    Returns:
        Gmail query string
    """
    query_parts = []

    if from_email:
        query_parts.append(f"{QUERY_OPERATORS['from']}{from_email}")

    if to_email:
        query_parts.append(f"{QUERY_OPERATORS['to']}{to_email}")

    if subject:
        # Escape quotes in subject
        escaped_subject = subject.replace('"', '\\"')
        query_parts.append(f'{QUERY_OPERATORS["subject"]}"{escaped_subject}"')

    if after_date:
        validate_date_string(after_date)
        query_parts.append(f"{QUERY_OPERATORS['after']}{after_date}")

    if before_date:
        validate_date_string(before_date)
        query_parts.append(f"{QUERY_OPERATORS['before']}{before_date}")

    if has_attachment:
        query_parts.append(f"{QUERY_OPERATORS['has']}attachment")

    if is_unread:
        query_parts.append(f"{QUERY_OPERATORS['is']}unread")

    if label:
        query_parts.append(f"{QUERY_OPERATORS['label']}{label}")

    # Add any additional operators
    for key, value in kwargs.items():
        if key in QUERY_OPERATORS and value:
            query_parts.append(f"{QUERY_OPERATORS[key]}{value}")

    query = " ".join(query_parts)
    return validate_email_query(query) if query else ""
