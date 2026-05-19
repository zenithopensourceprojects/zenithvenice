"""Per-chat fanout to every group, supergroup, or channel that has added the bot.

Counterpart to `ChannelDispatcher` (the official channel) and `UserFanout`
(per-user DMs). Iterates `telegram_subscribed_chats`, applies per-chat
filters, sends the rendered card, and records a `external_chat` delivery row
for idempotency.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import LinkPreviewOptions

from herald.bot.keyboards import article_keyboard
from herald.data import chats, deliveries
from herald.logging_setup import get_logger
from herald.render.card import render_post_card

if TYPE_CHECKING:
    from aiogram import Bot

    from herald.data.models import Post, SubscribedChat
    from herald.publisher.scheduler import RateLimiter


log = get_logger(__name__)


def is_eligible(chat: SubscribedChat, post: Post) -> bool:
    """Pure filter: does this chat want this post?"""
    if not chat.is_active:
        return False
    if post.category in set(chat.muted_categories):
        return False
    return post.credibility_score >= chat.min_score


class ChatFanout:
    """Send a single post to every active subscribed chat."""

    def __init__(self, *, bot: Bot, limiter: RateLimiter) -> None:
        self._bot = bot
        self._limiter = limiter
        self._inflight: set[str] = set()

    async def fanout(self, post: Post) -> None:
        """Filter, send, and record deliveries for `post`."""
        if post.id in self._inflight:
            log.info("chat_fanout_skip_inflight", post_id=post.id)
            return
        self._inflight.add(post.id)
        try:
            await self._fanout_inner(post)
        finally:
            self._inflight.discard(post.id)

    async def _fanout_inner(self, post: Post) -> None:
        candidates = chats.list_active_chats()
        log.info("chat_fanout_start", post_id=post.id, candidates=len(candidates))

        sent = 0
        skipped_filter = 0
        skipped_existing = 0
        failed = 0

        card = render_post_card(post)
        keyboard = article_keyboard(post)
        preview_options = (
            LinkPreviewOptions(
                url=card.preview_url,
                prefer_large_media=True,
                show_above_text=False,
            )
            if card.preview_url
            else LinkPreviewOptions(is_disabled=True)
        )

        for chat in candidates:
            if not is_eligible(chat, post):
                skipped_filter += 1
                continue
            if deliveries.was_sent(post.id, chat.tg_chat_id, "external_chat"):
                skipped_existing += 1
                continue
            ok = await self._send_one(chat, card, keyboard, preview_options, post.id)
            if ok:
                sent += 1
            else:
                failed += 1

        log.info(
            "chat_fanout_done",
            post_id=post.id,
            sent=sent,
            skipped_filter=skipped_filter,
            skipped_existing=skipped_existing,
            failed=failed,
        )

    async def _send_one(
        self,
        chat: SubscribedChat,
        card,  # type: ignore[no-untyped-def]
        keyboard,  # type: ignore[no-untyped-def]
        preview_options: LinkPreviewOptions,
        post_id: str,
    ) -> bool:
        attempts = 0
        while True:
            attempts += 1
            try:
                await self._limiter.acquire(chat.tg_chat_id)
                msg = await self._bot.send_message(
                    chat_id=chat.tg_chat_id,
                    text=card.text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    link_preview_options=preview_options,
                    disable_notification=False,
                )
            except TelegramRetryAfter as exc:
                if attempts >= 3:
                    log.warning(
                        "chat_fanout_giveup_rate_limit",
                        tg_chat_id=chat.tg_chat_id,
                        post_id=post_id,
                    )
                    return False
                await asyncio.sleep(float(exc.retry_after) + 0.5)
                continue
            except TelegramForbiddenError:
                # Bot was kicked or lost permission to post — stop targeting it.
                chats.deactivate_chat(chat.tg_chat_id)
                log.info("chat_fanout_forbidden", tg_chat_id=chat.tg_chat_id)
                return False
            except TelegramBadRequest as exc:
                msg_text = str(exc).lower()
                if "chat not found" in msg_text or "chat was upgraded" in msg_text:
                    chats.deactivate_chat(chat.tg_chat_id)
                log.warning(
                    "chat_fanout_bad_request",
                    tg_chat_id=chat.tg_chat_id,
                    post_id=post_id,
                    error=str(exc),
                )
                return False
            except Exception as exc:
                log.warning(
                    "chat_fanout_send_failed",
                    tg_chat_id=chat.tg_chat_id,
                    post_id=post_id,
                    error=str(exc),
                )
                return False

            deliveries.record_sent(
                post_id=post_id,
                chat_id=chat.tg_chat_id,
                message_id=msg.message_id,
                kind="external_chat",
            )
            chats.touch_last_post(chat.tg_chat_id)
            return True
