"""HTML escape helpers for Telegram parse_mode='HTML'."""

from __future__ import annotations

import html as _stdhtml

_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "a", "tg-spoiler", "blockquote"}


def escape_html(text: str | None) -> str:
    """Escape a plain string for safe inclusion in a Telegram HTML message."""
    if text is None:
        return ""
    return _stdhtml.escape(str(text), quote=False)


def truncate(text: str, limit: int, *, suffix: str = "…") -> str:
    """Truncate to `limit` characters, appending an ellipsis if shortened."""
    if not text or len(text) <= limit:
        return text or ""
    safe_limit = max(1, limit - len(suffix))
    return text[:safe_limit].rstrip() + suffix
