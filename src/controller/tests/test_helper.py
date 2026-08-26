from __future__ import annotations

import controller.helper as helper_mod


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
