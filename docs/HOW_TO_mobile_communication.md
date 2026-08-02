# How AROW Desktop communicates with AROW Mobile

## Purpose

AROW Desktop and AROW Mobile are separate applications maintained in separate
repositories, but they participate in one simulation workflow.

This document defines the desktop side of their communication contract:

- what Desktop sends to Mobile;
- what Desktop expects Mobile to return;
- when Desktop may consider a command successful;
- how ordering, reconnection, compatibility, and failures are handled.

Implementation details internal to Mobile are outside Desktop's scope.

## Current status

The cross-application protocol is not implemented yet. The message names and
structures below define the target contract and must be finalized jointly before
either repository treats them as stable.

Do not claim that desktop-to-mobile synchronization, mock-location activation, or
telemetry exchange already works end to end.

The current desktop simulation `active` flag describes desired desktop state. It
does not prove that Mobile has applied a mock location.

## Roles and authority

Desktop owns:

- operator intent;
- the selected device and simulation;
- the desired simulation lifecycle;
- validated railway positions;
- the desired target location;
- command ordering and correlation.

Mobile owns:

- Android capabilities and readiness;
- whether a command was received and accepted;
- whether the requested state was actually applied;
- the current on-device lifecycle state;
- Android platform errors;
- mobile-generated status and location telemetry.

Desktop communicates **desired state**. Mobile reports **applied state**.

Desktop must not treat command dispatch, transport delivery, or a `received`
acknowledgement as successful application.

## Transport independence

The message contract must remain independent from the transport used to carry it.
Communication may later use ADB, Android intents, a socket, WebSocket, or another
authenticated channel without changing message meaning.

Transport-specific framing, connection management, retry behavior, and
authentication belong behind a desktop communication boundary. GUI code must not
send transport messages directly.

## Common message envelope

Every exchanged message must contain:

```json
{
  "protocol_version": "1.0",
  "message_id": "unique-message-id",
  "correlation_id": null,
  "type": "simulation.location.set",
  "sent_at": "2026-07-30T12:00:00Z",
  "device_id": "opaque-device-id",
  "simulation_id": "simulation-id",
  "sequence": 42,
  "payload": {}
}
```

Field meanings:

- `protocol_version`: negotiated major and minor contract version.
- `message_id`: globally unique identifier used for deduplication.
- `correlation_id`: identifier of the message being answered, or `null`.
- `type`: stable message type.
- `sent_at`: UTC ISO 8601 timestamp.
- `device_id`: opaque protocol-level target-device identifier.
- `simulation_id`: affected simulation, or `null` for peer-level messages.
- `sequence`: monotonically increasing revision within one simulation, or `null`
  when ordering does not apply.
- `payload`: message-specific data.

Desktop must not expose transient transport identifiers as permanent protocol
identity. Mobile-visible identifiers are opaque and must be treated as sensitive.

## Messages Desktop sends

### `peer.hello`

Desktop starts every new or restored session with protocol negotiation.

Payload:

```json
{
  "supported_protocol_versions": ["1.0"],
  "desktop_instance_id": "opaque-desktop-id"
}
```

Desktop must not send simulation commands until:

1. Mobile returns its supported versions;
2. both peers select a compatible version;
3. Mobile reports its capabilities and readiness;
4. reconciliation completes after a reconnect.

If no compatible version exists, Desktop must surface an incompatibility state
rather than attempting best-effort commands with unknown semantics.

### `peer.capabilities.request`

Desktop requests Mobile's current platform capabilities and readiness.

Desktop expects Mobile to report at least:

- mobile application version;
- supported protocol versions;
- Android API level;
- mock-location support;
- mock-location-provider selection;
- required permission state;
- background-execution availability;
- location-services state;
- current connection and execution state.

Desktop uses capability results to enable, disable, or explain operator actions.
It must not guess readiness from the Android version alone.

### `simulation.configure`

