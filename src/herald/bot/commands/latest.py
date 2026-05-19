"""/latest command — sends the freshest verified stories as full cards."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

from herald.bot.keyboards import article_keyboard
from herald.data import posts
from herald.render.card import render_post_card

router = Router(name="latest")


_DEFAULT_LIMIT = 5
_MAX_LIMIT = 10


def _parse_limit(args: str | None) -> int:
    """Parse the `[N]` argument from `/latest [N]`, clamped to a safe range."""
    if not args:
        return _DEFAULT_LIMIT
    token = args.strip().split()[0] if args.strip() else ""
    try:
        return max(1, min(_MAX_LIMIT, int(token)))
    except ValueError:
        return _DEFAULT_LIMIT


async def _send_latest(message_target: Message, limit: int, bot: Bot) -> None:
    """Send up to `limit` post cards into the same chat as `message_target`."""
    items = posts.fetch_latest(limit=limit)
    if not items:
        await message_target.answer(
            "<i>No verified stories yet — check back in a few minutes.</i>",
            parse_mode="HTML",
        )
        return

    await message_target.answer(
        f"📰  <b>Latest verified stories</b>\n<i>Newest first · {len(items)} stories</i>",
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

    for post in items:
        card = render_post_card(post)
        await bot.send_message(
            chat_id=message_target.chat.id,
            text=card.text,
            parse_mode="HTML",
            reply_markup=article_keyboard(post),
            link_preview_options=LinkPreviewOptions(
                url=card.preview_url,
                prefer_large_media=True,
                show_above_text=False,
            ) if card.preview_url else LinkPreviewOptions(is_disabled=True),
            disable_notification=True,
        )


@router.message(Command("latest"))
async def on_latest(message: Message, command: CommandObject, bot: Bot) -> None:
    """Handle `/latest [N]`."""
    limit = _parse_limit(command.args)
    await _send_latest(message, limit, bot)


@router.callback_query(F.data == "cmd:latest")
async def on_latest_callback(query: CallbackQuery, bot: Bot) -> None:
    """Handle the inline keyboard 'Latest stories' button."""
    if isinstance(query.message, Message):
        await _send_latest(query.message, _DEFAULT_LIMIT, bot)
    await query.answer()
