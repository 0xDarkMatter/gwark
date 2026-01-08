"""Configuration schemas for gwark using Pydantic."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class EmailFilters(BaseModel):
    """Email filtering configuration."""

    domains: list[str] = Field(default_factory=list, description="Include only these domains")
    senders: list[str] = Field(default_factory=list, description="Include only these senders")
    exclude_senders: list[str] = Field(default_factory=list, description="Exclude these senders")
    exclude_subjects: list[str] = Field(default_factory=list, description="Exclude emails with these subject patterns")
    exclude_domains: list[str] = Field(default_factory=list, description="Exclude these domains")


class CalendarFilters(BaseModel):
    """Calendar filtering configuration."""

    work_only: bool = Field(default=False, description="Filter to work-related meetings only")
    work_domains: list[str] = Field(default_factory=list, description="Domains considered work-related")
    exclude_keywords: list[str] = Field(default_factory=list, description="Keywords to exclude from meetings")
    include_declined: bool = Field(default=False, description="Include declined meetings")


class DriveFilters(BaseModel):
    """Drive filtering configuration."""

    exclude_folders: list[str] = Field(default_factory=list, description="Folders to exclude")
    include_shared_drives: bool = Field(default=True, description="Include shared drives")
    owned_only: bool = Field(default=False, description="Only show files you own")


class ProfileSettings(BaseModel):
    """Profile-specific settings overrides."""

    days_back: Optional[int] = Field(default=None, description="Default days to look back")
    max_results: Optional[int] = Field(default=None, description="Default max results")
    output_format: Optional[str] = Field(default=None, description="Default output format")


class ProfileConfig(BaseModel):
    """A named profile with filters and settings."""

    name: str = Field(description="Profile name")
    description: str = Field(default="", description="Profile description")
    filters: dict = Field(default_factory=lambda: {
        "email": EmailFilters(),
        "calendar": CalendarFilters(),
        "drive": DriveFilters(),
    })
    settings: ProfileSettings = Field(default_factory=ProfileSettings)

    class Config:
        """Pydantic config."""
        extra = "allow"


class AuthConfig(BaseModel):
    """Authentication configuration."""

    credentials_path: Path = Field(
        default=Path(".gwark/credentials/oauth2_credentials.json"),
        description="Path to OAuth2 credentials file"
    )
    tokens_path: Path = Field(
        default=Path(".gwark/tokens"),
        description="Directory for storing OAuth2 tokens"
    )
    default_account: str = Field(default="primary", description="Default account ID")


class AIConfig(BaseModel):
    """AI summarization configuration."""

    provider: str = Field(default="anthropic", description="AI provider")
    model: str = Field(default="claude-3-haiku-20240307", description="Model to use")
    batch_size: int = Field(default=10, description="Emails per API call")
    max_body_chars: int = Field(default=2500, description="Max characters of email body to send")


class CalendarConfig(BaseModel):
    """Calendar-specific configuration."""

    calendars: list[str] = Field(
        default_factory=lambda: ["primary"],
        description="Calendar IDs to fetch (default: primary)"
    )
    default_days: int = Field(default=30, description="Default days to look back for calendar")


class DefaultsConfig(BaseModel):
    """Default settings."""

    days_back: int = Field(default=30, description="Default days to look back")
    max_results: int = Field(default=500, description="Default max results")
    output_format: str = Field(default="markdown", description="Default output format")
    output_directory: Path = Field(default=Path("./reports"), description="Default output directory")
    detail_level: str = Field(default="summary", description="Default detail level")


class GwarkConfig(BaseModel):
    """Main gwark configuration."""

    version: str = Field(default="1.0", description="Config version")
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    calendar: CalendarConfig = Field(default_factory=CalendarConfig)
    active_profile: str = Field(default="default", description="Active profile name")

    class Config:
        """Pydantic config."""
        extra = "allow"
