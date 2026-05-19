"""Human-friendly relative time formatting, IST-aware."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def format_time_ago(when: datetime, *, now: datetime | None = None) -> str:
    """Format a datetime as a compact relative phrase like '2h ago' or 'just now'.

    Falls back to a localised IST date for items older than seven days.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    delta_seconds = (current - when).total_seconds()

    if delta_seconds < 45:
        return "just now"
    if delta_seconds < 60 * 60:
        minutes = max(1, int(delta_seconds // 60))
        return f"{minutes}m ago"
    if delta_seconds < 60 * 60 * 24:
        hours = max(1, int(delta_seconds // 3600))
        return f"{hours}h ago"
    if delta_seconds < 60 * 60 * 24 * 7:
        days = max(1, int(delta_seconds // 86400))
        return f"{days}d ago"
    local = when.astimezone(IST)
    return f"{local.day} {local.strftime('%b')}"


def format_ist(when: datetime) -> str:
    """Render a datetime in IST as 'D Mon, HH:MM IST'."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    local = when.astimezone(IST)
    return local.strftime("%d %b, %H:%M IST")
