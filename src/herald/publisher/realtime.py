"""Supabase realtime listener: instant push when a verified post lands.

Realtime is best-effort. The poller is the safety net; if the realtime
channel disconnects or the supabase-py realtime API is unavailable, the
poller will still pick up unsent posts within `TELEGRAM_POLLER_INTERVAL_SECONDS`.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from herald.config import get_settings
from herald.data import posts
from herald.data.models import Post
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from herald.publisher.dispatch import ChannelDispatcher

log = get_logger(__name__)


def _extract_row(payload: Any) -> dict[str, Any] | None:
    """Pull the new-row dict out of a realtime payload across supabase-py versions.

    supabase-py 2.x passes a `PostgresChangesPayload`-like object that exposes
    `.data["record"]` (or `.data["new"]`); older clients passed a raw dict with
    `record`/`new` keys at the top level. We accept both.
    """
    if payload is None:
        return None
    if isinstance(payload, dict):
        candidate = payload.get("record") or payload.get("new") or payload.get("data")
        if isinstance(candidate, dict):
            inner = candidate.get("record") or candidate.get("new")
            if isinstance(inner, dict):
                return inner
            return candidate
        return None
    data = getattr(payload, "data", None)
    if isinstance(data, dict):
        candidate = data.get("record") or data.get("new")
        if isinstance(candidate, dict):
            return candidate
    record = getattr(payload, "record", None) or getattr(payload, "new", None)
    if isinstance(record, dict):
        return record
    return None


class RealtimeListener:
    """Subscribes to INSERTs on the `posts` table and dispatches them immediately."""

    def __init__(self, *, dispatcher: ChannelDispatcher) -> None:
        self._dispatcher = dispatcher
        self._settings = get_settings()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None

    async def run(self) -> None:
        """Run the realtime loop, reconnecting on failure with capped backoff."""
        backoff_ms = self._settings.telegram_realtime_reconnect_backoff_ms
        max_backoff = 60_000
        loop = asyncio.get_running_loop()

        while not self._stop.is_set():
            try:
                log.info("realtime_connecting")
                await self._connect_and_listen(loop)
                backoff_ms = self._settings.telegram_realtime_reconnect_backoff_ms
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("realtime_disconnected", error=str(exc), backoff_ms=backoff_ms)

            if self._stop.is_set():
                break
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=backoff_ms / 1000)
            backoff_ms = min(max_backoff, backoff_ms * 2)

        log.info("realtime_stopped")

    async def _connect_and_listen(self, loop: asyncio.AbstractEventLoop) -> None:
        """Open one realtime channel and process events until it closes."""
        try:
            from realtime import AsyncRealtimeClient
        except ImportError:
            log.warning("realtime_unavailable_module_missing")
            await self._stop.wait()
            return

        url = str(self._settings.supabase_url).replace("http", "ws", 1) + "/realtime/v1"
        token = self._settings.supabase_service_role_key.get_secret_value()
        client = AsyncRealtimeClient(url, token, auto_reconnect=False)

        await client.connect()
        try:
            channel = client.channel("herald-posts")

            def on_insert(payload: Any) -> None:
                try:
                    row = _extract_row(payload)
                except Exception as exc:
                    log.warning("realtime_payload_parse_failed", error=str(exc))
                    return
                if not row or row.get("status") != "published":
                    return
                loop.create_task(self._handle_row(row))

            channel.on_postgres_changes(
                event="INSERT",
                schema="public",
                table="posts",
                callback=on_insert,
            )
            await channel.subscribe()
            log.info("realtime_subscribed", topic="public:posts")

            await self._stop.wait()
        finally:
            with contextlib.suppress(Exception):
                await client.close()

    async def _handle_row(self, row: dict[str, Any]) -> None:
        """Validate a realtime row and hand it to the dispatcher."""
        try:
            post = Post.model_validate(row)
        except Exception as exc:
            log.warning("realtime_row_invalid", error=str(exc), post_id=row.get("id"))
            return

        if not post.id:
            return

        fresh = posts.fetch_post_by_id(post.id) or post
        await self._dispatcher.publish(fresh)

    def stop(self) -> None:
        """Signal the listener to exit at the next reconnect boundary."""
        self._stop.set()
