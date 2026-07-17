# Verification Matrix

## Checks required for every package

1. Run the narrow unit tests for changed parsers/services.
2. Run affected core work and controller callback tests.
3. Run mock ADB integration tests.
4. Run GUI behavior and screenshot tests when presentation changes.
5. Run logger/redaction tests whenever commands, payloads, history, or diagnostics
   change.
6. Run formatting, lint, typing, and security checks used by the repository.
7. Report any check not run and why.

## Coverage matrix

| Package | Required suites/evidence |
| --- | --- |
| 1 | `src/core/adb/tests/test_adb_parser.py`, phone/reconcile tests, authentication work tests, device block/integration tests, logger redaction |
| 2 | ADB retry tests, authentication/controller tests, fake protocol tracker tests, runner cancellation/shutdown tests |
| 3 | parser/protocol tests, simulation lifecycle tests, mock-location integration tests, coordinate redaction evidence |
| 4 | fake Sync protocol tests, transfer cancellation/progress, image validation, readiness block screenshots, package verification tests |
| 5 | bounded stream tests, bundle manifest/redaction tests, atomic export failure tests, consent/recording lifecycle tests if implemented |
| 6 | full `src/core/adb/tests/`, startup/close/preflight tests, history/redaction tests, affected work tests |

## Mandatory failure cases

Every ADB operation must consider and test where applicable:

- missing/non-executable ADB binary;
- daemon unavailable or killed externally;
- unauthorized, offline, absent, or rebound device;
- timeout before and during transfer;
- transient protocol failure followed by success;
- exhausted transient retries;
- permanent authentication/permission/input failure without retry;
- malformed, truncated, oversized, or unexpected output/frame;
- cancellation before start, mid-operation, and during shutdown;
- main-thread apply after runtime/device state changed;
- log/history/support-output redaction.

## Real-device validation checklist

Use only after mock/unit coverage passes. Record platform-tools version, Android
version/API, transport type, and observed outcome without recording raw serials,
pairing codes, or coordinates.

- Pair and connect a supported wireless device.
- Observe unauthorized/offline/ready transitions.
- Disconnect and reconnect without losing saved simulation identity.
- Restart ADB externally and verify health/tracker recovery.
- Start, update, verify, and stop mock location.
- Cancel a running update and close AROW during an active device operation.
- If implemented, verify helper install/update, screenshot, and support export.

## Final project gate

Before declaring the complete TODO project finished:

- all implemented finding acceptance criteria are checked;
- no TODO stubs remain for the core mock-location path;
- the 30-second device refresh is documented as watchdog or removed;
- disconnect and forget semantics are distinct and tested;
- no pairing code or coordinate appears in captured logs/bundles;
- no raw worker thread or unbounded ADB wait was introduced;
- documentation reflects supported Android/platform-tools versions and manual
  recovery steps.

