"""MCP tool handlers for Gmail operations."""

import logging
from typing import Any

from gmail_mcp.cache import EmailCache, PaginationManager
from gmail_mcp.gmail import GmailClient, GmailOperations
from gmail_mcp.gmail.batch import BatchOperations
from gmail_mcp.server.schemas import (
    ApplyLabelsRequest,
    ArchiveRequest,
    BatchApplyLabelsRequest,
    BatchReadRequest,
    GetProfileRequest,
    ListLabelsRequest,
    MarkAsReadRequest,
    MarkAsUnreadRequest,
    ReadEmailRequest,
    RemoveLabelsRequest,
    SearchEmailsRequest,
    StarRequest,
    UnstarRequest,
)
from gmail_mcp.utils.validators import ValidationError

logger = logging.getLogger(__name__)


class GmailToolHandlers:
    """Handlers for Gmail MCP tools."""

    def __init__(self):
        """Initialize tool handlers."""
        self.clients: dict[str, GmailClient] = {}
        self.operations: dict[str, GmailOperations] = {}
        self.batch_ops: dict[str, BatchOperations] = {}
        self.cache = EmailCache()
        self.pagination_manager = PaginationManager()

        logger.info("Gmail tool handlers initialized")

    async def _get_or_create_client(self, account_id: str) -> GmailClient:
        """Get or create Gmail client for account.

        Args:
            account_id: Account identifier

        Returns:
            Gmail client instance
        """
        if account_id not in self.clients:
            self.clients[account_id] = GmailClient(account_id=account_id)

        return self.clients[account_id]

    async def _get_or_create_operations(
        self, account_id: str
    ) -> GmailOperations:
        """Get or create Gmail operations for account.

        Args:
            account_id: Account identifier

        Returns:
            Gmail operations instance
        """
        if account_id not in self.operations:
            client = await self._get_or_create_client(account_id)
            self.operations[account_id] = GmailOperations(
                client=client,
                cache=self.cache,
                pagination_manager=self.pagination_manager,
            )

        return self.operations[account_id]

    async def _get_or_create_batch_ops(
        self, account_id: str
    ) -> BatchOperations:
        """Get or create batch operations for account.

        Args:
            account_id: Account identifier

        Returns:
            Batch operations instance
        """
        if account_id not in self.batch_ops:
            client = await self._get_or_create_client(account_id)
            self.batch_ops[account_id] = BatchOperations(client=client)

        return self.batch_ops[account_id]

    async def search_emails(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle search_emails tool.

        Args:
            params: Tool parameters

        Returns:
            Search results
        """
        try:
            request = SearchEmailsRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.search_emails(
                query=request.query,
                max_results=request.max_results,
                page_size=request.page_size,
                page_token=request.page_token,
            )

            logger.info(
                f"Search completed: {len(result['messages'])} results, "
                f"account={request.account_id}"
            )
            return result

        except ValidationError as e:
            logger.error(f"Validation error in search_emails: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in search_emails: {e}")
            raise

    async def read_email(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle read_email tool.

        Args:
            params: Tool parameters

        Returns:
            Email message data
        """
        try:
            request = ReadEmailRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.read_email(
                message_id=request.message_id,
                format=request.format,
            )

            logger.info(f"Read email: {request.message_id}, account={request.account_id}")
            return result

        except Exception as e:
            logger.error(f"Error in read_email: {e}")
            raise

    async def list_labels(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle list_labels tool.

        Args:
            params: Tool parameters

        Returns:
            List of labels
        """
        try:
            request = ListLabelsRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            labels = await ops.list_labels()

            logger.info(f"Listed {len(labels)} labels, account={request.account_id}")
            return {"labels": labels, "count": len(labels)}

        except Exception as e:
            logger.error(f"Error in list_labels: {e}")
            raise

    async def apply_labels(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle apply_labels tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = ApplyLabelsRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.apply_labels(
                message_id=request.message_id,
                label_ids=request.label_ids,
                remove_labels=request.remove_labels,
            )

            logger.info(
                f"Applied labels to {request.message_id}, account={request.account_id}"
            )
            return result

        except Exception as e:
            logger.error(f"Error in apply_labels: {e}")
            raise

    async def remove_labels(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle remove_labels tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = RemoveLabelsRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.remove_labels(
                message_id=request.message_id,
                label_ids=request.label_ids,
            )

            logger.info(
                f"Removed labels from {request.message_id}, account={request.account_id}"
            )
            return result

        except Exception as e:
            logger.error(f"Error in remove_labels: {e}")
            raise

    async def mark_as_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle mark_as_read tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = MarkAsReadRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.mark_as_read(request.message_id)

            logger.info(f"Marked as read: {request.message_id}, account={request.account_id}")
            return result

        except Exception as e:
            logger.error(f"Error in mark_as_read: {e}")
            raise

    async def mark_as_unread(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle mark_as_unread tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = MarkAsUnreadRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.mark_as_unread(request.message_id)

            logger.info(
                f"Marked as unread: {request.message_id}, account={request.account_id}"
            )
            return result

        except Exception as e:
            logger.error(f"Error in mark_as_unread: {e}")
            raise

    async def archive(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle archive tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = ArchiveRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.archive(request.message_id)

            logger.info(f"Archived: {request.message_id}, account={request.account_id}")
            return result

        except Exception as e:
            logger.error(f"Error in archive: {e}")
            raise

    async def star(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle star tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = StarRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.star(request.message_id)

            logger.info(f"Starred: {request.message_id}, account={request.account_id}")
            return result

        except Exception as e:
            logger.error(f"Error in star: {e}")
            raise

    async def unstar(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle unstar tool.

        Args:
            params: Tool parameters

        Returns:
            Modified message
        """
        try:
            request = UnstarRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.unstar(request.message_id)

            logger.info(f"Unstarred: {request.message_id}, account={request.account_id}")
            return result

        except Exception as e:
            logger.error(f"Error in unstar: {e}")
            raise

    async def batch_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle batch_read tool.

        Args:
            params: Tool parameters

        Returns:
            Batch read results
        """
        try:
            request = BatchReadRequest(**params)
            batch_ops = await self._get_or_create_batch_ops(request.account_id)

            result = await batch_ops.batch_read(
                message_ids=request.message_ids,
                format=request.format,
            )

            logger.info(
                f"Batch read: {result['success_count']}/{result['total']} successful, "
                f"account={request.account_id}"
            )
            return result

        except Exception as e:
            logger.error(f"Error in batch_read: {e}")
            raise

    async def batch_apply_labels(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle batch_apply_labels tool.

        Args:
            params: Tool parameters

        Returns:
            Batch operation results
        """
        try:
            request = BatchApplyLabelsRequest(**params)
            batch_ops = await self._get_or_create_batch_ops(request.account_id)

            result = await batch_ops.batch_apply_labels(
                message_ids=request.message_ids,
                add_label_ids=request.add_label_ids,
                remove_label_ids=request.remove_label_ids,
            )

            logger.info(
                f"Batch apply labels: {result['success_count']}/{result['total']} successful, "
                f"account={request.account_id}"
            )
            return result

        except Exception as e:
            logger.error(f"Error in batch_apply_labels: {e}")
            raise

    async def get_profile(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle get_profile tool.

        Args:
            params: Tool parameters

        Returns:
            User profile data
        """
        try:
            request = GetProfileRequest(**params)
            ops = await self._get_or_create_operations(request.account_id)

            result = await ops.get_profile()

            logger.info(f"Retrieved profile for account={request.account_id}")
            return result

        except Exception as e:
            logger.error(f"Error in get_profile: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Close all operations
        for ops in self.operations.values():
            await ops.close()

        # Close cache
        if self.cache:
            await self.cache.close()

        logger.info("Gmail tool handlers cleaned up")