Desktop creates or replaces the mobile-side configuration for a simulation.

Payload:

```json
{
  "target_location": {
    "lat": 48.8566,
    "lon": 2.3522
  },
  "railway_position": {
    "line_id": "opaque-line-id",
    "line_code": "001000",
    "section": 1,
    "kilometer": 12,
    "label": "optional display label"
  }
}
```

`railway_position` may be `null` for a free coordinate.

Desktop is responsible for validating railway referential data before sending it.
Mobile may validate structure and platform constraints but does not need to
reproduce the desktop railway referential.

Configuration does not imply that the simulation has started.

### `simulation.start`

Desktop requests that Mobile apply the current configuration and enter the
`running` state.

Desktop must keep desired and applied lifecycle states separate while the command
is pending. It may present a transitional state such as `starting`, but must not
present the simulation as applied until Mobile returns an `applied` result or an
equivalent state snapshot.

### `simulation.location.set`

Desktop updates the desired location for an existing simulation.

Payload:

```json
{
  "location": {
    "lat": 48.8566,
    "lon": 2.3522,
    "altitude_m": null,
    "accuracy_m": null,
    "bearing_deg": null,
    "speed_mps": null
  },
  "railway_position": {
    "line_id": "opaque-line-id",
    "line_code": "001000",
    "section": 1,
    "kilometer": 12,
    "label": "optional display label"
  }
}
```

Rules:

- Coordinates use WGS84 decimal degrees.
- Latitude is in `[-90, 90]`.
- Longitude is in `[-180, 180]`.
- Coordinate order is always `lat`, then `lon`.
- Optional motion values may be `null`.
- `railway_position` supplies descriptive context; `location` is what Mobile
  applies.
- Sending a location update must not implicitly start a stopped simulation unless
  a future protocol version defines that behavior explicitly.

Desktop assigns a new sequence to every desired-state revision. It must never
reuse one sequence for two different payloads.

### `simulation.pause`

Desktop requests temporary suspension while preserving resumable state.

Desktop must wait for Mobile to report `paused`. The protocol must expose whether
Mobile continues presenting the last mock location while paused; Desktop must not
infer that behavior.

### `simulation.resume`

Desktop requests that Mobile continue a paused simulation using the latest
accepted configuration.

Desktop must handle a rejection when Mobile no longer has resumable state, such
as after process death, provider revocation, or state cleanup.

### `simulation.stop`

Desktop requests termination of the simulation.

The requested location cleanup policy is explicit:

```json
{
  "clear_mock_location": true
}
```

Desktop must wait for Mobile's applied `stopped` state. If Android cannot clear
the last location as requested, Desktop must surface the limitation rather than
recording unqualified success.

### `simulation.delete`

Desktop requests removal of retained mobile-side state for a stopped simulation.

Deletion is idempotent. An already-absent simulation is a successful no-op unless
Mobile reports a conflicting active resource.

Desktop should stop a running simulation before deleting it. Deletion must not be
used as an implicit emergency stop unless that behavior is explicitly added to
the protocol.

### `simulation.state.request`

Desktop requests Mobile's current applied state for one simulation.

Desktop uses this message when:

- a command result is missing or ambiguous;
- the UI needs authoritative applied state;
- a timeout occurs;
- a simulation may have changed outside the current desktop session.

### `peer.state.request`

Desktop requests a complete reconciliation snapshot after startup, reconnection,
or detected state divergence.

Desktop must reconcile against Mobile's reported state before sending new
incremental commands. It must not assume that mobile process state survived a
disconnect.

### `heartbeat`

Desktop checks that the peer and executor remain responsive.

A heartbeat does not mutate simulation state. Missed heartbeats indicate unknown
connectivity, not proof that Android stopped applying the last location.

## Messages Desktop receives

### `peer.hello.result`

Mobile returns:

