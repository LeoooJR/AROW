"""
Paired worker / apply for persisted host install UUID (``ComputerDescriptor.stable_key``).

Disk I/O runs in :meth:`HostInstallIdentityWork.run`; the Qt main thread applies via
:class:`HostInstallIdentityWork.apply_main_thread` through :meth:`CoreRuntimeModel.apply_result`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from core.application_paths import get_or_create_application_dir
from core.core_runtime_work import CoreRuntimeWork
from core.devices import compute_computer_stable_key
from core.signals import CoreSignal, HostComputerIdentityPayload
from logger import logger

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel

_INSTALL_IDENTITY_FILENAME = "install_identity"


def install_identity_file_path() -> Path:
    """Resolved path for atomic read/write (tests may monkeypatch underlying app data root)."""
    return get_or_create_application_dir() / _INSTALL_IDENTITY_FILENAME


def _read_existing_normalized(path: Path) -> str:
    """Return normalized token or empty string if file unreadable / blank."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    return text.casefold()


def _load_or_create_install_token() -> str:
    """
    Read or exclusive-create persisted install UUID (worker-thread only).

    Uses exclusive create (``open(..., "x")``) on the final path so concurrent first-launches
    yield exactly one stored value; losers read back the winner's UUID.

    Raises:
        OSError: Propagated from filesystem operations.
        RuntimeError: If the file stays empty / unreadable after a create race.
    """
    path = install_identity_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    token = _read_existing_normalized(path)
    if token:
        return token

    # Truncate corrupted empty file so we can recreate.
    if path.is_file():
        path.unlink(missing_ok=True)

    new_token = str(uuid.uuid4())
    try:
        with open(path, "x", encoding="utf-8") as fh:
            fh.write(new_token + "\n")
    except FileExistsError:
        token = _read_existing_normalized(path)
        if token:
            return token
        raise RuntimeError(
            "install_identity file appeared but has no readable token — check permissions"
        ) from None

    return new_token.casefold()


@dataclass(frozen=True, slots=True)
class HostInstallIdentityOutcome:
    """Result of :meth:`HostInstallIdentityWork.run` (worker thread)."""

    install_token: str


class HostInstallIdentityWork(CoreRuntimeWork[HostInstallIdentityOutcome]):
    """
    Persist / load install token on a worker; apply stable_key and emit on the main thread.
    """

    def run(self) -> HostInstallIdentityOutcome:
        return HostInstallIdentityOutcome(install_token=_load_or_create_install_token())

    @staticmethod
    def apply_main_thread(
        model: CoreRuntimeModel, outcome: HostInstallIdentityOutcome
    ) -> None:
        from core.models import CoreRuntimeModel as _CoreRuntimeModel

        if not isinstance(model, _CoreRuntimeModel):
            raise TypeError("apply_main_thread() requires CoreRuntimeModel")
        token = (outcome.install_token or "").strip()
        if not token:
            logger.warning(
                "HostInstallIdentityWork.apply_main_thread: empty token — host stable_key unchanged",
            )
            return
        key = compute_computer_stable_key(token)
        model._host.descriptor.stable_key = key
        model._signal_bus.emit(
            CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED,
            HostComputerIdentityPayload(stable_key=key),
        )
        logger.debug(
            "HostInstallIdentityWork: host install identity applied (stable_key redacted in extras by default)",
        )
