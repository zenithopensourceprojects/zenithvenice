"""IST-aware cron scheduler for the morning + evening digest jobs.

Pure asyncio — no external scheduler dependency. Computes the next
occurrence of each configured time-of-day, sleeps until then, and fires.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta

from herald.config import get_settings
from herald.logging_setup import get_logger
from herald.utils.time_ago import IST

log = get_logger(__name__)


JobFn = Callable[[], Awaitable[None]]


class DailyCron:
    """Run a coroutine once per day at a fixed IST clock-time."""

    def __init__(self, *, name: str, at_ist: time, job: JobFn) -> None:
        self.name = name
        self._at = at_ist
        self._job = job
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Run forever, firing `job` at the configured IST time each day."""
        log.info("cron_started", job=self.name, at_ist=self._at.strftime("%H:%M"))
        while not self._stop.is_set():
            wait = self._seconds_until_next_fire()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait)
            except TimeoutError:
                pass
            else:
                break
            if self._stop.is_set():
                break
            try:
                await self._job()
            except Exception as exc:
                log.exception("cron_job_failed", job=self.name, error=str(exc))
        log.info("cron_stopped", job=self.name)

    def _seconds_until_next_fire(self) -> float:
        """Return how many seconds until the next IST occurrence of `self._at`."""
        now = datetime.now(IST)
        target_today = now.replace(
            hour=self._at.hour,
            minute=self._at.minute,
            second=0,
            microsecond=0,
        )
        if target_today <= now:
            target_today = target_today + timedelta(days=1)
        return max(1.0, (target_today - now).total_seconds())

    def stop(self) -> None:
        """Signal the cron loop to exit at the next sleep boundary."""
        self._stop.set()


def build_digest_crons(
    *,
    morning_job: JobFn,
    evening_job: JobFn,
) -> list[DailyCron]:
    """Construct the morning + evening digest crons from settings."""
    settings = get_settings()
    return [
        DailyCron(
            name="digest_morning",
            at_ist=settings.telegram_digest_morning_ist,
            job=morning_job,
        ),
        DailyCron(
            name="digest_evening",
            at_ist=settings.telegram_digest_evening_ist,
            job=evening_job,
        ),
    ]
