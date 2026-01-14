"""Gmail API client and operations."""

from .batch import BatchResult, HttpBatchFetcher
from .client import GmailClient
from .operations import GmailOperations

__all__ = [
    "BatchResult",
    "GmailClient",
    "GmailOperations",
    "HttpBatchFetcher",
]
