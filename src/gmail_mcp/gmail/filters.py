"""Advanced filtering engine for Gmail queries."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from gmail_mcp.utils.validators import build_query_from_filters, validate_email_query

logger = logging.getLogger(__name__)


class EmailFilter:
    """Build complex Gmail queries using a fluent interface."""

    def __init__(self):
        """Initialize email filter."""
        self.query_parts: list[str] = []

    def from_sender(self, email: str) -> "EmailFilter":
        """Filter by sender email.

        Args:
            email: Sender email address

        Returns:
            Self for chaining
        """
        self.query_parts.append(f"from:{email}")
        return self

    def to_recipient(self, email: str) -> "EmailFilter":
        """Filter by recipient email.

        Args:
            email: Recipient email address

        Returns:
            Self for chaining
        """
        self.query_parts.append(f"to:{email}")
        return self

    def subject_contains(self, text: str) -> "EmailFilter":
        """Filter by subject containing text.

        Args:
            text: Text to search in subject

        Returns:
            Self for chaining
        """
        escaped_text = text.replace('"', '\\"')
        self.query_parts.append(f'subject:"{escaped_text}"')
        return self

    def body_contains(self, text: str) -> "EmailFilter":
        """Filter by body containing text.

        Args:
            text: Text to search in body

        Returns:
            Self for chaining
        """
        escaped_text = text.replace('"', '\\"')
        self.query_parts.append(f'"{escaped_text}"')
        return self

    def after_date(self, date: datetime) -> "EmailFilter":
        """Filter emails after a specific date.

        Args:
            date: Date to filter after

        Returns:
            Self for chaining
        """
        date_str = date.strftime("%Y/%m/%d")
        self.query_parts.append(f"after:{date_str}")
        return self

    def before_date(self, date: datetime) -> "EmailFilter":
        """Filter emails before a specific date.

        Args:
            date: Date to filter before

        Returns:
            Self for chaining
        """
        date_str = date.strftime("%Y/%m/%d")
        self.query_parts.append(f"before:{date_str}")
        return self

    def date_range(self, start: datetime, end: datetime) -> "EmailFilter":
        """Filter emails within a date range.

        Args:
            start: Start date
            end: End date

        Returns:
            Self for chaining
        """
        return self.after_date(start).before_date(end)

    def last_n_days(self, days: int) -> "EmailFilter":
        """Filter emails from last N days.

        Args:
            days: Number of days

        Returns:
            Self for chaining
        """
        date = datetime.now() - timedelta(days=days)
        return self.after_date(date)

    def has_attachment(self) -> "EmailFilter":
        """Filter emails with attachments.

        Returns:
            Self for chaining
        """
        self.query_parts.append("has:attachment")
        return self

    def attachment_name(self, filename: str) -> "EmailFilter":
        """Filter by attachment filename.

        Args:
            filename: Attachment filename

        Returns:
            Self for chaining
        """
        self.query_parts.append(f"filename:{filename}")
        return self

    def is_unread(self) -> "EmailFilter":
        """Filter unread emails.

        Returns:
            Self for chaining
        """
        self.query_parts.append("is:unread")
        return self

    def is_read(self) -> "EmailFilter":
        """Filter read emails.

        Returns:
            Self for chaining
        """
        self.query_parts.append("-is:unread")
        return self

    def is_starred(self) -> "EmailFilter":
        """Filter starred emails.

        Returns:
            Self for chaining
        """
        self.query_parts.append("is:starred")
        return self

    def is_important(self) -> "EmailFilter":
        """Filter important emails.

        Returns:
            Self for chaining
        """
        self.query_parts.append("is:important")
        return self

    def in_label(self, label: str) -> "EmailFilter":
        """Filter by label.

        Args:
            label: Label name or ID

        Returns:
            Self for chaining
        """
        self.query_parts.append(f"label:{label}")
        return self

    def in_inbox(self) -> "EmailFilter":
        """Filter emails in inbox.

        Returns:
            Self for chaining
        """
        return self.in_label("inbox")

    def in_sent(self) -> "EmailFilter":
        """Filter sent emails.

        Returns:
            Self for chaining
        """
        return self.in_label("sent")

    def in_drafts(self) -> "EmailFilter":
        """Filter draft emails.

        Returns:
            Self for chaining
        """
        return self.in_label("draft")

    def in_trash(self) -> "EmailFilter":
        """Filter trashed emails.

        Returns:
            Self for chaining
        """
        return self.in_label("trash")

    def in_spam(self) -> "EmailFilter":
        """Filter spam emails.

        Returns:
            Self for chaining
        """
        return self.in_label("spam")

    def larger_than(self, size_mb: float) -> "EmailFilter":
        """Filter emails larger than size.

        Args:
            size_mb: Size in megabytes

        Returns:
            Self for chaining
        """
        size_bytes = int(size_mb * 1024 * 1024)
        self.query_parts.append(f"larger:{size_bytes}")
        return self

    def smaller_than(self, size_mb: float) -> "EmailFilter":
        """Filter emails smaller than size.

        Args:
            size_mb: Size in megabytes

        Returns:
            Self for chaining
        """
        size_bytes = int(size_mb * 1024 * 1024)
        self.query_parts.append(f"smaller:{size_bytes}")
        return self

    def has_words(self, *words: str) -> "EmailFilter":
        """Filter emails containing all words.

        Args:
            *words: Words to search for

        Returns:
            Self for chaining
        """
        for word in words:
            self.query_parts.append(word)
        return self

    def exact_phrase(self, phrase: str) -> "EmailFilter":
        """Filter emails containing exact phrase.

        Args:
            phrase: Exact phrase to search for

        Returns:
            Self for chaining
        """
        escaped_phrase = phrase.replace('"', '\\"')
        self.query_parts.append(f'"{escaped_phrase}"')
        return self

    def exclude_words(self, *words: str) -> "EmailFilter":
        """Exclude emails containing words.

        Args:
            *words: Words to exclude

        Returns:
            Self for chaining
        """
        for word in words:
            self.query_parts.append(f"-{word}")
        return self

    def or_condition(self, *filters: "EmailFilter") -> "EmailFilter":
        """Combine filters with OR logic.

        Args:
            *filters: Filters to combine

        Returns:
            Self for chaining
        """
        or_parts = [f.build() for f in filters]
        combined = "{" + " OR ".join(or_parts) + "}"
        self.query_parts.append(combined)
        return self

    def raw_query(self, query: str) -> "EmailFilter":
        """Add a raw query string.

        Args:
            query: Raw Gmail query

        Returns:
            Self for chaining
        """
        self.query_parts.append(f"({query})")
        return self

    def build(self) -> str:
        """Build the final query string.

        Returns:
            Gmail query string
        """
        query = " ".join(self.query_parts)
        return validate_email_query(query) if query else ""

    def reset(self) -> "EmailFilter":
        """Reset the filter to start fresh.

        Returns:
            Self for chaining
        """
        self.query_parts = []
        return self


class FilterPresets:
    """Common filter presets for quick access."""

    @staticmethod
    def unread_inbox() -> EmailFilter:
        """Get unread emails in inbox."""
        return EmailFilter().in_inbox().is_unread()

    @staticmethod
    def important_unread() -> EmailFilter:
        """Get important unread emails."""
        return EmailFilter().is_important().is_unread()

    @staticmethod
    def starred() -> EmailFilter:
        """Get starred emails."""
        return EmailFilter().is_starred()

    @staticmethod
    def from_sender_last_week(email: str) -> EmailFilter:
        """Get emails from sender in last week."""
        return EmailFilter().from_sender(email).last_n_days(7)

    @staticmethod
    def with_large_attachments(min_size_mb: float = 10) -> EmailFilter:
        """Get emails with large attachments."""
        return EmailFilter().has_attachment().larger_than(min_size_mb)

    @staticmethod
    def recent_with_pdf() -> EmailFilter:
        """Get recent emails with PDF attachments."""
        return EmailFilter().last_n_days(30).attachment_name("pdf")

    @staticmethod
    def unread_from_domain(domain: str) -> EmailFilter:
        """Get unread emails from a domain."""
        return EmailFilter().from_sender(f"*@{domain}").is_unread()
