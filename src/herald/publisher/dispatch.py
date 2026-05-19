"""Idempotent send pipeline: render a Post, push to channel, record delivery."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import LinkPreviewOptions

from herald.bot.keyboards import article_keyboard
from herald.config import get_settings
from herald.data import deliveries
from herald.logging_setup import get_logger
from herald.render.card import render_post_card

if TYPE_CHECKING:
    from aiogram import Bot

    from herald.data.models import Post
    from herald.publisher.chat_fanout import ChatFanout
    from herald.publisher.scheduler import RateLimiter
    from herald.publisher.user_fanout import UserFanout

log = get_logger(__name__)


class ChannelDispatcher:
    """Sends rendered post cards to the configured forum supergroup."""

    def __init__(
        self,
        *,
        bot: Bot,
        limiter: RateLimiter,
        user_fanout: UserFanout | None = None,
        chat_fanout: ChatFanout | None = None,
    ) -> None:
        self._bot = bot
        self._limiter = limiter
        self._user_fanout = user_fanout
        self._chat_fanout = chat_fanout
        self._settings = get_settings()
        self._inflight: set[str] = set()
        self._lock = asyncio.Lock()
        self._fanout_tasks: set[asyncio.Task[None]] = set()

    async def publish(self, post: Post) -> bool:
        """Send `post` to the configured channel exactly once. Returns True on success.

        When `TELEGRAM_CHANNEL_ID` is unset the channel send is skipped, but the
        post is still fanned out to every subscribed DM user and external chat,
        and a sentinel delivery row (chat_id=0) is written so the safety-net
        poller considers the post processed.
        """
        chat_id = self._settings.telegram_channel_id

        async with self._lock:
            if post.id in self._inflight:
                return False
            if deliveries.was_sent(post.id, chat_id, "channel"):
                return False
            self._inflight.add(post.id)

        try:
            if not self._settings.channel_enabled:
                return await self._publish_no_channel(post)
            return await self._send(post, chat_id)
        finally:
            async with self._lock:
                self._inflight.discard(post.id)

    async def _publish_no_channel(self, post: Post) -> bool:
        """Channel-less path: mark processed, then run fanouts."""
        deliveries.record_sent(
            post_id=post.id,
            chat_id=0,
            message_id=0,
            kind="channel",
        )
        log.info(
            "post_published_no_channel",
            post_id=post.id,
            score=post.credibility_score,
            category=post.category,
        )
        self._kick_fanout(post)
        return True

    async def _send(self, post: Post, chat_id: int) -> bool:
        topic_id = self._settings.topic_id_for(post.category)
        card = render_post_card(post)

        preview_options: LinkPreviewOptions
        if card.preview_url and not self._settings.telegram_disable_link_preview:
            preview_options = LinkPreviewOptions(
                url=card.preview_url,
                prefer_large_media=self._settings.telegram_prefer_large_preview,
                show_above_text=self._settings.telegram_preview_above_text,
            )
        else:
            preview_options = LinkPreviewOptions(is_disabled=True)

        attempts = 0
        while True:
            attempts += 1
            try:
                await self._limiter.acquire(chat_id)
                msg = await self._bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=topic_id,
                    text=card.text,
                    parse_mode="HTML",
                    reply_markup=article_keyboard(post),
                    link_preview_options=preview_options,
                    disable_notification=self._settings.telegram_disable_notification,
                )
                deliveries.record_sent(
                    post_id=post.id,
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    kind="channel",
                    topic_id=topic_id,
                )
                log.info(
                    "post_published",
                    post_id=post.id,
                    chat_id=chat_id,
                    topic_id=topic_id,
                    message_id=msg.message_id,
                    score=post.credibility_score,
                    category=post.category,
                )
                self._kick_fanout(post)
                return True

            except TelegramRetryAfter as exc:
                wait = float(exc.retry_after) + 0.5
                log.warning("rate_limited", retry_after=wait, post_id=post.id)
                await asyncio.sleep(wait)
                if attempts >= 5:
                    log.error("publish_giveup", post_id=post.id, attempts=attempts)
                    return False

            except Exception as exc:
                log.exception("publish_failed", post_id=post.id, error=str(exc))
                return False

    def _kick_fanout(self, post: Post) -> None:
        """Schedule per-user DM and per-chat fanout in the background."""
        if self._user_fanout is not None:
            task = asyncio.create_task(
                self._user_fanout.fanout(post),
                name=f"fanout:{post.id}",
            )
            self._fanout_tasks.add(task)
            task.add_done_callback(self._fanout_tasks.discard)

        if self._chat_fanout is not None:
            chat_task = asyncio.create_task(
                self._chat_fanout.fanout(post),
                name=f"chat_fanout:{post.id}",
            )
            self._fanout_tasks.add(chat_task)
            chat_task.add_done_callback(self._fanout_tasks.discard)
