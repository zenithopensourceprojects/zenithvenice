"""Convert a long summary string into a small set of bullet points."""

from __future__ import annotations

import re

_SENT_SPLIT = re.compile(r"(?<=[.!?\u0964\u0965])\s+(?=[A-Z\u0900-\u097F])")
_TRIM_PUNCT = re.compile(r"[\s\.\u2026\u0964\u0965]+$")


def summary_to_bullets(summary: str | None, n: int = 3) -> list[str]:
    """Split a free-text summary into up to `n` clean bullet sentences."""
    if not summary:
        return []
    text = summary.strip()
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    bullets: list[str] = []
    for part in parts:
        cleaned = _TRIM_PUNCT.sub("", part).strip()
        if cleaned:
            bullets.append(cleaned)
        if len(bullets) >= n:
            break
    return bullets
