# AROW Project Instructions

## Project overview

- This application spoofs the coordinates of a mobile phone from a computer using Android Debug Bridge (`ADB`).
- The GUI is built with `PySide6`.
- Communication between the computer and the phone is handled with ADB-related assets and logic in `src/assets` and `src/core/adb.py`.

## Repository structure

- `src/gui`: graphical user interface
- `src/gui/components`: reusable GUI component package, grouped by component category
- `src/gui/blocks`: reusable GUI block package for widgets composed from multiple components, grouped by block category
- `src/core`: model and core logic
- `src/geo`: Leaflet map integration and map-specific assets
- `src/controller`: communication layer between GUI and model
  - `src/controller/orchestration/`: top-level coordinators (e.g. `AppController`)
  - `src/controller/domains/`: domain sub-controllers (`AdbSubController`, `SimulationSubController`, `MapSubController`)
  - `src/controller/runner.py`, `helper.py`, `core_work_callbacks.py`, `controller.py`: shared async, validation, callbacks, and MVC base at package root

Follow the project MVC split:

- Model: `src/core`
- View: `src/gui`
- Controller: `src/controller`

## Git workflow

This repository uses two long-lived branches:

| Branch | Role |
|--------|------|
| **`dev`** | Integration branch — all day-to-day development lands here |
| **`main`** | Stable branch — production-ready releases only |

`main` is not the default target for agent automation or routine pull requests.

### Rules for agents and contributors

- **Branch from `dev`:** create feature or fix branches from an up-to-date `dev` checkout.
- **Open pull requests against `dev`:** never open routine PRs targeting `main`.
- **Do not commit directly to `main`:** routine work merges into `dev` via PR; `main` is updated only through intentional release promotion from `dev`.
- **Compare against `dev`:** use `dev...HEAD` for reviews and PR summaries (not `main...HEAD`).
- **Keep branches short-lived:** one logical change per branch; rebase or update from `dev` before opening or updating a PR.

### Typical flow

1. `git checkout dev && git pull`
2. `git checkout -b agent/<tool>/<short-description>` (or an equivalent feature branch name)
3. Commit on the feature branch
4. Open a PR with **base branch `dev`**
5. After merge, delete the feature branch when no longer needed

## Architecture boundaries

- Keep ADB calls inside `src/core/adb.py`.
- Keep network logic inside `src/core/network.py`.
- Keep device methods, device metadata, and related dataclasses in `src/gui/device.py`.
- Do not move model work into the GUI or controller just for convenience.

## Geo and dataset standards

Apply these rules whenever you touch `src/geo`.

### Tabular and spatial data operations

- Treat `pandas.DataFrame`, `geopandas.GeoDataFrame`, and related structures as columnar data.
- Prefer vectorized APIs, joins, concatenation, groupby aggregations, and spatial joins over row-wise Python loops.
- Avoid `iterrows`, per-row `apply` with Python callables, and manual index loops in geo data paths unless there is no practical alternative.
- If a scalar loop is truly required for a third-party API, isolate it, document why, and keep the hot path as small as possible.

### Dataset validation

- Express dataset shape, dtype, column, and value constraints for geo codepaths with `pandera`.
- Validate data at clear boundaries such as after load, before export, or before handing data to the map pipeline.
- Reuse or extend schema definitions in `src/geo/datasets.py` or nearby schema modules instead of scattering ad-hoc checks through `src/geo`.
- Handle schema failures with explicit project exceptions, following the `src/geo/exceptions.py` and `SchemaValidationError` pattern, rather than silent coercion.

### Map rendering

- Build server-side map HTML with `folium`; do not replace the map stack with ad-hoc Leaflet-only string generation unless the project explicitly decides to migrate.
- Keep first paint fast: simplify or decimate display geometry when appropriate, avoid redundant layers, and limit inline GeoJSON, plugins, and embedded JS/CSS that slow initial load.
- Prefer doing data preparation in Python before handing results to Folium so the browser has less work to do.

### Geo dependencies

- Keep `pandera` and `folium` in project dependencies when extending schemas or map features.
- Align geo-related imports and usage with the versions pinned in `requirements.txt`.

## Async model work

- Create and run model-side heavy work, map creation, and I/O through `src/controller/runner.py`.
- Use `JobSpecification` and `AsyncRunner.submit(job)` for async execution.
- Use the returned `JobHandler` and `runner.bind_handle_signals(handle)` when per-job signals are needed.
- Implement core-runtime async job completion handlers (`on_completed` / `on_failed`) in `src/controller/core_work_callbacks.py`, wired to those handlers, instead of accumulating ad-hoc methods on large controllers.
- Do not introduce ad-hoc threads or processes for model work; route it through `AsyncRunner` so cancellation, coalescing, and signals remain consistent.

