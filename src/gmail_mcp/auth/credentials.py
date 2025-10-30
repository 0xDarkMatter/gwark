"""Credential validation and management utilities."""

import logging
from typing import Optional

from google.oauth2.credentials import Credentials

from gmail_mcp.config import get_settings

logger = logging.getLogger(__name__)


class CredentialValidator:
    """Validates and manages Gmail API credentials."""

    def __init__(self):
        """Initialize credential validator."""
        self.settings = get_settings()
        self.required_scopes = set(self.settings.gmail_scopes)

    def validate_scopes(self, credentials: Credentials) -> tuple[bool, Optional[set[str]]]:
        """Validate that credentials have all required scopes.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            Tuple of (is_valid, missing_scopes)
        """
        if not credentials or not credentials.scopes:
            return False, self.required_scopes

        cred_scopes = set(credentials.scopes)
        missing_scopes = self.required_scopes - cred_scopes

        if missing_scopes:
            logger.warning(f"Credentials missing scopes: {missing_scopes}")
            return False, missing_scopes

        return True, None

    def validate_token_freshness(self, credentials: Credentials) -> bool:
        """Check if credentials token is still valid (not expired).

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            True if token is valid
        """
        if not credentials:
            return False

        return credentials.valid

    def has_refresh_token(self, credentials: Credentials) -> bool:
        """Check if credentials have a refresh token.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            True if refresh token exists
        """
        if not credentials:
            return False

        return bool(credentials.refresh_token)

    def validate_credentials(
        self,
        credentials: Credentials,
        check_freshness: bool = True,
        check_scopes: bool = True,
        check_refresh_token: bool = True,
    ) -> tuple[bool, list[str]]:
        """Comprehensive credential validation.

        Args:
            credentials: Google OAuth2 credentials
            check_freshness: Whether to check if token is expired
            check_scopes: Whether to validate scopes
            check_refresh_token: Whether to check for refresh token

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not credentials:
            errors.append("Credentials are None")
            return False, errors

        # Check token freshness
        if check_freshness and not self.validate_token_freshness(credentials):
            if credentials.expired:
                errors.append("Token is expired")
            else:
                errors.append("Token is invalid")

        # Check scopes
        if check_scopes:
            is_valid, missing_scopes = self.validate_scopes(credentials)
            if not is_valid:
                errors.append(f"Missing required scopes: {missing_scopes}")

        # Check refresh token
        if check_refresh_token and not self.has_refresh_token(credentials):
            errors.append("No refresh token available")

        is_valid = len(errors) == 0
        return is_valid, errors

    def get_credential_info(self, credentials: Credentials) -> dict:
        """Get information about credentials for debugging.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            Dictionary with credential information
        """
        if not credentials:
            return {"valid": False, "error": "Credentials are None"}

        return {
            "valid": credentials.valid,
            "expired": credentials.expired,
            "has_refresh_token": bool(credentials.refresh_token),
            "scopes": list(credentials.scopes) if credentials.scopes else [],
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id[:20] + "..." if credentials.client_id else None,
        }


def validate_credentials_or_raise(credentials: Credentials) -> None:
    """Validate credentials and raise exception if invalid.

    Args:
        credentials: Google OAuth2 credentials

    Raises:
        ValueError: If credentials are invalid
    """
    validator = CredentialValidator()
    is_valid, errors = validator.validate_credentials(
        credentials,
        check_freshness=False,  # Don't fail on expired tokens (can be refreshed)
        check_scopes=True,
        check_refresh_token=True,
    )

    if not is_valid:
        error_msg = "Invalid credentials: " + "; ".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)
