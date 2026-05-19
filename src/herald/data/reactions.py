"""Storage helpers for the `telegram_reactions` table."""

from __future__ import annotations

import contextlib

from herald.data.client import get_supabase


def record_reactions(*, post_id: str, tg_user_id: int, reactions: list[str]) -> None:
    """Insert a row per emoji currently set by the user on a post.

    Idempotent on the composite primary key (post_id, tg_user_id, reaction).
    """
    if not post_id or not tg_user_id or not reactions:
        return
    client = get_supabase()
    rows = [
        {"post_id": post_id, "tg_user_id": tg_user_id, "reaction": r}
        for r in reactions
        if r
    ]
    if not rows:
        return
    with contextlib.suppress(Exception):
        client.table("telegram_reactions").upsert(rows).execute()


def clear_user_reactions(*, post_id: str, tg_user_id: int) -> None:
    """Drop every reaction the user had previously set on the post."""
    if not post_id or not tg_user_id:
        return
    client = get_supabase()
    client.table("telegram_reactions").delete().eq(
        "post_id", post_id
    ).eq("tg_user_id", tg_user_id).execute()


def lookup_post_id(*, chat_id: int, message_id: int) -> str | None:
    """Resolve a Telegram (chat, message) pair back to its source post id."""
    client = get_supabase()
    res = (
        client.table("telegram_deliveries")
        .select("post_id")
        .eq("chat_id", chat_id)
        .eq("message_id", message_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    value = rows[0].get("post_id")
    return str(value) if value else None
