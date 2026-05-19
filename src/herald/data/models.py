"""Pydantic models mirroring rows in the public Supabase tables."""

from __future__ import annotations

from datetime import datetime, time  # noqa: TC003
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PostStatus = Literal["published", "corrected", "retracted"]
DeliveryKind = Literal["channel", "user_alert", "digest", "external_chat"]
NotifMode = Literal["instant", "digest", "breaking_only", "silent"]
ChatType = Literal["group", "supergroup", "channel"]


class Source(BaseModel):
    """A single citation attached to a post."""

    title: str
    url: str
    source_name: str | None = None
    published_at: datetime | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _coerce_title(cls, v: Any) -> str:
        return str(v or "").strip()


class Post(BaseModel):
    """A verified, published news post."""

    id: str
    headline: str
    summary: str
    category: str
    credibility_score: int
    credibility_reason: str = ""
    source_count: int = 1
    sources: list[Source] = Field(default_factory=list)
    fact_check_flags: list[str] = Field(default_factory=list)
    status: PostStatus = "published"
    correction_note: str | None = None
    published_at: datetime
    updated_at: datetime | None = None

    @field_validator("sources", mode="before")
    @classmethod
    def _normalise_sources(cls, v: Any) -> Any:
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("fact_check_flags", mode="before")
    @classmethod
    def _normalise_flags(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


class TelegramUser(BaseModel):
    """A Telegram user that has interacted with the Herald bot."""

    tg_user_id: int
    tg_chat_id: int
    username: str | None = None
    first_name: str | None = None
    language_code: str = "en"
    timezone: str = "Asia/Kolkata"
    subscribed_categories: list[str] = Field(default_factory=list)
    muted_categories: list[str] = Field(default_factory=list)
    notif_mode: NotifMode = "instant"
    quiet_start: time = time(23, 0)
    quiet_end: time = time(7, 0)
    is_blocked: bool = False
    created_at: datetime | None = None
    last_active_at: datetime | None = None


class Delivery(BaseModel):
    """A single Telegram message that delivered a post."""

    id: int | None = None
    post_id: str
    chat_id: int
    topic_id: int | None = None
    message_id: int
    kind: DeliveryKind
    sent_at: datetime | None = None


class SubscribedChat(BaseModel):
    """A group, supergroup, or channel that has added the Herald bot."""

    id: str | None = None
    tg_chat_id: int
    chat_type: ChatType
    title: str | None = None
    username: str | None = None
    added_by_user_id: int | None = None
    muted_categories: list[str] = Field(default_factory=list)
    min_score: int = 0
    is_active: bool = True
    added_at: datetime | None = None
    removed_at: datetime | None = None
    last_post_at: datetime | None = None
    updated_at: datetime | None = None


class Bookmark(BaseModel):
    """A saved post belonging to a Telegram user."""

    tg_user_id: int
    post_id: str
    saved_at: datetime | None = None
