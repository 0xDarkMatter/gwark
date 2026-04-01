"""Configuration settings for Gwark server."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import (
    CACHE_TTL_SECONDS,
    DEFAULT_ACCOUNT_ID,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONNECTION_POOL_SIZE,
    DEFAULT_MAX_CONCURRENT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_RATE_LIMIT_BURST,
    DEFAULT_RATE_LIMIT_PER_SECOND,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    GMAIL_SCOPES,
    MAX_ACCOUNTS,
    MAX_BATCH_SIZE,
    MAX_CACHE_SIZE_MB,
    MAX_RESULTS_PER_SEARCH,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server Configuration
    server_name: str = Field(default="Gwark Server", description="Server name")
    server_version: str = Field(default="0.1.0", description="Server version")
    log_level: str = Field(default="INFO", description="Logging level")

    # OAuth2 Configuration
    oauth2_credentials_path: Path = Field(
        default=Path(".gwark/credentials/oauth2_credentials.json"),
        description="Path to OAuth2 credentials file",
    )
    token_storage_path: Path = Field(
        default=Path(".gwark/tokens"), description="Directory for storing OAuth2 tokens"
    )
    encryption_key: Optional[str] = Field(
        default=None, description="Fernet encryption key for tokens"
    )
    gmail_scopes: list[str] = Field(
        default=GMAIL_SCOPES, description="Gmail API scopes"
    )

    # Cache Configuration
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_db_path: Path = Field(
        default=Path(".gwark/cache/email_cache.db"), description="SQLite cache database path"
    )
    cache_ttl_seconds: int = Field(
        default=CACHE_TTL_SECONDS, description="Cache TTL in seconds"
    )
    max_cache_size_mb: int = Field(
        default=MAX_CACHE_SIZE_MB, description="Maximum cache size in MB"
    )

    # Gmail API Configuration
    default_page_size: int = Field(
        default=DEFAULT_PAGE_SIZE, description="Default pagination size"
    )
    max_batch_size: int = Field(
        default=MAX_BATCH_SIZE, description="Maximum batch operation size"
    )
    default_batch_size: int = Field(
        default=DEFAULT_BATCH_SIZE, description="Default batch size"
    )
    max_results_per_search: int = Field(
        default=MAX_RESULTS_PER_SEARCH, description="Maximum search results"
    )
    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS, description="API timeout in seconds"
    )
    retry_attempts: int = Field(
        default=DEFAULT_RETRY_ATTEMPTS, description="Number of retry attempts"
    )
    retry_backoff_factor: float = Field(
        default=DEFAULT_RETRY_BACKOFF_FACTOR, description="Retry backoff factor"
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_per_second: int = Field(
        default=DEFAULT_RATE_LIMIT_PER_SECOND, description="Rate limit per second"
    )
    rate_limit_burst: int = Field(
        default=DEFAULT_RATE_LIMIT_BURST, description="Rate limit burst size"
    )

    # Multi-Account Support
    default_account_id: str = Field(
        default=DEFAULT_ACCOUNT_ID, description="Default account ID"
    )
    max_accounts: int = Field(default=MAX_ACCOUNTS, description="Maximum number of accounts")

    # Performance
    enable_async: bool = Field(default=True, description="Enable async operations")
    connection_pool_size: int = Field(
        default=DEFAULT_CONNECTION_POOL_SIZE, description="Connection pool size"
    )
    max_concurrent: int = Field(
        default=DEFAULT_MAX_CONCURRENT, description="Maximum concurrent API operations"
    )

    # Development
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    mock_gmail_api: bool = Field(default=False, description="Use mock Gmail API")

    def __init__(self, **kwargs):  # type: ignore
        """Initialize settings and create necessary directories."""
        super().__init__(**kwargs)
        self._create_directories()

    def _create_directories(self) -> None:
        """Create required directories if they don't exist."""
        directories = [
            self.token_storage_path,
            self.cache_db_path.parent,
            Path("logs"),
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.debug_mode or os.getenv("ENVIRONMENT") == "development"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
