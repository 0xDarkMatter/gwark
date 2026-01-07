"""Email extraction and processing utilities for gwark."""

import base64
import re
from typing import Any, Dict, List, Optional

from .dates import get_date_timestamp


def extract_name(email_string: str) -> str:
    """Extract display name from email address.

    Args:
        email_string: Email string like "John Doe <john@example.com>"

    Returns:
        Display name or email address if no name found
    """
    if not email_string:
        return "Unknown"

    # Try to extract name from "Name <email>" format
    match = re.match(r'^"?([^"<]+)"?\s*<', email_string)
    if match:
        return match.group(1).strip()

    # Try to extract from email@domain.com
    match = re.match(r"([^@]+)@", email_string)
    if match:
        # Convert john.doe to John Doe
        name = match.group(1).replace(".", " ").replace("_", " ")
        return name.title()

    return email_string


def extract_email_address(email_string: str) -> str:
    """Extract just the email address from a string.

    Args:
        email_string: Email string like "John Doe <john@example.com>"

    Returns:
        Email address only
    """
    if not email_string:
        return ""

    # Try to extract email from "Name <email>" format
    match = re.search(r"<([^>]+)>", email_string)
    if match:
        return match.group(1)

    # If no brackets, assume it's just an email
    match = re.search(r"[\w\.-]+@[\w\.-]+", email_string)
    if match:
        return match.group(0)

    return email_string


def get_email_body(payload: Dict[str, Any]) -> str:
    """Recursively extract email body text from payload.

    Args:
        payload: Gmail API message payload

    Returns:
        Decoded email body text
    """
    if "body" in payload and payload["body"].get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
        except Exception:
            return ""

    if "parts" in payload:
        for part in payload["parts"]:
            # Prefer text/plain, fallback to text/html
            if part.get("mimeType") in ["text/plain", "text/html"]:
                if part.get("body", {}).get("data"):
                    try:
                        return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                            "utf-8", errors="ignore"
                        )
                    except Exception:
                        continue
            # Recursive for nested parts
            if "parts" in part:
                body = get_email_body(part)
                if body:
                    return body
    return ""


def extract_attachments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract attachment information from email payload.

    Args:
        payload: Gmail API message payload

    Returns:
        List of attachment info dicts
    """
    attachments = []

    def _extract_from_parts(parts: List[Dict[str, Any]]) -> None:
        for part in parts:
            filename = part.get("filename")
            if filename:
                attachments.append({
                    "filename": filename,
                    "mimeType": part.get("mimeType", "unknown"),
                    "size": part.get("body", {}).get("size", 0),
                })
            # Recurse into nested parts
            if "parts" in part:
                _extract_from_parts(part["parts"])

    if "parts" in payload:
        _extract_from_parts(payload["parts"])

    return attachments


def extract_email_details(
    email_data: Dict[str, Any],
    detail_level: str = "full",
) -> Dict[str, Any]:
    """Extract relevant details from email message.

    Args:
        email_data: Raw Gmail API message data
        detail_level: Level of detail - "summary", "metadata", or "full"

    Returns:
        Structured email details dictionary
    """
    payload = email_data.get("payload", {})
    headers = payload.get("headers", [])

    # Build header lookup
    header_map = {h["name"]: h["value"] for h in headers}

    # Parse date
    date_str = header_map.get("Date", "")
    date_timestamp = get_date_timestamp(date_str)

    # Basic metadata available in all modes
    result = {
        "id": email_data["id"],
        "threadId": email_data.get("threadId"),
        "subject": header_map.get("Subject", "No Subject"),
        "from": header_map.get("From", "Unknown"),
        "to": header_map.get("To", "Unknown"),
        "date": date_str,
        "date_timestamp": date_timestamp,
        "snippet": email_data.get("snippet", ""),
        "labels": email_data.get("labelIds", []),
        "size_estimate": email_data.get("sizeEstimate", 0),
    }

    # Only extract body and attachments in full mode
    if detail_level == "full":
        body_text = get_email_body(payload)
        attachments = extract_attachments(payload)

        result["cc"] = header_map.get("Cc")
        result["bcc"] = header_map.get("Bcc")
        result["body_preview"] = body_text[:500] if body_text else email_data.get("snippet", "")
        result["body_full"] = body_text if len(body_text) < 10000 else body_text[:10000] + "..."
        result["attachments"] = attachments
    else:
        # Summary/metadata mode - minimal data
        result["attachments"] = []

    return result


def build_gmail_query(
    domain: Optional[str] = None,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    subject: Optional[str] = None,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    labels: Optional[List[str]] = None,
    has_attachment: Optional[bool] = None,
    custom_query: Optional[str] = None,
) -> str:
    """Build a Gmail search query from parameters.

    Args:
        domain: Domain to search (adds from:@domain OR to:@domain)
        sender: Sender email address
        recipient: Recipient email address
        subject: Subject search term
        after_date: Search after this date (YYYY/MM/DD)
        before_date: Search before this date (YYYY/MM/DD)
        labels: List of label names
        has_attachment: Filter for attachments
        custom_query: Raw Gmail query (overrides other params)

    Returns:
        Gmail search query string
    """
    if custom_query:
        return custom_query

    parts = []

    if domain:
        parts.append(f"(from:@{domain} OR to:@{domain})")

    if sender:
        parts.append(f"from:{sender}")

    if recipient:
        parts.append(f"to:{recipient}")

    if subject:
        parts.append(f'subject:"{subject}"')

    if after_date:
        parts.append(f"after:{after_date}")

    if before_date:
        parts.append(f"before:{before_date}")

    if labels:
        for label in labels:
            parts.append(f"label:{label}")

    if has_attachment:
        parts.append("has:attachment")

    return " ".join(parts) if parts else ""
