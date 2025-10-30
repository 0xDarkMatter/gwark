"""Rate limiting for Gmail API requests."""

import asyncio
import logging
import time
from collections import deque
from typing import Optional

from gmail_mcp.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for Gmail API requests.

    Gmail API quotas:
    - 250 quota units per user per second
    - Most read operations: 5 units
    - Write operations: 10-25 units

    This rate limiter uses a simplified approach counting requests rather than quota units.
    For production, consider tracking actual quota units per operation.
    """

    def __init__(
        self,
        rate_per_second: Optional[float] = None,
        burst_size: Optional[int] = None,
    ):
        """Initialize rate limiter.

        Args:
            rate_per_second: Maximum requests per second
            burst_size: Maximum burst size (number of tokens)
        """
        settings = get_settings()
        self.rate_per_second = rate_per_second or settings.rate_limit_per_second
        self.burst_size = burst_size or settings.rate_limit_burst

        self.tokens = float(self.burst_size)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

        # Track request timestamps for debugging
        self.request_times: deque[float] = deque(maxlen=100)

        logger.info(
            f"Rate limiter initialized: {self.rate_per_second} req/s, burst={self.burst_size}"
        )

    def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed."""
        now = time.monotonic()
        elapsed = now - self.last_update

        # Add tokens based on time elapsed
        tokens_to_add = elapsed * self.rate_per_second
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_update = now

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens for making a request.

        Args:
            tokens: Number of tokens to acquire (default 1 request)
        """
        if tokens > self.burst_size:
            raise ValueError(
                f"Requested tokens ({tokens}) exceeds burst size ({self.burst_size})"
            )

        async with self.lock:
            while True:
                self._refill_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self.request_times.append(time.monotonic())
                    return

                # Calculate wait time for needed tokens
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate_per_second

                logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {tokens} tokens")
                await asyncio.sleep(wait_time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        self._refill_tokens()

        if self.tokens >= tokens:
            self.tokens -= tokens
            self.request_times.append(time.monotonic())
            return True

        return False

    def get_current_rate(self) -> float:
        """Get current request rate based on recent requests.

        Returns:
            Current requests per second
        """
        if len(self.request_times) < 2:
            return 0.0

        now = time.monotonic()
        # Count requests in last second
        recent_requests = sum(1 for t in self.request_times if now - t <= 1.0)
        return float(recent_requests)

    def reset(self) -> None:
        """Reset rate limiter state."""
        self.tokens = float(self.burst_size)
        self.last_update = time.monotonic()
        self.request_times.clear()
        logger.debug("Rate limiter reset")

    def get_stats(self) -> dict:
        """Get rate limiter statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "rate_per_second": self.rate_per_second,
            "burst_size": self.burst_size,
            "current_tokens": self.tokens,
            "current_rate": self.get_current_rate(),
            "total_requests": len(self.request_times),
        }


class SyncRateLimiter:
    """Synchronous version of rate limiter for non-async code."""

    def __init__(
        self,
        rate_per_second: Optional[float] = None,
        burst_size: Optional[int] = None,
    ):
        """Initialize synchronous rate limiter.

        Args:
            rate_per_second: Maximum requests per second
            burst_size: Maximum burst size
        """
        settings = get_settings()
        self.rate_per_second = rate_per_second or settings.rate_limit_per_second
        self.burst_size = burst_size or settings.rate_limit_burst

        self.tokens = float(self.burst_size)
        self.last_update = time.monotonic()

    def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed."""
        now = time.monotonic()
        elapsed = now - self.last_update

        tokens_to_add = elapsed * self.rate_per_second
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_update = now

    def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens for making a request.

        Args:
            tokens: Number of tokens to acquire
        """
        while True:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return

            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate_per_second
            time.sleep(wait_time)
