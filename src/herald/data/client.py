"""Supabase client singleton."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from herald.config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached service-role Supabase client."""
    settings = get_settings()
    return create_client(
        str(settings.supabase_url),
        settings.supabase_service_role_key.get_secret_value(),
    )
