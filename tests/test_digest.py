"""Render-layer tests for the morning + evening digest."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from herald.data.models import Post
from herald.render.digest import render_digest
from herald.utils.time_ago import IST


def _post(*, score: int, headline: str, age_hours: int = 2) -> Post:
    """Build a minimal Post fixture for digest tests."""
    return Post(
        id="00000000-0000-0000-0000-000000000000",
        headline=headline,
        summary="Body that is not used by the digest renderer.",
        category="politics",
        credibility_score=score,
        source_count=3,
        sources=[],
        published_at=datetime.now(IST) - timedelta(hours=age_hours),
    )


def test_digest_renders_header_and_each_post() -> None:
    when = datetime(2026, 5, 18, 8, 0, tzinfo=IST)
    items = [
        _post(score=95, headline="Story one"),
        _post(score=88, headline="Story two"),
        _post(score=80, headline="Story three"),
    ]
    body = render_digest(items, slot="morning", when_ist=when)
    assert "Morning briefing" in body
    assert "Story one" in body
    assert "Story two" in body
    assert "Story three" in body
    assert body.count("\n\n") >= 3


def test_digest_handles_empty() -> None:
    when = datetime.now(IST)
    body = render_digest([], slot="evening", when_ist=when)
    assert "Evening briefing" in body
    assert "No verified stories" in body


@pytest.mark.parametrize("slot,emoji", [("morning", "☀️"), ("evening", "🌆")])
def test_digest_uses_correct_icon(slot, emoji) -> None:
    when = datetime.now(IST)
    body = render_digest([], slot=slot, when_ist=when)
    assert emoji in body
