"""Display-friendly hostname extraction, mirroring the frontend helper."""

from __future__ import annotations

from urllib.parse import urlparse


def get_hostname(url: str | None) -> str:
    """Return the bare hostname for a URL with the leading 'www.' stripped.

    Returns an empty string for falsy or malformed URLs.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host
