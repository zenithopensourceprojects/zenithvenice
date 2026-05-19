"""Token-bucket and rate-limiter behavioural tests."""

from __future__ import annotations

import asyncio
import time

import pytest

from herald.publisher.scheduler import RateLimiter, TokenBucket


def test_token_bucket_starts_full_and_drains() -> None:
    bucket = TokenBucket(rate_per_second=5.0, capacity=5.0)
    assert bucket.time_until_available(1.0) == 0.0
    bucket.consume(5.0)
    wait = bucket.time_until_available(1.0)
    assert wait > 0
    assert wait <= 1.0 / 5.0 + 0.05


def test_token_bucket_refills_over_time() -> None:
    bucket = TokenBucket(rate_per_second=10.0, capacity=1.0)
    bucket.consume(1.0)
    time.sleep(0.15)
    assert bucket.time_until_available(1.0) == 0.0


@pytest.mark.asyncio
async def test_rate_limiter_serialises_per_chat() -> None:
    limiter = RateLimiter(global_per_second=100.0, per_chat_per_second=2.0)
    chat_id = 42

    start = time.monotonic()
    await limiter.acquire(chat_id)
    await limiter.acquire(chat_id)
    await limiter.acquire(chat_id)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.4


@pytest.mark.asyncio
async def test_rate_limiter_allows_parallel_distinct_chats() -> None:
    limiter = RateLimiter(global_per_second=100.0, per_chat_per_second=1.0)

    async def hit(chat_id: int) -> None:
        await limiter.acquire(chat_id)

    start = time.monotonic()
    await asyncio.gather(hit(1), hit(2), hit(3), hit(4))
    elapsed = time.monotonic() - start
    assert elapsed < 0.5
