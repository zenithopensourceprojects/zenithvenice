"""Morning + evening digest broadcast pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder

from herald.config import get_settings
from herald.data import posts, users
from herald.logging_setup import get_logger
from herald.render.digest import DigestSlot, render_digest
from herald.utils.quiet_hours import is_within_window
from herald.utils.time_ago import IST

if TYPE_CHECKING:
    from aiogram import Bot

    from herald.data.models import TelegramUser
    from herald.publisher.scheduler import RateLimiter

log = get_logger(__name__)


_SLOT_HOURS: dict[DigestSlot, int] = {"morning": 12, "evening": 12}


def _build_keyboard() -> InlineKeyboardBuilder:
    """Build the inline keyboard attached to every digest message."""
    from aiogram.types import InlineKeyboardButton

    settings = get_settings()
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📰  Latest stories", callback_data="cmd:latest"),
        InlineKeyboardButton(text="📂  Categories",     callback_data="cat:menu"),
    )
    if settings.telegram_channel_invite_url:
        builder.row(
            InlineKeyboardButton(
                text="📣  Open the channel",
                url=settings.telegram_channel_invite_url,
            )
        )
    return builder


class DigestPublisher:
    """Build and broadcast a digest to every user opted-in for digests."""

    def __init__(self, *, bot: Bot, limiter: RateLimiter) -> None:
        self._bot = bot
        self._limiter = limiter
        self._settings = get_settings()

    async def run(self, slot: DigestSlot) -> None:
        """Broadcast the slot's digest to every digest-mode user."""
        items = posts.fetch_top_recent(
            hours=_SLOT_HOURS[slot],
            limit=self._settings.telegram_digest_top_n,
        )
        if not items:
            log.info("digest_skipped_no_posts", slot=slot)
            return

        when_ist = datetime.now(IST)
        text = render_digest(items, slot=slot, when_ist=when_ist)
        keyboard = _build_keyboard().as_markup()

        targets = users.list_active_users(mode="digest")
        log.info("digest_broadcast_start", slot=slot, recipients=len(targets), top=len(items))

        sent = 0
        skipped = 0
        # The digest is a single rendered string covering the last 12h. Users
        # who joined inside that window haven't seen those posts before, so it
        # would be backlog spam. Skip any user whose `created_at` is newer
        # than the oldest post in the digest.
        oldest_in_digest = min((p.published_at for p in items), default=None)

        for target in targets:
            if self._is_quiet_now(target, when_ist):
                skipped += 1
                continue
            if (
                oldest_in_digest is not None
                and target.created_at is not None
                and target.created_at > oldest_in_digest
            ):
                skipped += 1
                continue
            ok = await self._send(target, text, keyboard)
            if ok:
                sent += 1

        log.info(
            "digest_broadcast_done",
            slot=slot,
            sent=sent,
            skipped_quiet=skipped,
            failures=len(targets) - sent - skipped,
        )

    @staticmethod
    def _is_quiet_now(user: TelegramUser, when_ist: datetime) -> bool:
        """Return True if `when_ist` falls inside the user's quiet-hours window."""
        return is_within_window(
            now=when_ist,
            start=user.quiet_start,
            end=user.quiet_end,
        )

    async def _send(
        self,
        target: TelegramUser,
        text: str,
        keyboard,
    ) -> bool:
        """Send a single digest message, applying rate limits and error handling."""
        attempts = 0
        while True:
            attempts += 1
            try:
                await self._limiter.acquire(target.tg_chat_id)
                await self._bot.send_message(
                    chat_id=target.tg_chat_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                    disable_notification=False,
                )
                return True
            except TelegramRetryAfter as exc:
                if attempts >= 3:
                    log.warning("digest_giveup_rate_limit", tg_user_id=target.tg_user_id)
                    return False
                wait = float(exc.retry_after) + 0.5
                log.warning("digest_rate_limited", retry_after=wait)
                import asyncio
                await asyncio.sleep(wait)
            except TelegramForbiddenError:
                users.mark_blocked(target.tg_user_id)
                log.info("digest_user_blocked_us", tg_user_id=target.tg_user_id)
                return False
            except Exception as exc:
                log.warning(
                    "digest_send_failed",
                    tg_user_id=target.tg_user_id,
                    error=str(exc),
                )
                return False
