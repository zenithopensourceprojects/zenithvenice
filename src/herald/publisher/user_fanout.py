"""Per-user instant DM fanout.

After a post lands in the channel we fan it out to every user whose
preferences elect them to receive it directly. This pipeline is the
private-DM counterpart of `ChannelDispatcher`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import LinkPreviewOptions

from herald.bot.keyboards import article_keyboard
from herald.config import get_settings
from herald.data import deliveries, users
from herald.logging_setup import get_logger
from herald.render.card import is_breaking, render_post_card
from herald.utils.quiet_hours import is_within_window
from herald.utils.time_ago import IST

if TYPE_CHECKING:
    from aiogram import Bot

    from herald.data.models import Post, TelegramUser
    from herald.publisher.scheduler import RateLimiter


log = get_logger(__name__)


def is_eligible(user: TelegramUser, post: Post, *, now_ist: datetime) -> bool:
    """Return True if this user should receive a DM for this post.

    Pure function — no I/O. Filters applied in priority order:
      1. Not blocked
      2. Notification mode opts in (instant or breaking_only-with-score)
      3. Category not in user's mute list
      4. Not currently inside the user's quiet-hours window
    """
    if user.is_blocked:
        return False

    if user.notif_mode == "silent" or user.notif_mode == "digest":
        return False

    if user.notif_mode == "breaking_only" and not is_breaking(post):
        return False

    if post.category in set(user.muted_categories):
        return False

    return not is_within_window(now=now_ist, start=user.quiet_start, end=user.quiet_end)


class UserFanout:
    """Send a single post to every eligible opted-in Telegram user."""

    def __init__(self, *, bot: Bot, limiter: RateLimiter) -> None:
        self._bot = bot
        self._limiter = limiter
        self._settings = get_settings()
        self._inflight: set[str] = set()

    async def fanout(self, post: Post) -> None:
        """Filter, send, and record deliveries for `post`. Safe to await or fire-and-forget."""
        if post.id in self._inflight:
            log.info("user_fanout_skip_inflight", post_id=post.id)
            return
        self._inflight.add(post.id)
        try:
            await self._fanout_inner(post)
        finally:
            self._inflight.discard(post.id)

    async def _fanout_inner(self, post: Post) -> None:
        """Real fanout body — split out so the inflight guard is exception-safe."""
        now_ist = datetime.now(IST)
        candidates = users.list_active_users(limit=self._settings.telegram_fanout_max_users_per_post)
        log.info("user_fanout_start", post_id=post.id, candidates=len(candidates))

        sent = 0
        skipped_filter = 0
        skipped_existing = 0
        failed = 0

        card = render_post_card(post)
        keyboard = article_keyboard(post)

        for user in candidates:
            if not is_eligible(user, post, now_ist=now_ist):
                skipped_filter += 1
                continue
            if deliveries.was_sent(post.id, user.tg_chat_id, "user_alert"):
                skipped_existing += 1
                continue
            ok = await self._send_one(user, card, keyboard, post.id)
            if ok:
                sent += 1
            else:
                failed += 1

        log.info(
            "user_fanout_done",
            post_id=post.id,
            sent=sent,
            skipped_filter=skipped_filter,
            skipped_existing=skipped_existing,
            failed=failed,
        )

    async def _send_one(self, user: TelegramUser, card, keyboard, post_id: str) -> bool:
        """Send a single user-alert message with rate limiting and error handling."""
        attempts = 0
        while True:
            attempts += 1
            try:
                await self._limiter.acquire(user.tg_chat_id)
                msg = await self._bot.send_message(
                    chat_id=user.tg_chat_id,
                    text=card.text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    link_preview_options=LinkPreviewOptions(
                        url=card.preview_url,
                        prefer_large_media=True,
                        show_above_text=False,
                    ) if card.preview_url else LinkPreviewOptions(is_disabled=True),
                    disable_notification=False,
                )
            except TelegramRetryAfter as exc:
                if attempts >= 3:
                    log.warning(
                        "user_fanout_giveup_rate_limit",
                        tg_user_id=user.tg_user_id,
                        post_id=post_id,
                    )
                    return False
                await asyncio.sleep(float(exc.retry_after) + 0.5)
                continue
            except TelegramForbiddenError:
                users.mark_blocked(user.tg_user_id)
                log.info("user_fanout_user_blocked", tg_user_id=user.tg_user_id)
                return False
            except Exception as exc:
                log.warning(
                    "user_fanout_send_failed",
                    tg_user_id=user.tg_user_id,
                    post_id=post_id,
                    error=str(exc),
                )
                return False

            deliveries.record_sent(
                post_id=post_id,
                chat_id=user.tg_chat_id,
                message_id=msg.message_id,
                kind="user_alert",
            )
            return True
