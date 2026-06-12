from __future__ import annotations

import pytest

from core.entrypoint import ModelEntrypoint
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome

pytestmark = [pytest.mark.async_jobs]


class TestCloseCoreRuntimeWork:
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
