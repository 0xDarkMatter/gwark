#!/usr/bin/env python
"""Shared OAuth2 authentication for Google APIs."""

import sys
import pickle
from pathlib import Path
from typing import List, Optional, Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def get_google_service(
    service_name: str,
    version: str,
    scopes: List[str],
    token_filename: str
) -> Any:
    """Authenticate and return Google API service.

    This function handles the complete OAuth2 flow including:
    - Loading existing credentials from pickle file
    - Refreshing expired tokens
    - Running the OAuth2 flow for new authentication
    - Saving credentials for future use

    Args:
        service_name: Google API service name (e.g., 'calendar', 'drive', 'gmail')
        version: API version (e.g., 'v3', 'v1')
        scopes: List of OAuth2 scopes required for the API
        token_filename: Name of the token file (e.g., 'calendar_token.pickle')

    Returns:
        Authenticated Google API service object

    Raises:
        SystemExit: If OAuth2 credentials file is not found

    Example:
        >>> scopes = ['https://www.googleapis.com/auth/calendar.readonly']
        >>> service = get_google_service('calendar', 'v3', scopes, 'calendar_token.pickle')
        >>> events = service.events().list(calendarId='primary').execute()
    """
    creds: Optional[Credentials] = None
    project_root: Path = Path(__file__).parent.parent.parent.parent
    token_path: Path = project_root / '.gwark' / 'tokens' / token_filename
    creds_path: Path = project_root / '.gwark' / 'credentials' / 'oauth2_credentials.json'

    # Create directories if they don't exist
    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing token
    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[INFO] Refreshing credentials...")
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print(f"[ERROR] OAuth2 credentials not found at {creds_path}")
                print("Please download credentials from Google Cloud Console")
                print("and save to .gwark/credentials/oauth2_credentials.json")
                sys.exit(1)

            print("[INFO] Starting OAuth2 authentication flow...")
            flow: InstalledAppFlow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
        print("[OK] Credentials saved")

    return build(service_name, version, credentials=creds)


def get_calendar_service() -> Any:
    """Get authenticated Google Calendar API service.

    Convenience wrapper for calendar API access.

    Returns:
        Authenticated Calendar API v3 service
    """
    scopes: List[str] = ['https://www.googleapis.com/auth/calendar.readonly']
    return get_google_service('calendar', 'v3', scopes, 'calendar_token.pickle')


def get_drive_service() -> Any:
    """Get authenticated Google Drive API service.

    Includes full access for listing, comments, and revision management.

    Returns:
        Authenticated Drive API v3 service
    """
    scopes: List[str] = [
        'https://www.googleapis.com/auth/drive',  # Full access
    ]
    return get_google_service('drive', 'v3', scopes, 'drive_token.pickle')


def get_gmail_service() -> Any:
    """Get authenticated Gmail API service.

    Convenience wrapper for Gmail API access.

    Returns:
        Authenticated Gmail API v1 service
    """
    scopes: List[str] = ['https://www.googleapis.com/auth/gmail.readonly']
    return get_google_service('gmail', 'v1', scopes, 'gmail_token.pickle')


def get_people_service() -> Any:
    """Get authenticated Google People API service.

    Used for checking if senders are in Google Contacts.
    Includes scope for both My Contacts and Other Contacts (auto-saved).

    Returns:
        Authenticated People API v1 service
    """
    scopes: List[str] = [
        'https://www.googleapis.com/auth/contacts.readonly',        # My Contacts
        'https://www.googleapis.com/auth/contacts.other.readonly',  # Other Contacts
    ]
    return get_google_service('people', 'v1', scopes, 'people_token.pickle')


def get_forms_service() -> Any:
    """Get authenticated Google Forms API service.

    Convenience wrapper for Forms API access.
    Supports reading/writing forms and reading responses.

    Returns:
        Authenticated Forms API v1 service
    """
    scopes: List[str] = [
        'https://www.googleapis.com/auth/forms.body',              # Full read/write
        'https://www.googleapis.com/auth/forms.responses.readonly',  # Read responses
    ]
    return get_google_service('forms', 'v1', scopes, 'forms_token.pickle')


def get_docs_service() -> Any:
    """Get authenticated Google Docs API service.

    Convenience wrapper for Docs API access.
    Supports full read/write access to documents.

    Returns:
        Authenticated Docs API v1 service
    """
    scopes: List[str] = [
        'https://www.googleapis.com/auth/documents',  # Full read/write
    ]
    return get_google_service('docs', 'v1', scopes, 'docs_token.pickle')
