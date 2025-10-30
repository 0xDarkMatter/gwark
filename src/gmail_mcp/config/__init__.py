"""Configuration management."""

from .settings import Settings, get_settings
from .constants import (
    GMAIL_SCOPES,
    DEFAULT_PAGE_SIZE,
    MAX_BATCH_SIZE,
    CACHE_TTL_SECONDS,
)

__all__ = [
    "Settings",
    "get_settings",
    "GMAIL_SCOPES",
    "DEFAULT_PAGE_SIZE",
    "MAX_BATCH_SIZE",
    "CACHE_TTL_SECONDS",
]
