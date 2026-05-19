"""/about and /help commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, LinkPreviewOptions, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from herald.config import get_settings

router = Router(name="about")


_ABOUT_TEXT = (
    "🇮🇳  <b>India Verified</b>\n\n"
    "We aggregate Indian news from trusted publications, verify each story across "
    "multiple sources, and assign a credibility score before publishing.\n\n"
    "<b>How verification works</b>\n"
    "1. We fetch articles from a curated set of established publishers.\n"
    "2. Stories are clustered by topic so duplicates are merged into a single post.\n"
    "3. An AI fact-check pipeline cross-references claims and flags discrepancies.\n"
    "4. Only stories that pass clear a human-readable credibility check are published.\n\n"
    "<b>What every card shows</b>\n"
    "•  Credibility score (0–100) and the source count\n"
    "•  Three-bullet summary\n"
    "•  Direct links to every original publication\n"
    "•  Live link preview from the primary source\n\n"
    "<b>Commands</b>\n"
    "•  /latest — newest verified stories\n"
    "•  /categories — browse by topic\n"
    "•  /search &lt;keyword&gt; — keyword search\n"
    "•  /saved — your bookmarks\n"
    "•  /about — this screen\n"
)


@router.message(Command("about", "help", "info"))
async def on_about(message: Message) -> None:
    """Render the About / Help screen."""
    settings = get_settings()
    builder = InlineKeyboardBuilder()
    if settings.public_site_url:
        builder.row(
            InlineKeyboardButton(
                text="🌐  Open India Verified  ↗",
                url=settings.public_site_url + "/",
            )
        )
    if settings.telegram_channel_invite_url:
        builder.row(
            InlineKeyboardButton(
                text="📣  Join the channel",
                url=settings.telegram_channel_invite_url,
            )
        )

    await message.answer(
        _ABOUT_TEXT,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
