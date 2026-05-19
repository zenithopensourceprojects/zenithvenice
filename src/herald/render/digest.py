"""Top-N digest renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from herald.render.category import theme_for
from herald.render.credibility import band_for
from herald.utils.escape import escape_html, truncate

if TYPE_CHECKING:
    from datetime import datetime

    from herald.data.models import Post

DigestSlot = Literal["morning", "evening"]


_GREETINGS: dict[DigestSlot, tuple[str, str]] = {
    "morning": ("☀️", "Morning briefing"),
    "evening": ("🌆", "Evening briefing"),
}


def render_digest(
    posts: list[Post],
    *,
    slot: DigestSlot,
    when_ist: datetime,
) -> str:
    """Render a single message containing the top stories of the period."""
    icon, title = _GREETINGS[slot]
    header = (
        f"{icon}  <b>{title}</b>  ·  <i>India Verified</i>\n"
        f"<i>{when_ist.strftime('%a, %d %b · %H:%M IST')}</i>"
    )

    if not posts:
        return (
            f"{header}\n\n<i>No verified stories in the last 12 hours.</i>"
        )

    rows: list[str] = []
    for index, post in enumerate(posts, start=1):
        theme = theme_for(post.category)
        band = band_for(post.credibility_score)
        headline = escape_html(truncate(post.headline.strip(), 160))
        rows.append(
            f"<b>{index}.</b> {theme.emoji} <b>{headline}</b>\n"
            f"   {band.dot} {post.credibility_score}/100  ·  "
            f"<i>{escape_html(theme.label)}</i>  ·  "
            f"{post.source_count} sources"
        )

    body = "\n\n".join(rows)
    footer = (
        "<i>Tap any story to read on Telegram. "
        "Use /latest for more, /settings to change cadence.</i>"
    )
    return f"{header}\n\n{body}\n\n{footer}"
