"""
Device list enrichment via ADB shell (getprops and ``ro.serialno``) without extra threads.

Workers only: call from AsyncRunner/off-main jobs that already do blocking ADB I/O.

Public orchestrator :func:`enrich_phones_with_adb_shell_properties` sequences per-property
helpers so breakpoints and stacks stay readable. :class:`RefreshKnownDevicesWork` pairs blocking
listing + enrichment with main-thread emission via :meth:`RefreshKnownDevicesWork.apply_main_thread`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.adb.client import AdbClient
from core.adb.server import AdbServer
from core.devices import (
    Phone,
    apply_phone_android_api_level_enrichment,
    apply_phone_android_release_enrichment,
    apply_phone_device_name_enrichment,
    apply_phone_manufacturer_enrichment,
    apply_phone_product_model_enrichment,
    apply_phone_ro_serial_enrichment,
)
from core.signals import CoreSignal, DevicesUpdatedPayload
from core.work.core_runtime_work import CoreRuntimeWork, CoreRuntimeWorkOutcome

if TYPE_CHECKING:
    from core.models import CoreRuntimeModel

# Only states where ``adb -s … shell …`` reliably targets the handset.
_EXECUTABLE_STATES = frozenset(("device",))


def _phone_is_shell_targetable(phone: Phone) -> bool:
    """True when ``adb -s … shell …`` should target this handset reliably."""
    st = (phone.descriptor.state or "").strip().casefold()
    return st in _EXECUTABLE_STATES


def enrich_phones_with_manufacturer(adb_client: AdbClient, phones: list[Phone]) -> None:
    """``getprop ro.product.manufacturer`` for each shell-targetable phone."""
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        apply_phone_manufacturer_enrichment(
            phone, adb_client.get_product_manufacturer(phone)
        )


def enrich_phones_with_product_model(
    adb_client: AdbClient, phones: list[Phone]
) -> None:
    """``getprop ro.product.model`` for each shell-targetable phone."""
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        apply_phone_product_model_enrichment(phone, adb_client.get_product_model(phone))


def enrich_phones_with_device_name(adb_client: AdbClient, phones: list[Phone]) -> None:
    """``getprop device_name`` for each shell-targetable phone (non-empty only applies)."""
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        apply_phone_device_name_enrichment(
            phone, adb_client.get_device_name_prop(phone)
        )


def enrich_phones_with_android_release(
    adb_client: AdbClient, phones: list[Phone]
) -> None:
    """``getprop ro.build.version.release`` for each shell-targetable phone."""
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        apply_phone_android_release_enrichment(
            phone, adb_client.get_android_release(phone)
        )


def enrich_phones_with_android_sdk(adb_client: AdbClient, phones: list[Phone]) -> None:
    """``getprop ro.build.version.sdk`` (API level) for each shell-targetable phone."""
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        apply_phone_android_api_level_enrichment(
            phone, adb_client.get_android_sdk_api_level(phone)
        )


def enrich_phones_with_ro_serialno(adb_client: AdbClient, phones: list[Phone]) -> None:
    """``getprop ro.serialno`` for each shell-targetable phone (hardware_serial / stable_key)."""
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        apply_phone_ro_serial_enrichment(phone, adb_client.get_ro_serialno(phone))


def _enrich_phone_with_shell_properties(adb_client: AdbClient, phone: Phone) -> None:
    """Apply the batch ADB shell enrichment payload to one targetable phone."""
    props = adb_client.get_shell_enrichment_properties(phone)
    apply_phone_manufacturer_enrichment(phone, str(props.get("manufacturer") or ""))
    apply_phone_product_model_enrichment(phone, str(props.get("model") or ""))
    apply_phone_device_name_enrichment(phone, str(props.get("device_name") or ""))
    apply_phone_android_release_enrichment(
        phone, str(props.get("android_release") or "")
    )
    sdk_value = props.get("sdk")
    apply_phone_android_api_level_enrichment(
        phone, sdk_value if isinstance(sdk_value, int) else None
    )
    apply_phone_ro_serial_enrichment(phone, str(props.get("ro_serialno") or ""))


def enrich_phones_with_adb_shell_properties(
    adb_client: AdbClient, phones: list[Phone]
) -> None:
    """
    Full ADB shell property pass: manufacturer/model first (Tier-2 inputs), identity strings,
    then ``ro.serialno`` (Tier-1 wins when present).

    No-op when ``phones`` is empty so refresh/startup avoid redundant work.
    """
    if not phones:
        return
    for phone in phones:
        if not _phone_is_shell_targetable(phone):
            continue
        _enrich_phone_with_shell_properties(adb_client, phone)


@dataclass(frozen=True, slots=True)
class RefreshKnownDevicesOutcome(CoreRuntimeWorkOutcome):
    """Result of :meth:`RefreshKnownDevicesWork.run` (worker thread)."""

    devices: list[Phone] = field(default_factory=list)


class RefreshKnownDevicesWork(CoreRuntimeWork[RefreshKnownDevicesOutcome]):
    """
    Blocking ADB listing + shell property enrichment on a worker; apply emits ``DEVICES_UPDATED``.
    """

    def __init__(self, adb_server: AdbServer, adb_client: AdbClient) -> None:
        self._adb_server = adb_server
        self._adb_client = adb_client

    def run(self) -> RefreshKnownDevicesOutcome:
        phones = self._adb_server.get_known_devices()
        enrich_phones_with_adb_shell_properties(self._adb_client, phones)
        return RefreshKnownDevicesOutcome(devices=phones)

    @staticmethod
    def apply_main_thread(
        model: CoreRuntimeModel,
        outcome: RefreshKnownDevicesOutcome,
    ) -> None:
        from core.models import CoreRuntimeModel as _CoreRuntimeModel

        if not isinstance(model, _CoreRuntimeModel):
            raise TypeError("apply_main_thread() requires CoreRuntimeModel")
        model._adb_server.paired_devices.clear()
        model._adb_server.paired_devices.add_all(outcome.devices)
        model._signal_bus.emit(
            CoreSignal.DEVICES_UPDATED,
            DevicesUpdatedPayload(devices=outcome.devices),
        )
