"""/saved command — list a user's bookmarked posts."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message

from herald.bot.keyboards import saved_article_keyboard
from herald.data import bookmarks
from herald.render.card import render_post_card

router = Router(name="saved")


@router.message(Command("saved", "bookmarks"))
async def on_saved(message: Message, bot: Bot) -> None:
    """List the user's saved posts (most recent first)."""
    if not message.from_user:
        return

    items = bookmarks.list_saved(message.from_user.id, limit=10)

    if not items:
        await message.answer(
            "⭐  <b>Saved stories</b>\n\n"
            "You haven't saved anything yet.\n"
            "Tap <b>Save</b> on any post to bookmark it.",
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    await message.answer(
        f"⭐  <b>Saved stories</b>\n<i>{len(items)} most-recent bookmarks</i>",
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

    for post in items:
        card = render_post_card(post)
        await bot.send_message(
            chat_id=message.chat.id,
            text=card.text,
            parse_mode="HTML",
            reply_markup=saved_article_keyboard(post),
            link_preview_options=LinkPreviewOptions(
                url=card.preview_url,
                prefer_large_media=True,
                show_above_text=False,
            ) if card.preview_url else LinkPreviewOptions(is_disabled=True),
            disable_notification=True,
        )
