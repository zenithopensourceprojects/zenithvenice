"""/categories command — opens the category picker."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message

from herald.bot.keyboards import categories_keyboard

router = Router(name="categories")


@router.message(Command("categories", "topics"))
async def on_categories(message: Message) -> None:
    """Render the category picker."""
    await message.answer(
        "📂  <b>Categories</b>\n\nPick a topic to see the latest verified stories.",
        parse_mode="HTML",
        reply_markup=categories_keyboard(),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
