"""Idempotent delivery bookkeeping for the `telegram_deliveries` table."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from herald.data.client import get_supabase

if TYPE_CHECKING:
    from herald.data.models import DeliveryKind


def was_sent(post_id: str, chat_id: int, kind: DeliveryKind) -> bool:
    """Return True if a delivery row already exists for the (post, chat, kind) triple."""
    client = get_supabase()
    res = (
        client.table("telegram_deliveries")
        .select("id")
        .eq("post_id", post_id)
        .eq("chat_id", chat_id)
        .eq("kind", kind)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def record_sent(
    *,
    post_id: str,
    chat_id: int,
    message_id: int,
    kind: DeliveryKind,
    topic_id: int | None = None,
) -> None:
    """Insert a delivery row, ignoring violations of the unique constraint."""
    client = get_supabase()
    payload = {
        "post_id": post_id,
        "chat_id": chat_id,
        "topic_id": topic_id,
        "message_id": message_id,
        "kind": kind,
    }
    with contextlib.suppress(Exception):
        client.table("telegram_deliveries").insert(payload).execute()
