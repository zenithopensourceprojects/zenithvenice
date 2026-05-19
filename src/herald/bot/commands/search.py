"""/search command — opens the hub with paginated results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command

from herald.bot import views
from herald.bot.hub import open_hub
from herald.data import posts

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.filters import CommandObject
    from aiogram.types import Message

router = Router(name="search")


_MIN_LEN = 2
_LIMIT = 20


@router.message(Command("search", "find"))
async def on_search(message: Message, command: CommandObject, bot: Bot) -> None:
    """Handle `/search <query>` — results live in the hub."""
    query_text = (command.args or "").strip()
    if len(query_text) < _MIN_LEN:
        text, keyboard = views.render_search_prompt()
        await open_hub(message, bot, text=text, keyboard=keyboard)
        return

    results = posts.search(query_text, limit=_LIMIT)
    text, keyboard = views.render_search_results(results, query=query_text, page=0)
    await open_hub(message, bot, text=text, keyboard=keyboard)
