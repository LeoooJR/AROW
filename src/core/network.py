import ipaddress
import socket


def is_non_loopback_ipv4(value: str) -> bool:
    """Return whether ``value`` is a valid non-loopback IPv4 address."""
    try:
        address = ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, ValueError):
        return False
    return not address.is_loopback


def resolve_network_identity() -> tuple[str, bool]:
    """Return a usable host IPv4 address and whether one could be resolved."""
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if is_non_loopback_ipv4(ip):
            return ip, True
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            # UDP connect selects a local route without sending application data.
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        if is_non_loopback_ipv4(ip):
            return ip, True
    except OSError:
        pass
    return "127.0.0.1", False


class Network:
    """Placeholder for shared network-domain behavior."""

    pass


class Wifi:
    """Placeholder for Wi-Fi-specific network behavior."""

    pass
