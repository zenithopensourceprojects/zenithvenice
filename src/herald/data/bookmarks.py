"""Per-user Telegram bookmarks."""

from __future__ import annotations

import contextlib

from herald.data.client import get_supabase
from herald.data.models import Post


def save(tg_user_id: int, post_id: str) -> None:
    """Insert a bookmark for the user; idempotent on the composite primary key."""
    client = get_supabase()
    with contextlib.suppress(Exception):
        client.table("telegram_bookmarks").insert(
            {"tg_user_id": tg_user_id, "post_id": post_id}
        ).execute()


def remove(tg_user_id: int, post_id: str) -> None:
    """Delete a bookmark for the user, if it exists."""
    client = get_supabase()
    client.table("telegram_bookmarks").delete().eq(
        "tg_user_id", tg_user_id
    ).eq("post_id", post_id).execute()


def is_saved(tg_user_id: int, post_id: str) -> bool:
    """Return True if the user has bookmarked the given post."""
    client = get_supabase()
    res = (
        client.table("telegram_bookmarks")
        .select("post_id")
        .eq("tg_user_id", tg_user_id)
        .eq("post_id", post_id)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def list_saved(tg_user_id: int, limit: int = 20) -> list[Post]:
    """Return the user's most recently saved posts."""
    client = get_supabase()
    res = (
        client.table("telegram_bookmarks")
        .select("post_id, saved_at, posts(*)")
        .eq("tg_user_id", tg_user_id)
        .order("saved_at", desc=True)
        .limit(limit)
        .execute()
    )
    out: list[Post] = []
    for row in res.data or []:
        post_payload = row.get("posts") if isinstance(row, dict) else None
        if isinstance(post_payload, dict):
            out.append(Post.model_validate(post_payload))
    return out
