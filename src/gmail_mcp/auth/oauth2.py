"""OAuth2 authentication manager for Gmail API."""

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_mcp.config import get_settings

logger = logging.getLogger(__name__)


class OAuth2Manager:
    """Manages OAuth2 authentication flow for Gmail API."""

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        scopes: Optional[list[str]] = None,
    ):
        """Initialize OAuth2 manager.

        Args:
            credentials_path: Path to OAuth2 client credentials JSON file
            scopes: List of Gmail API scopes to request
        """
        self.settings = get_settings()
        self.credentials_path = credentials_path or self.settings.oauth2_credentials_path
        self.scopes = scopes or self.settings.gmail_scopes

        # Only warn if credentials file missing - it's only needed for new auth flows
        if not self.credentials_path.exists():
            logger.debug(f"OAuth2 credentials file not found: {self.credentials_path}")

    def _require_credentials_file(self) -> None:
        """Raise error if credentials file is missing (for auth flows that need it)."""
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"OAuth2 credentials file not found: {self.credentials_path}. "
                f"Please download it from Google Cloud Console and place it at this path."
            )

    def get_authorization_url(
        self,
        redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob",
        state: Optional[str] = None,
    ) -> tuple[str, str]:
        """Generate OAuth2 authorization URL.

        Args:
            redirect_uri: OAuth2 redirect URI
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        self._require_credentials_file()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=self.scopes,
            redirect_uri=redirect_uri,
        )

        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )

        logger.info(f"Generated authorization URL with state: {state}")
        return auth_url, state

    def exchange_code_for_token(
        self,
        authorization_code: str,
        redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob",
    ) -> Credentials:
        """Exchange authorization code for access token.

        Args:
            authorization_code: Authorization code from OAuth2 flow
            redirect_uri: OAuth2 redirect URI (must match the one used in authorization URL)

        Returns:
            Google OAuth2 Credentials object
        """
        self._require_credentials_file()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=self.scopes,
            redirect_uri=redirect_uri,
        )

        flow.fetch_token(code=authorization_code)
        credentials = flow.credentials

        logger.info("Successfully exchanged authorization code for tokens")
        return credentials

    def run_local_server_flow(self, port: int = 8080) -> Credentials:
        """Run OAuth2 flow using local server (recommended for development).

        Args:
            port: Port for local OAuth2 callback server

        Returns:
            Google OAuth2 Credentials object
        """
        self._require_credentials_file()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=self.scopes,
        )

        credentials = flow.run_local_server(
            port=port,
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        logger.info(f"Successfully completed OAuth2 flow on port {port}")
        return credentials

    def refresh_credentials(self, credentials: Credentials) -> Credentials:
        """Refresh expired OAuth2 credentials.

        Args:
            credentials: Existing credentials to refresh

        Returns:
            Refreshed credentials

        Raises:
            Exception: If refresh fails
        """
        if not credentials or not credentials.refresh_token:
            logger.error("Cannot refresh credentials: no refresh token available")
            raise ValueError("Credentials must have a refresh token to be refreshed")

        try:
            credentials.refresh(Request())
            logger.info("Successfully refreshed OAuth2 credentials")
            return credentials
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            raise

    def validate_credentials(self, credentials: Credentials) -> bool:
        """Validate that credentials are valid and have required scopes.

        Args:
            credentials: Credentials to validate

        Returns:
            True if credentials are valid
        """
        if not credentials:
            return False

        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                try:
                    self.refresh_credentials(credentials)
                    return True
                except Exception:
                    return False
            return False

        # Check if credentials have all required scopes
        cred_scopes = set(credentials.scopes or [])
        required_scopes = set(self.scopes)

        if not required_scopes.issubset(cred_scopes):
            missing_scopes = required_scopes - cred_scopes
            logger.debug(f"Credentials missing scopes: {missing_scopes}")
            return False

        return True

    async def async_refresh_credentials(self, credentials: Credentials) -> Credentials:
        """Async version of refresh_credentials.

        Args:
            credentials: Existing credentials to refresh

        Returns:
            Refreshed credentials
        """
        # For now, just wrap the sync version
        # In future, could use aiohttp for async token refresh
        return self.refresh_credentials(credentials)
