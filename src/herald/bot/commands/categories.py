"""/categories command — opens the hub at the categories grid."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command

from herald.bot import views
from herald.bot.hub import open_hub

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

router = Router(name="categories")


@router.message(Command("categories", "topics"))
async def on_categories(message: Message, bot: Bot) -> None:
    """Render the category picker inside the hub."""
    text, keyboard = views.render_categories_grid()
    await open_hub(message, bot, text=text, keyboard=keyboard)
