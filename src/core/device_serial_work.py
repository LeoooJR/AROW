"""
Device list enrichment: read ``ro.serialno`` via ADB without extra threads.

Workers only: call from AsyncRunner/off-main jobs that already do blocking ADB I/O.
"""

from __future__ import annotations

from core.adb import AdbClient
from core.devices import Phone, apply_phone_ro_serial_enrichment

# Only states where ``adb -s … shell …`` reliably targets the handset.
_EXECUTABLE_STATES = frozenset(("device",))


def enrich_phones_with_serial(adb_client: AdbClient, phones: list[Phone]) -> None:
    """
    For each connected phone (``state`` = ``device``), run ``shell getprop ro.serialno``

    Updates ``hardware_serial`` / ``stable_key`` in place; logs and skips failures.
    """
    for phone in phones:
        st = (phone.descriptor.state or "").strip().casefold()
        if st not in _EXECUTABLE_STATES:
            continue
        raw_serial = adb_client.get_ro_serialno(phone)
        apply_phone_ro_serial_enrichment(phone, raw_serial)


def refresh_known_devices_with_serial(model: object) -> list[Phone]:
    """
    List devices using the bound server, enrich with hardware serial.

    Intended as the AsyncRunner ``fn`` for manual refresh (see ``AdbSubController``).

    Raises:
        TypeError: if ``model`` is not :class:`~core.models.CoreRuntimeModel`.
    """
    from core.models import CoreRuntimeModel as _CoreRuntimeModel

    if not isinstance(model, _CoreRuntimeModel):
        raise TypeError("refresh_known_devices_with_serial requires CoreRuntimeModel")
    phones = model.get_known_devices()
    enrich_phones_with_serial(model.get_adb_client(), phones)
    return phones
