"""
Core domain signals: typed payloads and signal token definitions.

When adding a new core signal:
1. Add the payload dataclass.
2. Add a constant on :class:`CoreSignals`.
3. Register scope/dependency metadata when the signal participates in those rules.

Payload design rules (controllers must not depend on live core domain objects):
- Prefer the smallest set of primitive fields (``str``, ``int``, ``float``, ``bool``).
- ``pathlib.Path`` is allowed for filesystem resources; it is not a custom core domain type.
- When a custom core object must be represented, serialize it (for example via
  ``serialize()``) into a ``dict`` and carry only that dict in the payload.
- Do not place live core domain instances (``Phone``, ``Simulation``, ``Location``,
  ``AdbBinary``, ``Exception``, etc.) on core signal payloads.
- When a signal payload changes, update every emitter, subscriber, controller bridge,
  GUI consumer, and test on the full pathway for that signal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True, slots=True)
class CoreSignal(Generic[PayloadT]):
    """
    Typed signal token binding a stable string identifier to one payload type.

    Generic typing lets callers subscribe and emit without overload boilerplate.
    """

    value: str
    payload_type: type[PayloadT]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class HostComputerIdentityPayload:
    """Emitted when persisted install identity has been applied to the host descriptor."""

    stable_key: str


@dataclass(frozen=True, slots=True)
class AdbServerStartedPayload:
    """Payload emitted when the ADB server starts."""

    adb_binary_path: str


@dataclass(frozen=True, slots=True)
class AdbServerStoppedPayload:
    """Payload emitted when the ADB server stops."""

    adb_binary_path: str


@dataclass(frozen=True, slots=True)
class DevicesUpdatedPayload:
    """Payload emitted when the known/connected devices list changes."""

    devices: list[dict[str, object]]
    device_id_rebindings: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeviceAuthentificationSucceededPayload:
    """Payload emitted when a device is connected successfully."""

    device: dict[str, object]


@dataclass(frozen=True, slots=True)
class DeviceAuthentificationFailedPayload:
    """Payload emitted when a device authentification fails."""

    ip: str
    port: int
    association_code: str
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationCreatedPayload:
    """Payload emitted when a simulation is created."""

    simulation_id: str
    device_id: str
    device_name: str


@dataclass(frozen=True, slots=True)
class SimulationRestoredPayload:
    """Payload emitted when a simulation is restored."""

    simulation_id: str
    device_id: str
    device_name: str


@dataclass(frozen=True, slots=True)
class SimulationDeletedPayload:
    """Payload emitted when a simulation is deleted."""

    simulation_id: str
    device_id: str | None = None


@dataclass(frozen=True, slots=True)
class SimulationCreationFailedPayload:
    """Payload emitted when simulation creation is rejected."""

    device_id: str
    device_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationDeleteSkippedPayload:
    """Payload emitted when simulation deletion is a no-op for a device."""

    device_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationStateChangedPayload:
    """Payload emitted when simulation execution state changes."""

    simulation_id: str
    active: bool


@dataclass(frozen=True, slots=True)
class SimulationPositionChangedPayload:
    """Payload emitted when the effective simulation position changes."""

    simulation_id: str


@dataclass(frozen=True, slots=True)
class SimulationLocationValidationRequestedPayload:
    """Payload requesting async validation of a map milestone for a simulation."""

    simulation_id: str
    km: int
    line_code: str
    line_troncon: int
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class SimulationLocationValidatedPayload:
    """Payload emitted when a map milestone location passes referentiel validation."""

    simulation_id: str
    lat: float
    lon: float
    km: int
    line_id: str
    line_code: str
    line_troncon: int
    line_type: str
    line_label: str
    label: str
    milestone_type: Literal["Kilometer", "Hectometer"]
    line_geometry_wkb_b64: str


@dataclass(frozen=True, slots=True)
class SimulationLocationRejectedPayload:
    """Payload emitted when a map milestone location is rejected."""

    simulation_id: str
    km: int
    line_code: str
    line_troncon: int
    lat: float
    lon: float
    reason: str


@dataclass(frozen=True, slots=True)
class SimulationMapFileChangedPayload:
    """Payload emitted when the simulation map file changes."""

    simulation_id: str
    map_file_path: Path


@dataclass(frozen=True, slots=True)
class AdbServerStateChangedPayload:
    """Payload emitted when ADB server running status changes."""

    running: bool


@dataclass(frozen=True, slots=True)
class ErrorRaisedPayload:
    """Generic payload for recoverable domain errors."""

    source: str
    message: str
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class LogMessagePayload:
    """Payload carrying domain logs to outer layers (controller/UI)."""

    level: str
    message: str


@dataclass(frozen=True, slots=True)
class ActivityLogFileUpdatedPayload:
    """Payload emitted when the activity log file is updated."""

    path: Path


@dataclass(frozen=True, slots=True)
class MapRenderedPayload:
    """Payload emitted when map HTML has been written for a simulation."""

    simulation_id: str
    html_path: Path


@dataclass(frozen=True, slots=True)
class MapRenderFailedPayload:
    """Payload emitted when map rendering fails for a simulation."""

    simulation_id: str
    reason: str


class CoreSignals:
    """Namespace of typed core signal tokens."""

    ADB_SERVER_STARTED = CoreSignal("adb.server.started", AdbServerStartedPayload)
    ADB_SERVER_STOPPED = CoreSignal("adb.server.stopped", AdbServerStoppedPayload)
    ADB_SERVER_STATE_CHANGED = CoreSignal(
        "adb.server.state.changed", AdbServerStateChangedPayload
    )
    DEVICE_AUTHENTIFICATION_SUCCEEDED = CoreSignal(
        "device.authentification.succeeded",
        DeviceAuthentificationSucceededPayload,
    )
    DEVICE_AUTHENTIFICATION_FAILED = CoreSignal(
        "device.authentification.failed",
        DeviceAuthentificationFailedPayload,
    )
    DEVICES_UPDATED = CoreSignal("devices.updated", DevicesUpdatedPayload)
    SIMULATION_CREATED = CoreSignal("simulation.created", SimulationCreatedPayload)
    SIMULATION_RESTORED = CoreSignal("simulation.restored", SimulationRestoredPayload)
    SIMULATION_DELETED = CoreSignal("simulation.deleted", SimulationDeletedPayload)
    SIMULATION_CREATION_FAILED = CoreSignal(
        "simulation.creation.failed",
        SimulationCreationFailedPayload,
    )
    SIMULATION_DELETE_SKIPPED = CoreSignal(
        "simulation.delete.skipped",
        SimulationDeleteSkippedPayload,
    )
    SIMULATION_STATE_CHANGED = CoreSignal(
        "simulation.state.changed", SimulationStateChangedPayload
    )
    SIMULATION_POSITION_CHANGED = CoreSignal(
        "simulation.position.changed", SimulationPositionChangedPayload
    )
    SIMULATION_LOCATION_VALIDATION_REQUESTED = CoreSignal(
        "simulation.location.validation.requested",
        SimulationLocationValidationRequestedPayload,
    )
    SIMULATION_LOCATION_VALIDATED = CoreSignal(
        "simulation.location.validated",
        SimulationLocationValidatedPayload,
    )
    SIMULATION_LOCATION_REJECTED = CoreSignal(
        "simulation.location.rejected",
        SimulationLocationRejectedPayload,
    )
    SIMULATION_MAP_FILE_CHANGED = CoreSignal(
        "simulation.map.file.changed",
        SimulationMapFileChangedPayload,
    )
    ERROR_RAISED = CoreSignal("error.raised", ErrorRaisedPayload)
    LOG_MESSAGE = CoreSignal("log.message", LogMessagePayload)
    HOST_COMPUTER_IDENTITY_UPDATED = CoreSignal(
        "host.computer.identity.updated",
        HostComputerIdentityPayload,
    )
    ACTIVITY_LOG_FILE_UPDATED = CoreSignal(
        "activity.log.file.updated",
        ActivityLogFileUpdatedPayload,
    )
    MAP_RENDERED = CoreSignal("map.rendered", MapRenderedPayload)
    MAP_RENDER_FAILED = CoreSignal("map.render.failed", MapRenderFailedPayload)


class CoreSignalDependencyError(RuntimeError):
    """Raised when a core signal is emitted without required prior emissions."""

    def __init__(
        self,
        *,
        signal: CoreSignal[Any],
        missing: tuple[CoreSignal[Any], ...],
        scope: str | None = None,
    ) -> None:
        """Initialize an error describing unmet signal dependencies.

        Args:
            signal: Signal whose emission was rejected.
            missing: Prior signals that could satisfy the dependency.
            scope: Optional entity scope that must match prior emissions.
        """
        self.signal = signal
        self.missing = missing
        self.scope = scope
        if scope is None:
            message = (
                f"Cannot emit {signal!s}: requires prior "
                f"{', '.join(str(item) for item in missing)}"
            )
        else:
            message = (
                f"Cannot emit {signal!s} for scope {scope!r}: requires prior "
                f"{', '.join(str(item) for item in missing)} with the same scope"
            )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CoreSignalDependencyRule:
    """One dependency requirement: any listed signal may satisfy the rule."""

    any_of: tuple[CoreSignal[Any], ...]
    match_scope_from: str | None = None


@dataclass(frozen=True, slots=True)
class CoreSignalEmission:
    """One recorded core signal emission for debugging and dependency checks."""

    signal: CoreSignal[Any]
    payload: object
    scope: str | None = None


# Payload field used to index scoped emissions for dependency checks.
CORE_SIGNAL_SCOPE_FIELDS: Mapping[CoreSignal[Any], str] = {
    CoreSignals.ADB_SERVER_STARTED: "adb_binary_path",
    CoreSignals.ADB_SERVER_STOPPED: "adb_binary_path",
    CoreSignals.SIMULATION_CREATED: "simulation_id",
    CoreSignals.SIMULATION_RESTORED: "simulation_id",
    CoreSignals.SIMULATION_DELETED: "simulation_id",
    CoreSignals.SIMULATION_STATE_CHANGED: "simulation_id",
    CoreSignals.SIMULATION_POSITION_CHANGED: "simulation_id",
    CoreSignals.SIMULATION_LOCATION_VALIDATION_REQUESTED: "simulation_id",
    CoreSignals.SIMULATION_LOCATION_VALIDATED: "simulation_id",
    CoreSignals.SIMULATION_LOCATION_REJECTED: "simulation_id",
    CoreSignals.SIMULATION_MAP_FILE_CHANGED: "simulation_id",
    CoreSignals.MAP_RENDERED: "simulation_id",
    CoreSignals.MAP_RENDER_FAILED: "simulation_id",
}

# Required prior emissions before a signal may be published on the core bus.
CORE_SIGNAL_DEPENDENCIES: Mapping[
    CoreSignal[Any], tuple[CoreSignalDependencyRule, ...]
] = {
    CoreSignals.ADB_SERVER_STOPPED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.ADB_SERVER_STARTED,),
            match_scope_from="adb_binary_path",
        ),
    ),
    CoreSignals.DEVICE_AUTHENTIFICATION_SUCCEEDED: (
        CoreSignalDependencyRule(any_of=(CoreSignals.ADB_SERVER_STARTED,)),
    ),
    CoreSignals.DEVICES_UPDATED: (
        CoreSignalDependencyRule(any_of=(CoreSignals.ADB_SERVER_STARTED,)),
    ),
    CoreSignals.SIMULATION_CREATED: (
        CoreSignalDependencyRule(any_of=(CoreSignals.DEVICES_UPDATED,)),
    ),
    CoreSignals.SIMULATION_RESTORED: (
        CoreSignalDependencyRule(any_of=(CoreSignals.DEVICES_UPDATED,)),
    ),
    CoreSignals.SIMULATION_DELETED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.SIMULATION_STATE_CHANGED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.SIMULATION_POSITION_CHANGED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.SIMULATION_LOCATION_VALIDATION_REQUESTED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.SIMULATION_LOCATION_VALIDATED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.SIMULATION_LOCATION_REJECTED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.SIMULATION_MAP_FILE_CHANGED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.MAP_RENDERED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
    CoreSignals.MAP_RENDER_FAILED: (
        CoreSignalDependencyRule(
            any_of=(CoreSignals.SIMULATION_CREATED, CoreSignals.SIMULATION_RESTORED),
            match_scope_from="simulation_id",
        ),
    ),
}


def extract_core_signal_scope(signal: CoreSignal[Any], payload: object) -> str | None:
    """Return the scoped entity key carried by *payload*, when defined for *signal*."""
    field_name = CORE_SIGNAL_SCOPE_FIELDS.get(signal)
    if field_name is None:
        return None
    value = getattr(payload, field_name, None)
    if value is None:
        return None
    return str(value)
