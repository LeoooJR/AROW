# How to run AROW with mock ADB

## What this is for

Mock ADB lets you run the full application **without** the Android Debug Bridge daemon and **without** a real `adb` binary on disk. Device listing, pairing, and common “ADB shell style” replies are simulated with realistic-looking fake data so you can work on UI, flows, and demos without a phone or a working toolchain.

Mock mode is optional and off by default.

## Important limitation

Mock ADB applies only when the **full app** starts (controller + model).
If you use **`--interface-only`**, no core runtime runs, so **`--mock-adb` has no effect**.

## CLI (recommended while developing)

From the repository root, put `src` on the Python path and run the `main` module (same layout as pytest in this repo):

```bash
PYTHONPATH=src python -m main --mock-adb
```

If you normally start the UI from **`src/`** instead, **`python -m main --mock-adb`** there also works once `main.py` is the module you invoke.

To see Typer options and short help:

```bash
PYTHONPATH=src python -m main --help
```

Use the **`--mock-adb`** flag in your IDE or shell run configuration wherever you invoke the same entrypoint today.

## Environment variables

| Variable             | Accepted “true” values (case-insensitive, trimmed) | Purpose |
|----------------------|---------------------------------------------------|---------|
| **`AROW_USE_MOCK_ADB`** | `1`, `true`, `yes`                            | Enables mock ADB **without** passing `--mock-adb`. Handy for scripts, CI, or one-shot shells. |

If either **`--mock-adb`** **or** **`AROW_USE_MOCK_ADB`** is enabled, the app starts in mock ADB mode.

| Variable               | Meaning |
|------------------------|---------|
| **`AROW_MOCK_ADB_SEED`** | Optional integer. When set (and parseable), makes fake device details **repeatable** across runs — useful when you need stable screenshots or debugging. Leave unset for random-ish data each time. Invalid values are ignored as if unset. |

### Examples

**macOS / Linux (current shell only):**

```bash
export AROW_USE_MOCK_ADB=1
PYTHONPATH=src python -m main
```

**Repeatable synthetic devices:**

```bash
export AROW_USE_MOCK_ADB=1
export AROW_MOCK_ADB_SEED=42
PYTHONPATH=src python -m main
```

**Windows (PowerShell):**

```powershell
$env:AROW_USE_MOCK_ADB = "1"
python -m main
```

You can combine CLI and env: **`--mock-adb`** is enough on its own; **`AROW_USE_MOCK_ADB`** is mainly for automation when you prefer not to change the command line.

## Quick troubleshooting

| Symptom | What to check |
|--------|----------------|
| Still looks for real ADB files | Confirm you did **not** pass **`--interface-only`**. Use **`--mock-adb`** or **`AROW_USE_MOCK_ADB=1`**. |
| Data changes every launch | Expected unless you set **`AROW_MOCK_ADB_SEED`**. |

## Automated tests

Core tests exercise mock startup without a real adb binary; CI can rely on **`StartupCoreRuntimeWork(use_mock_adb=True)`** or equivalent from code — you do **not** need these env vars for that unless your harness starts the GUI entrypoint itself.
