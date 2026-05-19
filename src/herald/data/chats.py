"""Subscribed-chat upsert and lookup queries.

A *subscribed chat* is any group, supergroup, or channel that has added the
Herald bot. Membership is driven entirely by Telegram's `my_chat_member`
update — see `herald.bot.chat_membership`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from herald.data.client import get_supabase
from herald.data.models import ChatType, SubscribedChat


def register_chat(
    *,
    tg_chat_id: int,
    chat_type: ChatType,
    title: str | None,
    username: str | None,
    added_by_user_id: int | None,
) -> SubscribedChat:
    """Create or re-activate a subscribed-chat row when the bot joins."""
    client = get_supabase()
    payload: dict[str, object] = {
        "tg_chat_id": tg_chat_id,
        "chat_type": chat_type,
        "title": title,
        "username": username,
        "added_by_user_id": added_by_user_id,
        "is_active": True,
        "removed_at": None,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    res = (
        client.table("telegram_subscribed_chats")
        .upsert(payload, on_conflict="tg_chat_id")
        .execute()
    )
    rows = res.data or []
    return SubscribedChat.model_validate(rows[0]) if rows else SubscribedChat(**payload)


def deactivate_chat(tg_chat_id: int) -> None:
    """Mark a chat as inactive when the bot is kicked or leaves."""
    client = get_supabase()
    now = datetime.now(UTC).isoformat()
    client.table("telegram_subscribed_chats").update(
        {"is_active": False, "removed_at": now, "updated_at": now}
    ).eq("tg_chat_id", tg_chat_id).execute()


def get_chat(tg_chat_id: int) -> SubscribedChat | None:
    """Return a subscribed-chat row by chat id, or None if unseen."""
    client = get_supabase()
    res = (
        client.table("telegram_subscribed_chats")
        .select("*")
        .eq("tg_chat_id", tg_chat_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return SubscribedChat.model_validate(rows[0]) if rows else None


def list_active_chats(*, limit: int = 5000) -> list[SubscribedChat]:
    """Return all active subscribed chats — used by ChatFanout."""
    client = get_supabase()
    res = (
        client.table("telegram_subscribed_chats")
        .select("*")
        .eq("is_active", True)
        .order("added_at", desc=False)
        .limit(limit)
        .execute()
    )
    return [SubscribedChat.model_validate(row) for row in (res.data or [])]


def touch_last_post(tg_chat_id: int) -> None:
    """Update the chat's `last_post_at` after a successful delivery."""
    client = get_supabase()
    now = datetime.now(UTC).isoformat()
    client.table("telegram_subscribed_chats").update(
        {"last_post_at": now, "updated_at": now}
    ).eq("tg_chat_id", tg_chat_id).execute()
