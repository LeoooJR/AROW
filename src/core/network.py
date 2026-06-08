import ipaddress


def is_non_loopback_ipv4(value: str) -> bool:
    try:
        address = ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, ValueError):
        return False
    return not address.is_loopback


class Network:

    pass


class Wifi:

    pass
