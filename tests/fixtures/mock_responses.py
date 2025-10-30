"""Mock Gmail API responses for testing."""

from typing import Any


def mock_list_messages_response(count: int = 3, next_token: bool = False) -> dict[str, Any]:
    """Create mock list messages response.

    Args:
        count: Number of messages to include
        next_token: Whether to include next page token

    Returns:
        Mock response dictionary
    """
    messages = [{"id": f"msg_{i}", "threadId": f"thread_{i}"} for i in range(count)]

    response = {
        "messages": messages,
        "resultSizeEstimate": count,
    }

    if next_token:
        response["nextPageToken"] = "next_page_token_123"

    return response


def mock_get_message_response(message_id: str, format: str = "full") -> dict[str, Any]:
    """Create mock get message response.

    Args:
        message_id: Message ID
        format: Response format

    Returns:
        Mock message dictionary
    """
    if format == "minimal":
        return {
            "id": message_id,
            "threadId": f"thread_{message_id}",
        }
    elif format == "metadata":
        return {
            "id": message_id,
            "threadId": f"thread_{message_id}",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Test email snippet",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                ]
            },
        }
    else:  # full
        return {
            "id": message_id,
            "threadId": f"thread_{message_id}",
            "labelIds": ["INBOX"],
            "snippet": "Test email snippet",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                ],
                "body": {"data": "VGVzdCBlbWFpbCBjb250ZW50"},
            },
        }


def mock_list_labels_response() -> dict[str, Any]:
    """Create mock list labels response.

    Returns:
        Mock labels response
    """
    return {
        "labels": [
            {"id": "INBOX", "name": "INBOX", "type": "system"},
            {"id": "SENT", "name": "SENT", "type": "system"},
            {"id": "Label_1", "name": "Custom Label", "type": "user"},
        ]
    }
