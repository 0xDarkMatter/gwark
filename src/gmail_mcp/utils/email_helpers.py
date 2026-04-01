#!/usr/bin/env python
"""Email utility functions for Gwark."""

from typing import Optional


def extract_name(email_address: Optional[str]) -> str:
    """Extract name from email address.

    Handles various email formats:
    - "John Doe <john@example.com>" -> "John Doe"
    - "john.doe@example.com" -> "John Doe"
    - Empty/None -> "Unknown"

    Args:
        email_address: Email address string, possibly in format "Name <email@example.com>"

    Returns:
        Extracted name string or "Unknown" if not found

    Examples:
        >>> extract_name("John Doe <john@example.com>")
        'John Doe'
        >>> extract_name("john.doe@example.com")
        'John Doe'
        >>> extract_name(None)
        'Unknown'
    """
    if not email_address:
        return "Unknown"

    # Check if name is in angle brackets format: "Name <email@example.com>"
    if "<" in email_address:
        name_part = email_address.split("<")[0].strip()
        if name_part:
            return name_part

    # Extract from email address
    email_part = email_address.split("<")[-1].replace(">", "").strip()
    local_part = email_part.split("@")[0]

    # Replace dots and underscores with spaces, capitalize
    name = local_part.replace(".", " ").replace("_", " ").title()
    return name
