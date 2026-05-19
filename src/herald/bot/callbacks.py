"""Inline-keyboard callback handlers."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, LinkPreviewOptions

from herald.bot.keyboards import (
    quiet_hours_keyboard,
    quiet_hours_label,
    quiet_preset_window,
    settings_mode_keyboard,
    settings_mute_keyboard,
    settings_root_keyboard,
)
from herald.data import bookmarks, posts, users
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from herald.data.models import Post

log = get_logger(__name__)
router = Router(name="callbacks")


def _split_callback(data: str | None, expected_prefix: str) -> str | None:
    """Return the post-id payload from a callback data string of form `prefix:id`."""
    if not data or not data.startswith(expected_prefix):
        return None
    parts = data.split(":", 2)
    if len(parts) != 3:
        return None
    return parts[2]


@router.callback_query(F.data.startswith("bm:add:"))
async def on_bookmark_add(query: CallbackQuery) -> None:
    """Save a post to the user's bookmarks."""
    post_id = _split_callback(query.data, "bm:add:")
    if not post_id or not query.from_user:
        await query.answer("Sorry, that button is no longer valid.", show_alert=False)
        return

    if not users.get_user(query.from_user.id):
        users.upsert_user(
            tg_user_id=query.from_user.id,
            tg_chat_id=query.message.chat.id if query.message else query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            language_code=query.from_user.language_code,
        )

    bookmarks.save(query.from_user.id, post_id)
    await query.answer("Saved ⭐", show_alert=False)


@router.callback_query(F.data.startswith("bm:rm:"))
async def on_bookmark_remove(query: CallbackQuery) -> None:
    """Remove a post from the user's bookmarks."""
    post_id = _split_callback(query.data, "bm:rm:")
    if not post_id or not query.from_user:
        await query.answer("Sorry, that button is no longer valid.", show_alert=False)
        return

    bookmarks.remove(query.from_user.id, post_id)
    await query.answer("Removed.", show_alert=False)
    if query.message:
        with contextlib.suppress(Exception):
            await query.message.delete()


@router.callback_query(F.data.startswith("src:all:"))
async def on_show_all_sources(query: CallbackQuery, bot: Bot) -> None:
    """Open the hub at the all-sources view for the post under this card.

    The feed card itself stays in place; the hub message at the bottom of
    the chat is replaced with the sources view, keeping the feed clean.
    """
    post_id = _split_callback(query.data, "src:all:")
    if not post_id:
        await query.answer("Sorry, that button is no longer valid.", show_alert=False)
        return

    post: Post | None = posts.fetch_post_by_id(post_id)
    if not post:
        await query.answer("This post is no longer available.", show_alert=True)
        return

    if query.message is None:
        await query.answer()
        return

    from herald.bot import views
    from herald.bot.hub import open_hub

    text, keyboard = views.render_sources_view(post, return_cd="hub:root")
    await open_hub(query.message, bot, text=text, keyboard=keyboard)
    await query.answer()


_SETTINGS_HEADER = (
    "⚙️  <b>Notification preferences</b>\n\n"
    "<i>Tweak when and how Herald reaches you.</i>"
)


def _current_mode(tg_user_id: int) -> str:
    """Return the user's current notification mode, defaulting to 'instant'."""
    user = users.get_user(tg_user_id)
    return user.notif_mode if user else "instant"


def _current_muted(tg_user_id: int) -> list[str]:
    """Return the user's current muted-categories list."""
    user = users.get_user(tg_user_id)
    return list(user.muted_categories) if user else []


def _current_quiet(tg_user_id: int) -> tuple[str, str]:
    """Return the user's current quiet-hours window as ('HH:MM', 'HH:MM')."""
    user = users.get_user(tg_user_id)
    if not user:
        return ("00:00", "00:00")
    return (user.quiet_start.strftime("%H:%M"), user.quiet_end.strftime("%H:%M"))


def _build_root(tg_user_id: int):
    """Build the settings-root keyboard reflecting the user's current state."""
    mode = _current_mode(tg_user_id)
    start, end = _current_quiet(tg_user_id)
    return settings_root_keyboard(
        current_mode=mode,
        quiet_label=quiet_hours_label(start, end),
    )


async def _replace(query: CallbackQuery, text: str, markup) -> None:
    """Edit the existing settings message in place, swallowing edit-errors."""
    if not query.message:
        return
    with contextlib.suppress(Exception):
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


@router.callback_query(F.data == "set:root")
async def on_settings_root(query: CallbackQuery) -> None:
    """Render the settings root menu."""
    if not query.from_user:
        await query.answer()
        return
    await _replace(query, _SETTINGS_HEADER, _build_root(query.from_user.id))
    await query.answer()


