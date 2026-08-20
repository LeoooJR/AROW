"""Reconcile freshly discovered Android phones with the paired repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from core.devices.phone import (
    Phone,
    PhoneRepository,
    apply_discovered_phone_state,
)
from core.devices.stable_key import StableKey
from logger import logger


@dataclass(frozen=True, slots=True)
class DeviceReconcileResult:
    """Immutable summary for downstream device refresh and simulation cleanup.

    Rebindings contain only collision-resistant old-to-new ADB connection IDs.
    Removed IDs preserve repository order so callers can perform deterministic cleanup.
    """

    changed: bool
    device_id_rebindings: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    removed_device_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _ReconciliationState:
    """Mutable, inspectable state shared by the steps of one reconciliation pass.

    Matched phones are tracked by Python object identity because a stable-key reconnect
    changes the phone's repository key while preserving the existing ``Phone`` object.
    """

    paired_devices: PhoneRepository
    paired_by_stable_key: dict[str, Phone]
    matched_paired_object_ids: set[int] = field(default_factory=set)
    device_id_rebindings: dict[str, str] = field(default_factory=dict)
    changed: bool = False


class ReconciliationEngine:
    """Merge one complete ADB discovery snapshot into a paired-phone repository.

    Exact connection IDs have priority. A changed connection ID may reuse an existing
    phone only through a collision-resistant stable identity, preserving references held
    by simulations and UI state. Phones absent from the snapshot are removed and reported
    to the caller; the engine deliberately performs no cross-domain cleanup itself.
    """

    def reconcile(
        self,
        paired_devices: PhoneRepository,
        discovered_phones: list[Phone],
    ) -> DeviceReconcileResult:
        """Reconcile ``discovered_phones`` and return an immutable change summary."""
        # Normalize the snapshot before matching so duplicate ADB rows cannot update the
        # same repository entry more than once during a pass.
        deduplicated_phones = self._deduplicate_discovered_phones(discovered_phones)
        state = _ReconciliationState(
            paired_devices=paired_devices,
            # Capture stable identities before any connection-ID mutation occurs.
            paired_by_stable_key=paired_devices.index_by_stable_key(),
        )

        for discovered in deduplicated_phones:
            self._reconcile_discovered_phone(state, discovered)

        removed_device_ids = self._remove_unmatched_paired_phones(state)
        if state.changed:
            logger.info(
                "Paired devices reconciled",
                discovered_count=len(deduplicated_phones),
                paired_count=len(paired_devices),
            )
        return DeviceReconcileResult(
            changed=state.changed,
            device_id_rebindings=MappingProxyType(state.device_id_rebindings.copy()),
            removed_device_ids=removed_device_ids,
        )

    @staticmethod
    def _deduplicate_discovered_phones(phones: list[Phone]) -> list[Phone]:
        """Keep the last payload per non-empty ADB ID, matching ADB snapshot semantics."""
        deduplicated: dict[str, Phone] = {}
        for phone in phones:
            device_id = (phone.id or "").strip()
            if not device_id:
                logger.warning(
                    "Discovered phone skipped because its device id is empty",
                    phone_repr=repr(phone),
                )
                continue
            deduplicated[device_id] = phone
        return list(deduplicated.values())

    def _reconcile_discovered_phone(
        self,
        state: _ReconciliationState,
        discovered: Phone,
    ) -> None:
        """Add, retain, or update one normalized discovery payload."""
        paired = self._find_paired_phone(state, discovered)
        if paired is None:
            self._add_discovered_phone(state, discovered)
            return

        state.matched_paired_object_ids.add(id(paired))
        if self._phones_are_unchanged(paired, discovered):
            return
        self._update_paired_phone(state, paired, discovered)

    @staticmethod
    def _find_paired_phone(
        state: _ReconciliationState,
        discovered: Phone,
    ) -> Phone | None:
        """Prefer the transient ADB ID, then safely fall back to stable identity."""
        paired = state.paired_devices.get(discovered.id)
        if paired is not None:
            return paired

        stable_key = (discovered.stable_key or "").strip()
        parsed_key = StableKey.from_value(stable_key)
        # Fingerprint identities can collide across similar handsets, so they must never
        # cause a connection-ID rebind.
        if parsed_key is None or not parsed_key.is_collision_resistant():
            return None
        return state.paired_by_stable_key.get(stable_key)

    @staticmethod
    def _phones_are_unchanged(paired: Phone, discovered: Phone) -> bool:
        """Preserve the complete equality check used by the entrypoint flow."""
        return (
            paired.id == discovered.id
            and paired.state == discovered.state
            and paired.connectivity_type == discovered.connectivity_type
            and paired == discovered
        )

    @staticmethod
    def _add_discovered_phone(
        state: _ReconciliationState,
        discovered: Phone,
    ) -> None:
        """Register a phone that has no paired identity match."""
        state.paired_devices.add(discovered)
        state.matched_paired_object_ids.add(id(discovered))
        state.changed = True

    @staticmethod
    def _update_paired_phone(
        state: _ReconciliationState,
        paired: Phone,
        discovered: Phone,
    ) -> None:
        """Refresh the existing object and re-key its repository entry when required."""
        old_connection_id = paired.id
        connection_id_changed = old_connection_id != discovered.id
        if connection_id_changed:
            # The repository is keyed by ADB ID, so remove the old key before mutating the
            # descriptor and add the same object back under its new key afterward.
            state.paired_devices.remove(paired)

        apply_discovered_phone_state(paired, discovered)

        if connection_id_changed:
            state.paired_devices.add(paired)
            state.device_id_rebindings[old_connection_id] = discovered.id
        state.changed = True

    @staticmethod
    def _remove_unmatched_paired_phones(
        state: _ReconciliationState,
    ) -> tuple[str, ...]:
        """Remove phones absent from the snapshot and report IDs for caller cleanup."""
        removed_device_ids: list[str] = []
        # Iterate over a snapshot because removal mutates the repository. Object identity
        # remains valid even when a matched phone changed its ADB connection ID.
        for paired in list(state.paired_devices):
            if id(paired) in state.matched_paired_object_ids:
                continue
            state.paired_devices.remove(paired)
            removed_device_ids.append(paired.id)
            state.changed = True
        return tuple(removed_device_ids)
