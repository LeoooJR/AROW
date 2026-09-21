"""Test-only builders for physical phones with deterministic identities."""

from __future__ import annotations

from core.devices.phone import (
    AdbConnection,
    ConnectivityType,
    Phone,
    PhoneIdentity,
)


def make_phone(
    id: str,
    *,
    name: str | None = None,
    os: str | None = None,
    ip: str | None = None,
    port: int | None = None,
    device: str | None = None,
    product: str | None = None,
    model: str | None = None,
    state: str | None = None,
    hardware_serial: str | None = None,
    manufacturer: str | None = None,
    transport_id: str | None = None,
    android_api_level: int | None = None,
    connectivity_type: ConnectivityType | None = None,
) -> Phone:
    """Build a phone while keeping legacy fixtures' deterministic physical ids."""
    return Phone(
        AdbConnection.observed(
            id,
            state=state or "",
            transport_id=transport_id or "",
            connectivity_type=connectivity_type,
            ip=ip,
            port=port,
        ),
        identity=PhoneIdentity(id),
        name=name,
        os=os,
        device=device,
        product=product,
        model=model,
        hardware_serial=hardware_serial,
        manufacturer=manufacturer,
        android_api_level=android_api_level,
    )
