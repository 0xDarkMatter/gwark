#!/usr/bin/env python
"""Gmail API field masks for partial responses.

Using partial responses reduces payload size by 40-70% by requesting only
the fields we actually need. This improves performance and reduces API quota usage.
"""

from typing import Dict, List

# Base fields that are always useful
BASE_MESSAGE_FIELDS = "id,threadId,labelIds"

# Field masks for different use cases
FIELD_MASKS: Dict[str, str] = {
    # Minimal - just IDs for batch operations
    "minimal": BASE_MESSAGE_FIELDS,

    # Summary - for list views (no body content)
    "summary": (
        f"{BASE_MESSAGE_FIELDS},"
        "snippet,"
        "sizeEstimate,"
        "internalDate,"
        "payload/headers"
    ),

    # Metadata - headers only (no body)
    "metadata": (
        f"{BASE_MESSAGE_FIELDS},"
        "snippet,"
        "internalDate,"
        "payload(headers,mimeType)"
    ),

    # Headers - specific headers for email search
    "headers": (
        f"{BASE_MESSAGE_FIELDS},"
        "snippet,"
        "internalDate,"
        "payload(headers)"
    ),

    # Full - complete message with body
    "full": (
        f"{BASE_MESSAGE_FIELDS},"
        "snippet,"
        "internalDate,"
        "sizeEstimate,"
        "payload(headers,mimeType,parts,body)"
    ),

    # Full with attachments
    "full_with_attachments": (
        f"{BASE_MESSAGE_FIELDS},"
        "snippet,"
        "internalDate,"
        "sizeEstimate,"
        "payload(headers,mimeType,parts,body,filename)"
    ),
}

# Specific header fields to request when using metadata format
COMMON_HEADERS: List[str] = [
    "From",
    "To",
    "Cc",
    "Bcc",
    "Subject",
    "Date",
    "Message-ID",
    "In-Reply-To",
    "References",
]

# Extended headers for detailed analysis
EXTENDED_HEADERS: List[str] = COMMON_HEADERS + [
    "Reply-To",
    "Return-Path",
    "Delivered-To",
    "Received",
    "Content-Type",
    "MIME-Version",
    "X-Mailer",
    "X-Spam-Score",
    "X-Priority",
]


def get_field_mask(detail_level: str = "metadata") -> str:
    """Get field mask for a given detail level.

    Args:
        detail_level: One of 'minimal', 'summary', 'metadata', 'headers',
                     'full', or 'full_with_attachments'

    Returns:
        Field mask string for Gmail API

    Examples:
        >>> get_field_mask("summary")
        'id,threadId,labelIds,snippet,sizeEstimate,internalDate,payload/headers'
    """
    return FIELD_MASKS.get(detail_level, FIELD_MASKS["metadata"])


def get_headers_for_detail_level(detail_level: str = "metadata") -> List[str]:
    """Get list of headers to request for a detail level.

    Args:
        detail_level: Detail level

    Returns:
        List of header names

    Examples:
        >>> get_headers_for_detail_level("metadata")
        ['From', 'To', 'Cc', 'Bcc', 'Subject', 'Date', ...]
    """
    if detail_level in ["full", "full_with_attachments"]:
        return EXTENDED_HEADERS
    else:
        return COMMON_HEADERS


# List operation field masks (for messages.list)
LIST_FIELD_MASKS: Dict[str, str] = {
    # Minimal list - just message IDs
    "minimal": "messages(id),nextPageToken,resultSizeEstimate",

    # Standard list - IDs with thread info
    "standard": (
        "messages(id,threadId,labelIds),"
        "nextPageToken,"
        "resultSizeEstimate"
    ),

    # Full list - includes snippets (careful with quota!)
    "full": (
        "messages(id,threadId,labelIds,snippet,internalDate),"
        "nextPageToken,"
        "resultSizeEstimate"
    ),
}


def get_list_field_mask(detail_level: str = "standard") -> str:
    """Get field mask for list operations.

    Args:
        detail_level: One of 'minimal', 'standard', or 'full'

    Returns:
        Field mask string for messages.list

    Examples:
        >>> get_list_field_mask("minimal")
        'messages(id),nextPageToken,resultSizeEstimate'
    """
    return LIST_FIELD_MASKS.get(detail_level, LIST_FIELD_MASKS["standard"])
