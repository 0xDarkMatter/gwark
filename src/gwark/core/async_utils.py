"""Async utilities for parallel fetching with rate limiting.

Provides bounded parallel execution for Google API calls with
rate limiting to respect API quotas, plus exponential backoff
retry logic for transient errors.
"""

import asyncio
import os
import random
from typing import TypeVar, Callable, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import time


T = TypeVar('T')
R = TypeVar('R')

# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay cap in seconds (default: 60.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        jitter: Add random jitter to prevent thundering herd (default: True)

    Example:
        @retry_with_backoff(max_retries=3)
        def api_call():
            return requests.get(url)
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        def wrapper(*args, **kwargs) -> R:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if retryable
                    status = _get_error_status(e)
                    if status not in RETRYABLE_STATUS_CODES:
                        raise  # Non-retryable error

                    if attempt < max_retries:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())  # 50-150% of delay
                        time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


async def async_retry_with_backoff(
    func: Callable[..., R],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    **kwargs,
) -> R:
    """Async function with exponential backoff retry.

    Args:
        func: Sync function to call (will be run in thread)
        *args: Arguments to pass to func
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Base for exponential calculation
        jitter: Add random jitter
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result from func

    Example:
        result = await async_retry_with_backoff(
            api_call, arg1, arg2,
            max_retries=3
        )
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as e:
            last_exception = e

            # Check if retryable
            status = _get_error_status(e)
            if status not in RETRYABLE_STATUS_CODES:
                raise  # Non-retryable error

            if attempt < max_retries:
                delay = min(base_delay * (exponential_base ** attempt), max_delay)
                if jitter:
                    delay = delay * (0.5 + random.random())
                await asyncio.sleep(delay)

    raise last_exception


def _get_error_status(error: Exception) -> int:
    """Extract HTTP status code from various error types."""
    # Google API errors
    if hasattr(error, 'resp') and hasattr(error.resp, 'status'):
        return error.resp.status

    # gspread errors
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        return error.response.status_code

    # requests errors
    if hasattr(error, 'status_code'):
        return error.status_code

    # Check error message for status code
    error_str = str(error)
    for code in RETRYABLE_STATUS_CODES:
        if str(code) in error_str:
            return code

    return 0  # Unknown, don't retry


def retry_execute(
    request,
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation: str = "API call",
):
    """Execute a Google API request with retry for transient errors.

    Wraps the common pattern: service.resource().method(...).execute()
    with exponential backoff retry for 429/5xx errors.

    Args:
        request: Google API request object (result of .method() call)
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        operation: Description for retry warning messages

    Returns:
        API response dict

    Example:
        result = retry_execute(
            service.files().list(q=query, pageSize=100),
            operation="List Drive files"
        )
    """
    from gwark.core.output import print_warning

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return request.execute()
        except Exception as e:
            last_exception = e
            status = _get_error_status(e)
            if status not in RETRYABLE_STATUS_CODES:
                raise

            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), 60.0)
                delay = delay * (0.5 + random.random())
                print_warning(
                    f"{operation} failed ({status}), retrying in {delay:.1f}s... "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)

    raise last_exception


def check_anthropic_key() -> bool:
    """Check if ANTHROPIC_API_KEY is set before AI operations.

    Returns True if key is available, False with user-friendly warning if missing.
    """
    from gwark.core.output import print_warning

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print_warning("ANTHROPIC_API_KEY not set. AI features will be skipped.")
        print_warning("Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        return False
    return True


class SyncRateLimiter:
    """Token bucket rate limiter for synchronous code."""

    def __init__(self, rate_per_second: float = 50):
        """Initialize rate limiter.

        Args:
            rate_per_second: Maximum requests per second
        """
        self.rate = rate_per_second
        self.tokens = rate_per_second
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
        self.last_update = now

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            self._refill()
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self._refill()
            self.tokens -= 1


class AsyncFetcher:
    """Bounded parallel fetching with rate limiting and retry.

    Executes synchronous functions in parallel using asyncio.to_thread(),
    with semaphore-based concurrency control, rate limiting, and
    exponential backoff retry for transient errors (429, 5xx).

    Example:
        fetcher = AsyncFetcher(max_concurrent=10, rate_per_second=50)

        async def main():
            results = await fetcher.fetch_all(
                items=[1, 2, 3, 4, 5],
                fetch_func=lambda x: expensive_api_call(x)
            )

        run_async(main())
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        rate_per_second: float = 50,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        """Initialize fetcher.

        Args:
            max_concurrent: Maximum concurrent operations (default: 10)
            rate_per_second: Maximum requests per second (default: 50)
            max_retries: Maximum retry attempts for transient errors (default: 3)
            base_delay: Initial retry delay in seconds (default: 1.0)
            max_delay: Maximum retry delay cap (default: 60.0)
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = SyncRateLimiter(rate_per_second)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def fetch_one(
        self,
        item: T,
        fetch_func: Callable[[T], R],
    ) -> R:
        """Fetch a single item with rate limiting and retry.

        Args:
            item: Item to process
            fetch_func: Synchronous function to call

        Returns:
            Result from fetch_func
        """
        async with self.semaphore:
            await self.rate_limiter.acquire()

            last_exception = None
            for attempt in range(self.max_retries + 1):
                try:
                    return await asyncio.to_thread(fetch_func, item)
                except Exception as e:
                    last_exception = e
                    status = _get_error_status(e)

                    if status not in RETRYABLE_STATUS_CODES:
                        raise  # Non-retryable

                    if attempt < self.max_retries:
                        delay = min(
                            self.base_delay * (2 ** attempt),
                            self.max_delay
                        )
                        # Add jitter
                        delay = delay * (0.5 + random.random())
                        await asyncio.sleep(delay)

            raise last_exception

    async def fetch_all(
        self,
        items: List[T],
        fetch_func: Callable[[T], R],
        return_exceptions: bool = True,
    ) -> List[R]:
        """Fetch all items in parallel with bounds.

        Args:
            items: List of items to process
            fetch_func: Synchronous function to call for each item
            return_exceptions: If True, exceptions are returned as results
                             If False, first exception is raised

        Returns:
            List of results (or exceptions if return_exceptions=True)
        """
        tasks = [
            self.fetch_one(item, fetch_func)
            for item in items
        ]
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)

    async def fetch_all_with_callback(
        self,
        items: List[T],
        fetch_func: Callable[[T], R],
        on_complete: Optional[Callable[[T, R], None]] = None,
        on_error: Optional[Callable[[T, Exception], None]] = None,
    ) -> List[R]:
        """Fetch all items with progress callbacks.

        Args:
            items: List of items to process
            fetch_func: Synchronous function to call for each item
            on_complete: Called after each successful fetch
            on_error: Called after each failed fetch

        Returns:
            List of results (None for failures)
        """
        results = []

        async def fetch_with_callback(item: T) -> Optional[R]:
            try:
                result = await self.fetch_one(item, fetch_func)
                if on_complete:
                    on_complete(item, result)
                return result
            except Exception as e:
                if on_error:
                    on_error(item, e)
                return None

        tasks = [fetch_with_callback(item) for item in items]
        return await asyncio.gather(*tasks)


def run_async(coro) -> Any:
    """Run async coroutine from synchronous code.

    Wrapper for asyncio.run() that handles event loop creation
    properly for CLI compatibility.

    Args:
        coro: Coroutine to execute

    Returns:
        Result from the coroutine

    Example:
        async def fetch_data():
            fetcher = AsyncFetcher()
            return await fetcher.fetch_all(items, api_call)

        result = run_async(fetch_data())
    """
    return asyncio.run(coro)


async def parallel_map(
    items: List[T],
    func: Callable[[T], R],
    max_concurrent: int = 10,
    rate_per_second: float = 50,
) -> List[R]:
    """Convenience function for parallel mapping.

    Args:
        items: Items to process
        func: Function to apply to each item
        max_concurrent: Maximum concurrent operations
        rate_per_second: Rate limit

    Returns:
        List of results

    Example:
        results = run_async(parallel_map(
            items=calendar_ids,
            func=fetch_calendar_events,
            max_concurrent=10
        ))
    """
    fetcher = AsyncFetcher(max_concurrent, rate_per_second)
    return await fetcher.fetch_all(items, func)
