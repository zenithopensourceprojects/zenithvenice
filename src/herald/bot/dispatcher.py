"""Aiogram Bot + Dispatcher factory."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from herald.bot import callbacks as callbacks_module
from herald.bot import chat_membership as chat_membership_module
from herald.bot import hub_callbacks as hub_callbacks_module
from herald.bot import reactions as reactions_module
from herald.bot.commands import register_commands
from herald.bot.middleware import ErrorLoggingMiddleware, UserActivityMiddleware
from herald.config import get_settings

_PUBLIC_COMMANDS: list[BotCommand] = [
    BotCommand(command="latest",     description="Newest verified stories"),
    BotCommand(command="categories", description="Browse by topic"),
    BotCommand(command="search",     description="Search verified news"),
    BotCommand(command="saved",      description="Your bookmarks"),
    BotCommand(command="settings",   description="Notification preferences"),
    BotCommand(command="about",      description="How we verify"),
    BotCommand(command="help",       description="Show available commands"),
]


def build_bot() -> Bot:
    """Construct the aiogram Bot with HTML parse mode by default."""
    settings = get_settings()
    return Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=False,
            protect_content=False,
        ),
    )


def build_dispatcher() -> Dispatcher:
    """Construct the Dispatcher with middleware and all routers attached."""
    dp = Dispatcher()

    error_mw = ErrorLoggingMiddleware()
    activity_mw = UserActivityMiddleware()

    dp.message.middleware(error_mw)
    dp.callback_query.middleware(error_mw)
    dp.message.middleware(activity_mw)
    dp.callback_query.middleware(activity_mw)

    register_commands(dp)
    dp.include_router(hub_callbacks_module.router)
    dp.include_router(callbacks_module.router)
    dp.include_router(reactions_module.router)
    dp.include_router(chat_membership_module.router)

    return dp


async def install_command_menu(bot: Bot) -> None:
    """Push the public command menu so Telegram clients show the suggestions."""
    await bot.set_my_commands(_PUBLIC_COMMANDS)
