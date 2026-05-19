"""/start command — opens the hub or jumps to a deep-linked story."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import LinkPreviewOptions, Message

from herald.bot import views
from herald.bot.hub import open_hub
from herald.bot.keyboards import article_keyboard
from herald.data import posts
from herald.render.card import render_post_card

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def on_start_deep_link(message: Message, command: CommandObject, bot: Bot) -> None:
    """Handle deep-links such as `t.me/IndiaVerifiedBot?start=post_<uuid>`.

    A deep-link to a specific post still sends a one-shot card (it's a
    direct share, not a menu action). Plain /start opens the hub.
    """
    payload = (command.args or "").strip()
    if payload.startswith("post_"):
        post_id = payload.removeprefix("post_")
        post = posts.fetch_post_by_id(post_id)
        if post:
            card = render_post_card(post)
            await message.answer(
                card.text,
                parse_mode="HTML",
                reply_markup=article_keyboard(post),
                link_preview_options=LinkPreviewOptions(
                    url=card.preview_url,
                    prefer_large_media=True,
                    show_above_text=False,
                ) if card.preview_url else LinkPreviewOptions(is_disabled=True),
            )
            return
    await _open_root_hub(message, bot)


@router.message(CommandStart())
async def on_start(message: Message, bot: Bot) -> None:
    """Plain `/start` opens the hub home screen."""
    await _open_root_hub(message, bot)


async def _open_root_hub(message: Message, bot: Bot) -> None:
    """Render the hub's home view and replace any prior hub message."""
    first_name = message.from_user.first_name if message.from_user else None
    text, keyboard = views.render_root(first_name=first_name)
    await open_hub(message, bot, text=text, keyboard=keyboard)
