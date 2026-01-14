# Google API Threading Guide

Thread-safety patterns for Google API clients in Python.

## The Problem

Google API service objects are **NOT thread-safe**. Sharing a single service across threads causes:

- Race conditions (wrong data returned)
- Segmentation faults (process crashes)
- Silent failures (~70% failure rate observed)

```python
# BAD - shared service across threads
service = get_gmail_service()

def fetch_email(msg_id):
    return service.users().messages().get(id=msg_id).execute()  # Race condition!

with ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(fetch_email, message_ids)  # Will fail ~70% of requests
```

## Why It Happens

The service object manages mutable internal state:

| Component | State | Thread Conflict |
|-----------|-------|-----------------|
| HTTP connection pool | Active connections | Connections reused mid-request |
| Request builder | URL, params, headers | Overwritten by other threads |
| Auth handler | Token refresh state | Race during token refresh |

When Thread A starts building a request and Thread B overwrites the state before Thread A calls `.execute()`, you get corrupted requests or segfaults.

## The Solution: Thread-Local Storage

Give each thread its own service instance using `threading.local()`:

```python
import threading
from gmail_mcp.auth import get_gmail_service

# Thread-local storage
thread_local = threading.local()

def get_thread_service():
    """Get thread-local Gmail service instance."""
    if not hasattr(thread_local, "service"):
        thread_local.service = get_gmail_service()
    return thread_local.service

def fetch_email(msg_id):
    service = get_thread_service()  # Each thread gets its own service
    return service.users().messages().get(userId="me", id=msg_id).execute()

# Now safe to use with ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(fetch_email, message_ids)  # 100% success rate
```

## How Thread-Local Works

```
┌─────────────────────────────────────────────────────────────┐
│                    threading.local()                         │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Thread 1    │  Thread 2    │  Thread 3    │  Thread N      │
│  ┌────────┐  │  ┌────────┐  │  ┌────────┐  │  ┌────────┐   │
│  │Service │  │  │Service │  │  │Service │  │  │Service │   │
│  │instance│  │  │instance│  │  │instance│  │  │instance│   │
│  └────────┘  │  └────────┘  │  └────────┘  │  └────────┘   │
│  (isolated)  │  (isolated)  │  (isolated)  │  (isolated)   │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

Each thread accesses `thread_local.service` but gets its own isolated instance.

## Performance Comparison

Tested fetching 100 emails with 10 workers:

| Approach | Success Rate | Speed |
|----------|--------------|-------|
| Shared service | ~30% | N/A (crashes) |
| Thread-local service | 100% | 15 emails/sec |

## Complete Example

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

from gmail_mcp.auth import get_gmail_service
from gwark.core.email_utils import extract_email_details

def fetch_emails_parallel(message_ids: list, max_workers: int = 10) -> list:
    """Fetch multiple emails in parallel safely."""

    # Thread-local storage for service instances
    thread_local = threading.local()

    def get_thread_service():
        if not hasattr(thread_local, "service"):
            thread_local.service = get_gmail_service()
        return thread_local.service

    def fetch_one(msg_id: str) -> dict | None:
        """Fetch single email with retry."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                service = get_thread_service()
                email_data = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
                return extract_email_details(email_data)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Backoff
                else:
                    print(f"Failed {msg_id}: {e}")
                    return None
        return None

    # Parallel fetch
    emails = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, mid): mid for mid in message_ids}
        for future in as_completed(futures):
            result = future.result()
            if result:
                emails.append(result)

    return emails
```

## Alternative: Sequential Fetch

If thread-safety complexity isn't worth it for small batches:

```python
def fetch_emails_sequential(message_ids: list) -> list:
    """Fetch emails one at a time (simpler, slower)."""
    service = get_gmail_service()
    emails = []

    for msg_id in message_ids:
        try:
            email_data = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full",
            ).execute()
            emails.append(extract_email_details(email_data))
        except Exception as e:
            print(f"Failed {msg_id}: {e}")

    return emails
```

| Approach | Emails/sec | Best For |
|----------|------------|----------|
| Sequential | ~3-5 | < 50 emails |
| Parallel (20 workers) | ~35 | 50-5000 emails |

## Optimal Worker Count

Benchmarked with 200 emails:

| Workers | Speed | Notes |
|---------|-------|-------|
| 10 | 23/sec | Conservative |
| 20 | 35/sec | **Optimal** |
| 30 | 36/sec | Marginal gain |
| 50 | 30/sec | Rate limited |

**Recommendation: 20 workers** - best balance of speed and stability. Beyond 30, Gmail API rate limits cause slowdown.

## Key Takeaways

1. **Never share** Google API service objects across threads
2. **Use `threading.local()`** to give each thread its own instance
3. **Add retry logic** - transient failures happen even with proper threading
4. **Limit workers** - 10-20 is usually optimal (rate limits + memory)

## References

- [Google API Python Client Threading](https://googleapis.github.io/google-api-python-client/docs/thread_safety.html)
- [Python threading.local() docs](https://docs.python.org/3/library/threading.html#thread-local-data)
