"""/start command — welcome screen and deep-link handler."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, LinkPreviewOptions, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from herald.bot.keyboards import article_keyboard
from herald.config import get_settings
from herald.data import posts
from herald.render.card import render_post_card
from herald.utils.escape import escape_html

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def on_start_deep_link(message: Message, command: CommandObject) -> None:
    """Handle deep-links such as `t.me/IndiaVerifiedBot?start=post_<uuid>`."""
    payload = (command.args or "").strip()
    if payload.startswith("post_"):
        post_id = payload.removeprefix("post_")
        post = posts.fetch_post_by_id(post_id)
        if post:
            card = render_post_card(post)
            await message.answer(
                card.text,
                parse_mode="HTML",
                reply_markup=article_keyboard(post),
                link_preview_options=LinkPreviewOptions(
                    url=card.preview_url,
                    prefer_large_media=True,
                    show_above_text=False,
                ) if card.preview_url else LinkPreviewOptions(is_disabled=True),
            )
            return
    await _send_welcome(message)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    """Plain `/start` with no payload."""
    await _send_welcome(message)


async def _send_welcome(message: Message) -> None:
    """Render the canonical welcome card with quick-action buttons."""
    settings = get_settings()
    name = escape_html(message.from_user.first_name or "there") if message.from_user else "there"

    text = (
        f"🇮🇳  <b>India Verified</b>\n"
        f"<i>Welcome, {name}.</i>\n\n"
        "I deliver only verified, multi-source Indian news — no rumours, "
        "no spam, no engagement traps.\n\n"
        "<b>What you can do here</b>\n"
        "•  /latest — the freshest verified stories\n"
        "•  /categories — browse by topic\n"
        "•  /search &lt;keyword&gt; — find specific stories\n"
        "•  /saved — your bookmarks\n"
        "•  /about — how we verify\n\n"
        "Every story shows its credibility score, sources, and time."
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📰  Latest stories", callback_data="cmd:latest"))
    builder.row(InlineKeyboardButton(text="📂  Browse categories", callback_data="cat:menu"))
    if settings.telegram_channel_invite_url:
        builder.row(
            InlineKeyboardButton(
                text="📣  Join the channel",
                url=settings.telegram_channel_invite_url,
            )
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
