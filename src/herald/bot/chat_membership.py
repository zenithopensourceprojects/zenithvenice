"""Track groups, supergroups, and channels that add the Herald bot.

Telegram delivers a `my_chat_member` update whenever the bot's own status in
a chat changes. We use that single signal to keep `telegram_subscribed_chats`
in sync — no slash command required from the user.

Active states (member / administrator / restricted-but-can-send) → register.
Inactive states (left / kicked) → mark inactive.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from aiogram import Router

from herald.data import chats
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from aiogram.types import ChatMemberUpdated

    from herald.data.models import ChatType

router = Router(name="chat_membership")
log = get_logger(__name__)

_ACTIVE_STATUSES = {"member", "administrator", "restricted"}
_INACTIVE_STATUSES = {"left", "kicked"}


def _coerce_chat_type(raw: str) -> ChatType | None:
    if raw in ("group", "supergroup", "channel"):
        return raw  # type: ignore[return-value]
    return None


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated) -> None:
    """React to the bot's own membership changing in a chat."""
    chat = event.chat
    new_status = event.new_chat_member.status
    chat_type = _coerce_chat_type(chat.type)

    # Private chats are handled by /start + the user upsert middleware.
    if chat_type is None:
        return

    if new_status in _ACTIVE_STATUSES:
        added_by = event.from_user.id if event.from_user and not event.from_user.is_bot else None
        chats.register_chat(
            tg_chat_id=chat.id,
            chat_type=chat_type,
            title=chat.title,
            username=chat.username,
            added_by_user_id=added_by,
        )
        log.info(
            "chat_subscribed",
            tg_chat_id=chat.id,
            chat_type=chat_type,
            title=chat.title,
            added_by=added_by,
        )
        with contextlib.suppress(Exception):
            await _send_welcome(event)
        return

    if new_status in _INACTIVE_STATUSES:
        chats.deactivate_chat(chat.id)
        log.info(
            "chat_unsubscribed",
            tg_chat_id=chat.id,
            chat_type=chat_type,
            new_status=new_status,
        )


async def _send_welcome(event: ChatMemberUpdated) -> None:
    """Post a one-time welcome message in the chat where the bot was added.

    Channels: bot must be an admin to send, so this gracefully no-ops on
    permission errors via the suppress() in the caller.
    """
    bot = event.bot
    if bot is None:
        return
    text = (
        "🇮🇳  <b>India Verified</b> is now in this chat.\n\n"
        "I'll automatically post every verified, multi-source story here as "
        "soon as it's published. Each card shows its credibility score, "
        "sources, and time.\n\n"
        "Remove me any time and I'll stop posting."
    )
    await bot.send_message(chat_id=event.chat.id, text=text, parse_mode="HTML")
