from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.adb.exceptions import AdbServerException
from core.entrypoint import ModelEntrypoint
from core.signals import AdbServerStoppedPayload, CoreSignals
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

        model_entrypoint.emit_core_signal = fake_emit  # type: ignore[method-assign]
        CloseCoreRuntimeWork.apply_main_thread(
            model_entrypoint, CloseOutcome(adb_server=None)
        )
        assert model_entrypoint.adb_server is None
        assert emitted == []

    def test_apply_main_thread_clears_runtime_and_emits_signal(self) -> None:
        state = MockAdbState(seed=1, initial_devices=0)
        server = MockAdbServer(state=state)
        client = MockAdbClient(state=state)
        model_entrypoint = ModelEntrypoint()
        model_entrypoint.adb_server = server
        model_entrypoint.adb_client = client
        emitted: list[tuple[object, object]] = []

        def fake_emit(signal: object, payload: object) -> None:
            emitted.append((signal, payload))

        model_entrypoint.emit_core_signal = fake_emit  # type: ignore[method-assign]
        CloseCoreRuntimeWork.apply_main_thread(
            model_entrypoint, CloseOutcome(adb_server=server)
        )

        assert model_entrypoint.adb_server is None
        assert model_entrypoint.adb_client is None
        assert emitted == [
            (
                CoreSignals.ADB_SERVER_STOPPED,
                AdbServerStoppedPayload(adb_binary_path=str(server.binary.path)),
            )
        ]
