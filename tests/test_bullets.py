"""Unit tests for the summary-to-bullets splitter."""

from __future__ import annotations

from herald.render.bullets import summary_to_bullets


def test_empty_returns_no_bullets() -> None:
    assert summary_to_bullets("") == []
    assert summary_to_bullets(None) == []


def test_three_sentence_summary_yields_three_bullets() -> None:
    summary = (
        "Six new highways totalling 1,800 km were approved by cabinet today. "
        "Major rail electrification across all eight NE states is targeted by 2027. "
        "Airports are planned for Itanagar, Kohima, and Shillong."
    )
    bullets = summary_to_bullets(summary, n=3)
    assert len(bullets) == 3
    assert bullets[0].startswith("Six new highways")
    assert all(not b.endswith(".") for b in bullets)


def test_caps_bullet_count_at_n() -> None:
    summary = "One. Two. Three. Four. Five."
    assert summary_to_bullets(summary, n=2) == ["One", "Two"]


def test_handles_devanagari() -> None:
    summary = "मोदी सरकार ने घोषणा की है। बजट को मंजूरी मिली।"
    bullets = summary_to_bullets(summary, n=3)
    assert len(bullets) == 2
    assert "मोदी" in bullets[0]
