"""Configuration schemas for gwark."""

from .config import (
    GwarkConfig,
    ProfileConfig,
    EmailFilters,
    CalendarFilters,
    DriveFilters,
)
from .themes import (
    TextStyle,
    ParagraphStyle,
    DocTheme,
    get_default_theme,
)

__all__ = [
    "GwarkConfig",
    "ProfileConfig",
    "EmailFilters",
    "CalendarFilters",
    "DriveFilters",
    "TextStyle",
    "ParagraphStyle",
    "DocTheme",
    "get_default_theme",
]
