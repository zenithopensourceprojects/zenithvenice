"""/latest command — opens the hub at the paginated latest-news list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command

from herald.bot import views
from herald.bot.hub import open_hub
from herald.data import posts

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

router = Router(name="latest")


@router.message(Command("latest"))
async def on_latest(message: Message, bot: Bot) -> None:
    """Open the hub showing the latest verified stories."""
    items = posts.fetch_latest(limit=20)
    text, keyboard = views.render_latest(items, page=0)
    await open_hub(message, bot, text=text, keyboard=keyboard)