## Qt model/view usage

- When the view needs lists, tables, or trees, prefer Qt model classes in `src/core/qt_models.py`.
- Use the Qt model/view pattern when it is a better fit than passing plain Python data through the controller.

## Python standards

### Comments and typing

- Comment non-obvious logic and algorithmic steps.
- Algorithmic logic should be commented generously enough that the intent and flow are easy to follow.
- Use type hints for function parameters and return values, and for variables when they improve clarity.
- Prefer built-in collection types and standard `typing` annotations.

### Paths

- Use `pathlib.Path` for all filesystem paths.
- Do not introduce raw string paths when a `Path` object is appropriate.

### Logging and console output

- Use `loguru` for logging.
- Log with strong context: include paths, inputs, outputs, identifiers, and relevant state.
- When styled terminal output is needed, use `rich`.

### Error handling

- Wrap failure-prone operations such as I/O, network access, and parsing in `try/except`.
- Raise explicit, helpful exceptions that explain what failed.
- Use `assert` only for strict internal preconditions.
- Prefer explicit exceptions such as `ValueError` for recoverable or user-facing validation.

## GUI standards

Apply these rules whenever you touch `src/gui`.

### Design guidelines

- Follow `DESIGN.md` for the AROW visual direction, including light/dark palettes, typography, spacing, widget styling, and interaction states.
- Treat `DESIGN.md` as the design source of truth before adding new GUI colors, dimensions, component treatments, or theme behavior.

### Settings and dimensions

GUI settings are split between **app-wide tokens** and **owner-local modules**, mirroring the signals layout.

#### App-wide settings (`src/gui/settings.py`)

- Import the shared container: `from gui.settings import Settings`.
- Use `Settings` for cross-cutting layout tokens only:
  - `Settings.FONT`, `Settings.SPACING`, `Settings.DIMENSION`
  - `Settings.BORDER_RADIUS`, `Settings.ANIMATION`, `Settings.PANEL`
- If a value is shared across multiple components, blocks, panels, or stylesheets, add or adjust it here instead of hardcoding elsewhere.

#### Owner-local settings (`*_settings.py`)

- Component-, block-, and panel-specific dimensions live next to their owner as frozen dataclass modules with a module-level singleton (e.g. `button_settings`, `device_settings`, `welcome_settings`).
- Import the owner singleton directly, for example:
  - `from gui.components.buttons.button_settings import button_settings`
  - `from gui.blocks.device.device_settings import device_settings`
  - `from gui.welcome_settings import welcome_settings`
- Current owner-local modules:
  - Components: `button_settings`, `input_settings`, `list_settings`, `container_settings`, `feedback_settings`, `indicator_settings`, `svg_settings`
  - Blocks: `activity_log_settings`, `card_settings`, `device_settings`, `location_settings`, `map_settings`, `start_settings`, `top_bar_settings`
  - GUI-level panels/tabs: `welcome_settings`, `host_panel_settings`
- When adding a new reusable component or block, create `<owner>_settings.py` beside the owner module if it needs dedicated sizing or timing constants.
- Do not add owner-specific constants back into `src/gui/settings.py`; keep `settings.py` for shared shell tokens only.
- `src/gui/stylesheet.py` may import both `Settings` and owner-local settings modules as needed.

### Colors

- Use colors from `src/gui/colors.py`.
- If a needed color does not exist, add or update it there rather than defining a one-off value locally.

### Components and layouts

- Put reusable GUI building blocks in `src/gui/components/`, not `src/gui/elements.py`.
- Treat `src/gui/elements.py` as a backward-compatible re-export shim for legacy imports only; new code should import from `gui.components` or a category subpackage such as `gui.components.buttons`.
- Keep components grouped by purpose in the existing category packages:
  - `base`: shared component protocol and Qt/ABC metaclass helpers
  - `buttons`: action and tool button widgets
  - `containers`: composite card, group, and placeholder widgets
  - `dialogs`: file and message dialogs
  - `feedback`: transient feedback such as toasts
  - `file_display`: file summary/display widgets
  - `indicators`: progress and state indicators
  - `inputs`: form/input widgets
  - `labels`: reusable text and icon-label widgets
  - `lists`: list widgets
  - `media`: image and SVG rendering widgets
- If a new reusable component does not fit an existing category, create a new category package under `src/gui/components/` instead of forcing it into an unrelated module.
- Export new reusable components from their category `__init__.py` and from `src/gui/components/__init__.py` when they are intended for project-wide use.
- Components should inherit from `Component` when they participate in the shared component lifecycle, implement `_set_size_policy`, `_set_alignment`, `_connect_signals`, and `apply_theme_icons`, and call `_finalize_ui_hooks()` after their child widgets and state are initialized.
- Prefer component-local `Text` and `UI` dataclasses for stable labels and child-widget references when a component has user-facing text or meaningful internal widgets.
- Use layout helpers from `src/gui/wrapper.py` when they fit:
  - `VerticalLayoutWrapper`
  - `HorizontalLayoutWrapper`
  - `GridLayoutWrapper`

