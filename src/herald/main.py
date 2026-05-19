"""Herald entrypoint: launch the bot, the poller, and the realtime listener."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys

from herald.bot.dispatcher import build_bot, build_dispatcher, install_command_menu
from herald.config import get_settings
from herald.logging_setup import configure_logging, get_logger
from herald.publisher.chat_fanout import ChatFanout
from herald.publisher.digest import DigestPublisher
from herald.publisher.dispatch import ChannelDispatcher
from herald.publisher.poller import ChannelPoller
from herald.publisher.realtime import RealtimeListener
from herald.publisher.scheduler import RateLimiter
from herald.publisher.scheduling import build_digest_crons
from herald.publisher.user_fanout import UserFanout

log = get_logger(__name__)


async def _run() -> int:
    """Wire all subsystems and run them concurrently until shutdown."""
    settings = get_settings()
    configure_logging(level=settings.telegram_log_level, pretty=sys.stdout.isatty())

    bot = build_bot()
    dp = build_dispatcher()

    limiter = RateLimiter(
        global_per_second=settings.telegram_rate_global_per_second,
        per_chat_per_second=settings.telegram_rate_per_chat_per_second,
    )
    user_fanout = UserFanout(bot=bot, limiter=limiter)
    chat_fanout = ChatFanout(bot=bot, limiter=limiter)
    dispatcher = ChannelDispatcher(
        bot=bot,
        limiter=limiter,
        user_fanout=user_fanout,
        chat_fanout=chat_fanout,
    )
    poller = ChannelPoller(dispatcher=dispatcher)
    realtime = RealtimeListener(dispatcher=dispatcher)
    digester = DigestPublisher(bot=bot, limiter=limiter)
    crons = build_digest_crons(
        morning_job=lambda: digester.run("morning"),
        evening_job=lambda: digester.run("evening"),
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(getattr(signal, sig_name), stop_event.set)

    await install_command_menu(bot)
    log.info(
        "herald_starting",
        channel_id=settings.telegram_channel_id,
        webhook=settings.telegram_use_webhook,
    )

    bot_task = asyncio.create_task(_run_bot(bot, dp), name="bot")
    poller_task = asyncio.create_task(poller.run(), name="poller")
    realtime_task = asyncio.create_task(realtime.run(), name="realtime")
    cron_tasks = [asyncio.create_task(c.run(), name=c.name) for c in crons]
    stop_task = asyncio.create_task(stop_event.wait(), name="stop")

    done, pending = await asyncio.wait(
        {bot_task, poller_task, realtime_task, stop_task, *cron_tasks},
        return_when=asyncio.FIRST_COMPLETED,
    )

    log.info("herald_stopping")
    poller.stop()
    realtime.stop()
    for cron in crons:
        cron.stop()
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    with contextlib.suppress(Exception):
        await bot.session.close()

    for finished in done:
        exc = finished.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            log.exception("subsystem_failed", task=finished.get_name(), error=str(exc))
            return 1

    return 0


async def _run_bot(bot, dp) -> None:  # type: ignore[no-untyped-def]
    """Long-poll the Telegram API until cancelled."""
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def _install_uvloop_if_available() -> None:
    """Install uvloop as the active event-loop policy when running on POSIX."""
    if sys.platform == "win32":
        return
    try:
        import uvloop
    except ImportError:
        return
    uvloop.install()


def cli() -> None:
    """Synchronous entry-point used by `python -m herald` and the `herald` script."""
    _install_uvloop_if_available()
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    cli()
