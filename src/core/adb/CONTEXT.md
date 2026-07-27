# ADB context

## Purpose

`core.adb` owns bundled ADB binary discovery, command construction and parsing,
server control, client operations, exceptions, and the deterministic `MockAdb`
implementation.

## Boundaries and philosophy

- Keep every ADB subprocess and protocol operation in this package. GUI and
  controllers must use model APIs rather than invoking ADB directly.
- Never pair, connect, disconnect, start or stop spoofing on, or otherwise mutate
  a real device unless the user explicitly requests it.
- Default development and automated tests to `MockAdb`; never use an attached
  device as an incidental test target.
- Preserve argument-safe subprocess construction, timeouts, return-code handling,
  exception translation, and logging redaction.
- Never expose pairing codes, credentials, or sensitive device data in logs or
  errors.

## Primary dependencies

- Python **subprocess** and bundled platform tools implement the ADB boundary.
- **Tenacity** supports bounded retry behavior where configured.
- **Loguru** records redacted operational diagnostics.
- **pytest** tests clients, commands, parsers, and server behavior with mocks only.

Versions remain in `pyproject.toml`.

## Validation and references

- Run the ADB tests under `src/core/adb/tests` plus affected `core/work` and
  controller tests.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Mock development workflow:
  [`../../../HOW_TO_mock_adb.md`](../../../HOW_TO_mock_adb.md).
