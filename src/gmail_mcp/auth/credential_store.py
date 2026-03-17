"""
Fabric-compliant credential storage for gwark.

Stores Google OAuth2 tokens following the Fabric Protocol:
- Environment variables (GWARK_*)
- OS Keyring (fabric-gwark service)
- .env file fallback

Each Google API service gets its own keyring entry to support
different scopes (Gmail, Calendar, Drive, etc.).
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

# Keyring is optional but strongly recommended
try:
    import keyring
    from keyring.errors import KeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception  # type: ignore


class CredentialStore:
    """Credential storage with env -> keyring -> .env priority.

    Supports Google OAuth2 credentials with per-service token storage.
    Compatible with Fabric workspace conventions.
    """

    SERVICE = "gwark"
    KEYRING_SERVICE = f"fabric-{SERVICE}"  # = "fabric-gwark"

    def __init__(self, env_file: Optional[Path] = None):
        self.env_file = env_file or Path.cwd() / ".env"

    def _env_var(self, key: str) -> str:
        """Convert key to env var name: access_token → GWARK_ACCESS_TOKEN"""
        return f"{self.SERVICE.upper()}_{key.upper()}"

    # --- Basic Credential Operations ---

    def get(self, key: str) -> Optional[str]:
        """Get credential: env -> keyring -> .env"""
        # 1. Environment variable
        if value := os.environ.get(self._env_var(key)):
            return value

        # 2. OS Keyring
        if KEYRING_AVAILABLE:
            try:
                if value := keyring.get_password(self.KEYRING_SERVICE, key):
                    return value
            except KeyringError:
                pass

        # 3. .env file
        return self._get_from_dotenv(key)

    def set(self, key: str, value: str) -> None:
        """Store credential in keyring, or .env if unavailable."""
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(self.KEYRING_SERVICE, key, value)
                return
            except KeyringError:
                pass

        # Fallback to .env
        self._set_in_dotenv(key, value)

    def delete(self, key: str) -> bool:
        """Delete credential from keyring and .env."""
        deleted = False

        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.KEYRING_SERVICE, key)
                deleted = True
            except KeyringError:
                pass

        if self._delete_from_dotenv(key):
            deleted = True

        return deleted

    def get_source(self, key: str) -> str:
        """Identify where credential is stored: environment|keyring|dotenv|none"""
        if os.environ.get(self._env_var(key)):
            return "environment"

        if KEYRING_AVAILABLE:
            try:
                if keyring.get_password(self.KEYRING_SERVICE, key):
                    return "keyring"
            except KeyringError:
                pass

        if self._get_from_dotenv(key):
            return "dotenv"

        return "none"

    # --- Google OAuth2 Token Operations ---

    def _token_key(self, service_name: str) -> str:
        """Keyring key for a specific Google service's tokens.

        Args:
            service_name: Google service name (gmail, calendar, drive, sheets, etc.)
        """
        return f"__oauth_tokens_{service_name}__"

    def save_google_credentials(
        self,
        credentials: Credentials,
        service_name: str = "default",
    ) -> None:
        """Save Google OAuth2 credentials to keyring.

        Args:
            credentials: Google OAuth2 Credentials object
            service_name: Which Google service (gmail, calendar, drive, etc.)
        """
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }

        token_json = json.dumps(token_data)
        key = self._token_key(service_name)

        self.set(key, token_json)
        logger.info(f"Saved credentials for service: {service_name}")

    def load_google_credentials(
        self,
        service_name: str = "default",
    ) -> Optional[Credentials]:
        """Load Google OAuth2 credentials from keyring.

        Args:
            service_name: Which Google service (gmail, calendar, drive, etc.)

        Returns:
            Google Credentials object or None
        """
        key = self._token_key(service_name)
        token_json = self.get(key)

        if not token_json:
            return None

        try:
            token_data = json.loads(token_json)
            credentials = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
            )
            logger.info(f"Loaded credentials for service: {service_name}")
            return credentials
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to load credentials for {service_name}: {e}")
            return None

    def delete_google_credentials(self, service_name: str = "default") -> bool:
        """Delete stored credentials for a Google service."""
        key = self._token_key(service_name)
        return self.delete(key)

    def has_google_credentials(self, service_name: str = "default") -> bool:
        """Check if credentials exist for a Google service."""
        key = self._token_key(service_name)
        return self.get_source(key) != "none"

    def list_services(self) -> list[str]:
        """List all Google services with stored credentials."""
        services = []
        # Check known services
        for svc in ["gmail", "calendar", "drive", "sheets", "docs",
                     "forms", "slides", "people", "default"]:
            if self.has_google_credentials(svc):
                services.append(svc)
        return services

    def get_credentials_source(self, service_name: str = "default") -> str:
        """Get where credentials for a service are stored."""
        key = self._token_key(service_name)
        return self.get_source(key)

    def status(self) -> dict:
        """Get authentication status for CLI display."""
        services = self.list_services()
        if services:
            return {
                "authenticated": True,
                "services": services,
                "source": self.get_credentials_source(services[0]),
                "keyring_available": KEYRING_AVAILABLE,
            }

        return {
            "authenticated": False,
            "services": [],
            "source": "none",
            "keyring_available": KEYRING_AVAILABLE,
        }

    # --- .env file operations ---

    def _parse_dotenv(self) -> dict[str, str]:
        """Parse .env file into dict."""
        if not self.env_file.exists():
            return {}

        result = {}
        try:
            for line in self.env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    value = value.strip().strip("\"'")
                    result[key.strip()] = value
        except OSError:
            pass

        return result

    def _write_dotenv(self, data: dict[str, str]) -> None:
        """Write dict to .env file."""
        lines = [f"{k}={v}" for k, v in sorted(data.items())]
        try:
            self.env_file.parent.mkdir(parents=True, exist_ok=True)
            self.env_file.write_text(
                "\n".join(lines) + "\n" if lines else "",
                encoding="utf-8",
            )
            if os.name != "nt":
                os.chmod(self.env_file, 0o600)
        except OSError:
            pass

    def _get_from_dotenv(self, key: str) -> Optional[str]:
        """Get value from .env file."""
        return self._parse_dotenv().get(self._env_var(key))

    def _set_in_dotenv(self, key: str, value: str) -> None:
        """Set value in .env file."""
        data = self._parse_dotenv()
        data[self._env_var(key)] = value
        self._write_dotenv(data)

    def _delete_from_dotenv(self, key: str) -> bool:
        """Delete value from .env file."""
        data = self._parse_dotenv()
        env_key = self._env_var(key)
        if env_key in data:
            del data[env_key]
            self._write_dotenv(data)
            return True
        return False


# Module-level singleton
_store: Optional[CredentialStore] = None


def get_credential_store() -> CredentialStore:
    """Get or create the credential store singleton."""
    global _store
    if _store is None:
        _store = CredentialStore()
    return _store
