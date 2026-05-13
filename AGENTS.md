# AROW Project Instructions

## Project overview

- This application spoofs the coordinates of a mobile phone from a computer using Android Debug Bridge (`ADB`).
- The GUI is built with `PySide6`.
- Communication between the computer and the phone is handled with ADB-related assets and logic in `src/assets` and `src/core/adb.py`.

## Repository structure

- `src/gui`: graphical user interface
- `src/core`: model and core logic
- `src/geo`: Leaflet map integration and map-specific assets
- `src/controller`: communication layer between GUI and model

Follow the project MVC split:

- Model: `src/core`
- View: `src/gui`
- Controller: `src/controller`

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

- Create and run model-side heavy work, map creation, and I/O through `src/controller/async.py`.
- Use `JobSpecification` and `AsyncRunner.submit(job)` for async execution.
- Use the returned `JobHandler` and `runner.bind_handle_signals(handle)` when per-job signals are needed.
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

- Use values from `src/gui/settings.py` for margins, spacing, dimensions, and fonts.
- If a needed value is missing, add or adjust it in `src/gui/settings.py` instead of hardcoding it elsewhere.

### Colors

- Use colors from `src/gui/colors.py`.
- If a needed color does not exist, add or update it there rather than defining a one-off value locally.

### Reusable elements and layouts

- Put reusable UI building blocks in `src/gui/elements.py`.
- Use layout helpers from `src/gui/wrapper.py` when they fit:
  - `VerticalLayoutWrapper`
  - `HorizontalLayoutWrapper`
  - `GridLayoutWrapper`

### Icons

- Use `src/gui/icons.py` for GUI Qt resource icons.
- Use `src/geo/icons.py` for folium or Leaflet map icons.

### Signals

- Use view-originating signals from `src/gui/signals.py` (`ViewSignals` / `view_signals`) for cross-component communication.
- Do not define new global GUI signals elsewhere unless there is a compelling architectural reason.

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
