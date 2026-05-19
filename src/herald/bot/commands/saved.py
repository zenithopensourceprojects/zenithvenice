"""/saved command — opens the hub at the bookmarks list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command

from herald.bot import views
from herald.bot.hub import open_hub
from herald.data import bookmarks

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

router = Router(name="saved")


@router.message(Command("saved", "bookmarks"))
async def on_saved(message: Message, bot: Bot) -> None:
    """Render the user's bookmarks inside the hub."""
    if not message.from_user:
        return
    items = bookmarks.list_saved(message.from_user.id, limit=50)
    text, keyboard = views.render_saved(items, page=0)
    await open_hub(message, bot, text=text, keyboard=keyboard)
