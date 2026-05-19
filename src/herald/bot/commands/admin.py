"""Admin-only commands: /stats and /broadcast.

Gated by `TELEGRAM_ADMIN_USER_IDS` from settings. Non-admins receive a
silent acknowledgment so we don't leak the surface to randoms.
"""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import LinkPreviewOptions, Message

from herald.config import get_settings
from herald.data.client import get_supabase
from herald.logging_setup import get_logger

router = Router(name="admin")
log = get_logger(__name__)


def _is_admin(tg_user_id: int) -> bool:
    """Return True if the caller's id is in TELEGRAM_ADMIN_USER_IDS."""
    return tg_user_id in get_settings().admin_user_ids


@router.message(Command("stats"))
async def on_stats(message: Message) -> None:
    """Print a small operational dashboard for admins."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    client = get_supabase()
    try:
        users_total = client.table("telegram_users").select(
            "tg_user_id", count="exact"
        ).limit(1).execute().count or 0
        users_blocked = client.table("telegram_users").select(
            "tg_user_id", count="exact"
        ).eq("is_blocked", True).limit(1).execute().count or 0
        deliveries_total = client.table("telegram_deliveries").select(
            "id", count="exact"
        ).limit(1).execute().count or 0
        bookmarks_total = client.table("telegram_bookmarks").select(
            "tg_user_id", count="exact"
        ).limit(1).execute().count or 0
    except Exception as exc:
        await message.answer(f"<b>stats failed:</b> <code>{exc}</code>", parse_mode="HTML")
        log.exception("admin_stats_failed", error=str(exc))
        return

    body = (
        "📊  <b>Herald operational stats</b>\n\n"
        f"<b>Users</b>          {users_total:,}\n"
        f"<b>Blocked us</b>     {users_blocked:,}\n"
        f"<b>Deliveries</b>     {deliveries_total:,}\n"
        f"<b>Bookmarks</b>      {bookmarks_total:,}"
    )
    await message.answer(
        body,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.message(Command("broadcast"))
async def on_broadcast(message: Message, command: CommandObject, bot: Bot) -> None:
    """Send a one-off plain-HTML announcement to every active user.

    Usage: /broadcast <html message>
    Uses the existing rate limiter via aiogram's built-in retry semantics.
    """
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    body = (command.args or "").strip()
    if not body:
        await message.answer(
            "Usage: <code>/broadcast Some &lt;b&gt;HTML&lt;/b&gt; copy</code>",
            parse_mode="HTML",
        )
        return

    from herald.data import users as users_data

    targets = users_data.list_active_users(limit=20000)
    sent = 0
    failed = 0
    for target in targets:
        try:
            await bot.send_message(
                chat_id=target.tg_chat_id,
                text=body,
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            sent += 1
        except Exception:
            failed += 1

    log.info("admin_broadcast_done", sent=sent, failed=failed, by=message.from_user.id)
    await message.answer(
        f"📣  Broadcast complete — sent: <b>{sent}</b>, failed: <b>{failed}</b>",
        parse_mode="HTML",
    )
