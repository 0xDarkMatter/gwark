"""OAuth2 authentication utilities for Google APIs."""

from gmail_mcp.auth.oauth import (
    get_google_service,
    get_calendar_service,
    get_drive_service,
    get_gmail_service,
    get_people_service,
    get_forms_service,
    get_docs_service,
    get_sheets_credentials,
    get_sheets_client,
)
from gmail_mcp.auth.oauth2 import OAuth2Manager
from gmail_mcp.auth.token_manager import TokenManager

__all__ = [
    "get_google_service",
    "get_calendar_service",
    "get_drive_service",
    "get_gmail_service",
    "get_people_service",
    "get_forms_service",
    "get_docs_service",
    "get_sheets_credentials",
    "get_sheets_client",
    "OAuth2Manager",
    "TokenManager",
]
