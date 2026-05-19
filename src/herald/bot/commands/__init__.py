"""Command handlers for /start, /latest, /categories, /search, /about, /help, /saved."""

from __future__ import annotations

from typing import TYPE_CHECKING

from herald.bot.commands import (
    about,
    admin,
    categories,
    latest,
    saved,
    search,
    settings,
    start,
)

if TYPE_CHECKING:
    from aiogram import Dispatcher


def register_commands(dp: Dispatcher) -> None:
    """Attach every command router to the given dispatcher."""
    dp.include_router(start.router)
    dp.include_router(latest.router)
    dp.include_router(categories.router)
    dp.include_router(search.router)
    dp.include_router(saved.router)
    dp.include_router(settings.router)
    dp.include_router(admin.router)
    dp.include_router(about.router)
