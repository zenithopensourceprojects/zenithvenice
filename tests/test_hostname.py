"""Hostname and time-ago helper tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from herald.utils.escape import escape_html, truncate
from herald.utils.hostname import get_hostname
from herald.utils.time_ago import format_time_ago


@pytest.mark.parametrize(
    "given,expected",
    [
        ("https://www.ndtv.com/article",     "ndtv.com"),
        ("https://thehindu.com/path",        "thehindu.com"),
        ("https://WWW.IndianExpress.com/x",  "indianexpress.com"),
        ("ndtv.com/path",                    "ndtv.com"),
        ("",                                 ""),
        (None,                               ""),
    ],
)
def test_get_hostname(given: str | None, expected: str) -> None:
    assert get_hostname(given) == expected


def test_format_time_ago_buckets() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert format_time_ago(now - timedelta(seconds=10), now=now) == "just now"
    assert format_time_ago(now - timedelta(minutes=5), now=now) == "5m ago"
    assert format_time_ago(now - timedelta(hours=3), now=now) == "3h ago"
    assert format_time_ago(now - timedelta(days=2), now=now) == "2d ago"


def test_escape_html_handles_none_and_specials() -> None:
    assert escape_html(None) == ""
    assert escape_html("<script>") == "&lt;script&gt;"


def test_truncate_keeps_short_strings_unchanged() -> None:
    assert truncate("hi", 10) == "hi"
    assert truncate("a" * 50, 10).endswith("…")
    assert len(truncate("a" * 50, 10)) == 10
