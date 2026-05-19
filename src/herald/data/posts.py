"""Read-only access to the `posts` table."""

from __future__ import annotations

from datetime import UTC

from herald.data.client import get_supabase
from herald.data.models import Post


def fetch_pending_channel_deliveries(limit: int = 50) -> list[Post]:
    """Return verified posts that have not yet been broadcast to the channel."""
    client = get_supabase()
    res = (
        client.table("posts_pending_channel_delivery")
        .select("*")
        .order("published_at", desc=False)
        .limit(limit)
        .execute()
    )
    return [Post.model_validate(row) for row in (res.data or [])]


def fetch_post_by_id(post_id: str) -> Post | None:
    """Return a single post by id, or None if not found."""
    client = get_supabase()
    res = (
        client.table("posts")
        .select("*")
        .eq("id", post_id)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return Post.model_validate(rows[0]) if rows else None


def fetch_latest(limit: int = 5, *, category: str | None = None) -> list[Post]:
    """Return the freshest published posts, optionally filtered by category."""
    client = get_supabase()
    query = (
        client.table("posts")
        .select("*")
        .eq("status", "published")
        .order("published_at", desc=True)
        .limit(limit)
    )
    if category:
        query = query.eq("category", category)
    res = query.execute()
    return [Post.model_validate(row) for row in (res.data or [])]


def fetch_top_recent(*, hours: int = 12, limit: int = 5) -> list[Post]:
    """Return the most credible posts published in the last `hours` hours."""
    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    client = get_supabase()
    res = (
        client.table("posts")
        .select("*")
        .eq("status", "published")
        .gte("published_at", since)
        .order("credibility_score", desc=True)
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [Post.model_validate(row) for row in (res.data or [])]


def search(query: str, limit: int = 10) -> list[Post]:
    """Full-text-style ILIKE search against headline + summary."""
    if not query.strip():
        return []
    client = get_supabase()
    needle = f"%{query.strip()}%"
    res = (
        client.table("posts")
        .select("*")
        .eq("status", "published")
        .or_(f"headline.ilike.{needle},summary.ilike.{needle}")
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [Post.model_validate(row) for row in (res.data or [])]