- its supported protocol versions;
- mobile application version;
- mobile instance or installation identifier;
- the selected compatible version, when one exists;
- a structured incompatibility error otherwise.

Desktop must persist negotiated session state only for the lifetime and identity
for which it remains valid.

### `peer.capabilities`

Mobile reports its current capabilities and readiness.

Capabilities may change while connected. Desktop must accept updated capability
messages, revise available actions, and avoid sending commands that Mobile has
declared unsupported.

### `command.result`

Every desktop command must eventually receive a result correlated with the
desktop `message_id`.

Example:

```json
{
  "protocol_version": "1.0",
  "message_id": "mobile-response-id",
  "correlation_id": "desktop-command-id",
  "type": "command.result",
  "sent_at": "2026-07-30T12:00:01Z",
  "device_id": "opaque-device-id",
  "simulation_id": "simulation-id",
  "sequence": 42,
  "payload": {
    "status": "applied",
    "error": null
  }
}
```

Supported result statuses:

- `received`: parsed and queued, but not yet applied;
- `applied`: requested state successfully applied;
- `rejected`: received but not accepted;
- `failed`: execution began but failed;
- `superseded`: replaced by a newer sequence;
- `duplicate`: the same message was already processed.

Only `applied` confirms successful execution. `duplicate` may confirm success only
when the response also carries the original terminal result or Desktop verifies
state with a snapshot.

### `simulation.state.snapshot`

Mobile reports authoritative applied state:

```json
{
  "known": true,
  "lifecycle": "running",
  "latest_sequence": 42,
  "target_location": {
    "lat": 48.8566,
    "lon": 2.3522
  },
  "applied_location": {
    "lat": 48.8566,
    "lon": 2.3522
  },
  "provider_ready": true,
  "last_error": null
}
```

Shared lifecycle values:

- `unconfigured`
- `configured`
- `starting`
- `running`
- `paused`
- `stopping`
- `stopped`
- `error`

Desktop must preserve the distinction between `target_location` and
`applied_location`. When they differ, the UI and logs must describe the state as
pending, failed, stale, or otherwise unsynchronized.

### `peer.state.snapshot`

Mobile returns a complete reconciliation view:

- negotiated protocol version;
- current capabilities and readiness;
- known simulation, if any;
- applied lifecycle state;
- latest accepted sequence;
- latest target and applied locations;
- last command result or execution error.

Desktop uses this snapshot to decide whether to:

- accept Mobile's existing applied state;
- resend a newer desired revision;
- stop an unexpected mobile simulation;
- mark the simulation as divergent and require operator action.

Destructive reconciliation must never rely only on a weak or ambiguous device
identity.

### `telemetry.location`

When supported and enabled, Mobile may report device-generated location telemetry.

Telemetry must identify what it represents, such as:

- physical or provider-observed location;
- effective application-visible location;
- applied mock location.

Desktop must not label telemetry as `real_location` unless the payload semantics
explicitly guarantee that meaning.

Telemetry samples should include their observation timestamp and may include
accuracy, altitude, bearing, and speed.

### `telemetry.status`

Mobile may report asynchronous changes such as:

- mock provider revoked;
- required permission changed;
- location services disabled;
- background execution restricted;
- simulation interrupted;
- unrecoverable Android platform error.

Desktop must update applied state and operator feedback even when no command is
currently pending.

### `heartbeat.result`

Mobile confirms responsiveness without changing simulation state.

Desktop should track connection health separately from simulation lifecycle.

## Structured errors

Desktop consumes stable machine-readable error codes and treats the accompanying
message as user-facing context.

Example:

```json
{
  "status": "rejected",
  "error": {
    "code": "MOCK_PROVIDER_NOT_SELECTED",
    "message": "Select AROW as the mock location application.",
    "retryable": false
  }
}
```

Desktop must not parse error messages to determine behavior.

Expected error families include:

