"""Render-layer integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from herald.data.models import Post, Source
from herald.render.card import (
    is_breaking,
    render_credibility_badge,
    render_full_sources_card,
    render_list_item,
    render_post_card,
)


def _make_post(
    *,
    score: int = 95,
    age_minutes: int = 120,
    sources: int = 4,
) -> Post:
    """Build a representative Post fixture for render tests."""
    published = datetime.now(UTC) - timedelta(minutes=age_minutes)
    src_list = [
        Source(
            title=f"Source headline {i}",
            url=f"https://www.ndtv.com/article-{i}" if i == 0 else f"https://thehindu.com/article-{i}",
            source_name=("NDTV" if i == 0 else "The Hindu"),
            published_at=published,
        )
        for i in range(sources)
    ]
    return Post(
        id="11111111-1111-1111-1111-111111111111",
        headline="Modi government announces ₹2 lakh crore infrastructure push for the Northeast",
        summary=(
            "Six new highways totalling 1,800 km were approved by cabinet today. "
            "Major rail electrification across all eight NE states is targeted by 2027. "
            "Airports are planned for Itanagar, Kohima, and Shillong."
        ),
        category="politics",
        credibility_score=score,
        credibility_reason="Verified across four publications.",
        source_count=sources,
        sources=src_list,
        published_at=published,
    )


def test_card_contains_brand_and_category() -> None:
    card = render_post_card(_make_post())
    assert "INDIA VERIFIED" in card.text
    assert "Politics" in card.text


def test_card_renders_credibility_dot() -> None:
    high = render_post_card(_make_post(score=92))
    mid = render_post_card(_make_post(score=70))
    low = render_post_card(_make_post(score=40))
    assert "🟢" in high.text
    assert "🟡" in mid.text
    assert "🔴" in low.text


def test_card_links_first_source_for_preview() -> None:
    card = render_post_card(_make_post())
    assert card.preview_url is not None
    assert card.preview_url.startswith("https://")


def test_card_lists_top_three_sources_with_overflow() -> None:
    card = render_post_card(_make_post(sources=5))
    assert "+2 more" in card.text


def test_breaking_tag_when_fresh_and_high_score() -> None:
    fresh = _make_post(score=95, age_minutes=10)
    stale = _make_post(score=95, age_minutes=240)
    assert is_breaking(fresh) is True
    assert is_breaking(stale) is False


@pytest.mark.parametrize("score,expected", [(95, "🟢"), (75, "🟡"), (40, "🔴")])
def test_credibility_badge_band(score: int, expected: str) -> None:
    badge = render_credibility_badge(_make_post(score=score))
    assert expected in badge


def test_list_item_includes_index() -> None:
    rendered = render_list_item(_make_post(), index=1)
    assert rendered.startswith("1. ")


def test_full_sources_card_lists_every_source() -> None:
    body = render_full_sources_card(_make_post(sources=4))
    assert "Sources" in body
    assert body.count("href=") == 4
