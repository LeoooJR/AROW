from __future__ import annotations

import os
from pathlib import Path

import pytest

from core import ADB_BINARY_BUILD_NUMBER, ADB_BINARY_BUILD_VERSION, ADB_BINARY_VERSION
from core.adb import AdbBinary
from core.work import startup_work


def test_ensure_adb_binary_executable_passes_for_executable_file(
    tmp_path: Path,
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    adb_path.chmod(0o700)

    startup_work._ensure_adb_binary_executable(adb_path)


def test_ensure_adb_binary_executable_raises_for_non_executable_file(
    tmp_path: Path,
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    adb_path.chmod(0o600)

    if os.access(adb_path, os.X_OK):
        pytest.skip("Platform reports the fixture file as executable")

    with pytest.raises(PermissionError, match="ADB binary is not executable"):
        startup_work._ensure_adb_binary_executable(adb_path)


def test_start_adb_server_checks_binary_before_constructing_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    calls: list[str] = []

    class FakeAdbServer:
        def __init__(self, binary: AdbBinary) -> None:
            calls.append("construct")
            self.binary = binary
            self.paired_devices = []

        @classmethod
        def get_binary_version(cls, binary: AdbBinary) -> AdbBinary:
            calls.append("version")
            return AdbBinary(
                path=binary.path,
                version=ADB_BINARY_VERSION,
                build_version=ADB_BINARY_BUILD_VERSION,
                build_number=ADB_BINARY_BUILD_NUMBER,
            )

    def fake_ensure(path: Path) -> None:
        assert path == adb_path
        calls.append("ensure")

    monkeypatch.setattr(startup_work, "_resolve_adb_binary_path", lambda: adb_path)
    monkeypatch.setattr(startup_work, "_ensure_adb_binary_executable", fake_ensure)
    monkeypatch.setattr(startup_work, "AdbServer", FakeAdbServer)

    server = startup_work._start_adb_server()

    assert isinstance(server, FakeAdbServer)
    assert calls == ["ensure", "version", "construct"]


def test_start_adb_server_rejects_binary_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adb_path = tmp_path / "adb"
    adb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    constructed: list[AdbBinary] = []

    class FakeAdbServer:
        def __init__(self, binary: AdbBinary) -> None:
            constructed.append(binary)

        @classmethod
        def get_binary_version(cls, binary: AdbBinary) -> AdbBinary:
            return AdbBinary(
                path=binary.path,
                version="Android Debug Bridge version 9.9.9",
                build_version=ADB_BINARY_BUILD_VERSION,
                build_number=ADB_BINARY_BUILD_NUMBER,
            )

    monkeypatch.setattr(startup_work, "_resolve_adb_binary_path", lambda: adb_path)
    monkeypatch.setattr(
        startup_work, "_ensure_adb_binary_executable", lambda _path: None
    )
    monkeypatch.setattr(startup_work, "AdbServer", FakeAdbServer)

    with pytest.raises(RuntimeError, match="Failed to start ADB server") as exc_info:
        startup_work._start_adb_server()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "frozen metadata" in str(exc_info.value.__cause__)
    assert constructed == []
