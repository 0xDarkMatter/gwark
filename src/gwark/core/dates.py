"""Date parsing and formatting utilities for gwark."""

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple


def parse_email_date(date_str: str) -> Optional[datetime]:
    """Parse an email date string to datetime.

    Args:
        date_str: Email date header value

    Returns:
        datetime object or None if parsing fails
    """
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def format_date(dt: datetime, fmt: str = "%d/%m/%Y") -> str:
    """Format a datetime to string.

    Args:
        dt: datetime to format
        fmt: strftime format string

    Returns:
        Formatted date string
    """
    return dt.strftime(fmt)


def format_short_date(date_str: str) -> str:
    """Format an email date string to DD/MM/YYYY.

    Args:
        date_str: Email date string

    Returns:
        Formatted date string or original if parsing fails
    """
    parsed = parse_email_date(date_str)
    if parsed:
        return format_date(parsed, "%d/%m/%Y")
    return date_str


def format_datetime(date_str: str) -> str:
    """Format an email date string to DD/MM/YYYY HH:MM.

    Args:
        date_str: Email date string

    Returns:
        Formatted datetime string or original if parsing fails
    """
    parsed = parse_email_date(date_str)
    if parsed:
        return format_date(parsed, "%d/%m/%Y %H:%M")
    return date_str


def parse_date_range(
    days_back: int = 30,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """Calculate a date range for searching.

    Args:
        days_back: Number of days to look back from today
        start_date: Explicit start date (overrides days_back)
        end_date: Explicit end date (defaults to now)

    Returns:
        Tuple of (start_datetime, end_datetime)
    """
    if end_date is None:
        end_date = datetime.now()

    if start_date is None:
        start_date = end_date - timedelta(days=days_back)

    return start_date, end_date


def date_to_gmail_query(dt: datetime) -> str:
    """Convert datetime to Gmail query format (YYYY/MM/DD).

    Args:
        dt: datetime to convert

    Returns:
        Date string in Gmail query format
    """
    return dt.strftime("%Y/%m/%d")


def get_date_timestamp(date_str: str) -> float:
    """Get timestamp from email date string for sorting.

    Args:
        date_str: Email date string

    Returns:
        Unix timestamp or 0 if parsing fails
    """
    parsed = parse_email_date(date_str)
    return parsed.timestamp() if parsed else 0.0
