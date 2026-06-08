from __future__ import annotations

import pytest

from core.models import CoreRuntimeModel
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome

pytestmark = [pytest.mark.async_jobs]


class TestCloseCoreRuntimeWork:
    def test_apply_main_thread_skips_signal_without_server(self) -> None:
        model = CoreRuntimeModel()
        emitted: list[tuple[object, object]] = []

        def fake_emit(signal: object, payload: object) -> None:
            emitted.append((signal, payload))

        model._signal_bus.emit = fake_emit
        CloseCoreRuntimeWork.apply_main_thread(model, CloseOutcome(adb_server=None))
        assert model.adb_server is None
        assert emitted == []
