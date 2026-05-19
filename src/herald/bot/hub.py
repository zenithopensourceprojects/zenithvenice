"""The Hub — a single editable control-panel message per chat.

All on-demand menu navigation lives inside one rotating message that gets
edited in place. Live news (push fanout) remains as standalone feed
messages; the hub never spawns extra messages on top of the feed.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

from aiogram.types import LinkPreviewOptions

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


_HUB_TTL_SECONDS = 60 * 60 * 24  # 24h — older entries get garbage-collected.


class _HubRegistry:
    """Per-process map from chat_id to the current hub message id."""

    def __init__(self) -> None:
        self._state: dict[int, tuple[int, float]] = {}

    def get(self, chat_id: int) -> int | None:
        entry = self._state.get(chat_id)
        if entry is None:
            return None
        message_id, ts = entry
        if time.time() - ts > _HUB_TTL_SECONDS:
            self._state.pop(chat_id, None)
            return None
        return message_id

    def set(self, chat_id: int, message_id: int) -> None:
        self._state[chat_id] = (message_id, time.time())

    def clear(self, chat_id: int) -> None:
        self._state.pop(chat_id, None)


_registry = _HubRegistry()


async def open_hub(
    message: Message,
    bot: Bot,
    *,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> Message:
    """Open or replace the chat's hub message.

    If a previous hub exists in this chat, it is silently deleted so the
    feed stays clean. Returns the new hub `Message`.
    """
    chat_id = message.chat.id
    prev = _registry.get(chat_id)
    if prev is not None:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, prev)
        _registry.clear(chat_id)

    sent = await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    _registry.set(chat_id, sent.message_id)
    return sent


async def edit_hub(
    query: CallbackQuery,
    *,
    text: str,
    keyboard: InlineKeyboardMarkup,
    disable_preview: bool = True,
    preview_url: str | None = None,
) -> None:
    """Edit the hub in place. Silently swallows the 'message is not modified' edge.

    When `preview_url` is provided and `disable_preview=False`, Telegram will
    render a large preview above the text — used for the article-view screen.
    """
    if query.message is None:
        return

    if disable_preview:
        link_preview = LinkPreviewOptions(is_disabled=True)
    elif preview_url:
        link_preview = LinkPreviewOptions(
            url=preview_url,
            prefer_large_media=True,
            show_above_text=False,
        )
    else:
        link_preview = LinkPreviewOptions(is_disabled=True)

    chat_id = query.message.chat.id
    _registry.set(chat_id, query.message.message_id)

    with contextlib.suppress(Exception):
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
            link_preview_options=link_preview,
        )


async def close_hub(query: CallbackQuery, *, farewell: str = "✅  <i>Closed.</i>") -> None:
    """Replace the hub with a small farewell line and forget it."""
    if query.message is None:
        return
    _registry.clear(query.message.chat.id)
    with contextlib.suppress(Exception):
        await query.message.edit_text(
            farewell,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
