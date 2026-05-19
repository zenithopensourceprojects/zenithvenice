"""Safety-net poller: periodically scans for posts not yet broadcast."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from herald.config import get_settings
from herald.data import posts
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from herald.publisher.dispatch import ChannelDispatcher

log = get_logger(__name__)


class ChannelPoller:
    """Drains `posts_pending_channel_delivery` on a fixed interval."""

    def __init__(self, *, dispatcher: ChannelDispatcher) -> None:
        self._dispatcher = dispatcher
        self._settings = get_settings()
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Run the poller loop until `stop()` is called."""
        interval = max(5, int(self._settings.telegram_poller_interval_seconds))
        log.info("poller_started", interval_seconds=interval)
        await self._tick()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except TimeoutError:
                await self._tick()
            else:
                break
        log.info("poller_stopped")

    async def _tick(self) -> None:
        try:
            pending = posts.fetch_pending_channel_deliveries(limit=50)
        except Exception as exc:
            log.warning("poller_fetch_failed", error=str(exc))
            return

        if not pending:
            return

        log.info("poller_pending", count=len(pending))
        for post in pending:
            if self._stop.is_set():
                break
            await self._dispatcher.publish(post)

    def stop(self) -> None:
        """Signal the poller to exit at the next iteration boundary."""
        self._stop.set()
