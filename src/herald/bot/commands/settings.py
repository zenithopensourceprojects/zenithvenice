"""/settings command — interactive notification preferences."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command

from herald.bot.hub import open_hub
from herald.bot.keyboards import quiet_hours_label, settings_root_keyboard
from herald.data import users

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

router = Router(name="settings")


_HEADER = (
    "⚙️   <b>Notification preferences</b>\n\n"
    "<i>Tweak when and how Herald reaches you.</i>\n"
    "Changes apply immediately — no save button."
)


@router.message(Command("settings", "prefs"))
async def on_settings(message: Message, bot: Bot) -> None:
    """Render the settings root menu inside the hub."""
    if not message.from_user:
        return

    user = users.get_user(message.from_user.id)
    current_mode = user.notif_mode if user else "instant"
    if user:
        quiet = quiet_hours_label(
            user.quiet_start.strftime("%H:%M"),
            user.quiet_end.strftime("%H:%M"),
        )
    else:
        quiet = "Off"

    keyboard = settings_root_keyboard(
        current_mode=current_mode,
        quiet_label=quiet,
    )
    await open_hub(message, bot, text=_HEADER, keyboard=keyboard)
