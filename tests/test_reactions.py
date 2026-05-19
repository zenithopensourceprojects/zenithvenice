"""Tests for the reaction emoji extractor."""

from __future__ import annotations

from types import SimpleNamespace

from herald.bot.reactions import _extract_emoji


def test_extract_emoji_handles_plain_emoji() -> None:
    items = [SimpleNamespace(emoji="👍"), SimpleNamespace(emoji="🔥")]
    assert _extract_emoji(items) == ["👍", "🔥"]


def test_extract_emoji_falls_back_to_custom_id() -> None:
    items = [SimpleNamespace(emoji=None, custom_emoji_id="123abc")]
    assert _extract_emoji(items) == ["123abc"]


def test_extract_emoji_skips_empty_entries() -> None:
    items = [
        SimpleNamespace(emoji=None, custom_emoji_id=None),
        SimpleNamespace(emoji="👀"),
    ]
    assert _extract_emoji(items) == ["👀"]


def test_extract_emoji_handles_empty_input() -> None:
    assert _extract_emoji([]) == []
