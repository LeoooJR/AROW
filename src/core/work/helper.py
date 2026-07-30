"""Preflight decorator for core runtime work ``run()`` methods."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeGuard, TypeVar

from logger import logger

TOutcome = TypeVar("TOutcome")

PreflightErrorFactory = Callable[[object], BaseException]

_SERVER_ATTRS = ("_adb_server", "adb_server")
_CLIENT_ATTRS = ("_adb_client", "adb_client")
_DEVICE_IP_ATTRS = ("_ip", "ip")
_DEVICE_PORT_ATTRS = ("_port", "port")


def _resolve_attr(work: object, names: tuple[str, ...]) -> object | None:
    for name in names:
        if hasattr(work, name):
            value = getattr(work, name)
            if value is not None:
                return value
    return None


def _resolve_server(work: object) -> object | None:
    return _resolve_attr(work, _SERVER_ATTRS)


def _resolve_client(work: object) -> object | None:
    return _resolve_attr(work, _CLIENT_ATTRS)


def _valid_device_port(value: object) -> TypeGuard[int]:
    return (
        not isinstance(value, bool) and isinstance(value, int) and 1 <= value <= 65535
    )


def _resolve_device_endpoint(work: object) -> tuple[str, int] | None:
    ip = _resolve_attr(work, _DEVICE_IP_ATTRS)
    port = _resolve_attr(work, _DEVICE_PORT_ATTRS)
    if not isinstance(ip, str) or not ip.strip():
        return None
    if not _valid_device_port(port):
        return None
    return ip, port


def _device_endpoint_status(work: object, server: object) -> bool | None:
    """Return duplicate status, or ``None`` when the check cannot be performed."""
    endpoint = _resolve_device_endpoint(work)
    paired_devices = getattr(server, "paired_devices", None)
    if endpoint is None or paired_devices is None:
        return None
    try:
        devices = iter(paired_devices)
    except TypeError:
        return None
    ip, port = endpoint
    for device in devices:
        device_port = getattr(device, "port", None)
        if (
            getattr(device, "ip", None) == ip
            and _valid_device_port(device_port)
            and device_port == port
        ):
            return True
    return False


def device_endpoint_is_paired(work: object) -> bool:
    """Return whether work targets an endpoint already present on its ADB server."""
    server = _resolve_server(work)
    return server is not None and _device_endpoint_status(work, server) is True


def _validate_client_usable(client: object) -> bool:
    """Validate that the client has binary metadata required for ADB execution."""
    binary = getattr(client, "binary", None)
    if binary is None:
        return False
    path = getattr(binary, "path", None)
    return path is not None and str(path).strip() != ""


def _server_is_running(server: object) -> bool:
    probe = getattr(server, "is_server_running", None)
    if not callable(probe):
        return False
    return bool(probe())


def _server_mdns_available(server: object) -> bool:
    refresh = getattr(server, "refresh_mdns_availability", None)
    if not callable(refresh):
        return False
    return bool(refresh())


def _server_network_available(server: object) -> bool:
    refresh = getattr(server, "refresh_network_availability", None)
    if not callable(refresh):
        return False
    return bool(refresh())


def _raise_preflight_error(
    work: object,
    error_to_raise: BaseException | PreflightErrorFactory | None,
) -> None:
    if error_to_raise is None:
        raise RuntimeError("Core runtime work preflight failed")
    if callable(error_to_raise):
        raise error_to_raise(work)
    raise error_to_raise


def preflight(
    *,
    check_server_started: bool = False,
    check_client_created: bool = False,
    check_device_not_paired: bool = False,
    check_network_available: bool = False,
    check_mdns_available: bool = False,
    error_to_raise: BaseException | PreflightErrorFactory | None = None,
) -> Callable[[Callable[..., TOutcome]], Callable[..., TOutcome]]:
    """
    Run active ADB preflight checks before a work ``run()`` body.

    Entrypoint callers may still perform cheap property guards; this decorator
    performs runtime health probes once the work instance holds server/client refs.
    """

    def decorator(
        run_method: Callable[..., TOutcome],
    ) -> Callable[..., TOutcome]:
        @wraps(run_method)
        def wrapper(self: object, *args: Any, **kwargs: Any) -> TOutcome:
            server: object | None = None

            if (
                check_server_started
                or check_device_not_paired
                or check_network_available
                or check_mdns_available
            ):
                server = _resolve_server(self)
                if server is None:
                    logger.warning(
                        "Work preflight failed because the ADB server is missing",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)

            if check_device_not_paired and server is not None:
                endpoint_status = _device_endpoint_status(self, server)
                if endpoint_status is None:
                    logger.warning(
                        "Work preflight failed because device endpoint metadata is unavailable",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)
                if endpoint_status:
                    logger.warning(
                        "Work preflight failed because the device endpoint is already paired",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)

            if check_server_started and server is not None:
                if not _server_is_running(server):
                    logger.warning(
                        "Work preflight failed because the ADB server is unhealthy",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)

            if check_client_created:
                client = _resolve_client(self)
                if client is None or not _validate_client_usable(client):
                    logger.warning(
                        "Work preflight failed because the ADB client is unavailable",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)

            if check_network_available and server is not None:
                if not _server_network_available(server):
                    logger.warning(
                        "Work preflight failed because the host network is unavailable",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)

            if check_mdns_available and server is not None:
                if not _server_mdns_available(server):
                    logger.warning(
                        "Work preflight failed because ADB mDNS is unavailable",
                        work_type=type(self).__name__,
                    )
                    _raise_preflight_error(self, error_to_raise)

            return run_method(self, *args, **kwargs)

        return wrapper

    return decorator
