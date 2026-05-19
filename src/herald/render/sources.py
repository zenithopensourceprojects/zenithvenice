"""Source-list rendering and selection helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from herald.utils.escape import escape_html, truncate
from herald.utils.hostname import get_hostname

if TYPE_CHECKING:
    from herald.data.models import Source

_PUBLISHER_OVERRIDES: dict[str, str] = {
    "ndtv.com":           "NDTV",
    "thehindu.com":       "The Hindu",
    "indianexpress.com":  "Indian Express",
    "hindustantimes.com": "Hindustan Times",
    "timesofindia.indiatimes.com": "Times of India",
    "thewire.in":         "The Wire",
    "scroll.in":          "Scroll",
    "theprint.in":        "ThePrint",
    "livemint.com":       "Mint",
    "business-standard.com": "Business Standard",
    "deccanherald.com":   "Deccan Herald",
    "news18.com":         "News18",
    "indiatoday.in":      "India Today",
    "moneycontrol.com":   "Moneycontrol",
    "reuters.com":        "Reuters",
    "bbc.com":            "BBC",
    "bbc.co.uk":          "BBC",
    "aljazeera.com":      "Al Jazeera",
}


def display_name(source: Source) -> str:
    """Best-effort publisher display name for a source."""
    host = get_hostname(source.url)
    if host in _PUBLISHER_OVERRIDES:
        return _PUBLISHER_OVERRIDES[host]
    if source.source_name:
        return source.source_name.strip()
    if source.title:
        return truncate(source.title.strip(), 32)
    return host or "Source"


def primary_source(sources: list[Source]) -> Source | None:
    """Return the first source whose URL is non-empty (used for link preview)."""
    for s in sources:
        if s.url:
            return s
    return None


def render_source_list(sources: list[Source], *, top: int = 3) -> str:
    """Render the inline source list shown directly in the message body."""
    if not sources:
        return ""
    lines = ["<b>▸ Sources</b>"]
    visible = sources[:top]
    for src in visible:
        if not src.url:
            continue
        name = escape_html(display_name(src))
        host = get_hostname(src.url)
        url = escape_html(src.url)
        host_label = f"  ·  <i>{escape_html(host)}</i>" if host else ""
        lines.append(f"•  <a href=\"{url}\">{name}</a>{host_label}")
    extra = max(0, len(sources) - len(visible))
    if extra:
        lines.append(f"•  <i>+{extra} more</i>")
    return "\n".join(lines)


def render_source_list_full(sources: list[Source]) -> str:
    """Render every source on its own line for the 'All sources' callback."""
    if not sources:
        return "<i>No sources attached.</i>"
    lines: list[str] = []
    for index, src in enumerate(sources, start=1):
        if not src.url:
            continue
        name = escape_html(display_name(src))
        host = escape_html(get_hostname(src.url))
        url = escape_html(src.url)
        title = escape_html(truncate(src.title or "", 90))
        head = f"<b>{index}. <a href=\"{url}\">{name}</a></b>  ·  <i>{host}</i>"
        body = f"\n   {title}" if title and title.lower() != name.lower() else ""
        lines.append(head + body)
    return "\n\n".join(lines) if lines else "<i>No sources attached.</i>"
