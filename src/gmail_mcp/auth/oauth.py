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
    token_path: Path = project_root / 'data' / 'tokens' / token_filename
    creds_path: Path = project_root / 'config' / 'oauth2_credentials.json'

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
                print("and save to config/oauth2_credentials.json")
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

    Convenience wrapper for drive API access.

    Returns:
        Authenticated Drive API v3 service
    """
    scopes: List[str] = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
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
