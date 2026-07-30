"""Tests for shared host network resolution."""

from __future__ import annotations

import pytest

import core.network as network


def test_resolve_network_identity_uses_non_loopback_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(network.socket, "gethostname", lambda: "workstation")
    monkeypatch.setattr(
        network.socket, "gethostbyname", lambda _hostname: "192.168.1.10"
    )

    assert network.resolve_network_identity() == ("192.168.1.10", True)


def test_resolve_network_identity_falls_back_to_udp_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSocket:
        def __enter__(self) -> FakeSocket:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def connect(self, _address: tuple[str, int]) -> None:
            return None

        def getsockname(self) -> tuple[str, int]:
            return ("10.0.0.42", 54321)

    monkeypatch.setattr(network.socket, "gethostname", lambda: "workstation")
    monkeypatch.setattr(network.socket, "gethostbyname", lambda _hostname: "127.0.0.1")
    monkeypatch.setattr(
        network.socket,
        "socket",
        lambda _family, _type: FakeSocket(),
    )

    assert network.resolve_network_identity() == ("10.0.0.42", True)


def test_resolve_network_identity_returns_loopback_when_probes_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSocket:
        def __enter__(self) -> FailingSocket:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def connect(self, _address: tuple[str, int]) -> None:
            raise OSError("no route")

    monkeypatch.setattr(network.socket, "gethostname", lambda: "workstation")
    monkeypatch.setattr(
        network.socket,
        "gethostbyname",
        lambda _hostname: (_ for _ in ()).throw(OSError("lookup failed")),
    )
    monkeypatch.setattr(
        network.socket,
        "socket",
        lambda _family, _type: FailingSocket(),
    )

    assert network.resolve_network_identity() == ("127.0.0.1", False)
