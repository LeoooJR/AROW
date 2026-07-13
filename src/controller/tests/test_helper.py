from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import controller.helper as helper_mod


class _FakeModelEntrypoint:
    pass


class _FakeMainWindow:
    pass


@dataclass
class _Controller:
    model_entrypoint: Any | None = None
    view: Any | None = None
    called: int = 0


@dataclass
class _SubControllerOwner:
    _subcontroller: _Controller
    called: int = 0


@pytest.fixture(autouse=True)
def _patch_guard_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep guard tests focused without constructing real app objects."""
    monkeypatch.setattr(helper_mod, "ModelEntrypoint", _FakeModelEntrypoint)
    monkeypatch.setattr(helper_mod, "MainWindow", _FakeMainWindow)


def test_validate_model_entrypoint_accepts_direct_and_subcontroller_owner(
) -> None:
    @helper_mod.validate_model_entrypoint
    def guarded_call(target: Any) -> str:
        target.called += 1
        return "called"

    direct = _Controller(model_entrypoint=_FakeModelEntrypoint())
    nested = _SubControllerOwner(
        _subcontroller=_Controller(model_entrypoint=_FakeModelEntrypoint())
    )

    assert guarded_call(direct) == "called"
    assert guarded_call(nested) == "called"
    assert direct.called == 1
    assert nested.called == 1


def test_validate_model_entrypoint_skips_invalid_target_without_calling(
) -> None:
    @helper_mod.validate_model_entrypoint
    def guarded_call(target: Any) -> str:
        target.called += 1
        return "called"

    direct = _Controller(model_entrypoint=object())
    nested = _SubControllerOwner(_subcontroller=_Controller(model_entrypoint=object()))

    assert guarded_call(direct) is None
    assert guarded_call(nested) is None
    assert direct.called == 0
    assert nested.called == 0


def test_validate_model_entrypoint_raises_when_no_entrypoint_is_available(
) -> None:
    @helper_mod.validate_model_entrypoint
    def guarded_call(target: Any) -> str:
        return "called"

    with pytest.raises(ValueError, match="Model entrypoint not found"):
        guarded_call(object())


def test_validate_view_accepts_direct_and_subcontroller_owner() -> None:
    @helper_mod.validate_view
    def guarded_call(target: Any) -> str:
        target.called += 1
        return "called"

    direct = _Controller(view=_FakeMainWindow())
    nested = _SubControllerOwner(_subcontroller=_Controller(view=_FakeMainWindow()))

    assert guarded_call(direct) == "called"
    assert guarded_call(nested) == "called"
    assert direct.called == 1
    assert nested.called == 1


def test_validate_view_skips_invalid_target_without_calling() -> None:
    @helper_mod.validate_view
    def guarded_call(target: Any) -> str:
        target.called += 1
        return "called"

    direct = _Controller(view=object())
    nested = _SubControllerOwner(_subcontroller=_Controller(view=object()))

    assert guarded_call(direct) is None
    assert guarded_call(nested) is None
    assert direct.called == 0
    assert nested.called == 0


def test_validate_view_raises_when_no_view_is_available() -> None:
    @helper_mod.validate_view
    def guarded_call(target: Any) -> str:
        return "called"

    with pytest.raises(ValueError, match="View not found"):
        guarded_call(object())


def test_delay_runs_callback_later_and_only_once(qtbot) -> None:
    calls: list[str] = []

    timer = helper_mod.delay(20)(lambda: calls.append("fired"))

    assert calls == []
    assert timer.isSingleShot()
    qtbot.waitUntil(lambda: calls == ["fired"], timeout=1000)
    qtbot.wait(50)
    assert calls == ["fired"]


def test_watchdog_can_be_stopped_before_callback_fires(qtbot) -> None:
    calls: list[str] = []

    timer = helper_mod.watchdog(40)(lambda: calls.append("fired"))
    timer.stop()

    assert timer.isSingleShot()
    qtbot.wait(80)
    assert calls == []


def test_repeat_runs_callback_until_timer_is_stopped(qtbot) -> None:
    calls: list[str] = []

    timer = helper_mod.repeat(15)(lambda: calls.append("tick"))

    assert not timer.isSingleShot()
    qtbot.waitUntil(lambda: len(calls) >= 2, timeout=1000)
    timer.stop()
    count_after_stop = len(calls)
    qtbot.wait(50)
    assert len(calls) == count_after_stop
