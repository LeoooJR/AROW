"""
Canonical catalog of :class:`~core.work.core_runtime_work.CoreRuntimeWork` types used with
:class:`~core.entrypoint.ModelEntrypoint` and :meth:`~core.entrypoint.ModelEntrypoint.apply_result`.

``CORE_RUNTIME_WORKS`` is the single place to enumerate work/outcome pairs for debugging and
registration. Registrations made only via :func:`~core.entrypoint.register_core_runtime_result_applier`
do not appear in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.collection import Repository
from core.work.authentificate_device_work import (
    AuthenticateDeviceWork,
    AuthentificateDeviceOutcome,
)
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.host_install_identity_work import (
    HostInstallIdentityOutcome,
    HostInstallIdentityWork,
)
from core.work.refresh_known_devices_work import (
    RefreshKnownDevicesOutcome,
    RefreshKnownDevicesWork,
)
from core.work.render_map_work import RenderMapOutcome, RenderMapWork
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome


@dataclass(frozen=True, slots=True)
class CoreRuntimeWorkCatalogEntry:
    """Stable id plus work/outcome types; optional hints for tracing entrypoint methods."""

    id: str
    work_cls: type[CoreRuntimeWork[Any]]
    outcome_cls: type[CoreRuntimeWorkOutcome]
    job_origin: str
    entrypoint_methods: tuple[str, ...] = ()


class CoreRuntimeWorksRepository(Repository[CoreRuntimeWorkCatalogEntry]):
    """Registers all built-in core-runtime work/outcome pairs (see :data:`CORE_RUNTIME_WORKS`)."""

    def __init__(self) -> None:
        super().__init__()
        entries: tuple[CoreRuntimeWorkCatalogEntry, ...] = (
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.startup",
                work_cls=StartupCoreRuntimeWork,
                outcome_cls=StartupOutcome,
                job_origin="startup_core_runtime",
                entrypoint_methods=("ModelEntrypoint.startup",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.authenticate-device",
                work_cls=AuthenticateDeviceWork,
                outcome_cls=AuthentificateDeviceOutcome,
                job_origin="authentification_workflow",
                entrypoint_methods=("ModelEntrypoint.authentificate_device",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.host-install-identity",
                work_cls=HostInstallIdentityWork,
                outcome_cls=HostInstallIdentityOutcome,
                job_origin="host_install_identity",
                entrypoint_methods=("ModelEntrypoint.run_host_install_identity",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.refresh-known-devices",
                work_cls=RefreshKnownDevicesWork,
                outcome_cls=RefreshKnownDevicesOutcome,
                job_origin="refresh_device_list",
                entrypoint_methods=("ModelEntrypoint.refresh_known_devices",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.close",
                work_cls=CloseCoreRuntimeWork,
                outcome_cls=CloseOutcome,
                job_origin="close_core_runtime",
                entrypoint_methods=("ModelEntrypoint.close_core_runtime",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.render-map",
                work_cls=RenderMapWork,
                outcome_cls=RenderMapOutcome,
                job_origin="render_map",
                entrypoint_methods=("ModelEntrypoint.render_map",),
            ),
        )
        self.add_all(list(entries))

        outcomes = [e.outcome_cls for e in entries]
        work_types = [e.work_cls for e in entries]
        job_origins = [e.job_origin for e in entries]
        if len(outcomes) != len(set(outcomes)):
            raise AssertionError(
                "Duplicate outcome_cls in CORE_RUNTIME_WORKS bootstrap"
            )
        if len(work_types) != len(set(work_types)):
            raise AssertionError("Duplicate work_cls in CORE_RUNTIME_WORKS bootstrap")
        if len(job_origins) != len(set(job_origins)):
            raise AssertionError("Duplicate job_origin in CORE_RUNTIME_WORKS bootstrap")


CORE_RUNTIME_WORKS = CoreRuntimeWorksRepository()
