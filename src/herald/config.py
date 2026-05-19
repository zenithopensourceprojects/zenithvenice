"""Application settings, loaded from environment variables."""

from __future__ import annotations

from datetime import time
from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CategoryKey = Literal[
    "politics",
    "business",
    "sports",
    "crime",
    "science",
    "health",
    "tech",
    "world",
    "entertainment",
    "education",
]


CATEGORY_KEYS: tuple[CategoryKey, ...] = (
    "politics",
    "business",
    "sports",
    "crime",
    "science",
    "health",
    "tech",
    "world",
    "entertainment",
    "education",
)


class Settings(BaseSettings):
    """Strongly-typed view of environment variables, prefixed with TELEGRAM_ where relevant."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: SecretStr = Field(...)
    telegram_bot_username: str = Field(default="")

    telegram_channel_id: int = Field(default=0)
    telegram_channel_invite_url: str = Field(default="")

    telegram_topic_politics: int | None = None
    telegram_topic_business: int | None = None
    telegram_topic_sports: int | None = None
    telegram_topic_crime: int | None = None
    telegram_topic_science: int | None = None
    telegram_topic_health: int | None = None
    telegram_topic_tech: int | None = None
    telegram_topic_world: int | None = None
    telegram_topic_entertainment: int | None = None
    telegram_topic_education: int | None = None

    telegram_admin_user_ids: str = Field(default="")

    telegram_parse_mode: Literal["HTML", "MarkdownV2"] = "HTML"
    telegram_disable_notification: bool = False
    telegram_disable_link_preview: bool = False
    telegram_prefer_large_preview: bool = True
    telegram_preview_above_text: bool = False

    telegram_breaking_min_score: int = 90
    telegram_breaking_max_age_minutes: int = 30
    telegram_digest_morning_ist: time = time(8, 0)
    telegram_digest_evening_ist: time = time(20, 0)
    telegram_digest_top_n: int = 5
    telegram_fanout_max_users_per_post: int = 20000

    telegram_rate_global_per_second: float = 25.0
    telegram_rate_per_chat_per_second: float = 1.0
    telegram_rate_group_per_minute: int = 20

    telegram_poller_interval_seconds: int = 60
    telegram_realtime_reconnect_backoff_ms: int = 2000

    telegram_use_webhook: bool = False
    telegram_webhook_url: str = ""
    telegram_webhook_secret: SecretStr | None = None
    telegram_webhook_port: int = 8081

    telegram_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    supabase_url: HttpUrl = Field(...)
    supabase_service_role_key: SecretStr = Field(...)

    public_site_url: str = "https://verifiedindian.vercel.app"

    @field_validator("public_site_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator(
        "telegram_topic_politics",
        "telegram_topic_business",
        "telegram_topic_sports",
        "telegram_topic_crime",
        "telegram_topic_science",
        "telegram_topic_health",
        "telegram_topic_tech",
        "telegram_topic_world",
        "telegram_topic_entertainment",
        "telegram_topic_education",
        "telegram_webhook_secret",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        """Treat empty/whitespace-only env strings as None for optional fields."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("telegram_channel_id", mode="before")
    @classmethod
    def _empty_channel_id_to_zero(cls, v: object) -> object:
        """Treat empty TELEGRAM_CHANNEL_ID as 0 (disables channel publishing)."""
        if isinstance(v, str) and not v.strip():
            return 0
        return v

    @property
    def admin_user_ids(self) -> set[int]:
        """Parsed CSV of TELEGRAM_ADMIN_USER_IDS into a set of ints."""
        out: set[int] = set()
        for token in self.telegram_admin_user_ids.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                out.add(int(token))
            except ValueError:
                continue
        return out

    @property
    def channel_enabled(self) -> bool:
        """True when an official Telegram channel is configured for publishing."""
        return self.telegram_channel_id != 0

    def topic_id_for(self, category: str) -> int | None:
        """Return the configured forum-topic id for the given category, if any."""
        return getattr(self, f"telegram_topic_{category}", None)

    def post_web_url(self, post_id: str) -> str:
        """Canonical website URL for a post."""
        return f"{self.public_site_url}/news/{post_id}/"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached Settings singleton."""
    return Settings()
