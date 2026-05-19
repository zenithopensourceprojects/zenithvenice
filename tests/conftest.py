"""Test bootstrap: provide minimal env vars so `get_settings()` can load."""

from __future__ import annotations

import os

import pytest

_REQUIRED_ENV = {
    "TELEGRAM_BOT_TOKEN": "0:TEST",
    "TELEGRAM_CHANNEL_ID": "-1001234567890",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-test-key",
}


@pytest.fixture(autouse=True, scope="session")
def _seed_env() -> None:
    """Ensure pydantic-settings has the variables it requires."""
    for key, value in _REQUIRED_ENV.items():
        os.environ.setdefault(key, value)
