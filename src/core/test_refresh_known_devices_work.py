"""Tests for src/core/work/refresh_known_devices_work.py (shell enrichment orchestration)."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.work.refresh_known_devices_work import enrich_phones_with_adb_shell_properties


def test_enrich_phones_with_adb_shell_properties_empty_skips_adb_methods() -> None:
    """No phones implies no getters on the client (fast path)."""
    client = MagicMock()
    enrich_phones_with_adb_shell_properties(client, [])
    client.assert_not_called()
