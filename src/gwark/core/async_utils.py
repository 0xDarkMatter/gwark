"""Async utilities for parallel fetching with rate limiting.

Provides bounded parallel execution for Google API calls with
rate limiting to respect API quotas.
"""

import asyncio
from typing import TypeVar, Callable, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import time


T = TypeVar('T')
R = TypeVar('R')


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
    """Bounded parallel fetching with rate limiting.

    Executes synchronous functions in parallel using asyncio.to_thread(),
    with semaphore-based concurrency control and rate limiting.

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
    ):
        """Initialize fetcher.

        Args:
            max_concurrent: Maximum concurrent operations (default: 10)
            rate_per_second: Maximum requests per second (default: 50)
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = SyncRateLimiter(rate_per_second)

    async def fetch_one(
        self,
        item: T,
        fetch_func: Callable[[T], R],
    ) -> R:
        """Fetch a single item with rate limiting.

        Args:
            item: Item to process
            fetch_func: Synchronous function to call

        Returns:
            Result from fetch_func
        """
        async with self.semaphore:
            await self.rate_limiter.acquire()
            return await asyncio.to_thread(fetch_func, item)

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
