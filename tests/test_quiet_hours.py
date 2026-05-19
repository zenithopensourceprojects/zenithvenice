"""Quiet-hours window evaluation tests."""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest

from herald.utils.quiet_hours import is_within_window


def _at(hour: int, minute: int = 0) -> datetime:
    """Build a UTC datetime at the given clock time on a fixed day."""
    return datetime(2026, 5, 18, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    "now_h,start,end,expected",
    [
        (23, time(22, 0), time(7, 0), True),
        (3,  time(22, 0), time(7, 0), True),
        (7,  time(22, 0), time(7, 0), False),
        (8,  time(22, 0), time(7, 0), False),
        (21, time(22, 0), time(7, 0), False),
        (12, time(9, 0),  time(17, 0), True),
        (8,  time(9, 0),  time(17, 0), False),
        (17, time(9, 0),  time(17, 0), False),
    ],
)
def test_window_membership(now_h, start, end, expected) -> None:
    assert is_within_window(now=_at(now_h), start=start, end=end) is expected


def test_zero_width_window_is_never_quiet() -> None:
    assert is_within_window(now=_at(2), start=time(0, 0), end=time(0, 0)) is False
