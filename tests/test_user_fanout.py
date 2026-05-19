"""Pure-logic tests for the per-user fanout eligibility filter."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from herald.data.models import Post, TelegramUser
from herald.publisher.user_fanout import is_eligible
from herald.utils.time_ago import IST


def _user(**overrides) -> TelegramUser:
    """Build a minimal TelegramUser fixture."""
    defaults = dict(
        tg_user_id=1,
        tg_chat_id=1,
        notif_mode="instant",
        muted_categories=[],
        quiet_start=time(0, 0),
        quiet_end=time(0, 0),
        is_blocked=False,
    )
    defaults.update(overrides)
    return TelegramUser(**defaults)


def _post(*, score: int = 95, age_minutes: int = 5, category: str = "politics") -> Post:
    """Build a minimal Post fixture."""
    return Post(
        id="00000000-0000-0000-0000-000000000000",
        headline="H",
        summary="Body.",
        category=category,
        credibility_score=score,
        source_count=1,
        sources=[],
        published_at=datetime.now(IST) - timedelta(minutes=age_minutes),
    )


_NOW = datetime(2026, 5, 18, 12, 0, tzinfo=IST)


def test_blocked_user_is_ineligible() -> None:
    assert is_eligible(_user(is_blocked=True), _post(), now_ist=_NOW) is False


def test_silent_user_is_ineligible() -> None:
    assert is_eligible(_user(notif_mode="silent"), _post(), now_ist=_NOW) is False


def test_digest_user_is_ineligible_for_instant_fanout() -> None:
    assert is_eligible(_user(notif_mode="digest"), _post(), now_ist=_NOW) is False


def test_breaking_only_skips_non_breaking_post() -> None:
    user = _user(notif_mode="breaking_only")
    weak_post = _post(score=70)
    assert is_eligible(user, weak_post, now_ist=_NOW) is False


def test_breaking_only_accepts_breaking_post() -> None:
    user = _user(notif_mode="breaking_only")
    breaking = _post(score=95, age_minutes=5)
    assert is_eligible(user, breaking, now_ist=_NOW) is True


def test_muted_category_is_ineligible() -> None:
    user = _user(muted_categories=["politics"])
    assert is_eligible(user, _post(category="politics"), now_ist=_NOW) is False


def test_quiet_hours_block_delivery() -> None:
    user = _user(quiet_start=time(23, 0), quiet_end=time(7, 0))
    night = datetime(2026, 5, 18, 2, 30, tzinfo=IST)
    assert is_eligible(user, _post(), now_ist=night) is False


def test_default_instant_user_with_clean_post_is_eligible() -> None:
    assert is_eligible(_user(), _post(), now_ist=_NOW) is True
