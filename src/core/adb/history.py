"""Ordered ADB command history representation and management policy."""

from __future__ import annotations

import datetime
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from typing import Final

from core.adb.command import AdbCommandResult, AdbCommandSpec

ADB_HISTORY_MAX_ENTRIES: Final[int] = 100

AdbCommandHistoryEntry = tuple[AdbCommandSpec[object], AdbCommandResult]
AdbCommandHistoryEntries = Mapping[datetime.datetime, AdbCommandHistoryEntry]


class AdbCommandHistory(Mapping[datetime.datetime, AdbCommandHistoryEntry]):
    """Read-only ordered view of timestamped ADB command results."""

    __slots__ = ("_entries",)

    def __init__(self, entries: AdbCommandHistoryEntries | None = None) -> None:
        """Initialize an ordered history from optional existing entries."""
        self._entries = (
            OrderedDict(entries.items()) if entries is not None else OrderedDict()
        )

    def __getitem__(self, timestamp: datetime.datetime) -> AdbCommandHistoryEntry:
        return self._entries[timestamp]

    def __iter__(self) -> Iterator[datetime.datetime]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __reversed__(self) -> Iterator[datetime.datetime]:
        return reversed(self._entries)

    def _add(
        self,
        timestamp: datetime.datetime,
        entry: AdbCommandHistoryEntry,
    ) -> None:
        self._entries[timestamp] = entry

    def _remove_oldest(self) -> None:
        self._entries.popitem(last=False)

    def _remove(self, command: AdbCommandSpec[object]) -> None:
        self._entries = OrderedDict(
            (timestamp, entry)
            for timestamp, entry in self._entries.items()
            if entry[0] != command
        )

    def _clear(self) -> None:
        self._entries.clear()

    def _entries_newest_first(self) -> Iterator[AdbCommandHistoryEntry]:
        return reversed(self._entries.values())


class AdbCommandHistoryManager:
    """Own all mutation and query policy for one ADB command history."""

    def __init__(self) -> None:
        """Initialize a manager with an empty command history."""
        self._history = AdbCommandHistory()

    @property
    def history(self) -> AdbCommandHistory:
        """Return the managed read-only history collection."""
        return self._history

    def replace(self, entries: AdbCommandHistoryEntries) -> None:
        """Replace the managed collection with an ordered copy of entries."""
        self._history = AdbCommandHistory(entries)

    def clear(self) -> None:
        """Remove every history entry while retaining the collection instance."""
        self._history._clear()

    def add(
        self,
        command: AdbCommandSpec[object],
        result: AdbCommandResult,
    ) -> None:
        """Append a timestamped result and retain only the newest entries."""
        self._history._add(datetime.datetime.now(), (command, result))
        while len(self._history) > ADB_HISTORY_MAX_ENTRIES:
            self._history._remove_oldest()

    def remove(self, command: AdbCommandSpec[object]) -> None:
        """Remove every entry for the supplied command specification."""
        self._history._remove(command)

    def latest_time(self) -> datetime.datetime:
        """Return the timestamp of the newest entry."""
        return next(reversed(self._history))

    def latest_entry(self) -> AdbCommandHistoryEntry:
        """Return the newest command and result."""
        return self._history[self.latest_time()]

    def latest_command(self) -> AdbCommandSpec[object]:
        """Return the newest command specification."""
        return self.latest_entry()[0]

    def latest_result(self) -> AdbCommandResult:
        """Return the newest command result."""
        return self.latest_entry()[1]

    def entries_newest_first(self) -> Iterator[AdbCommandHistoryEntry]:
        """Iterate over entries from newest to oldest."""
        return self._history._entries_newest_first()
