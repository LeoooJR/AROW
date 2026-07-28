"""Tests for the GUI run command."""

import sys
from collections.abc import Iterator
from types import ModuleType
from unittest.mock import Mock, call, patch

import pytest
from typer.testing import CliRunner

from __init__ import __application__, __version__
from commands import app

runner = CliRunner()


@pytest.fixture
def gui_dependencies(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Mock]]:
    """Replace GUI startup dependencies without launching Qt or touching ADB."""
    register_bundled_fonts = Mock(name="register_bundled_fonts")
    main_window_type = Mock(name="MainWindow")
    app_controller_type = Mock(name="AppController")
    model_entrypoint_type = Mock(name="ModelEntrypoint")

    fonts_module = ModuleType("gui.fonts")
    fonts_module.register_bundled_fonts = register_bundled_fonts  # type: ignore[attr-defined]
    window_module = ModuleType("gui.window")
    window_module.MainWindow = main_window_type  # type: ignore[attr-defined]
    controller_module = ModuleType("controller")
    controller_module.AppController = app_controller_type  # type: ignore[attr-defined]
    entrypoint_module = ModuleType("core.entrypoint")
    entrypoint_module.ModelEntrypoint = model_entrypoint_type  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "gui.fonts", fonts_module)
    monkeypatch.setitem(sys.modules, "gui.window", window_module)
    monkeypatch.setitem(sys.modules, "controller", controller_module)
    monkeypatch.setitem(sys.modules, "core.entrypoint", entrypoint_module)

    dependencies = {
        "register_bundled_fonts": register_bundled_fonts,
        "MainWindow": main_window_type,
        "AppController": app_controller_type,
        "ModelEntrypoint": model_entrypoint_type,
    }
    yield dependencies


@pytest.mark.parametrize(
    ("arguments", "use_mock_adb", "serialize_logs"),
    [
        (["run", "gui"], False, False),
        (["run", "--mock-adb", "gui"], True, False),
        (["run", "--json-logs", "gui"], False, True),
    ],
)
def test_gui_command_wires_application(
    arguments: list[str],
    use_mock_adb: bool,
    serialize_logs: bool,
    gui_dependencies: dict[str, Mock],
) -> None:
    """The command configures Qt and wires the GUI to the model and controller."""
    qt_application = Mock(name="qt_application")
    qt_application.exec.return_value = 7
    qapplication_type = Mock(name="QApplication")
    qapplication_type.instance.return_value = None
    qapplication_type.return_value = qt_application

    lifecycle = Mock()
    lifecycle.attach_mock(gui_dependencies["register_bundled_fonts"], "fonts")
    lifecycle.attach_mock(gui_dependencies["MainWindow"], "window")
    paths = Mock(name="application_paths")
    log_path = paths.application_log_file.return_value

    with (
        patch("commands.run.gui.QtWidgets.QApplication", qapplication_type),
        patch("commands.run.gui.locale.setlocale"),
        patch("commands.run.gui.APPLICATION_PATHS", paths),
        patch("commands.run.gui.setup_logger") as setup_logger,
    ):
        result = runner.invoke(app, arguments)

    assert result.exit_code == 7
    qapplication_type.assert_called_once_with([])
    qt_application.setApplicationName.assert_called_once_with(__application__)
    qt_application.setDesktopFileName.assert_called_once_with(__application__)
    qt_application.setApplicationVersion.assert_called_once_with(__version__)
    setup_logger.assert_called_once_with(log_path, serialize=serialize_logs)
    gui_dependencies["register_bundled_fonts"].assert_called_once_with()
    assert lifecycle.mock_calls.index(call.fonts()) < lifecycle.mock_calls.index(
        call.window()
    )

    main_window = gui_dependencies["MainWindow"].return_value
    model_entrypoint = gui_dependencies["ModelEntrypoint"].return_value
    gui_dependencies["ModelEntrypoint"].assert_called_once_with(
        use_mock_adb=use_mock_adb,
        paths=paths,
    )
    gui_dependencies["AppController"].assert_called_once_with(
        model_entrypoint=model_entrypoint,
        view=main_window,
    )
    main_window.show.assert_called_once_with()
    qt_application.exec.assert_called_once_with()


def test_gui_command_reuses_existing_qapplication(
    gui_dependencies: dict[str, Mock],
) -> None:
    """An existing Qt application is reused instead of creating another one."""
    qt_application = Mock(name="qt_application")
    qt_application.exec.return_value = 0
    qapplication_type = Mock(name="QApplication")
    qapplication_type.instance.return_value = qt_application

    with (
        patch("commands.run.gui.QtWidgets.QApplication", qapplication_type),
        patch("commands.run.gui.locale.setlocale"),
        patch("commands.run.gui.setup_logger"),
    ):
        result = runner.invoke(app, ["run", "gui"])

    assert result.exit_code == 0
    qapplication_type.assert_not_called()
    qt_application.exec.assert_called_once_with()
