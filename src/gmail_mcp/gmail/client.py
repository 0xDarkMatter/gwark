"""Gmail API client wrapper with async support and error handling."""

import asyncio
import logging
from typing import Any, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_mcp.auth import OAuth2Manager, TokenManager
from gmail_mcp.config import get_settings
from gmail_mcp.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class GmailClient:
    """Async wrapper around Gmail API with authentication and rate limiting."""

    def __init__(
        self,
        account_id: str = "primary",
        credentials: Optional[Credentials] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """Initialize Gmail client.

        Args:
            account_id: Account identifier
            credentials: Google OAuth2 credentials
            rate_limiter: Rate limiter instance
        """
        self.settings = get_settings()
        self.account_id = account_id
        self.credentials = credentials
        self.rate_limiter = rate_limiter or RateLimiter()

        self.oauth_manager = OAuth2Manager()
        self.token_manager = TokenManager()

        self._service: Optional[Any] = None
        logger.info(f"Gmail client initialized for account: {account_id}")

    async def _ensure_authenticated(self) -> None:
        """Ensure client has valid credentials."""
        if self.credentials is None:
            # Try to load from token manager
            self.credentials = await self.token_manager.async_load_credentials(
                self.account_id
            )

            if self.credentials is None:
                raise ValueError(
                    f"No credentials found for account {self.account_id}. "
                    "Please run OAuth2 setup first."
                )

        # Check if credentials are valid
        if not self.oauth_manager.validate_credentials(self.credentials):
            # Try to refresh
            try:
                self.credentials = await self.oauth_manager.async_refresh_credentials(
                    self.credentials
                )
                # Save refreshed credentials
                await self.token_manager.async_save_credentials(
                    self.credentials, self.account_id
                )
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                raise ValueError(
                    f"Invalid credentials for account {self.account_id}. "
                    "Please re-authenticate."
                )

    async def _get_service(self) -> Any:
        """Get or create Gmail API service.

        Returns:
            Gmail API service instance
        """
        await self._ensure_authenticated()

        if self._service is None:
            # Build service in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self._service = await loop.run_in_executor(
                None,
                lambda: build(
                    "gmail",
                    "v1",
                    credentials=self.credentials,
                    cache_discovery=False,
                ),
            )

        return self._service

    async def execute_with_retry(
        self,
        request: Any,
        max_retries: Optional[int] = None,
    ) -> Any:
        """Execute API request with retry logic and rate limiting.

        Args:
            request: Gmail API request object
            max_retries: Maximum number of retries

        Returns:
            API response

        Raises:
            HttpError: If request fails after retries
        """
        max_retries = max_retries or self.settings.retry_attempts
        backoff = self.settings.retry_backoff_factor

        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                await self.rate_limiter.acquire()

                # Execute request in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, request.execute)
                return response

            except HttpError as e:
                status_code = e.resp.status

                # Don't retry on client errors (4xx except rate limit)
                if 400 <= status_code < 500 and status_code != 429:
                    logger.error(f"Client error: {e}")
                    raise

                # Retry on rate limit and server errors
                if attempt < max_retries - 1:
                    wait_time = backoff ** attempt
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise

            except Exception as e:
                logger.error(f"Unexpected error executing request: {e}")
                raise

    async def list_messages(
        self,
        query: str = "",
        max_results: Optional[int] = None,
        page_token: Optional[str] = None,
        label_ids: Optional[list[str]] = None,
        include_spam_trash: bool = False,
    ) -> dict[str, Any]:
        """List messages matching query.

        Args:
            query: Gmail search query
            max_results: Maximum results to return
            page_token: Page token for pagination
            label_ids: Filter by label IDs
            include_spam_trash: Include spam and trash

        Returns:
            Response with messages and nextPageToken
        """
        service = await self._get_service()

        params = {
            "userId": "me",
            "q": query,
            "includeSpamTrash": include_spam_trash,
        }

        if max_results:
            params["maxResults"] = max_results
        if page_token:
            params["pageToken"] = page_token
        if label_ids:
            params["labelIds"] = label_ids

        request = service.users().messages().list(**params)
        return await self.execute_with_retry(request)

    async def get_message(
        self,
        message_id: str,
        format: str = "full",
        metadata_headers: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Get a specific message.

        Args:
            message_id: Gmail message ID
            format: Response format (full, metadata, minimal, raw)
            metadata_headers: Headers to include when format=metadata

        Returns:
            Message data
        """
        service = await self._get_service()

        params = {
            "userId": "me",
            "id": message_id,
            "format": format,
        }

        if metadata_headers and format == "metadata":
            params["metadataHeaders"] = metadata_headers

        request = service.users().messages().get(**params)
        return await self.execute_with_retry(request)

    async def modify_message(
        self,
        message_id: str,
        add_label_ids: Optional[list[str]] = None,
        remove_label_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Modify message labels.

        Args:
            message_id: Gmail message ID
            add_label_ids: Labels to add
            remove_label_ids: Labels to remove

        Returns:
            Modified message
        """
        service = await self._get_service()

        body = {}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        request = service.users().messages().modify(userId="me", id=message_id, body=body)
        return await self.execute_with_retry(request)

    async def batch_modify(
        self,
        message_ids: list[str],
        add_label_ids: Optional[list[str]] = None,
        remove_label_ids: Optional[list[str]] = None,
    ) -> None:
        """Batch modify messages.

        Args:
            message_ids: List of message IDs
            add_label_ids: Labels to add
            remove_label_ids: Labels to remove
        """
        service = await self._get_service()

        body = {"ids": message_ids}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        request = service.users().messages().batchModify(userId="me", body=body)
        await self.execute_with_retry(request)

    async def list_labels(self) -> dict[str, Any]:
        """List all labels.

        Returns:
            Response with labels
        """
        service = await self._get_service()
        request = service.users().labels().list(userId="me")
        return await self.execute_with_retry(request)

    async def get_label(self, label_id: str) -> dict[str, Any]:
        """Get a specific label.

        Args:
            label_id: Label ID

        Returns:
            Label data
        """
        service = await self._get_service()
        request = service.users().labels().get(userId="me", id=label_id)
        return await self.execute_with_retry(request)

    async def get_profile(self) -> dict[str, Any]:
        """Get user profile.

        Returns:
            User profile data
        """
        service = await self._get_service()
        request = service.users().getProfile(userId="me")
        return await self.execute_with_retry(request)

    async def close(self) -> None:
        """Close client and cleanup resources."""
        # Gmail API client doesn't require explicit cleanup
        # But we keep this for consistency
        self._service = None
        logger.info(f"Gmail client closed for account: {self.account_id}")
