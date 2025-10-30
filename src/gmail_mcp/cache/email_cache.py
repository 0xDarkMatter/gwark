"""SQLite-based email metadata cache for improved performance."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from gmail_mcp.config import get_settings

logger = logging.getLogger(__name__)


class EmailCache:
    """Async SQLite-based cache for email metadata and content."""

    def __init__(self, db_path: Optional[Path] = None, ttl_seconds: Optional[int] = None):
        """Initialize email cache.

        Args:
            db_path: Path to SQLite database file
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        settings = get_settings()
        self.db_path = db_path or settings.cache_db_path
        self.ttl_seconds = ttl_seconds or settings.cache_ttl_seconds

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        logger.info(f"Email cache initialized: {self.db_path}, TTL={self.ttl_seconds}s")

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        async with self._lock:
            if self._db is None:
                self._db = await aiosqlite.connect(str(self.db_path))
                await self._create_tables()
                logger.info("Email cache database initialized")

    async def _create_tables(self) -> None:
        """Create cache tables if they don't exist."""
        if not self._db:
            return

        # Email metadata cache
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS email_metadata (
                account_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                PRIMARY KEY (account_id, message_id)
            )
            """
        )

        # Email content cache
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS email_content (
                account_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                content_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                size_bytes INTEGER NOT NULL,
                PRIMARY KEY (account_id, message_id)
            )
            """
        )

        # Search results cache
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS search_results (
                account_id TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                PRIMARY KEY (account_id, query_hash)
            )
            """
        )

        # Create indexes for faster lookups
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_metadata_accessed ON email_metadata(accessed_at)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_accessed ON email_content(accessed_at)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_accessed ON search_results(accessed_at)"
        )

        await self._db.commit()

    async def get_metadata(
        self, account_id: str, message_id: str
    ) -> Optional[dict[str, Any]]:
        """Get email metadata from cache.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID

        Returns:
            Cached metadata or None if not found/expired
        """
        if not self._db:
            await self.initialize()

        async with self._lock:
            cursor = await self._db.execute(  # type: ignore
                """
                SELECT metadata_json, created_at
                FROM email_metadata
                WHERE account_id = ? AND message_id = ?
                """,
                (account_id, message_id),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            metadata_json, created_at = row

            # Check if expired
            if time.time() - created_at > self.ttl_seconds:
                logger.debug(f"Cache expired for message {message_id}")
                await self.delete_metadata(account_id, message_id)
                return None

            # Update access time
            await self._db.execute(  # type: ignore
                """
                UPDATE email_metadata
                SET accessed_at = ?
                WHERE account_id = ? AND message_id = ?
                """,
                (time.time(), account_id, message_id),
            )
            await self._db.commit()  # type: ignore

            return json.loads(metadata_json)

    async def set_metadata(
        self, account_id: str, message_id: str, metadata: dict[str, Any]
    ) -> None:
        """Store email metadata in cache.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID
            metadata: Metadata dictionary to cache
        """
        if not self._db:
            await self.initialize()

        metadata_json = json.dumps(metadata)
        now = time.time()

        async with self._lock:
            await self._db.execute(  # type: ignore
                """
                INSERT OR REPLACE INTO email_metadata
                (account_id, message_id, metadata_json, created_at, accessed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account_id, message_id, metadata_json, now, now),
            )
            await self._db.commit()  # type: ignore

        logger.debug(f"Cached metadata for message {message_id}")

    async def get_content(
        self, account_id: str, message_id: str
    ) -> Optional[dict[str, Any]]:
        """Get email content from cache.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID

        Returns:
            Cached content or None if not found/expired
        """
        if not self._db:
            await self.initialize()

        async with self._lock:
            cursor = await self._db.execute(  # type: ignore
                """
                SELECT content_json, created_at
                FROM email_content
                WHERE account_id = ? AND message_id = ?
                """,
                (account_id, message_id),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            content_json, created_at = row

            if time.time() - created_at > self.ttl_seconds:
                logger.debug(f"Cache expired for content {message_id}")
                await self.delete_content(account_id, message_id)
                return None

            # Update access time
            await self._db.execute(  # type: ignore
                """
                UPDATE email_content
                SET accessed_at = ?
                WHERE account_id = ? AND message_id = ?
                """,
                (time.time(), account_id, message_id),
            )
            await self._db.commit()  # type: ignore

            return json.loads(content_json)

    async def set_content(
        self, account_id: str, message_id: str, content: dict[str, Any]
    ) -> None:
        """Store email content in cache.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID
            content: Content dictionary to cache
        """
        if not self._db:
            await self.initialize()

        content_json = json.dumps(content)
        size_bytes = len(content_json)
        now = time.time()

        async with self._lock:
            await self._db.execute(  # type: ignore
                """
                INSERT OR REPLACE INTO email_content
                (account_id, message_id, content_json, created_at, accessed_at, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (account_id, message_id, content_json, now, now, size_bytes),
            )
            await self._db.commit()  # type: ignore

        logger.debug(f"Cached content for message {message_id} ({size_bytes} bytes)")

    async def delete_metadata(self, account_id: str, message_id: str) -> None:
        """Delete metadata from cache.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID
        """
        if not self._db:
            return

        async with self._lock:
            await self._db.execute(  # type: ignore
                "DELETE FROM email_metadata WHERE account_id = ? AND message_id = ?",
                (account_id, message_id),
            )
            await self._db.commit()  # type: ignore

    async def delete_content(self, account_id: str, message_id: str) -> None:
        """Delete content from cache.

        Args:
            account_id: Account identifier
            message_id: Gmail message ID
        """
        if not self._db:
            return

        async with self._lock:
            await self._db.execute(  # type: ignore
                "DELETE FROM email_content WHERE account_id = ? AND message_id = ?",
                (account_id, message_id),
            )
            await self._db.commit()  # type: ignore

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        if not self._db:
            await self.initialize()

        cutoff_time = time.time() - self.ttl_seconds

        async with self._lock:
            # Clean metadata
            cursor = await self._db.execute(  # type: ignore
                "DELETE FROM email_metadata WHERE created_at < ?",
                (cutoff_time,),
            )
            metadata_count = cursor.rowcount

            # Clean content
            cursor = await self._db.execute(  # type: ignore
                "DELETE FROM email_content WHERE created_at < ?",
                (cutoff_time,),
            )
            content_count = cursor.rowcount

            # Clean search results
            cursor = await self._db.execute(  # type: ignore
                "DELETE FROM search_results WHERE created_at < ?",
                (cutoff_time,),
            )
            search_count = cursor.rowcount

            await self._db.commit()  # type: ignore

            total = metadata_count + content_count + search_count
            if total > 0:
                logger.info(f"Cleaned up {total} expired cache entries")

            return total

    async def clear_account(self, account_id: str) -> None:
        """Clear all cache entries for an account.

        Args:
            account_id: Account identifier
        """
        if not self._db:
            return

        async with self._lock:
            await self._db.execute(  # type: ignore
                "DELETE FROM email_metadata WHERE account_id = ?", (account_id,)
            )
            await self._db.execute(  # type: ignore
                "DELETE FROM email_content WHERE account_id = ?", (account_id,)
            )
            await self._db.execute(  # type: ignore
                "DELETE FROM search_results WHERE account_id = ?", (account_id,)
            )
            await self._db.commit()  # type: ignore

        logger.info(f"Cleared cache for account {account_id}")

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self._db:
            await self.initialize()

        async with self._lock:
            # Count entries
            cursor = await self._db.execute("SELECT COUNT(*) FROM email_metadata")  # type: ignore
            metadata_count = (await cursor.fetchone())[0]

            cursor = await self._db.execute("SELECT COUNT(*) FROM email_content")  # type: ignore
            content_count = (await cursor.fetchone())[0]

            cursor = await self._db.execute("SELECT COUNT(*) FROM search_results")  # type: ignore
            search_count = (await cursor.fetchone())[0]

            # Get total size
            cursor = await self._db.execute(  # type: ignore
                "SELECT SUM(size_bytes) FROM email_content"
            )
            total_size = (await cursor.fetchone())[0] or 0

            return {
                "metadata_entries": metadata_count,
                "content_entries": content_count,
                "search_entries": search_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "ttl_seconds": self.ttl_seconds,
                "db_path": str(self.db_path),
            }

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Email cache closed")
