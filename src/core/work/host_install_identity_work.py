"""
Paired worker / apply for persisted host install UUID (``ComputerDescriptor.stable_key``).

Disk I/O runs in :meth:`HostInstallIdentityWork.run`; the Qt main thread applies via
:class:`HostInstallIdentityWork.apply_main_thread` through :meth:`ModelEntrypoint.apply_result`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from core.application_paths import get_or_create_application_dir
from core.devices import compute_computer_stable_key
from core.signals import CoreSignal, HostComputerIdentityPayload
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from logger import logger

if TYPE_CHECKING:
    from core.entrypoint import ModelEntrypoint

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
class HostInstallIdentityOutcome(CoreRuntimeWorkOutcome):
    """Result of :meth:`HostInstallIdentityWork.run` (worker thread)."""

    install_token: str


class HostInstallIdentityWork(CoreRuntimeWork[HostInstallIdentityOutcome]):
    """
    Persist / load install token on a worker; apply stable_key and emit on the main thread.
    """

    def run(self) -> HostInstallIdentityOutcome:
        """
        Load or atomically create the persisted host install UUID
        (AsyncRunner worker thread).

        Delegates to :func:`_load_or_create_install_token`, which reads
        ``install_identity`` under the application data directory or exclusive-
        creates it on first launch. :meth:`apply_main_thread` derives
        ``stable_key`` and emits ``HOST_COMPUTER_IDENTITY_UPDATED``.

        Returns:
            HostInstallIdentityOutcome: ``install_token`` — normalized
            (casefolded) UUID string for main-thread application.

        Raises:
            OSError: Filesystem failure creating the application directory,
            reading, unlinking, or writing ``install_identity`` (includes
            :class:`PermissionError`).
            RuntimeError: Exclusive create raced with another process and the
            resulting file is empty or unreadable.
        """
        return HostInstallIdentityOutcome(install_token=_load_or_create_install_token())

    @staticmethod
    def apply_main_thread(
        model_entrypoint: ModelEntrypoint, outcome: HostInstallIdentityOutcome
    ) -> None:
        from core.entrypoint import ModelEntrypoint as _ModelEntrypoint

        if not isinstance(model_entrypoint, _ModelEntrypoint):
            raise TypeError("apply_main_thread() requires ModelEntrypoint")
        token = (outcome.install_token or "").strip()
        if not token:
            logger.warning(
                "HostInstallIdentityWork.apply_main_thread: empty token — host stable_key unchanged",
            )
            return
        key = compute_computer_stable_key(token)
        model_entrypoint._host.descriptor.stable_key = key
        model_entrypoint._signal_bus.emit(
            CoreSignal.HOST_COMPUTER_IDENTITY_UPDATED,
            HostComputerIdentityPayload(stable_key=key),
        )
        logger.debug(
            "HostInstallIdentityWork: host install identity applied (stable_key redacted in extras by default)",
        )
