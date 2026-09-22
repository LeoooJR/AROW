"""Reconcile physical phones and their current ADB connections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeVar

from core.devices.phone import Phone, PhoneRepository
from core.devices.stable_key import FirstTierStableKey, StableKey
from logger import logger


@dataclass(frozen=True, slots=True)
class PhoneAdded:
    """Record a physical phone added to the canonical repository.

    Attributes:
        phone_id: Added physical-phone identity.
    """

    phone_id: str


@dataclass(frozen=True, slots=True)
class PhoneUpdated:
    """Record a canonical phone refreshed without changing identity.

    Attributes:
        phone_id: Updated physical-phone identity.
    """

    phone_id: str


@dataclass(frozen=True, slots=True)
class PhoneIdentityChanged:
    """Record a canonical phone changed to a new physical identity.

    Attributes:
        previous_phone_id: Physical identity before discovery enrichment.
        current_phone_id: Physical identity after discovery enrichment.
    """

    previous_phone_id: str
    current_phone_id: str


@dataclass(frozen=True, slots=True)
class PhoneRemoved:
    """Record a physical phone removed from the canonical repository.

    Attributes:
        phone_id: Removed physical-phone identity.
    """

    phone_id: str


type PhoneReconciliationChange = (
    PhoneAdded | PhoneUpdated | PhoneIdentityChanged | PhoneRemoved
)


@dataclass(frozen=True, slots=True)
class PhoneReconciliationReport:
    """Describe repository changes as an ordered domain event journal.

    Attributes:
        changes: Reconciliation events in the order they occurred.
    """

    changes: tuple[PhoneReconciliationChange, ...] = ()

    @property
    def has_changes(self) -> bool:
        """Return whether reconciliation changed canonical phone state."""
        return bool(self.changes)

    @property
    def identity_changes(self) -> tuple[PhoneIdentityChanged, ...]:
        """Return physical identity changes in journal order."""
        return tuple(
            change
            for change in self.changes
            if isinstance(change, PhoneIdentityChanged)
        )

    @property
    def removals(self) -> tuple[PhoneRemoved, ...]:
        """Return physical-phone removals in journal order."""
        return tuple(
            change for change in self.changes if isinstance(change, PhoneRemoved)
        )


_PhoneGroupReason = Literal["tier_one", "repository_owner", "connection"]


@dataclass(frozen=True, slots=True)
class _PhoneGroupKey:
    """Identify why discovery observations belong to one physical phone.

    Attributes:
        reason: Matching rule that established the group.
        value: Stable identity, repository identity, or connection identifier.
    """

    reason: _PhoneGroupReason
    value: str


_ValueT = TypeVar("_ValueT")


def _first_nonblank(*values: str) -> str:
    """Return the first non-empty discovery value.

    Args:
        *values: Values in descending precedence order.

    Returns:
        The first truthy value, or an empty string when none exists.
    """
    return next((value for value in values if value), "")


def _first_defined(primary: _ValueT | None, fallback: _ValueT | None) -> _ValueT | None:
    """Return the first value that is not ``None``.

    Args:
        primary: Preferred value.
        fallback: Value used when ``primary`` is ``None``.

    Returns:
        ``primary`` when defined; otherwise ``fallback``.
    """
    return primary if primary is not None else fallback


def _tier_one_key(phone: Phone) -> FirstTierStableKey | None:
    """Return a phone's parsed Tier-1 identity when available.

    Args:
        phone: Phone whose stable key should be parsed.

    Returns:
        The Tier-1 key, or ``None`` for missing and Tier-2 keys.
    """
    parsed = StableKey.from_value(phone.stable_key)
    return parsed if isinstance(parsed, FirstTierStableKey) else None


@dataclass(frozen=True, slots=True)
class _DiscoverySnapshot:
    """Own normalized physical phones from one complete ADB observation.

    Attributes:
        phones: Grouped physical phones in deterministic discovery order.
    """

    phones: tuple[Phone, ...]

    @classmethod
    def from_observations(
        cls,
        repository: PhoneRepository,
        phones: list[Phone],
    ) -> _DiscoverySnapshot:
        """Normalize raw observations into physical-phone aggregates.

        Args:
            repository: Canonical phones used to recognize endpoint ownership.
            phones: Raw phone observations returned by ADB discovery.

        Returns:
            A deterministic snapshot containing one aggregate per group.
        """
        latest_by_connection = cls._latest_by_connection(phones)
        observation_groups = cls._group_observations(
            repository,
            latest_by_connection,
        )
        return cls(
            phones=tuple(
                cls._merge_observation_group(group) for group in observation_groups
            )
        )

    @staticmethod
    def _latest_by_connection(phones: list[Phone]) -> dict[str, Phone]:
        """Keep the last observation for each ADB connection identifier."""
        latest: dict[str, Phone] = {}
        for phone in phones:
            for connection in phone.connections:
                latest[connection.id] = phone
        return latest

    @classmethod
    def _group_observations(
        cls,
        repository: PhoneRepository,
        latest_by_connection: dict[str, Phone],
    ) -> tuple[tuple[Phone, ...], ...]:
        """Group observations by their strongest available physical identity."""
        groups: dict[_PhoneGroupKey, dict[int, Phone]] = {}
        for connection_id, phone in latest_by_connection.items():
            key = cls._group_key(repository, connection_id, phone)
            groups.setdefault(key, {})[id(phone)] = phone
        return tuple(tuple(group.values()) for group in groups.values())

    @staticmethod
    def _group_key(
        repository: PhoneRepository,
        connection_id: str,
        phone: Phone,
    ) -> _PhoneGroupKey:
        """Choose Tier-1, repository-owner, then endpoint grouping."""
        tier_one = _tier_one_key(phone)
        if tier_one is not None:
            return _PhoneGroupKey("tier_one", tier_one.value)
        owner = repository.get_by_connection_id(connection_id)
        if owner is not None:
            return _PhoneGroupKey("repository_owner", owner.identity.value)
        return _PhoneGroupKey("connection", connection_id)

    @classmethod
    def _merge_observation_group(cls, observations: tuple[Phone, ...]) -> Phone:
        """Merge one ordered observation group into its primary aggregate."""
        ordered = sorted(observations, key=cls._observation_priority)
        aggregate = ordered[0]
        for observation in ordered[1:]:
            cls._merge_observation(aggregate, observation)
        return aggregate

    @staticmethod
    def _observation_priority(phone: Phone) -> tuple[bool, str]:
        """Sort USB observations before Wi-Fi, then by endpoint identifier."""
        connection = phone.display_connection
        return connection.connectivity_type != "usb", connection.id

    @staticmethod
    def _merge_observation(aggregate: Phone, observation: Phone) -> None:
        """Merge one secondary observation into the primary aggregate."""
        for connection in observation.connections:
            aggregate.add_connection(connection)
        aggregate.apply_shell_enrichment(
            manufacturer=_first_nonblank(
                aggregate.manufacturer,
                observation.manufacturer,
            ),
            model=_first_nonblank(aggregate.model, observation.model),
            shell_device_name=_first_nonblank(
                aggregate.shell_device_name,
                observation.shell_device_name,
            ),
            os=_first_nonblank(aggregate.os, observation.os),
            android_api_level=_first_defined(
                aggregate.android_api_level,
                observation.android_api_level,
            ),
            hardware_serial=_first_nonblank(
                aggregate.hardware_serial,
                observation.hardware_serial,
            ),
        )


class _CanonicalPhoneMatcher:
    """Claim each canonical phone at most once during reconciliation."""

    def __init__(self, repository: PhoneRepository) -> None:
        """Capture canonical lookup indexes before repository mutations.

        Args:
            repository: Repository containing canonical phone instances.
        """
        self._repository = repository
        self._by_stable_identity = repository.index_by_stable_identity()
        self._unclaimed = {id(phone): phone for phone in repository}

    def claim(self, discovered: Phone) -> Phone | None:
        """Claim the strongest available canonical match.

        Args:
            discovered: Grouped discovery aggregate to match.

        Returns:
            An unclaimed canonical phone, or ``None`` when no match exists.
        """
        candidate = self._repository.get(discovered.identity.value)
        if candidate is None:
            candidate = self._connection_owner(discovered)
        if candidate is None:
            candidate = self._stable_identity_match(discovered)
        return self._claim_candidate(candidate)

    def _connection_owner(self, discovered: Phone) -> Phone | None:
        """Return the unique canonical owner of discovered endpoints."""
        owners = {
            id(owner): owner
            for connection in discovered.connections
            if (owner := self._repository.get_by_connection_id(connection.id))
            is not None
        }
        return next(iter(owners.values())) if len(owners) == 1 else None

    def _stable_identity_match(self, discovered: Phone) -> Phone | None:
        """Return the canonical phone sharing a Tier-1 stable identity."""
        stable_identity = _tier_one_key(discovered)
        if stable_identity is None:
            return None
        return self._by_stable_identity.get(stable_identity)

    def _claim_candidate(self, candidate: Phone | None) -> Phone | None:
        """Remove and return an available candidate from the match pool."""
        if candidate is None:
            return None
        return self._unclaimed.pop(id(candidate), None)

    @property
    def unclaimed_phones(self) -> tuple[Phone, ...]:
        """Return canonical phones absent from the discovery snapshot."""
        return tuple(self._unclaimed.values())


class _PhoneChangeJournal:
    """Record reconciliation outcomes using domain-specific events."""

    def __init__(self) -> None:
        """Initialize an empty ordered change journal."""
        self._changes: list[PhoneReconciliationChange] = []

    def record_added(self, phone: Phone) -> None:
        """Record a newly canonical phone."""
        self._changes.append(PhoneAdded(phone.id))

    def record_updated(self, phone: Phone) -> None:
        """Record a canonical phone changed without identity promotion."""
        self._changes.append(PhoneUpdated(phone.id))

    def record_identity_change(self, previous_phone_id: str, phone: Phone) -> None:
        """Record a canonical phone changed to a new physical identity."""
        self._changes.append(
            PhoneIdentityChanged(previous_phone_id, phone.identity.value)
        )

    def record_removed(self, phone: Phone) -> None:
        """Record a canonical phone removed after missing discovery."""
        self._changes.append(PhoneRemoved(phone.id))

    def finish(self) -> PhoneReconciliationReport:
        """Freeze the ordered events into a public reconciliation report."""
        return PhoneReconciliationReport(tuple(self._changes))


class ReconciliationEngine:
    """Merge a complete ADB snapshot into canonical physical phones.

    Discovery normalization, canonical matching, and outcome reporting are owned
    by focused collaborators so this class reads as the domain workflow.
    """

    def reconcile(
        self,
        paired_devices: PhoneRepository,
        discovered_phones: list[Phone],
    ) -> PhoneReconciliationReport:
        """Reconcile one complete discovery snapshot with stored phones.

        Args:
            paired_devices: Repository containing canonical phone instances.
            discovered_phones: Fresh phone observations from ADB discovery.

        Returns:
            An ordered semantic report of repository-visible changes.

        Raises:
            ValueError: If repository reindexing finds an identity or endpoint
                collision.
        """
        snapshot = _DiscoverySnapshot.from_observations(
            paired_devices,
            discovered_phones,
        )
        matcher = _CanonicalPhoneMatcher(paired_devices)
        journal = _PhoneChangeJournal()
        for discovered in snapshot.phones:
            self._reconcile_phone(paired_devices, matcher, journal, discovered)
        self._remove_unclaimed_phones(paired_devices, matcher, journal)
        report = journal.finish()
        self._log_changes(report, snapshot, paired_devices)
        return report

    @staticmethod
    def _reconcile_phone(
        repository: PhoneRepository,
        matcher: _CanonicalPhoneMatcher,
        journal: _PhoneChangeJournal,
        discovered: Phone,
    ) -> None:
        """Add, retain, or update one grouped discovery aggregate."""
        paired = matcher.claim(discovered)
        if paired is None:
            repository.add(discovered)
            journal.record_added(discovered)
            return
        previous_phone_id = paired.identity.value
        previous_connection_ids = tuple(
            connection.id for connection in paired.connections
        )
        if not paired.apply_discovery(discovered):
            return
        repository.reindex(
            paired,
            old_identity=previous_phone_id,
            old_connection_ids=previous_connection_ids,
        )
        if previous_phone_id == paired.identity.value:
            journal.record_updated(paired)
            return
        journal.record_identity_change(previous_phone_id, paired)

    @staticmethod
    def _remove_unclaimed_phones(
        repository: PhoneRepository,
        matcher: _CanonicalPhoneMatcher,
        journal: _PhoneChangeJournal,
    ) -> None:
        """Remove and record canonical phones absent from discovery."""
        for phone in matcher.unclaimed_phones:
            repository.remove(phone)
            journal.record_removed(phone)

    @staticmethod
    def _log_changes(
        report: PhoneReconciliationReport,
        snapshot: _DiscoverySnapshot,
        repository: PhoneRepository,
    ) -> None:
        """Log one summary when reconciliation changed canonical state."""
        if report.has_changes:
            logger.info(
                "Paired devices reconciled",
                discovered_count=len(snapshot.phones),
                paired_count=len(repository),
            )
