"""Token-bucket rate limiter respecting Telegram's published quotas."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    """A single token-bucket cell."""

    rate: float
    capacity: float
    tokens: float
    last: float


class TokenBucket:
    """Async-safe token bucket with monotonic clock."""

    def __init__(self, *, rate_per_second: float, capacity: float | None = None) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        cap = float(capacity if capacity is not None else max(1.0, rate_per_second))
        self._cell = _Bucket(rate=rate_per_second, capacity=cap, tokens=cap, last=time.monotonic())

    def time_until_available(self, n: float = 1.0) -> float:
        """Return the seconds the caller must wait before `n` tokens can be drawn."""
        now = time.monotonic()
        elapsed = now - self._cell.last
        self._cell.tokens = min(self._cell.capacity, self._cell.tokens + elapsed * self._cell.rate)
        self._cell.last = now
        if self._cell.tokens >= n:
            return 0.0
        return (n - self._cell.tokens) / self._cell.rate

    def consume(self, n: float = 1.0) -> None:
        """Subtract `n` tokens. Caller is expected to have waited if necessary."""
        self._cell.tokens = max(0.0, self._cell.tokens - n)


class RateLimiter:
    """Composite limiter combining a global bucket with per-chat buckets."""

    def __init__(
        self,
        *,
        global_per_second: float,
        per_chat_per_second: float,
    ) -> None:
        self._global = TokenBucket(rate_per_second=global_per_second)
        self._per_chat_rate = per_chat_per_second
        self._chat_buckets: dict[int, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _chat_bucket(self, chat_id: int) -> TokenBucket:
        bucket = self._chat_buckets.get(chat_id)
        if bucket is None:
            bucket = TokenBucket(
                rate_per_second=self._per_chat_rate,
                capacity=max(1.0, self._per_chat_rate),
            )
            self._chat_buckets[chat_id] = bucket
        return bucket

    async def acquire(self, chat_id: int) -> None:
        """Block until a token is available for both the global and per-chat buckets."""
        async with self._lock:
            while True:
                wait_global = self._global.time_until_available(1.0)
                wait_chat = self._chat_bucket(chat_id).time_until_available(1.0)
                wait = max(wait_global, wait_chat)
                if wait <= 0:
                    self._global.consume(1.0)
                    self._chat_bucket(chat_id).consume(1.0)
                    return
                await asyncio.sleep(wait)