@router.callback_query(F.data == "set:close")
async def on_settings_close(query: CallbackQuery) -> None:
    """Close the settings menu by removing the keyboard."""
    if query.message:
        with contextlib.suppress(Exception):
            await query.message.edit_text(
                "✅  <i>Preferences saved.</i>",
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
    await query.answer("Done.", show_alert=False)


@router.callback_query(F.data == "set:mode")
async def on_settings_mode_open(query: CallbackQuery) -> None:
    """Open the notification-mode picker."""
    if not query.from_user:
        await query.answer()
        return
    mode = _current_mode(query.from_user.id)
    text = (
        "🔔  <b>Choose your cadence</b>\n\n"
        "<b>Instant</b> — every story, the moment it lands.\n"
        "<b>Digest</b> — top stories twice a day at 8 AM and 8 PM IST.\n"
        "<b>Breaking only</b> — push only stories with credibility ≥ 90.\n"
        "<b>Silent</b> — no DMs; check the channel when you want."
    )
    await _replace(query, text, settings_mode_keyboard(mode))
    await query.answer()


@router.callback_query(F.data.startswith("set:mode:"))
async def on_settings_mode_pick(query: CallbackQuery) -> None:
    """Persist the user's selected notification mode."""
    if not query.from_user or not query.data:
        await query.answer()
        return
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.answer()
        return
    mode = parts[2]
    if mode not in {"instant", "digest", "breaking_only", "silent"}:
        await query.answer("Unknown mode.", show_alert=False)
        return

    users.set_notif_mode(query.from_user.id, mode)
    log.info("settings_mode_changed", tg_user_id=query.from_user.id, mode=mode)
    await _replace(query, _SETTINGS_HEADER, _build_root(query.from_user.id))
    await query.answer("Updated.", show_alert=False)


@router.callback_query(F.data == "set:mute")
async def on_settings_mute_open(query: CallbackQuery) -> None:
    """Open the per-category mute toggle grid."""
    if not query.from_user:
        await query.answer()
        return
    muted = _current_muted(query.from_user.id)
    text = (
        "🔇  <b>Mute categories</b>\n\n"
        "<i>Tap a category to toggle. 🔕 = muted, 🔔 = receiving.</i>\n"
        "Channel topics still post; this only affects DMs."
    )
    await _replace(query, text, settings_mute_keyboard(muted))
    await query.answer()


@router.callback_query(F.data.startswith("set:mute:"))
async def on_settings_mute_toggle(query: CallbackQuery) -> None:
    """Toggle a single category in the user's mute list."""
    if not query.from_user or not query.data:
        await query.answer()
        return
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.answer()
        return
    category = parts[2]

    new_muted = users.toggle_muted_category(query.from_user.id, category)
    log.info(
        "settings_mute_toggled",
        tg_user_id=query.from_user.id,
        category=category,
        muted=category in new_muted,
    )
    text = (
        "🔇  <b>Mute categories</b>\n\n"
        "<i>Tap a category to toggle. 🔕 = muted, 🔔 = receiving.</i>"
    )
    await _replace(query, text, settings_mute_keyboard(new_muted))
    await query.answer("Updated.", show_alert=False)


@router.callback_query(F.data == "set:quiet")
async def on_settings_quiet_open(query: CallbackQuery) -> None:
    """Open the quiet-hours preset picker."""
    if not query.from_user:
        await query.answer()
        return
    start, end = _current_quiet(query.from_user.id)
    text = (
        "🌙  <b>Quiet hours</b>\n\n"
        "<i>Within this IST window we'll hold back the digest. "
        "Channel posts and breaking alerts still arrive in the channel.</i>"
    )
    await _replace(query, text, quiet_hours_keyboard(start, end))
    await query.answer()


@router.callback_query(F.data.startswith("set:quiet:"))
async def on_settings_quiet_pick(query: CallbackQuery) -> None:
    """Persist a quiet-hours preset selection."""
    if not query.from_user or not query.data:
        await query.answer()
        return
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.answer()
        return
    window = quiet_preset_window(parts[2])
    if window is None:
        await query.answer("Unknown preset.", show_alert=False)
        return

    start, end = window
    users.set_quiet_hours(query.from_user.id, start, end)
    log.info(
        "settings_quiet_changed",
        tg_user_id=query.from_user.id,
        start=start,
        end=end,
    )
    await _replace(query, _SETTINGS_HEADER, _build_root(query.from_user.id))
    await query.answer("Updated.", show_alert=False)
