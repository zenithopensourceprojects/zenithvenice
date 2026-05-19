"""Inline keyboard builders for Herald."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from herald.config import get_settings
from herald.render.category import all_themes, theme_for
from herald.render.sources import display_name, primary_source
from herald.utils.escape import truncate

if TYPE_CHECKING:
    from herald.data.models import Post


def _share_url(headline: str, url: str) -> str:
    """Return a t.me/share URL that opens Telegram's native forward picker."""
    return (
        "https://t.me/share/url"
        f"?url={quote_plus(url)}"
        f"&text={quote_plus(truncate(headline, 180))}"
    )


def article_keyboard(post: Post) -> InlineKeyboardMarkup:
    """Inline keyboard rendered under every news card."""
    settings = get_settings()
    web_url = settings.post_web_url(post.id)

    builder = InlineKeyboardBuilder()

    primary = primary_source(post.sources)
    if primary:
        primary_label = truncate(f"📰  Read on {display_name(primary)}", 56)
        builder.row(InlineKeyboardButton(text=primary_label + "  ↗", url=primary.url))

    builder.row(InlineKeyboardButton(text="🌐  Open on India Verified  ↗", url=web_url))

    builder.row(
        InlineKeyboardButton(text="⭐ Save",        callback_data=f"bm:add:{post.id}"),
        InlineKeyboardButton(text="📚 All sources", callback_data=f"src:all:{post.id}"),
        InlineKeyboardButton(text="↗ Share",        url=_share_url(post.headline, web_url)),
    )

    return builder.as_markup()


def saved_article_keyboard(post: Post) -> InlineKeyboardMarkup:
    """Variant used when listing already-saved posts."""
    settings = get_settings()
    web_url = settings.post_web_url(post.id)

    builder = InlineKeyboardBuilder()
    primary = primary_source(post.sources)
    if primary:
        builder.row(InlineKeyboardButton(text="📰  Read full  ↗", url=primary.url))
    builder.row(InlineKeyboardButton(text="🌐  Open on India Verified  ↗", url=web_url))
    builder.row(
        InlineKeyboardButton(text="🗑  Remove from saved", callback_data=f"bm:rm:{post.id}"),
        InlineKeyboardButton(text="📚 All sources",        callback_data=f"src:all:{post.id}"),
    )
    return builder.as_markup()


def categories_keyboard() -> InlineKeyboardMarkup:
    """Two-column grid of every supported category."""
    builder = InlineKeyboardBuilder()
    for theme in all_themes():
        builder.button(
            text=f"{theme.emoji}  {theme.label}",
            callback_data=f"cat:show:{theme.key}",
        )
    builder.adjust(2)
    return builder.as_markup()


def back_to_categories_keyboard() -> InlineKeyboardMarkup:
    """Single button returning the user to the category picker."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="« Back to categories", callback_data="cat:menu")
    )
    return builder.as_markup()


def category_label(category: str) -> str:
    """Human-readable label for a category key (used in messages)."""
    theme = theme_for(category)
    return f"{theme.emoji} {theme.label}"


def settings_root_keyboard(
    *,
    current_mode: str,
    quiet_label: str = "Off",
) -> InlineKeyboardMarkup:
    """Top-level settings menu."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🔔  Notifications: {_mode_label(current_mode)}",
            callback_data="set:mode",
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔇  Mute categories", callback_data="set:mute"),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🌙  Quiet hours: {quiet_label}",
            callback_data="set:quiet",
        )
    )
    builder.row(
        InlineKeyboardButton(text="✅  Done", callback_data="set:close"),
    )
    return builder.as_markup()


_QUIET_PRESETS: list[tuple[str, str, str]] = [
    ("off",     "00:00", "00:00"),
    ("22-07",   "22:00", "07:00"),
    ("23-07",   "23:00", "07:00"),
    ("00-08",   "00:00", "08:00"),
    ("21-06",   "21:00", "06:00"),
]


def quiet_hours_keyboard(current_start: str, current_end: str) -> InlineKeyboardMarkup:
    """Quiet-hours preset picker — five common windows."""
    builder = InlineKeyboardBuilder()
    for key, start, end in _QUIET_PRESETS:
        label = _quiet_preset_label(key, start, end)
        active = start == current_start and end == current_end
        marker = "● " if active else "○ "
        builder.row(
            InlineKeyboardButton(
                text=f"{marker}{label}",
                callback_data=f"set:quiet:{key}",
            )
        )
    builder.row(InlineKeyboardButton(text="« Back", callback_data="set:root"))
    return builder.as_markup()


def quiet_hours_label(start: str, end: str) -> str:
    """Compact human label for the current quiet-hours window."""
    if start == end:
        return "Off"
    return f"{start} → {end}"


def quiet_preset_window(key: str) -> tuple[str, str] | None:
    """Resolve a preset key to its (start, end) HH:MM tuple."""
    for entry_key, start, end in _QUIET_PRESETS:
        if entry_key == key:
            return start, end
    return None


def _quiet_preset_label(key: str, start: str, end: str) -> str:
    """Format a single preset entry for the picker."""
    if key == "off":
        return "Off — always notify"
    return f"{start} → {end} IST"


def settings_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """Mode-picker keyboard — instant / digest / breaking_only / silent."""
    builder = InlineKeyboardBuilder()
    for mode in ("instant", "digest", "breaking_only", "silent"):
        marker = "● " if mode == current_mode else "○ "
        builder.row(
            InlineKeyboardButton(
                text=f"{marker}{_mode_label(mode)}",
                callback_data=f"set:mode:{mode}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="« Back", callback_data="set:root"),
    )
    return builder.as_markup()


def settings_mute_keyboard(muted: list[str]) -> InlineKeyboardMarkup:
    """Per-category toggle grid — checked = muted, unchecked = receiving."""
    builder = InlineKeyboardBuilder()
    muted_set = set(muted)
    for theme in all_themes():
        is_muted = theme.key in muted_set
        marker = "🔕 " if is_muted else "🔔 "
        builder.button(
            text=f"{marker}{theme.label}",
            callback_data=f"set:mute:{theme.key}",
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="« Back", callback_data="set:root"))
    return builder.as_markup()


def _mode_label(mode: str) -> str:
    """Pretty label for a notification mode."""
    return {
        "instant":       "Every story (instant)",
        "digest":        "Twice-a-day digest",
        "breaking_only": "Breaking only (≥ 90)",
        "silent":        "Channel only, no DMs",
    }.get(mode, mode)
