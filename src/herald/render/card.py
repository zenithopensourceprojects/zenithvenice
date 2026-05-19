"""Top-level news-card renderer: one Post → text + preview URL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from herald.config import get_settings
from herald.render.bullets import summary_to_bullets
from herald.render.category import theme_for
from herald.render.credibility import band_for, render_bar, render_line
from herald.render.sources import (
    primary_source,
    render_source_list,
    render_source_list_full,
)
from herald.utils.escape import escape_html, truncate
from herald.utils.time_ago import format_time_ago

if TYPE_CHECKING:
    from herald.data.models import Post

_BREAKING_AGE_SECONDS = 30 * 60
_HEADLINE_LIMIT = 220
_BULLET_LIMIT = 180


@dataclass(frozen=True)
class RenderedCard:
    """Output of `render_post_card`: HTML text plus the URL Telegram should preview."""

    text: str
    preview_url: str | None


def is_breaking(post: Post) -> bool:
    """Return True for very fresh, very-credible posts (the 'Breaking' tag)."""
    if post.credibility_score < get_settings().telegram_breaking_min_score:
        return False
    age = (datetime.now(UTC) - post.published_at).total_seconds()
    return age <= _BREAKING_AGE_SECONDS


def render_post_card(post: Post) -> RenderedCard:
    """Return the polished HTML body for a single verified post."""
    theme = theme_for(post.category)
    headline = escape_html(truncate(post.headline.strip(), _HEADLINE_LIMIT))
    breaking = is_breaking(post)

    # Top strip: brand  ·  category  ·  freshness. Fits on one line on mobile.
    age_label = format_time_ago(post.published_at)
    freshness = f"🔴 LIVE · {age_label}" if breaking else f"⏱ {age_label}"
    header = (
        f"🇮🇳  <b>INDIA VERIFIED</b>  ·  "
        f"{theme.emoji} <i>{escape_html(theme.label)}</i>  ·  "
        f"<i>{freshness}</i>"
    )

    # Credibility row: score + bar + verdict + source count.
    cred_line = (
        f"{render_line(post.credibility_score, post.source_count)}\n"
        f"{render_bar(post.credibility_score, segments=10)}"
    )

    headline_block = (
        f"<b>🔴 BREAKING</b>\n<b>{headline}</b>" if breaking else f"<b>{headline}</b>"
    )

    bullets_raw = summary_to_bullets(post.summary, n=3)
    bullets_block = (
        "\n".join(f"▸  {escape_html(truncate(b, _BULLET_LIMIT))}" for b in bullets_raw)
        if bullets_raw
        else ""
    )

    source_block = render_source_list(post.sources, top=3)

    # Footer reserved for verification / status flags only — freshness moved up top.
    footer_parts: list[str] = []
    if post.fact_check_flags:
        n = len(post.fact_check_flags)
        footer_parts.append(f"🛡 {n} fact-check flag" + ("s" if n != 1 else ""))
    elif post.credibility_score >= 80:
        footer_parts.append("🛡 Fact-check passed")
    if post.status == "corrected":
        footer_parts.append("✏️ Corrected")
    if post.status == "retracted":
        footer_parts.append("⚠️ Retracted")

    sections: list[str] = [
        header,
        cred_line,
        headline_block,
    ]
    if bullets_block:
        sections.append(bullets_block)
    if source_block:
        sections.append(source_block)
    if footer_parts:
        sections.append("  ·  ".join(footer_parts))

    text = "\n\n".join(sections)
    preview = primary_source(post.sources)

    return RenderedCard(text=text, preview_url=preview.url if preview else None)


def render_credibility_badge(post: Post) -> str:
    """Compact credibility badge used in list views."""
    band = band_for(post.credibility_score)
    return f"{band.dot} {post.credibility_score}/100"


def render_list_item(post: Post, *, index: int | None = None) -> str:
    """Render a one-line list item for /latest, /search, and /saved."""
    theme = theme_for(post.category)
    headline = escape_html(truncate(post.headline.strip(), 140))
    badge = render_credibility_badge(post)
    age = format_time_ago(post.published_at)
    prefix = f"{index}. " if index is not None else ""
    return (
        f"{prefix}{theme.emoji} <b>{headline}</b>\n"
        f"   {badge}  ·  <i>{escape_html(theme.label)}</i>  ·  {age}"
    )


def render_full_sources_card(post: Post) -> str:
    """Render the body shown when the user taps the 'All sources' button."""
    theme = theme_for(post.category)
    head = (
        f"📚 <b>Sources</b>  ·  {theme.emoji} <i>{escape_html(theme.label)}</i>\n\n"
        f"<b>{escape_html(truncate(post.headline.strip(), 200))}</b>"
    )
    body = render_source_list_full(post.sources)
    return f"{head}\n\n{body}"
