# Run command context

## Purpose

`commands.run` owns launch options and runtime bootstrapping for AROW's execution
modes, including the PySide6 GUI and mock-ADB selection.

## Boundaries and philosophy

- Convert CLI options into bootstrap configuration; do not place model work here.
- Create Qt application, window, model entrypoint, and controller in a predictable
  order, registering bundled fonts before styled widgets are imported.
- Preserve `--mock-adb` as the safe development path. Never use launch code to
  connect to or mutate a real device without explicit user authorization.
- Keep imports that require a live `QApplication` deferred when startup ordering
  depends on it.

## Primary dependencies

- **Typer** supplies command context and exits.
- **PySide6** supplies `QApplication` and the GUI event loop.
- **pytest**, **pytest-qt**, and `CliRunner` test bootstrap behavior with mocks.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/commands/run/tests src/commands/tests`.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Safe mock launch: [`../../../HOW_TO_mock_adb.md`](../../../HOW_TO_mock_adb.md).
