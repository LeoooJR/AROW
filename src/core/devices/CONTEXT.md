# Device domain context

## Purpose

`core.devices` defines host and phone descriptors, device behavior, stable
identity keys, and device-related repository semantics.

## Boundaries and philosophy

- Keep device metadata and behavior in typed domain objects; controllers and GUI
  consume those objects through model APIs.
- Maintain stable identity independently from transient transport metadata such as
  display names, IP addresses, and ports.
- Keep descriptors and related value objects explicit and type annotated.
- Route operations that execute ADB commands through `core.adb`; this package does
  not open subprocesses.
- Preserve equality, hashing, serialization, and update semantics when extending
  descriptors.

## Primary dependencies

- Python **dataclasses** model device descriptors and stable values.
- **Loguru** records repository and device-state diagnostics.
- **pytest** verifies identity, descriptor, host, and phone behavior without real
  devices.

Versions remain in `pyproject.toml`.

## Validation and references

- Run device tests discovered under `src/core` plus affected ADB, work, and
  controller tests.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Mock ADB workflow: [`../../../HOW_TO_mock_adb.md`](../../../HOW_TO_mock_adb.md).
