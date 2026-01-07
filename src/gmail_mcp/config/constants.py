"""Constants for Gmail MCP server."""

from typing import Final

# Gmail API Scopes
GMAIL_SCOPES: Final[list[str]] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

# Pagination
DEFAULT_PAGE_SIZE: Final[int] = 100
MIN_PAGE_SIZE: Final[int] = 10
MAX_PAGE_SIZE: Final[int] = 500
MAX_RESULTS_PER_SEARCH: Final[int] = 500

# Batch Operations
DEFAULT_BATCH_SIZE: Final[int] = 20
MAX_BATCH_SIZE: Final[int] = 50
MIN_BATCH_SIZE: Final[int] = 1

# Cache Configuration
CACHE_TTL_SECONDS: Final[int] = 3600  # 1 hour
CACHE_CLEANUP_INTERVAL: Final[int] = 1800  # 30 minutes
MAX_CACHE_SIZE_MB: Final[int] = 500

# Rate Limiting (Gmail API quotas)
# Google Workspace limits (verified):
#   - Project: 1,200,000 queries/min (20,000/sec)
#   - Per-user: 15,000 queries/min (250/sec)
# Quota unit costs:
#   - messages.list: 5 units
#   - messages.get: 5 units
#   - messages.modify: 5 units
#   - batchModify: 50 units
# Effective read throughput: 250/5 = 50 messages/sec per user
DEFAULT_RATE_LIMIT_PER_SECOND: Final[int] = 250
DEFAULT_RATE_LIMIT_BURST: Final[int] = 100

# Concurrency
DEFAULT_MAX_CONCURRENT: Final[int] = 50  # Parallel operations

# API Timeouts
DEFAULT_TIMEOUT_SECONDS: Final[int] = 30
MAX_TIMEOUT_SECONDS: Final[int] = 120

# Retry Configuration
DEFAULT_RETRY_ATTEMPTS: Final[int] = 3
DEFAULT_RETRY_BACKOFF_FACTOR: Final[float] = 2.0
MAX_RETRY_ATTEMPTS: Final[int] = 5

# Connection Pool
DEFAULT_CONNECTION_POOL_SIZE: Final[int] = 10
MAX_CONNECTION_POOL_SIZE: Final[int] = 50

# Multi-Account
DEFAULT_ACCOUNT_ID: Final[str] = "primary"
MAX_ACCOUNTS: Final[int] = 5

# Email Formats
EMAIL_FORMAT_FULL: Final[str] = "full"
EMAIL_FORMAT_METADATA: Final[str] = "metadata"
EMAIL_FORMAT_MINIMAL: Final[str] = "minimal"
EMAIL_FORMAT_RAW: Final[str] = "raw"

# Gmail Query Operators
QUERY_OPERATORS: Final[dict[str, str]] = {
    "from": "from:",
    "to": "to:",
    "subject": "subject:",
    "after": "after:",
    "before": "before:",
    "has": "has:",
    "is": "is:",
    "label": "label:",
    "filename": "filename:",
    "newer_than": "newer_than:",
    "older_than": "older_than:",
}

# Common Labels
LABEL_INBOX: Final[str] = "INBOX"
LABEL_SENT: Final[str] = "SENT"
LABEL_DRAFT: Final[str] = "DRAFT"
LABEL_SPAM: Final[str] = "SPAM"
LABEL_TRASH: Final[str] = "TRASH"
LABEL_UNREAD: Final[str] = "UNREAD"
LABEL_STARRED: Final[str] = "STARRED"
LABEL_IMPORTANT: Final[str] = "IMPORTANT"

# Token Encryption
TOKEN_ENCRYPTION_ALGORITHM: Final[str] = "Fernet"
TOKEN_FILE_EXTENSION: Final[str] = ".token"

# Logging
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
