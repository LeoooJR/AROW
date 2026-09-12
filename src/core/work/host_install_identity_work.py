"""
Paired worker / apply for persisted host install UUID (``ComputerDescriptor.stable_key``).

Disk I/O runs in :meth:`HostInstallIdentityWork.run`; the Qt main thread applies via
:class:`HostInstallIdentityWork.apply_main_thread` through :meth:`ModelEntrypoint.apply_result`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from core.devices.computer import compute_computer_stable_key
from core.entrypoint_protocol import CoreSignalEmitter, HostIdentityEntrypoint
from core.exceptions import CoreException
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome
from core.work.helper import preflight
from logger import logger


def _read_existing_normalized(path: Path) -> str:
    """Return normalized token or empty string if file unreadable / blank."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    return text.casefold()


def _load_or_create_install_token(path: Path) -> str:
    """
    Read or exclusive-create persisted install UUID (worker-thread only).

    Uses exclusive create (``open(..., "x")``) on the final path so concurrent first-launches
    yield exactly one stored value; losers read back the winner's UUID.

    Raises:
        OSError: Propagated from filesystem operations.
        RuntimeError: If the file stays empty / unreadable after a create race.
    """
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


class HostInstallIdentityError(CoreException):
    """Host install identity work failed."""

    def __init__(self, reason: str) -> None:
        """Initialize a host-install identity failure with its reason."""
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class HostInstallIdentityOutcome(CoreRuntimeWorkOutcome):
    """Result of :meth:`HostInstallIdentityWork.run` (worker thread)."""

    install_token: str


class HostInstallIdentityWork(CoreRuntimeWork[HostInstallIdentityOutcome]):
    """
    Persist / load install token on a worker; apply stable_key and emit on the main thread.
    """

    def __init__(self, *, install_identity_file: Path) -> None:
        """Initialize work for an install-identity file.

        Args:
            install_identity_file: Path read or created by the worker.
        """
        self._install_identity_file = install_identity_file

    @preflight()
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
        return HostInstallIdentityOutcome(
            install_token=_load_or_create_install_token(self._install_identity_file)
        )

    @staticmethod
    def apply_main_thread(
        model_entrypoint: CoreSignalEmitter, outcome: HostInstallIdentityOutcome
    ) -> None:
        """Apply a persisted install identity to the host model.

        Args:
            model_entrypoint: Main-thread host-identity boundary.
            outcome: Worker result containing the normalized install token.
        """
        host_entrypoint = cast(HostIdentityEntrypoint, model_entrypoint)
        token = (outcome.install_token or "").strip()
        if not token:
            logger.warning(
                "Host stable key was not updated because the install token is empty",
            )
            return
        key = compute_computer_stable_key(token)
        host_entrypoint.set_host_identity(key)
        logger.debug(
            "Host install identity applied",
        )

    @staticmethod
    def apply_failure_main_thread(
        model_entrypoint: CoreSignalEmitter, error: BaseException
    ) -> None:
        """Emit a generic core error for an install-identity failure."""
        HostInstallIdentityWork.emit_generic_error(
            model_entrypoint,
            source="HostInstallIdentityWork",
            message=str(error),
            error=error,
        )
