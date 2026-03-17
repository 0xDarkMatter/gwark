#!/usr/bin/env python
"""Shared OAuth2 authentication for Google APIs.

Uses Fabric-compliant credential storage:
1. OS Keyring (fabric-gwark service) — primary
2. Legacy pickle files — migration fallback (auto-migrates to keyring)
3. OAuth2 credentials file — only needed for initial auth flow
"""

import os
import pickle
import sys
from pathlib import Path
from typing import List, Optional, Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from gmail_mcp.auth.credential_store import get_credential_store


def get_gwark_dir() -> Path:
    """Get the gwark configuration directory.

    Resolution order:
    1. GWARK_CONFIG_DIR environment variable (if set)
    2. Current working directory's .gwark/ (if it exists)
    3. User home ~/.gwark/ (default)

    Returns:
        Path to the gwark configuration directory
    """
    # 1. Check environment variable
    env_dir = os.environ.get("GWARK_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)

    # 2. Check current working directory
    cwd_gwark = Path.cwd() / ".gwark"
    if cwd_gwark.exists():
        return cwd_gwark

    # 3. Fall back to user home
    return Path.home() / ".gwark"


def _service_name_from_token(token_filename: str) -> str:
    """Extract service name from legacy token filename.

    'calendar_token.pickle' -> 'calendar'
    'gmail_token.pickle' -> 'gmail'
    """
    name = token_filename.replace("_token.pickle", "").replace(".pickle", "")
    return name


def _try_load_legacy_pickle(gwark_dir: Path, token_filename: str) -> Optional[Credentials]:
    """Try to load credentials from legacy pickle file.

    If found, returns credentials for migration to keyring.
    """
    token_path = gwark_dir / "tokens" / token_filename
    if not token_path.exists():
        return None

    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if isinstance(creds, Credentials):
            return creds
    except Exception:
        pass

    return None


def _try_load_encrypted_token(gwark_dir: Path, account_id: str = "primary") -> Optional[Credentials]:
    """Try to load credentials from Fernet-encrypted token file (legacy TokenManager format)."""
    try:
        from gmail_mcp.auth.token_manager import TokenManager
        tm = TokenManager(storage_path=gwark_dir / "tokens")
        return tm.load_credentials(account_id)
    except Exception:
        return None


def get_google_service(
    service_name: str,
    version: str,
    scopes: List[str],
    token_filename: str
) -> Any:
    """Authenticate and return Google API service.

    Credential resolution order:
    1. Keyring (fabric-gwark) — Fabric-compliant primary storage
    2. Legacy encrypted .token file — auto-migrates to keyring
    3. Legacy pickle file — auto-migrates to keyring
    4. New OAuth2 flow — saves to keyring

    Args:
        service_name: Google API service name (e.g., 'calendar', 'drive', 'gmail')
        version: API version (e.g., 'v3', 'v1')
        scopes: List of OAuth2 scopes required for the API
        token_filename: Legacy token filename (e.g., 'calendar_token.pickle')

    Returns:
        Authenticated Google API service object
    """
    store = get_credential_store()
    svc_key = _service_name_from_token(token_filename)
    creds: Optional[Credentials] = None
    gwark_dir: Path = get_gwark_dir()
    migrated = False

    # 1. Try keyring (primary)
    creds = store.load_google_credentials(svc_key)

    # 2. Try legacy encrypted token
    if not creds:
        creds = _try_load_encrypted_token(gwark_dir)
        if creds:
            migrated = True

    # 3. Try legacy pickle
    if not creds:
        creds = _try_load_legacy_pickle(gwark_dir, token_filename)
        if creds:
            migrated = True

    # Refresh if expired
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            print(f"[INFO] Refreshing {svc_key} credentials...")
            try:
                creds.refresh(Request())
                migrated = True  # Save refreshed token
            except Exception as e:
                error_msg = str(e).lower()
                if "revoked" in error_msg or "invalid_grant" in error_msg:
                    print(f"[ERROR] Token has been revoked or expired permanently.")
                    print(f"  Run: gwark config auth setup")
                    # Clear stale keyring entry
                    store.delete_google_credentials(svc_key)
                    sys.exit(2)
                elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                    print(f"[ERROR] Network error refreshing credentials: {e}")
                    sys.exit(1)
                else:
                    print(f"[ERROR] Failed to refresh credentials: {e}")
                    print(f"  Run: gwark config auth setup")
                    sys.exit(2)
        else:
            creds = None  # Invalid and can't refresh

    # 4. New auth flow if no valid credentials
    if not creds:
        creds_path = gwark_dir / "credentials" / "oauth2_credentials.json"
        if not creds_path.exists():
            print(f"[ERROR] Not authenticated and no OAuth2 credentials file found.")
            print(f"")
            print(f"To authenticate, either:")
            print(f"  1. Run: gwark config auth setup")
            print(f"  2. Place OAuth2 credentials at: {creds_path}")
            print(f"")
            print(f"Configuration lookup order:")
            print(f"  1. GWARK_CONFIG_DIR environment variable")
            print(f"  2. Current directory's .gwark/")
            print(f"  3. ~/.gwark/")
            sys.exit(2)

        print(f"[INFO] Starting OAuth2 authentication flow for {svc_key}...")
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
        creds = flow.run_local_server(port=0)
        migrated = True

    # Save to keyring (migration or new auth)
    if migrated and creds and creds.valid:
        store.save_google_credentials(creds, svc_key)
        print(f"[OK] Credentials saved to keyring for {svc_key}")

    return build(service_name, version, credentials=creds)


def get_calendar_service() -> Any:
    """Get authenticated Google Calendar API service."""
    scopes: List[str] = ["https://www.googleapis.com/auth/calendar.readonly"]
    return get_google_service("calendar", "v3", scopes, "calendar_token.pickle")


def get_drive_service() -> Any:
    """Get authenticated Google Drive API service."""
    scopes: List[str] = [
        "https://www.googleapis.com/auth/drive",
    ]
    return get_google_service("drive", "v3", scopes, "drive_token.pickle")


def get_gmail_service() -> Any:
    """Get authenticated Gmail API service."""
    scopes: List[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
    return get_google_service("gmail", "v1", scopes, "gmail_token.pickle")


def get_people_service() -> Any:
    """Get authenticated Google People API service."""
    scopes: List[str] = [
        "https://www.googleapis.com/auth/contacts.readonly",
        "https://www.googleapis.com/auth/contacts.other.readonly",
    ]
    return get_google_service("people", "v1", scopes, "people_token.pickle")


def get_forms_service() -> Any:
    """Get authenticated Google Forms API service."""
    scopes: List[str] = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/forms.responses.readonly",
    ]
    return get_google_service("forms", "v1", scopes, "forms_token.pickle")


def get_docs_service() -> Any:
    """Get authenticated Google Docs API service."""
    scopes: List[str] = [
        "https://www.googleapis.com/auth/documents",
    ]
    return get_google_service("docs", "v1", scopes, "docs_token.pickle")


def get_sheets_credentials() -> Credentials:
    """Get Google Sheets OAuth2 credentials.

    Returns raw Credentials object for use with gspread.authorize().
    """
    scopes: List[str] = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ]

    store = get_credential_store()
    svc_key = "sheets"
    creds: Optional[Credentials] = None
    gwark_dir: Path = get_gwark_dir()
    migrated = False

    # 1. Try keyring
    creds = store.load_google_credentials(svc_key)

    # 2. Try legacy pickle
    if not creds:
        creds = _try_load_legacy_pickle(gwark_dir, "sheets_token.pickle")
        if creds:
            migrated = True

    # Refresh if expired
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            print("[INFO] Refreshing Sheets credentials...")
            try:
                creds.refresh(Request())
                migrated = True
            except Exception as e:
                error_msg = str(e).lower()
                if "revoked" in error_msg or "invalid_grant" in error_msg:
                    print(f"[ERROR] Sheets token has been revoked.")
                    print(f"  Run: gwark config auth setup")
                    store.delete_google_credentials(svc_key)
                    sys.exit(2)
                elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                    print(f"[ERROR] Network error refreshing Sheets credentials: {e}")
                    sys.exit(1)
                else:
                    print(f"[ERROR] Failed to refresh Sheets credentials: {e}")
                    print(f"  Run: gwark config auth setup")
                    sys.exit(2)
        else:
            creds = None

    # New auth flow
    if not creds:
        creds_path = gwark_dir / "credentials" / "oauth2_credentials.json"
        if not creds_path.exists():
            print(f"[ERROR] Not authenticated and no OAuth2 credentials file found.")
            print(f"  Run: gwark config auth setup")
            sys.exit(2)

        print("[INFO] Starting OAuth2 authentication flow for Sheets...")
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
        creds = flow.run_local_server(port=0)
        migrated = True

    # Save to keyring
    if migrated and creds and creds.valid:
        store.save_google_credentials(creds, svc_key)
        print("[OK] Sheets credentials saved to keyring")

    return creds


def get_sheets_client() -> Any:
    """Get authenticated gspread client using Gwark's OAuth system."""
    import gspread
    creds = get_sheets_credentials()
    return gspread.authorize(creds)


def get_slides_service() -> Any:
    """Get authenticated Google Slides API service."""
    scopes: List[str] = [
        "https://www.googleapis.com/auth/presentations",
    ]
    return get_google_service("slides", "v1", scopes, "slides_token.pickle")
