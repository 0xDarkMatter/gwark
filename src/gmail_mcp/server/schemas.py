"""Pydantic schemas for MCP tool requests and responses."""

from typing import Any, Optional

from pydantic import BaseModel, Field


# Search Emails
class SearchEmailsRequest(BaseModel):
    """Request schema for searching emails."""

    query: str = Field(..., description="Gmail search query")
    max_results: Optional[int] = Field(None, description="Maximum total results")
    page_size: Optional[int] = Field(None, description="Results per page")
    page_token: Optional[str] = Field(None, description="Page token for pagination")
    account_id: str = Field("primary", description="Account identifier")


class SearchEmailsResponse(BaseModel):
    """Response schema for email search."""

    messages: list[dict[str, Any]] = Field(..., description="List of messages")
    nextPageToken: Optional[str] = Field(None, description="Next page token")
    resultSizeEstimate: int = Field(..., description="Estimated total results")
    pageSize: int = Field(..., description="Page size used")
    query: str = Field(..., description="Query used")


# Read Email
class ReadEmailRequest(BaseModel):
    """Request schema for reading an email."""

    message_id: str = Field(..., description="Gmail message ID")
    format: str = Field("full", description="Response format (full, metadata, minimal)")
    account_id: str = Field("primary", description="Account identifier")


# Apply Labels
class ApplyLabelsRequest(BaseModel):
    """Request schema for applying labels."""

    message_id: str = Field(..., description="Gmail message ID")
    label_ids: list[str] = Field(..., description="Label IDs to add")
    remove_labels: Optional[list[str]] = Field(None, description="Label IDs to remove")
    account_id: str = Field("primary", description="Account identifier")


# Remove Labels
class RemoveLabelsRequest(BaseModel):
    """Request schema for removing labels."""

    message_id: str = Field(..., description="Gmail message ID")
    label_ids: list[str] = Field(..., description="Label IDs to remove")
    account_id: str = Field("primary", description="Account identifier")


# List Labels
class ListLabelsRequest(BaseModel):
    """Request schema for listing labels."""

    account_id: str = Field("primary", description="Account identifier")


# Batch Read
class BatchReadRequest(BaseModel):
    """Request schema for batch reading emails."""

    message_ids: list[str] = Field(..., description="List of message IDs")
    format: str = Field("metadata", description="Response format")
    account_id: str = Field("primary", description="Account identifier")


# Batch Apply Labels
class BatchApplyLabelsRequest(BaseModel):
    """Request schema for batch applying labels."""

    message_ids: list[str] = Field(..., description="List of message IDs")
    add_label_ids: Optional[list[str]] = Field(None, description="Labels to add")
    remove_label_ids: Optional[list[str]] = Field(None, description="Labels to remove")
    account_id: str = Field("primary", description="Account identifier")


# Mark as Read/Unread
class MarkAsReadRequest(BaseModel):
    """Request schema for marking email as read."""

    message_id: str = Field(..., description="Gmail message ID")
    account_id: str = Field("primary", description="Account identifier")


class MarkAsUnreadRequest(BaseModel):
    """Request schema for marking email as unread."""

    message_id: str = Field(..., description="Gmail message ID")
    account_id: str = Field("primary", description="Account identifier")


# Archive
class ArchiveRequest(BaseModel):
    """Request schema for archiving email."""

    message_id: str = Field(..., description="Gmail message ID")
    account_id: str = Field("primary", description="Account identifier")


# Star/Unstar
class StarRequest(BaseModel):
    """Request schema for starring email."""

    message_id: str = Field(..., description="Gmail message ID")
    account_id: str = Field("primary", description="Account identifier")


class UnstarRequest(BaseModel):
    """Request schema for unstarring email."""

    message_id: str = Field(..., description="Gmail message ID")
    account_id: str = Field("primary", description="Account identifier")


# Get Profile
class GetProfileRequest(BaseModel):
    """Request schema for getting user profile."""

    account_id: str = Field("primary", description="Account identifier")


# Error Response
class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error details")


# Success Response
class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = Field(True, description="Operation success status")
    message: Optional[str] = Field(None, description="Success message")
    data: Optional[dict[str, Any]] = Field(None, description="Response data")
