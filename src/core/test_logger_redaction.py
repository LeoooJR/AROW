"""Tests for loguru extras redaction (UUID and sensitive keys)."""

from __future__ import annotations

import pytest

from logger import _serialize_extras, maybe_redact_extra_value, redact_stable_identifier

pytestmark = [pytest.mark.devices]


def test_stable_key_extra_fully_redacted() -> None:
    assert (
        maybe_redact_extra_value("stable_key", "pc:v1:install:anything") == "<redacted>"
    )


def test_association_code_extra_fully_redacted() -> None:
    out = maybe_redact_extra_value("association_code", "secret-code-123")
    assert out == "<redacted>"
    assert "secret-code" not in out


def test_safe_key_keeps_readable_repr() -> None:
    assert "hello" in maybe_redact_extra_value("message", "hello")


def test_maybe_redact_uuid_in_value_by_heuristic() -> None:
    u = "11111111-2222-3333-4444-555555555555"
    out = maybe_redact_extra_value("misc", u)
    assert u not in out
    assert "redacted" in out.lower()


def test_redact_stable_identifier_substitutes_uuid() -> None:
    txt = "ctx aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee end"
    out = redact_stable_identifier(txt)
    assert "aaaa" not in out
    assert "<redacted:uuid>" in out


def test_serialize_extras_uses_maybe_redact() -> None:
    blob = _serialize_extras(
        {"extra": {"hardware_serial": "SN123", "count": 2}},
    )
    assert "SN123" not in blob
    assert "<redacted>" in blob
    assert "count=2" in blob
