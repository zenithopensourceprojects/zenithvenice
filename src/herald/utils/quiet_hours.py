"""Quiet-hours window evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime, time


def is_within_window(*, now: datetime, start: time, end: time) -> bool:
    """Return True if `now`'s time falls inside the [start, end) window.

    Handles wrap-around windows that cross midnight (e.g. 23:00 → 07:00)
    correctly. A degenerate window where start == end is treated as
    "never quiet".
    """
    if start == end:
        return False
    current = now.time()
    if start < end:
        return start <= current < end
    return current >= start or current < end
