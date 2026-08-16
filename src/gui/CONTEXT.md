# GUI context

## Purpose

`gui` is AROW's PySide6 view layer: the main window, panels, reusable components
and blocks, theme and resource infrastructure, and view-originating signals.

## Boundaries and philosophy

- Follow `DESIGN.md` for visual direction, spacing, themes, accessibility, and
  screenshot review.
- Keep panels thin: they own chrome, visibility, orchestration, data routing, and
  explicit facade methods. Blocks own local rendering and interaction behavior.
- Use categorized signals from `gui.signals.signals`; do not extend legacy flat
  signal APIs. Custom connected methods and timer callbacks use matching typed
  `@Slot(...)` signatures and named handlers.
- Put cross-cutting colors in `constants/colors.py`, styling in
  `constants/stylesheet.py`, reusable animation in `animation.py`, and shared
  layout tokens in `constants/settings.py`.
- Put owner-specific sizing and timing constants in a frozen local settings
  dataclass. Do not embed one-off styles in widget modules.
- Use `constants/icons.py` for Qt resource icons. Keep `statics`,
  `ressources.qrc`, and generated `ressources_rc.py` synchronized; never edit
  the generated file.
- Communicate with the model through controllers and view signals, never through
  ADB subprocesses or direct model work.

## Primary dependencies

- **PySide6** provides widgets, models, signals, painting, SVG, and web-engine
  integration.
- **Faker** supplies deterministic-looking demonstration data where explicitly
  used.
- **pytest** and **pytest-qt** provide behavioral and offscreen screenshot tests.

Versions remain in `pyproject.toml`.

## Validation and references

- Run the nearest GUI behavioral tests. Appearance changes also require the
  nearest `@pytest.mark.screenshot` test and visual inspection; shell-wide changes
  use the full-window screenshot.
- Rebuild resources after resource changes with
  `uv run pyside6-rcc src/gui/ressources.qrc -o src/gui/ressources_rc.py`.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Design system: [`../../DESIGN.md`](../../DESIGN.md).
- Signal flows:
  [`../../docs/HOW_TO_controller_and_signals.md`](../../docs/HOW_TO_controller_and_signals.md).
