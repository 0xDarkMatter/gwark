"""Token storage and management with encryption support."""

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials

from gmail_mcp.config import get_settings
from gmail_mcp.config.constants import TOKEN_FILE_EXTENSION

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages encrypted storage and retrieval of OAuth2 tokens for multiple accounts."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        encryption_key: Optional[str] = None,
    ):
        """Initialize token manager.

        Args:
            storage_path: Directory for storing token files
            encryption_key: Fernet encryption key (auto-generated if not provided)
        """
        self.settings = get_settings()
        self.storage_path = storage_path or self.settings.token_storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        if encryption_key:
            self.encryption_key = encryption_key.encode()
        else:
            self.encryption_key = self._get_or_create_encryption_key()

        self.cipher = Fernet(self.encryption_key)
        logger.info(f"Token manager initialized with storage path: {self.storage_path}")

    def _get_or_create_encryption_key(self) -> bytes:
        """Get existing encryption key or create a new one.

        Returns:
            Fernet encryption key
        """
        key_file = self.storage_path / ".encryption_key"

        if key_file.exists():
            with open(key_file, "rb") as f:
                key = f.read()
            logger.debug("Loaded existing encryption key")
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            # Restrict permissions on the key file
            key_file.chmod(0o600)
            logger.info("Generated new encryption key")

        return key

    def _get_token_file_path(self, account_id: str) -> Path:
        """Get the file path for a specific account's token.

        Args:
            account_id: Unique identifier for the account

        Returns:
            Path to token file
        """
        # Sanitize account_id to prevent path traversal
        safe_account_id = "".join(
            c for c in account_id if c.isalnum() or c in ("-", "_")
        )
        return self.storage_path / f"{safe_account_id}{TOKEN_FILE_EXTENSION}"

    def save_credentials(
        self,
        credentials: Credentials,
        account_id: str = "primary",
    ) -> None:
        """Save encrypted credentials to disk.

        Args:
            credentials: Google OAuth2 credentials
            account_id: Unique identifier for the account
        """
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

        # Serialize to JSON
        token_json = json.dumps(token_data)

        # Encrypt
        encrypted_data = self.cipher.encrypt(token_json.encode())

        # Write to file
        token_file = self._get_token_file_path(account_id)
        with open(token_file, "wb") as f:
            f.write(encrypted_data)

        # Restrict permissions
        token_file.chmod(0o600)

        logger.info(f"Saved encrypted credentials for account: {account_id}")

    def _load_pickle_fallback(self, account_id: str) -> Optional[Credentials]:
        """Try to load credentials from legacy pickle format.

        Args:
            account_id: Account identifier (used to find gmail_token.pickle)

        Returns:
            Credentials if found, None otherwise
        """
        # Try common pickle file names
        pickle_names = [
            f"{account_id}_token.pickle",
            "gmail_token.pickle",
            f"{account_id}.pickle",
        ]

        for pickle_name in pickle_names:
            pickle_file = self.storage_path / pickle_name
            if pickle_file.exists():
                try:
                    with open(pickle_file, "rb") as f:
                        creds = pickle.load(f)
                    if isinstance(creds, Credentials):
                        logger.info(f"Loaded credentials from legacy pickle: {pickle_name}")
                        return creds
                except Exception as e:
                    logger.debug(f"Failed to load pickle {pickle_name}: {e}")

        return None

    def load_credentials(self, account_id: str = "primary") -> Optional[Credentials]:
        """Load encrypted credentials from disk.

        Args:
            account_id: Unique identifier for the account

        Returns:
            Google OAuth2 credentials or None if not found
        """
        token_file = self._get_token_file_path(account_id)

        if not token_file.exists():
            # Try legacy pickle fallback
            creds = self._load_pickle_fallback(account_id)
            if creds:
                return creds
            logger.warning(f"No credentials found for account: {account_id}")
            return None

        try:
            # Read encrypted data
            with open(token_file, "rb") as f:
                encrypted_data = f.read()

            # Decrypt
            decrypted_data = self.cipher.decrypt(encrypted_data)
            token_data = json.loads(decrypted_data)

            # Reconstruct Credentials object
            credentials = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
            )

            logger.info(f"Loaded credentials for account: {account_id}")
            return credentials

        except Exception as e:
            logger.error(f"Failed to load credentials for {account_id}: {e}")
            # Try pickle fallback on decrypt failure too
            return self._load_pickle_fallback(account_id)

    def delete_credentials(self, account_id: str = "primary") -> bool:
        """Delete stored credentials for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if deleted, False if not found
        """
        token_file = self._get_token_file_path(account_id)

        if token_file.exists():
            token_file.unlink()
            logger.info(f"Deleted credentials for account: {account_id}")
            return True
        else:
            logger.warning(f"No credentials to delete for account: {account_id}")
            return False

    def list_accounts(self) -> list[str]:
        """List all accounts with stored credentials.

        Returns:
            List of account IDs
        """
        accounts = []
        for token_file in self.storage_path.glob(f"*{TOKEN_FILE_EXTENSION}"):
            account_id = token_file.stem
            accounts.append(account_id)

        logger.debug(f"Found {len(accounts)} stored accounts")
        return sorted(accounts)

    def has_credentials(self, account_id: str = "primary") -> bool:
        """Check if credentials exist for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if credentials exist
        """
        return self._get_token_file_path(account_id).exists()

    async def async_save_credentials(
        self,
        credentials: Credentials,
        account_id: str = "primary",
    ) -> None:
        """Async version of save_credentials.

        Args:
            credentials: Google OAuth2 credentials
            account_id: Unique identifier for the account
        """
        # For now, just wrap the sync version
        # In future, could use aiofiles for async file I/O
        self.save_credentials(credentials, account_id)

    async def async_load_credentials(
        self,
        account_id: str = "primary",
    ) -> Optional[Credentials]:
        """Async version of load_credentials.

        Args:
            account_id: Unique identifier for the account

        Returns:
            Google OAuth2 credentials or None if not found
        """
        # For now, just wrap the sync version
        return self.load_credentials(account_id)
