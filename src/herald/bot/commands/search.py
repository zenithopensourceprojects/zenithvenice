"""/search command — keyword search across verified posts."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import LinkPreviewOptions, Message

from herald.bot.keyboards import article_keyboard
from herald.data import posts
from herald.render.card import render_post_card
from herald.utils.escape import escape_html, truncate

router = Router(name="search")


_MIN_LEN = 2
_LIMIT = 5


@router.message(Command("search", "find"))
async def on_search(message: Message, command: CommandObject, bot: Bot) -> None:
    """Handle `/search <query>`."""
    query_text = (command.args or "").strip()
    if len(query_text) < _MIN_LEN:
        await message.answer(
            "<b>Search</b>\n\nUsage:  <code>/search modi northeast</code>\n"
            "Type at least two characters.",
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    results = posts.search(query_text, limit=_LIMIT)
    safe_query = escape_html(truncate(query_text, 80))

    if not results:
        await message.answer(
            f"🔎  <b>No matches</b> for «{safe_query}».",
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    await message.answer(
        f"🔎  <b>Results for «{safe_query}»</b>\n<i>{len(results)} verified stories</i>",
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

    for post in results:
        card = render_post_card(post)
        await bot.send_message(
            chat_id=message.chat.id,
            text=card.text,
            parse_mode="HTML",
            reply_markup=article_keyboard(post),
            link_preview_options=LinkPreviewOptions(
                url=card.preview_url,
                prefer_large_media=True,
                show_above_text=False,
            ) if card.preview_url else LinkPreviewOptions(is_disabled=True),
            disable_notification=True,
        )
