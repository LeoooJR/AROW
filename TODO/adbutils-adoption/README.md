# ADButils Findings — AROW Implementation Project

## Purpose

This project converts the `openatx/adbutils` comparative review into an executable
AROW backlog. It is a planning artifact only: items are not implemented merely
because they are listed here.

The upstream reference was read from `openatx/adbutils` `master` on 2026-07-16.
Its `adbutils/` tree reported SHA
`196e061e986d9c405b9c015c5a1e0af814077b57`. Treat upstream code as a source of
ideas and compatibility cases, not as a drop-in runtime dependency.

## Required project rules

- Read `AGENTS.md` before starting any item.
- Keep all ADB execution and protocol code inside `src/core/adb/`.
- Run blocking ADB, file, network, and long-lived monitoring work through
  `src/controller/runner.py` with `JobSpecification` and `AsyncRunner`.
- Keep controllers as orchestration and GUI code as presentation.
- Preserve AROW's subprocess timeouts, retry classification, structured logging,
  redaction, stable identity, mock ADB, and main-thread apply pattern.
- Use `Path` for host paths, immutable tuples for command arguments, and typed
  outcomes at core/controller boundaries.
- Do not add `adbutils` as a runtime dependency unless a separate architectural
  decision explicitly approves it.
- Do not copy upstream code without preserving the MIT license requirements.

## Work packages

| Order | Document | Findings | Depends on |
| ---: | --- | --- | --- |
| 1 | [01-correctness-and-secrets.md](01-correctness-and-secrets.md) | Flexible device parsing, actionable states, disconnect/forget, pairing-secret lifetime | None |
| 2 | [02-connection-workflow.md](02-connection-workflow.md) | Pair/connect/readiness state machine, transport targeting, event-driven tracking | Package 1 |
| 3 | [03-capabilities-and-location.md](03-capabilities-and-location.md) | Capability model, typed shell results, complete mock-location service | Packages 1–2 |
| 4 | [04-device-operations.md](04-device-operations.md) | Sync/file transfer, screenshots, readiness data, helper APK lifecycle | Package 3 |
| 5 | [05-diagnostics.md](05-diagnostics.md) | Logcat/support bundles, optional screen recording | Packages 2–4 |
| 6 | [06-adb-architecture-hardening.md](06-adb-architecture-hardening.md) | Shared executor, immutable commands, history records, enrichment warnings, health probe | Can start after package 1; coordinate with all ADB work |
| — | [07-upstream-guardrails.md](07-upstream-guardrails.md) | Unsafe upstream patterns that must not enter AROW | Applies to every package |
| — | [08-verification-matrix.md](08-verification-matrix.md) | Required test layers and completion evidence | Applies to every package |

## Recommended delivery sequence

1. Land parser/state fixes and secret-lifetime changes first. They are small,
   user-visible, and reduce ambiguity for every later workflow.
2. Implement explicit connect/wait and disconnect semantics before adding the
   tracking stream.
3. Add tracking as a cancellable source of refresh requests; do not let it own
   device repositories or GUI state.
4. Introduce capability and shell-result types before implementing location or
   helper-package behavior.
5. Complete the location service before optional support tooling.
6. Apply architecture hardening incrementally to avoid one oversized rewrite.

## Per-item execution protocol

For each finding, the implementing agent must:

1. inspect the listed AROW files and current tests;
2. confirm the dependency items are complete or explicitly adapt the plan;
3. add parser/unit tests before or alongside implementation;
4. add work/controller integration tests for asynchronous behavior;
5. update `MockAdbState`/`MockAdbClient` for every new ADB command or state;
6. run the narrow tests listed in the finding;
7. run the applicable checks in the verification matrix;
8. record deviations and remaining risks in the PR description or handoff.

## Definition of done

A finding is complete only when its acceptance criteria pass, error and
cancellation paths are tested, no secret or stable identifier is newly exposed,
and the implementation respects the MVC and async boundaries above.

