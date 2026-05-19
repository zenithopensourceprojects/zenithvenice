"""Credibility-score visualisation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CredibilityBand:
    """Score band with a label, dot emoji, and bar emoji for the gauge."""

    label: str
    dot: str
    bar: str


HIGH = CredibilityBand(label="Highly verified", dot="🟢", bar="🟩")
MID = CredibilityBand(label="Verified", dot="🟡", bar="🟨")
LOW = CredibilityBand(label="Provisional", dot="🔴", bar="🟥")


def band_for(score: int) -> CredibilityBand:
    """Map a 0–100 score to its display band."""
    if score >= 80:
        return HIGH
    if score >= 60:
        return MID
    return LOW


def render_bar(score: int, *, segments: int = 5) -> str:
    """Return a fixed-width emoji bar showing the score."""
    score = max(0, min(100, score))
    band = band_for(score)
    filled = max(0, min(segments, round(score / 100 * segments)))
    return band.bar * filled + "⬜" * (segments - filled)


def render_line(score: int, source_count: int) -> str:
    """One-line credibility summary used in the post card header."""
    score = max(0, min(100, score))
    band = band_for(score)
    noun = "source" if source_count == 1 else "sources"
    return f"{band.dot} <b>{score}</b>/100  ·  {band.label}  ·  {source_count} {noun}"