- protocol or version incompatibility;
- invalid or malformed payload;
- wrong target device;
- unknown simulation;
- stale or conflicting sequence;
- capability unavailable;
- permission or provider readiness failure;
- Android execution failure;
- authentication or authorization failure;
- internal mobile failure.

The shared contract must define stable codes before release.

## Desktop command lifecycle

Desktop tracks each command through explicit stages:

```text
created -> dispatched -> received -> applied
                              \-> rejected
                              \-> failed
                              \-> superseded
```

Transport failure or timeout produces `unknown`, not automatic `failed`, because
Mobile may have applied a command without successfully returning its result.

For an unknown outcome, Desktop should request a state snapshot before retrying a
non-idempotent action.

## Ordering and idempotency

- Every command has a unique `message_id`.
- Reusing a `message_id` with a different payload is forbidden.
- Desired-state changes carry monotonically increasing per-simulation sequences.
- A lower sequence cannot overwrite a newer desired or applied state.
- Equal sequences with different payloads are conflicts.
- Retries reuse the original `message_id`; they do not create a logically new
  command.
- Desktop must tolerate duplicate results.
- Results for deleted simulations or superseded sequences must not restore stale
  UI or model state.
- Coalescing location changes is allowed before dispatch, but a dispatched command
  retains its identity and terminal result.

## Reconnection and reconciliation

After connection loss:

1. Mark transport state as disconnected or unknown.
2. Preserve desired desktop state.
3. Do not assume Mobile stopped applying its last location.
4. Re-negotiate the protocol after reconnect.
5. Request capabilities and a peer state snapshot.
6. Compare Mobile's latest sequence and applied state with Desktop's desired state.
7. Resume incremental commands only after reconciliation.

Desktop must not blindly replay every historical command. It should send the
minimum command needed to converge Mobile onto the current desired state.

## Compatibility

- Negotiate versions during `peer.hello`.
- Unknown additive fields are ignored within a compatible major version.
- Existing fields must not be silently reinterpreted.
- Unsupported major versions are rejected clearly.
- Breaking changes require a new major protocol version.
- Message types, lifecycle values, capability names, and error codes become stable
  public contracts once released.

Maintain canonical JSON fixtures that both repositories validate.

## Security and privacy

- Authenticate Mobile before sending simulation data.
- Confirm that the peer is authorized for the addressed device and simulation.
- Treat coordinates, device identifiers, and execution history as sensitive.
- Never log pairing codes, credentials, raw hardware serials, authentication
  tokens, or exact coordinates.
- Preserve the existing ADB and logger redaction guarantees when a transport is
  added.
- Bound message sizes, timeouts, retries, and retained deduplication state.
- Reject malformed or unauthenticated messages before applying them to desktop
  model state.

## Desktop implementation boundaries

When this protocol is implemented:

- Transport and serialization belong in `src/core`, behind typed interfaces.
- GUI code emits user intent and renders state; it does not construct wire
  messages.
- Controllers orchestrate connection and asynchronous work through the existing
  shared runner rather than creating ad-hoc threads.
- Mobile results are converted into typed core payloads before being forwarded to
  controllers or the GUI.
- Blocking transport operations never run on the Qt main thread.
- Desired desktop state and reported mobile state remain separately modeled.
- Shutdown explicitly settles, cancels, or preserves pending command state.

Tests use a fake mobile peer and `MockAdb`. They must not require a real Android
device, live network service, credentials, or user-specific pairing state.

## Cross-repository change rule

Any change to a mobile-visible message, field, lifecycle value, capability, or
error code is a cross-repository contract change.

Such a change must include:

1. compatibility analysis;
2. matching schema or fixture updates in both repositories;
3. producer and consumer tests;
4. tests for malformed input, duplicates, stale sequences, reconnects, timeouts,
   and unsupported versions;
5. a safe release order or feature-negotiation strategy.

Do not implement Desktop messages based only on assumptions about what Mobile will
accept. Stabilize the shared contract first.
