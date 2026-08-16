"""Tests for operating system theme detection and startup stylesheet selection."""

from __future__ import annotations

import importlib
import subprocess
import sys
from types import SimpleNamespace

from gui.constants import colors


class _FakeWindowsRegistryKey:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


def _completed_process(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_macos_system_theme_falls_back_when_defaults_missing(monkeypatch) -> None:
    monkeypatch.setattr(colors.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(colors.shutil, "which", lambda _name: None)

    assert colors.get_system_theme() == "light"


def test_macos_system_theme_detects_dark(monkeypatch) -> None:
    monkeypatch.setattr(colors.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(colors.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        colors.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process("Dark\n"),
    )

    assert colors.get_system_theme() == "dark"


def test_linux_system_theme_falls_back_when_gsettings_missing(monkeypatch) -> None:
    monkeypatch.setattr(colors.platform, "system", lambda: "Linux")
    monkeypatch.setattr(colors.shutil, "which", lambda _name: None)

    assert colors.get_system_theme() == "light"


def test_linux_system_theme_detects_dark(monkeypatch) -> None:
    monkeypatch.setattr(colors.platform, "system", lambda: "Linux")
    monkeypatch.setattr(colors.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        colors.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process("'prefer-dark'\n"),
    )

    assert colors.get_system_theme() == "dark"


def test_windows_system_theme_falls_back_on_non_windows_platform(monkeypatch) -> None:
    monkeypatch.setattr(colors.platform, "system", lambda: "Windows")
    monkeypatch.setattr(colors.sys, "platform", "darwin")

    assert colors.get_system_theme() == "light"


def test_windows_system_theme_detects_dark(monkeypatch) -> None:
    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=lambda *args, **kwargs: _FakeWindowsRegistryKey(),
        QueryValueEx=lambda *args, **kwargs: (0, None),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    monkeypatch.setattr(colors.platform, "system", lambda: "Windows")
    monkeypatch.setattr(colors.sys, "platform", "win32")

    assert colors.get_system_theme() == "dark"


def test_system_theme_falls_back_to_light_for_unknown_os(monkeypatch) -> None:
    monkeypatch.setattr(colors.platform, "system", lambda: "FreeBSD")

    assert colors.get_system_theme() == "light"


def test_initialize_app_theme_updates_current_theme(monkeypatch) -> None:
    monkeypatch.setattr(colors, "get_system_theme", lambda: "dark")

    try:
        assert colors.initialize_app_theme_from_system() == "dark"
        assert colors.get_current_theme() == "dark"
    finally:
        colors.set_current_theme("light")


def test_stylesheet_named_variable_uses_current_app_theme() -> None:
    from gui.constants import stylesheet as stylesheet_module

    try:
        colors.set_current_theme("dark")
        stylesheet_module = importlib.reload(stylesheet_module)

        assert stylesheet_module.stylesheet == stylesheet_module.stylesheet_dark
    finally:
        colors.set_current_theme("light")
        importlib.reload(stylesheet_module)
