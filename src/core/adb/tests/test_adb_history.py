"""Tests for centralized ADB command history management."""

from __future__ import annotations

import datetime
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path
from typing import cast

import pytest

from core.adb.binary import AdbBinary
from core.adb.client import AdbClient
from core.adb.command import AdbCommandResult, AdbCommandResultStatus, AdbCommands
from core.adb.history import (
    ADB_HISTORY_MAX_ENTRIES,
    AdbCommandHistory,
    AdbCommandHistoryManager,
)
from core.adb.server import AdbServer


def _result() -> AdbCommandResult:
    return AdbCommandResult(status=AdbCommandResultStatus.SUCCESS)


def test_history_is_an_ordered_read_only_mapping() -> None:
    first_time = datetime.datetime(2026, 1, 1, 10, 0, 0)
    second_time = datetime.datetime(2026, 1, 1, 10, 0, 1)
    first_entry = (AdbCommands.START_SERVER, _result())
    second_entry = (AdbCommands.KILL_SERVER, _result())
    history = AdbCommandHistory(
        OrderedDict(
            [
                (first_time, first_entry),
                (second_time, second_entry),
            ]
        )
    )

    assert list(history) == [first_time, second_time]
    assert list(history.values()) == [first_entry, second_entry]
    with pytest.raises(TypeError):
        cast(MutableMapping[datetime.datetime, object], history)[first_time] = object()


def test_manager_adds_entries_and_prunes_the_oldest() -> None:
    manager = AdbCommandHistoryManager()

    for _ in range(ADB_HISTORY_MAX_ENTRIES + 3):
        manager.add(AdbCommands.GET_DEVICES, _result())

    assert len(manager.history) == ADB_HISTORY_MAX_ENTRIES
    assert manager.latest_command() is AdbCommands.GET_DEVICES


def test_manager_removes_all_matching_commands() -> None:
    manager = AdbCommandHistoryManager()
    manager.replace(
        OrderedDict(
            [
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 0),
                    (AdbCommands.START_SERVER, _result()),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 1),
                    (AdbCommands.KILL_SERVER, _result()),
                ),
                (
                    datetime.datetime(2026, 1, 1, 10, 0, 2),
                    (AdbCommands.START_SERVER, _result()),
                ),
            ]
        )
    )

    manager.remove(AdbCommands.START_SERVER)

    assert [entry[0] for entry in manager.history.values()] == [AdbCommands.KILL_SERVER]


def test_manager_replaces_clears_and_queries_latest_entry() -> None:
    first_time = datetime.datetime(2026, 1, 1, 10, 0, 0)
    latest_time = datetime.datetime(2026, 1, 1, 10, 0, 1)
    first_result = _result()
    latest_result = _result()
    manager = AdbCommandHistoryManager()

    manager.replace(
        OrderedDict(
            [
                (first_time, (AdbCommands.START_SERVER, first_result)),
                (latest_time, (AdbCommands.KILL_SERVER, latest_result)),
            ]
        )
    )

    assert manager.latest_time() == latest_time
    assert manager.latest_entry() == (AdbCommands.KILL_SERVER, latest_result)
    assert manager.latest_command() is AdbCommands.KILL_SERVER
    assert manager.latest_result() is latest_result
    assert list(manager.entries_newest_first()) == [
        (AdbCommands.KILL_SERVER, latest_result),
        (AdbCommands.START_SERVER, first_result),
    ]

    manager.clear()

    assert len(manager.history) == 0
    with pytest.raises(StopIteration):
        manager.latest_time()


def test_client_and_server_use_independent_manager_instances() -> None:
    binary = AdbBinary(path=Path("/mock/adb"))
    client = AdbClient(binary)
    server = AdbServer(binary)

    client.add_to_history(AdbCommands.GET_DEVICES, _result())

    assert client._history_manager is not server._history_manager
    assert client.history is not server.history
    assert len(client.history) == 1
    assert len(server.history) == 0
