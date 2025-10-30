"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest

from gmail_mcp.cache import EmailCache, PaginationManager
from gmail_mcp.config import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create test settings with temporary paths."""
    settings = Settings(
        cache_db_path=tmp_path / "cache" / "test.db",
        token_storage_path=tmp_path / "tokens",
        debug_mode=True,
        mock_gmail_api=True,
    )
    return settings


@pytest.fixture
async def email_cache(tmp_path: Path) -> AsyncGenerator[EmailCache, None]:
    """Create email cache for testing."""
    cache = EmailCache(db_path=tmp_path / "test_cache.db", ttl_seconds=60)
    await cache.initialize()
    yield cache
    await cache.close()


@pytest.fixture
def pagination_manager() -> PaginationManager:
    """Create pagination manager for testing."""
    return PaginationManager()


@pytest.fixture
def mock_gmail_client() -> MagicMock:
    """Create mock Gmail client."""
    client = MagicMock()
    client.account_id = "test_account"
    return client


@pytest.fixture
def sample_email_metadata() -> dict:
    """Sample email metadata for testing."""
    return {
        "id": "test_message_123",
        "threadId": "test_thread_123",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "This is a test email",
        "sizeEstimate": 1024,
        "internalDate": "1234567890000",
    }


@pytest.fixture
def sample_email_content() -> dict:
    """Sample email content for testing."""
    return {
        "id": "test_message_123",
        "threadId": "test_thread_123",
        "labelIds": ["INBOX"],
        "snippet": "This is a test email",
        "payload": {
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Subject", "value": "Test Email"},
                {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"},
            ],
            "body": {"data": "VGVzdCBlbWFpbCBjb250ZW50"},  # base64 "Test email content"
        },
    }
