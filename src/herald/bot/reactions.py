"""Telegram message-reaction event handler.

Subscribes to `MessageReactionUpdated` updates so emoji reactions left on
channel or DM messages are folded back into `telegram_reactions`. These
counts feed the website's "trending" signal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router

from herald.data import reactions
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from aiogram.types import MessageReactionUpdated, ReactionType


log = get_logger(__name__)
router = Router(name="reactions")


def _extract_emoji(items: list[ReactionType]) -> list[str]:
    """Flatten an aiogram reaction list into raw emoji strings."""
    out: list[str] = []
    for item in items or []:
        emoji = getattr(item, "emoji", None) or getattr(item, "custom_emoji_id", None)
        if emoji:
            out.append(str(emoji))
    return out


@router.message_reaction()
async def on_message_reaction(update: MessageReactionUpdated) -> None:
    """Handle a user's reaction change on any Herald-published message."""
    if not update.user:
        return

    chat_id = update.chat.id
    message_id = update.message_id

    post_id = reactions.lookup_post_id(chat_id=chat_id, message_id=message_id)
    if not post_id:
        return

    new_emoji = _extract_emoji(list(update.new_reaction or []))

    reactions.clear_user_reactions(post_id=post_id, tg_user_id=update.user.id)
    if new_emoji:
        reactions.record_reactions(
            post_id=post_id,
            tg_user_id=update.user.id,
            reactions=new_emoji,
        )

    log.info(
        "reaction_recorded",
        post_id=post_id,
        tg_user_id=update.user.id,
        emoji=new_emoji,
    )
