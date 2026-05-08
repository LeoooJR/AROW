"""Tests for src/core/work/device_serial_work.py (shell enrichment orchestration)."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.work.device_serial_work import enrich_phones_with_adb_shell_properties


def test_enrich_phones_with_adb_shell_properties_empty_skips_adb_methods() -> None:
    """No phones implies no getters on the client (fast path)."""
    client = MagicMock()
    enrich_phones_with_adb_shell_properties(client, [])
    client.assert_not_called()
