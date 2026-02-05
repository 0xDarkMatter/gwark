"""Core utilities for gwark."""

from .config import load_config, get_profile, get_active_profile
from .output import OutputFormatter
from .dates import parse_date_range, format_date
from .email_utils import extract_name, extract_email_details
from .markdown_converter import MarkdownToDocsConverter, DocsToMarkdownConverter
from .docs_analyzer import (
    DocsStructureAnalyzer,
    DocumentStructure,
    Section,
    format_structure_table,
    format_structure_tree,
)
from .docs_comments import DocsCommentManager
from .async_utils import (
    AsyncFetcher,
    SyncRateLimiter,
    run_async,
    parallel_map,
    retry_with_backoff,
    async_retry_with_backoff,
)
from .slides_client import (
    SlidesClient,
    SlideInfo,
    SlideElement,
    PresentationStructure,
)

__all__ = [
    "load_config",
    "get_profile",
    "get_active_profile",
    "OutputFormatter",
    "parse_date_range",
    "format_date",
    "extract_name",
    "extract_email_details",
    "MarkdownToDocsConverter",
    "DocsToMarkdownConverter",
    "DocsStructureAnalyzer",
    "DocumentStructure",
    "Section",
    "format_structure_table",
    "format_structure_tree",
    "DocsCommentManager",
    "AsyncFetcher",
    "SyncRateLimiter",
    "run_async",
    "parallel_map",
    "retry_with_backoff",
    "async_retry_with_backoff",
    "SlidesClient",
    "SlideInfo",
    "SlideElement",
    "PresentationStructure",
]
