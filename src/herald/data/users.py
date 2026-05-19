"""Telegram-user upsert and preference queries."""

from __future__ import annotations

from datetime import UTC, datetime

from herald.data.client import get_supabase
from herald.data.models import TelegramUser


def upsert_user(
    *,
    tg_user_id: int,
    tg_chat_id: int,
    username: str | None,
    first_name: str | None,
    language_code: str | None,
) -> TelegramUser:
    """Create the user row on first contact; refresh `last_active_at` thereafter."""
    client = get_supabase()
    payload: dict[str, object] = {
        "tg_user_id": tg_user_id,
        "tg_chat_id": tg_chat_id,
        "username": username,
        "first_name": first_name,
        "language_code": (language_code or "en")[:8],
        "last_active_at": datetime.now(UTC).isoformat(),
    }
    res = (
        client.table("telegram_users")
        .upsert(payload, on_conflict="tg_user_id")
        .execute()
    )
    rows = res.data or []
    return TelegramUser.model_validate(rows[0]) if rows else TelegramUser(**payload)


def get_user(tg_user_id: int) -> TelegramUser | None:
    """Return a user row by Telegram user id, or None if unseen."""
    client = get_supabase()
    res = (
        client.table("telegram_users")
        .select("*")
        .eq("tg_user_id", tg_user_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return TelegramUser.model_validate(rows[0]) if rows else None


def mark_blocked(tg_user_id: int) -> None:
    """Flag a user as having blocked the bot so we stop targeting them."""
    client = get_supabase()
    client.table("telegram_users").update({"is_blocked": True}).eq(
        "tg_user_id", tg_user_id
    ).execute()


def list_active_users(*, mode: str | None = None, limit: int = 5000) -> list[TelegramUser]:
    """Return non-blocked users, optionally filtered by notif_mode."""
    client = get_supabase()
    query = (
        client.table("telegram_users")
        .select("*")
        .eq("is_blocked", False)
        .order("last_active_at", desc=True)
        .limit(limit)
    )
    if mode:
        query = query.eq("notif_mode", mode)
    res = query.execute()
    return [TelegramUser.model_validate(row) for row in (res.data or [])]


def set_notif_mode(tg_user_id: int, mode: str) -> None:
    """Update a user's notification mode (instant / digest / breaking_only / silent)."""
    client = get_supabase()
    client.table("telegram_users").update({"notif_mode": mode}).eq(
        "tg_user_id", tg_user_id
    ).execute()


def toggle_muted_category(tg_user_id: int, category: str) -> list[str]:
    """Toggle membership of `category` in the user's `muted_categories` array.

    Returns the new list of muted categories.
    """
    user = get_user(tg_user_id)
    if user is None:
        return []
    muted = list(user.muted_categories)
    if category in muted:
        muted.remove(category)
    else:
        muted.append(category)
    client = get_supabase()
    client.table("telegram_users").update({"muted_categories": muted}).eq(
        "tg_user_id", tg_user_id
    ).execute()
    return muted


def set_quiet_hours(tg_user_id: int, start: str, end: str) -> None:
    """Update the user's quiet-hours window (HH:MM strings)."""
    client = get_supabase()
    client.table("telegram_users").update(
        {"quiet_start": start, "quiet_end": end}
    ).eq("tg_user_id", tg_user_id).execute()