### Blocks and panels

- Put reusable multi-component GUI widgets in `src/gui/blocks/`. A block is larger than a component and is composed from multiple components or helper widgets.
- Keep blocks grouped by category. Current block categories include:
  - `base`: shared `Block` lifecycle protocol
  - `activity`: activity log stream, filtering, rows, file display, and activity storage
  - `card`: reusable card/groupbox-style information blocks such as identity and bridge status cards
  - `device`: device selection block, device list rows, badges, timestamps, placeholder rows, and selection helpers
  - `map`: map canvas, placeholder, legend, coordinates, and simulation controls
  - `start`: welcome start/recent-file and walkthrough blocks
  - `top_bar`: application header, palette controls, title, and sidebar visibility controls
- Prefer one block per file. Keep block-specific helper classes beside the block they serve, and avoid aggregate compatibility files that only re-export renamed blocks.
- Export reusable blocks from their category `__init__.py` and from `src/gui/blocks/__init__.py` when they are intended for project-wide use.
- Blocks should inherit from `Block` when they participate in the shared block lifecycle, implement `_set_size_policy`, `_set_alignment`, `_connect_signals`, and `apply_theme_icons`, and call `_finalize_ui_hooks()` after their child widgets and state are initialized.
- Prefer block-local `Text` and `UI` dataclasses for stable copy and child-widget references. Placeholder, demo, default, and generated values owned by a block must live under the block `Text` dataclass.
- Blocks own block-specific widgets, helper rows/classes, placeholder seeding, row rendering, filtering, list item sizing, selection/highlight behavior, theme-icon propagation, and block-specific signal handlers.
- Panels should remain thin shells for panel chrome and orchestration: title/header widgets, expand/collapse behavior, visibility handling, routing real data into blocks, and public facade methods required by `window.py` or tests.
- Panel `UI` dataclasses may store direct block instances, but should not duplicate or expose widgets owned by those blocks. Prefer explicit panel facade methods over reaching through chained block UI references from outside the block.
- Keep `src/gui/location.py` out of the blocks refactor until the location panel receives its planned dedicated refactor.
- Put block-internal tests under each block category's `tests/` directory inside `src/gui/blocks/`. Keep panel, window, component, and end-to-end GUI integration tests under `src/gui/tests/`.
- When behavior moves from a panel into a block, move or add the matching tests under the block category and cover both successful behavior and error or state-regression paths.

### Icons

- Use `src/gui/icons.py` for GUI Qt resource icons.
- Use `src/geo/icons.py` for folium or Leaflet map icons.

### Signals

- Use view-originating signals from `src/gui/signals.py` for cross-component communication.
- Import the shared singleton: `from gui.signals import signals`.
- Access signals through categorized attributes on `signals`, mirroring `Settings`:
  - `signals.UI` — palette, panel visibility, sidebar display/hide, map-tab activation
  - `signals.ADB_SERVER` — ADB server lifecycle
  - `signals.DEVICE` — pairing, selection, refresh, removal
  - `signals.HOST` — host identity and metadata
  - `signals.ACTIVITY_LOG` — activity log file updates
  - `signals.SIMULATION` — simulation start/stop and position/context changes
- Example: `signals.UI.DisplayLeftPanelsRequested.connect(...)`, `signals.DEVICE.DeviceSelectionSucceeded.emit(...)`.
- Sidebar visibility uses explicit `Display*` / `Hide*` signals; do not reintroduce boolean left/right toggle signals.
- Add new GUI-originating signals to the appropriate category class in `src/gui/signals.py`; do not define new global GUI signals elsewhere unless there is a compelling architectural reason.
- Do not use the legacy `view_signals` / flat `ViewSignals` API in new or updated code.

### Stylesheets

- Keep styling in `src/gui/stylesheet.py`.
- Do not embed inline style strings in other Python files; extend the stylesheet module instead.

### Animations

- Implement common or generic animation helpers in `src/gui/animation.py`.
- Reuse helpers from `src/gui/animation.py` instead of duplicating shared animation logic in panel or widget modules.

### Qt resources

When adding, removing, renaming, or updating GUI assets referenced by the Qt resource file:

- Update assets under `src/gui/statics/` as needed.
- Ensure `src/gui/ressources.qrc` matches the asset set.
- Recompile the resource module when the task is complete:

```bash
pyside6-rcc src/gui/ressources.qrc -o src/gui/ressources_rc.py
```

The compiled module is `src/gui/ressources_rc.py`.
