"""Tests for source-root machine-readable application logging."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from logger import _json_loguru_format


def test_json_log_preserves_agent_context_and_redacts_sensitive_values(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "application.jsonl"
    stable_id = "11111111-2222-3333-4444-555555555555"
    handler_id = logger.add(
        log_path,
        format=_json_loguru_format,
        serialize=True,
        encoding="utf-8",
    )
    try:
        logger.bind(
            origin="CORE",
            association_code="pairing-secret",
            count=2,
            details={"api_key": "nested-secret", "ready": True},
        ).info("Runtime event {}", stable_id)
    finally:
        logger.remove(handler_id)

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    record = payload["record"]

    assert record["message"] == "Runtime event <redacted:uuid>"
    assert record["level"]["name"] == "INFO"
    assert record["extra"] == {
        "association_code": "<redacted>",
        "count": 2,
        "details": {"api_key": "<redacted>", "ready": True},
        "log_schema_version": 1,
        "origin": "CORE",
    }
    assert record["function"] == (
        "test_json_log_preserves_agent_context_and_redacts_sensitive_values"
    )
    assert record["process"]["id"] > 0
    assert stable_id not in payload["text"]
    assert "pairing-secret" not in log_path.read_text(encoding="utf-8")
    assert "nested-secret" not in log_path.read_text(encoding="utf-8")
