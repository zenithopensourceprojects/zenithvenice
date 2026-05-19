"""Cross-version payload extraction for the supabase realtime callback."""

from __future__ import annotations

from types import SimpleNamespace

from herald.publisher.realtime import _extract_row

_ROW = {"id": "abc", "status": "published", "headline": "h"}


def test_extract_legacy_dict_with_record_key() -> None:
    assert _extract_row({"record": _ROW}) == _ROW


def test_extract_legacy_dict_with_new_key() -> None:
    assert _extract_row({"new": _ROW}) == _ROW


def test_extract_supabase_v2_object_with_data_record() -> None:
    payload = SimpleNamespace(data={"record": _ROW, "schema": "public"})
    assert _extract_row(payload) == _ROW


def test_extract_supabase_v2_object_with_record_attr() -> None:
    payload = SimpleNamespace(record=_ROW)
    assert _extract_row(payload) == _ROW


def test_extract_returns_none_for_garbage() -> None:
    assert _extract_row(None) is None
    assert _extract_row(42) is None
    assert _extract_row({"unrelated": 1}) is None
    assert _extract_row(SimpleNamespace(other="x")) is None


def test_extract_handles_nested_dict_data_wrapper() -> None:
    payload = {"data": {"record": _ROW}}
    assert _extract_row(payload) == _ROW
