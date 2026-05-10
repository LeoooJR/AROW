"""
Canonical catalog of :class:`~core.work.core_runtime_work.CoreRuntimeWork` types used with
:class:`~core.models.CoreRuntimeModel` and :meth:`~core.models.CoreRuntimeModel.apply_result`.

``CORE_RUNTIME_WORKS`` is the single place to enumerate work/outcome pairs for debugging and
registration. Registrations made only via :func:`~core.models.register_core_runtime_result_applier`
do not appear in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from collection import Repository
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
from core.work.startup_work import StartupCoreRuntimeWork, StartupOutcome


@dataclass(frozen=True, slots=True)
class CoreRuntimeWorkCatalogEntry:
    """Stable id plus work/outcome types; optional hints for tracing model entrypoints."""

    id: str
    work_cls: type[CoreRuntimeWork[Any]]
    outcome_cls: type[CoreRuntimeWorkOutcome]
    model_methods: tuple[str, ...] = ()


class CoreRuntimeWorksRepository(Repository[CoreRuntimeWorkCatalogEntry]):
    """Registers all built-in core-runtime work/outcome pairs (see :data:`CORE_RUNTIME_WORKS`)."""

    def __init__(self) -> None:
        super().__init__()
        entries: tuple[CoreRuntimeWorkCatalogEntry, ...] = (
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.startup",
                work_cls=StartupCoreRuntimeWork,
                outcome_cls=StartupOutcome,
                model_methods=("CoreRuntimeModel.startup",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.authenticate-device",
                work_cls=AuthenticateDeviceWork,
                outcome_cls=AuthentificateDeviceOutcome,
                model_methods=("CoreRuntimeModel.authentificate_device",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.host-install-identity",
                work_cls=HostInstallIdentityWork,
                outcome_cls=HostInstallIdentityOutcome,
                model_methods=("CoreRuntimeModel.run_host_install_identity",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.refresh-known-devices",
                work_cls=RefreshKnownDevicesWork,
                outcome_cls=RefreshKnownDevicesOutcome,
                model_methods=("CoreRuntimeModel.refresh_known_devices",),
            ),
            CoreRuntimeWorkCatalogEntry(
                id="core-runtime.close",
                work_cls=CloseCoreRuntimeWork,
                outcome_cls=CloseOutcome,
                model_methods=("CoreRuntimeModel.close_core_runtime",),
            ),
        )
        self.add_all(list(entries))

        outcomes = [e.outcome_cls for e in entries]
        work_types = [e.work_cls for e in entries]
        if len(outcomes) != len(set(outcomes)):
            raise AssertionError(
                "Duplicate outcome_cls in CORE_RUNTIME_WORKS bootstrap"
            )
        if len(work_types) != len(set(work_types)):
            raise AssertionError("Duplicate work_cls in CORE_RUNTIME_WORKS bootstrap")


CORE_RUNTIME_WORKS = CoreRuntimeWorksRepository()
