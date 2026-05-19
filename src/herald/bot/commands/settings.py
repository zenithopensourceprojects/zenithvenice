"""/settings command — interactive notification preferences."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message

from herald.bot.keyboards import quiet_hours_label, settings_root_keyboard
from herald.data import users

router = Router(name="settings")


_HEADER = (
    "⚙️  <b>Notification preferences</b>\n\n"
    "<i>Tweak when and how Herald reaches you.</i>\n"
    "Changes apply immediately — no save button."
)


@router.message(Command("settings", "prefs"))
async def on_settings(message: Message) -> None:
    """Render the settings root menu for the user."""
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

    await message.answer(
        _HEADER,
        parse_mode="HTML",
        reply_markup=settings_root_keyboard(
            current_mode=current_mode,
            quiet_label=quiet,
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
