"""/about and /help commands — both open the hub at the About view."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command

from herald.bot import views
from herald.bot.hub import open_hub

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

router = Router(name="about")


@router.message(Command("about", "help", "info"))
async def on_about(message: Message, bot: Bot) -> None:
    """Render About / Help inside the hub."""
    text, keyboard = views.render_about()
    await open_hub(message, bot, text=text, keyboard=keyboard)
