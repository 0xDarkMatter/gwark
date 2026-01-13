"""Email extraction and processing utilities for gwark."""

import base64
import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .dates import get_date_timestamp

if TYPE_CHECKING:
    from gwark.schemas.config import EmailFilters


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


def get_gmail_category(labels: List[str]) -> str:
    """Extract Gmail category from labels.

    Args:
        labels: List of Gmail label IDs

    Returns:
        Category name: "Primary", "Updates", "Promotions", "Social", "Forums"
    """
    category_map = {
        "CATEGORY_UPDATES": "Updates",
        "CATEGORY_PROMOTIONS": "Promotions",
        "CATEGORY_SOCIAL": "Social",
        "CATEGORY_FORUMS": "Forums",
    }

    for label in labels:
        if label in category_map:
            return category_map[label]

    # Default to Primary if no category label
    return "Primary"


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

    # Get labels and derive Gmail category
    labels = email_data.get("labelIds", [])
    gmail_category = get_gmail_category(labels)

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
        "labels": labels,
        "gmail_category": gmail_category,
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


def apply_email_filters(
    emails: List[Dict[str, Any]],
    filters: "EmailFilters",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply profile filters to emails.

    Args:
        emails: List of email dictionaries from extract_email_details()
        filters: EmailFilters configuration from profile

    Returns:
        Tuple of (kept_emails, filtered_emails)
    """
    kept = []
    filtered = []

    for email in emails:
        reason = _get_filter_reason(email, filters)
        if reason:
            email["filter_reason"] = reason
            filtered.append(email)
        else:
            kept.append(email)

    return kept, filtered


def _get_filter_reason(email: Dict[str, Any], filters: "EmailFilters") -> Optional[str]:
    """Check if email matches any exclude rules.

    Returns:
        Reason string if email should be filtered, None if it should be kept
    """
    sender = email.get("from", "").lower()
    sender_email = extract_email_address(sender).lower()
    subject = email.get("subject", "").lower()
    labels = email.get("labels", [])

    # Check exclude_senders (prefix match)
    for pattern in filters.exclude_senders:
        if sender_email.startswith(pattern.lower()):
            return f"sender:{pattern}"

    # Check exclude_domains
    for domain in filters.exclude_domains:
        if f"@{domain.lower()}" in sender_email:
            return f"domain:{domain}"

    # Check exclude_subjects (substring match, case-insensitive)
    for pattern in filters.exclude_subjects:
        if pattern.lower() in subject:
            return f"subject:{pattern}"

    # Check exclude_labels
    for label in filters.exclude_labels:
        if label in labels:
            return f"label:{label}"

    return None


def filter_emails_by_rules(
    emails: List[Dict[str, Any]],
    exclude_senders: Optional[List[str]] = None,
    exclude_subjects: Optional[List[str]] = None,
    exclude_labels: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Simple filter function without needing EmailFilters object.

    Args:
        emails: List of email dictionaries
        exclude_senders: List of sender patterns to exclude
        exclude_subjects: List of subject patterns to exclude
        exclude_labels: List of Gmail labels to exclude

    Returns:
        Tuple of (kept_emails, filtered_emails)
    """
    from gwark.schemas.config import EmailFilters

    filters = EmailFilters(
        exclude_senders=exclude_senders or [],
        exclude_subjects=exclude_subjects or [],
        exclude_labels=exclude_labels or [],
    )
    return apply_email_filters(emails, filters)


def detect_response_status(
    emails: List[Dict[str, Any]],
    service,
    user_email: str,
) -> List[Dict[str, Any]]:
    """Check if user has replied to each email thread.

    Args:
        emails: List of email dictionaries with threadId
        service: Gmail API service object
        user_email: User's email address for sender matching

    Returns:
        Emails with added response_status field:
        - "replied": User already responded in this thread
        - "needs_response": External party sent last, user should respond
        - "awaiting_reply": User sent last, waiting for external reply
        - "no_response_needed": User is sender (sent email)
    """
    if not emails:
        return emails

    # Get unique thread IDs
    thread_ids = list(set(e.get("threadId") for e in emails if e.get("threadId")))

    # Batch fetch thread info
    thread_info = _fetch_thread_info(service, thread_ids, user_email)

    # Apply status to each email
    user_email_lower = user_email.lower()
    for email in emails:
        thread_id = email.get("threadId")
        sender_email = extract_email_address(email.get("from", "")).lower()

        # If user sent this email, no response needed
        if sender_email == user_email_lower or user_email_lower in sender_email:
            email["response_status"] = "no_response_needed"
            continue

        if thread_id and thread_id in thread_info:
            info = thread_info[thread_id]
            email["response_status"] = info["status"]
            email["thread_message_count"] = info["message_count"]
            if info.get("user_last_replied"):
                email["user_last_replied"] = info["user_last_replied"]
        else:
            # No thread info, assume needs response if from external
            email["response_status"] = "needs_response"

    return emails


def _fetch_thread_info(
    service,
    thread_ids: List[str],
    user_email: str,
) -> Dict[str, Dict[str, Any]]:
    """Fetch thread information to determine response status.

    Returns:
        Dict mapping threadId to status info
    """
    result = {}
    user_email_lower = user_email.lower()

    def fetch_thread(thread_id: str) -> Tuple[str, Dict[str, Any]]:
        try:
            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="metadata",
                metadataHeaders=["From", "Date"],
            ).execute()

            messages = thread.get("messages", [])
            if not messages:
                return thread_id, {"status": "needs_response", "message_count": 0}

            # Find last message and check if user sent any
            user_sent_any = False
            user_last_sent_date = None
            last_message_from_user = False

            for msg in messages:
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                sender = extract_email_address(headers.get("From", "")).lower()
                date_str = headers.get("Date", "")

                is_user = sender == user_email_lower or user_email_lower in sender
                if is_user:
                    user_sent_any = True
                    user_last_sent_date = date_str

            # Check last message
            last_msg = messages[-1]
            last_headers = {h["name"]: h["value"] for h in last_msg.get("payload", {}).get("headers", [])}
            last_sender = extract_email_address(last_headers.get("From", "")).lower()
            last_message_from_user = last_sender == user_email_lower or user_email_lower in last_sender

            # Determine status
            if last_message_from_user:
                status = "awaiting_reply"
            elif user_sent_any:
                status = "replied"  # User replied but external sent again
            else:
                status = "needs_response"

            return thread_id, {
                "status": status,
                "message_count": len(messages),
                "user_last_replied": user_last_sent_date,
            }

        except Exception:
            return thread_id, {"status": "needs_response", "message_count": 0}

    # Sequential fetch for stability
    for i, tid in enumerate(thread_ids):
        thread_id, info = fetch_thread(tid)
        result[thread_id] = info

    return result
