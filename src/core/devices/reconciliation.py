"""Reconcile physical phones and their current ADB connections."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping

from core.devices.phone import Phone, PhoneRepository
from core.devices.stable_key import FirstTierStableKey, StableKey
from logger import logger


@dataclass(frozen=True, slots=True)
class DeviceReconcileResult:
    """Immutable physical-phone reconciliation summary.

    Attributes:
        changed: Whether repository-visible state changed.
        phone_id_rebindings: Previous-to-current physical identity mappings.
        removed_phone_ids: Physical identities removed from the repository.
    """

    changed: bool
    phone_id_rebindings: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    removed_phone_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _ReconciliationState:
    """Mutable state shared by one reconciliation pass.

    Attributes:
        paired_devices: Repository being reconciled.
        paired_by_stable_identity: Tier-1 identity index captured before updates.
        matched_paired_object_ids: Python identities of already matched phones.
        phone_id_rebindings: Physical identity changes produced by the pass.
        changed: Whether any repository-visible state changed.
    """

    paired_devices: PhoneRepository
    paired_by_stable_identity: dict[FirstTierStableKey, Phone]
    matched_paired_object_ids: set[int] = field(default_factory=set)
    phone_id_rebindings: dict[str, str] = field(default_factory=dict)
    changed: bool = False


def _tier_one_value(phone: Phone) -> str | None:
    """Return a phone's serialized Tier-1 identity when available.

    Args:
        phone: Phone whose stable key should be parsed.

    Returns:
        The serialized Tier-1 value, or ``None`` for missing and Tier-2 keys.
    """
    parsed = StableKey.from_value(phone.stable_key)
    return parsed.value if isinstance(parsed, FirstTierStableKey) else None


class ReconciliationEngine:
    """Merge a complete ADB snapshot into physical-phone aggregates.

    Exact endpoint ownership takes precedence over Tier-1 stable identity. Each
    canonical phone can be consumed only once per pass, preventing simultaneous
    USB and Wi-Fi observations from rebinding the same aggregate twice.
    """

    def reconcile(
        self,
        paired_devices: PhoneRepository,
        discovered_phones: list[Phone],
    ) -> DeviceReconcileResult:
        """Reconcile one complete discovery snapshot with stored phones.

        Args:
            paired_devices: Repository containing canonical phone instances.
            discovered_phones: Fresh phone observations from ADB discovery.

        Returns:
            An immutable summary of changes, rebindings, and removals.

        Raises:
            ValueError: If a reconciled phone collides with an existing identity
                or ADB endpoint during repository reindexing.
        """
        grouped = self._group_discovered_phones(paired_devices, discovered_phones)
        state = _ReconciliationState(
            paired_devices=paired_devices,
            paired_by_stable_identity=paired_devices.index_by_stable_identity(),
        )
        for discovered in grouped:
            self._reconcile_discovered_phone(state, discovered)
        removed_phone_ids = self._remove_unmatched_paired_phones(state)
        if state.changed:
            logger.info(
                "Paired devices reconciled",
                discovered_count=len(grouped),
                paired_count=len(paired_devices),
            )
        return DeviceReconcileResult(
            changed=state.changed,
            phone_id_rebindings=MappingProxyType(state.phone_id_rebindings.copy()),
            removed_phone_ids=removed_phone_ids,
        )

    @staticmethod
    def _group_discovered_phones(
        paired_devices: PhoneRepository,
        phones: list[Phone],
    ) -> list[Phone]:
        """Group rows by Tier-1 identity or existing endpoint ownership.

        Args:
            paired_devices: Repository used to resolve existing endpoint owners.
            phones: Raw phone observations to deduplicate and group.

        Returns:
            Physical-phone aggregates with merged connections and enrichment.
        """
        deduplicated: dict[str, Phone] = {}
        for phone in phones:
            for connection in phone.connections:
                deduplicated[connection.id] = phone

        groups: dict[str, list[Phone]] = {}
        for connection_id, phone in deduplicated.items():
            tier_one = _tier_one_value(phone)
            owner = paired_devices.get_by_connection_id(connection_id)
            group_key = (
                f"stable:{tier_one}"
                if tier_one is not None
                else (
                    f"owned:{owner.identity.value}"
                    if owner is not None
                    else f"connection:{connection_id}"
                )
            )
            groups.setdefault(group_key, []).append(phone)

        grouped: list[Phone] = []
        for observations in groups.values():
            observations.sort(
                key=lambda phone: (
                    phone.display_connection.connectivity_type != "usb",
                    phone.display_connection.id,
                )
            )
            aggregate = observations[0]
            for observation in observations[1:]:
                for connection in observation.connections:
                    aggregate.add_connection(connection)
                aggregate.apply_shell_enrichment(
                    manufacturer=aggregate.manufacturer or observation.manufacturer,
                    model=aggregate.model or observation.model,
                    shell_device_name=(
                        aggregate.shell_device_name or observation.shell_device_name
                    ),
                    os=aggregate.os or observation.os,
                    android_api_level=(
                        aggregate.android_api_level
                        if aggregate.android_api_level is not None
                        else observation.android_api_level
                    ),
                    hardware_serial=(
                        aggregate.hardware_serial or observation.hardware_serial
                    ),
                )
            grouped.append(aggregate)
        return grouped

    def _reconcile_discovered_phone(
        self,
        state: _ReconciliationState,
        discovered: Phone,
    ) -> None:
        """Add, retain, or update one grouped discovery aggregate.

        Args:
            state: Mutable state for the current reconciliation pass.
            discovered: Grouped phone aggregate to reconcile.

        Raises:
            ValueError: If repository reindexing detects an identity or endpoint
                collision.
        """
        paired = self._find_paired_phone(state, discovered)
        if paired is None:
            state.paired_devices.add(discovered)
            state.matched_paired_object_ids.add(id(discovered))
            state.changed = True
            return
        state.matched_paired_object_ids.add(id(paired))
        if self._phones_are_unchanged(paired, discovered):
            return
        old_identity = paired.identity.value
        old_connection_ids = tuple(connection.id for connection in paired.connections)
        paired.apply_discovery(discovered)
        state.paired_devices.reindex(
            paired,
            old_identity=old_identity,
            old_connection_ids=old_connection_ids,
        )
        if old_identity != paired.identity.value:
            state.phone_id_rebindings[old_identity] = paired.identity.value
        state.changed = True

    @staticmethod
    def _find_paired_phone(
        state: _ReconciliationState,
        discovered: Phone,
    ) -> Phone | None:
        """Find the canonical phone matching a discovery aggregate.

        Args:
            state: Mutable state for the current reconciliation pass.
            discovered: Grouped phone aggregate to match.

        Returns:
            The direct, endpoint-owned, or unused Tier-1 match; otherwise
            ``None``.
        """
        direct = state.paired_devices.get(discovered.identity.value)
        if direct is not None:
            return direct
        owners = {
            id(owner): owner
            for connection in discovered.connections
            if (owner := state.paired_devices.get_by_connection_id(connection.id))
            is not None
        }
        if len(owners) == 1:
            return next(iter(owners.values()))
        stable_identity = StableKey.from_value(discovered.stable_key)
        if isinstance(stable_identity, FirstTierStableKey):
            candidate = state.paired_by_stable_identity.get(stable_identity)
            if (
                candidate is not None
                and id(candidate) not in state.matched_paired_object_ids
            ):
                return candidate
        return None

    @staticmethod
    def _phones_are_unchanged(paired: Phone, discovered: Phone) -> bool:
        """Compare effective discovery state with a canonical phone.

        Inactive observations preserve the last known connection timestamp, and
        provisional discovery identities preserve the canonical identity.

        Args:
            paired: Canonical repository phone.
            discovered: Fresh grouped discovery aggregate.

        Returns:
            ``True`` when applying discovery would not change effective state.
        """
        previous = {connection.id: connection for connection in paired.connections}
        effective_connections = []
        for connection in discovered.connections:
            old = previous.get(connection.id)
            if connection.last_connection is None and old is not None:
                connection = replace(connection, last_connection=old.last_connection)
            effective_connections.append(connection)
        effective_identity = (
            paired.identity
            if discovered.identity.is_provisional
            else discovered.identity
        )
        return (
            paired.identity == effective_identity
            and paired.descriptor == discovered.descriptor
            and paired.connections
            == tuple(sorted(effective_connections, key=lambda item: item.id))
        )

    @staticmethod
    def _remove_unmatched_paired_phones(
        state: _ReconciliationState,
    ) -> tuple[str, ...]:
        """Remove canonical phones absent from the discovery snapshot.

        Args:
            state: Mutable state for the current reconciliation pass.

        Returns:
            Removed physical identities in repository iteration order.
        """
        removed: list[str] = []
        for paired in list(state.paired_devices):
            if id(paired) in state.matched_paired_object_ids:
                continue
            removed.append(paired.identity.value)
            state.paired_devices.remove(paired)
            state.changed = True
        return tuple(removed)
