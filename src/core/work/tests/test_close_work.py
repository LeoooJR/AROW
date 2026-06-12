from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.adb.exceptions import AdbServerException
from core.entrypoint import ModelEntrypoint
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome

pytestmark = [pytest.mark.async_jobs]


class TestCloseCoreRuntimeWork:
    def test_run_stops_server_and_returns_outcome(self) -> None:
        adb_server = MagicMock()
        adb_server.binary.path = "/mock/adb"

        outcome = CloseCoreRuntimeWork(adb_server).run()

        adb_server.stop.assert_called_once()
        assert outcome == CloseOutcome(adb_server=adb_server)

    def test_run_propagates_stop_failure(self) -> None:
        adb_server = MagicMock()
        adb_server.stop.side_effect = AdbServerException("Failed to stop adb server")

        with pytest.raises(AdbServerException, match="Failed to stop adb server"):
            CloseCoreRuntimeWork(adb_server).run()

    def test_apply_main_thread_skips_signal_without_server(self) -> None:
        model_entrypoint = ModelEntrypoint()
        emitted: list[tuple[object, object]] = []

        def fake_emit(signal: object, payload: object) -> None:
            emitted.append((signal, payload))

        model_entrypoint._signal_bus.emit = fake_emit  # type: ignore[method-assign]
        CloseCoreRuntimeWork.apply_main_thread(
            model_entrypoint, CloseOutcome(adb_server=None)
        )
        assert model_entrypoint.adb_server is None
        assert emitted == []
