from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.adb.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices.phone import Phone
from core.entrypoint import ModelEntrypoint
from core.work.authentificate_device_work import (
    AuthentificateDeviceOutcome,
    DeviceAuthentificationError,
)

pytestmark = [pytest.mark.async_jobs]


def _mark_host_network_available(model_entrypoint: ModelEntrypoint) -> None:
    model_entrypoint.host.descriptor.network_available = True
    model_entrypoint.host.refresh_network_identity = lambda: None  # type: ignore[method-assign]


class TestModelEntrypoint:
    def test_authentificate_device_requires_initialized_adb(self) -> None:
        """Pairing is rejected until startup has bound server and client on the entrypoint."""
        model_entrypoint = ModelEntrypoint()
        with pytest.raises(
            AttributeError, match="must be initialized before authentification"
        ):
            model_entrypoint.authentificate_device("127.0.0.1", 5555, "123456")

    @patch("core.entrypoint.AuthenticateDeviceWork")
    def test_authentificate_device_skips_work_when_ip_already_paired(
        self, mock_work_cls: MagicMock
    ) -> None:
        """
        :meth:`ModelEntrypoint.authentificate_device` must not start a new pair attempt
        when ``paired_devices`` already contains a handset with the same IP.
        """
        state = MockAdbState(seed=11, initial_devices=0)
        server = MockAdbServer(state=state)
        client = MockAdbClient(state=state)
        duplicate_ip = "192.168.77.1"
        port = 5555
        code = "123456"
        server.paired_devices.add(
            Phone(id="existing-handset", ip=duplicate_ip, port=port)
        )
        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = server
        model_entrypoint._adb_client = client
        _mark_host_network_available(model_entrypoint)

        with pytest.raises(DeviceAuthentificationError) as exc_info:
            model_entrypoint.authentificate_device(duplicate_ip, port, code)

        mock_work_cls.assert_not_called()
        error = exc_info.value
        assert error.ip == duplicate_ip
        assert error.port == port
        assert error.association_code == code
        assert error.reason == "Device with this IP address is already paired"

    @patch("core.entrypoint.AuthenticateDeviceWork")
    def test_authentificate_device_delegates_to_work_when_ip_not_paired(
        self, mock_work_cls: MagicMock
    ) -> None:
        """When no paired device uses the requested IP, pairing work runs as usual."""
        state = MockAdbState(seed=12, initial_devices=0)
        server = MockAdbServer(state=state)
        client = MockAdbClient(state=state)
        requested_ip = "10.0.0.9"
        port = 37777
        code = "000000"
        server.paired_devices.add(Phone(id="other-handset", ip="10.0.0.8", port=port))
        expected_phone = Phone(id="new-pair", ip=requested_ip, port=port)
        expected_outcome = AuthentificateDeviceOutcome(success_phone=expected_phone)
        mock_work_cls.return_value.run.return_value = expected_outcome

        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = server
        model_entrypoint._adb_client = client
        _mark_host_network_available(model_entrypoint)

        outcome = model_entrypoint.authentificate_device(requested_ip, port, code)

        mock_work_cls.assert_called_once_with(
            adb_server=server,
            adb_client=client,
            ip=requested_ip,
            port=port,
            association_code=code,
        )
        assert outcome is expected_outcome

    @patch("core.entrypoint.AuthenticateDeviceWork")
    def test_authentificate_device_fails_when_host_network_unavailable(
        self, mock_work_cls: MagicMock
    ) -> None:
        state = MockAdbState(seed=13, initial_devices=0)
        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = MockAdbServer(state=state)
        model_entrypoint._adb_client = MockAdbClient(state=state)
        model_entrypoint.host.descriptor.network_available = False
        model_entrypoint.host.refresh_network_identity = lambda: None  # type: ignore[method-assign]

        with pytest.raises(DeviceAuthentificationError) as exc_info:
            model_entrypoint.authentificate_device("192.168.1.42", 37777, "123456")

        mock_work_cls.assert_not_called()
        error = exc_info.value
        assert error.reason == "Host network is unavailable"
        assert error.ip == "192.168.1.42"

    @patch("core.entrypoint.AuthenticateDeviceWork")
    def test_authentificate_device_refreshes_host_network_before_gating(
        self, mock_work_cls: MagicMock
    ) -> None:
        state = MockAdbState(seed=14, initial_devices=0)
        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = MockAdbServer(state=state)
        model_entrypoint._adb_client = MockAdbClient(state=state)
        model_entrypoint.host.descriptor.network_available = False
        refresh_calls: list[None] = []

        def refresh_network_identity() -> None:
            refresh_calls.append(None)
            model_entrypoint.host.descriptor.network_available = True

        model_entrypoint.host.refresh_network_identity = refresh_network_identity  # type: ignore[method-assign]
        expected_phone = Phone(id="paired", state="device")
        expected_outcome = AuthentificateDeviceOutcome(success_phone=expected_phone)
        mock_work_cls.return_value.run.return_value = expected_outcome

        outcome = model_entrypoint.authentificate_device(
            "192.168.1.42", 37777, "123456"
        )

        assert len(refresh_calls) == 1
        mock_work_cls.assert_called_once()
        assert outcome is expected_outcome

    @patch("core.entrypoint.AuthenticateDeviceWork")
    def test_authentificate_device_network_guard_runs_before_duplicate_ip_check(
        self, mock_work_cls: MagicMock
    ) -> None:
        state = MockAdbState(seed=15, initial_devices=0)
        duplicate_ip = "192.168.77.1"
        port = 5555
        code = "123456"
        server = MockAdbServer(state=state)
        server.paired_devices.add(
            Phone(id="existing-handset", ip=duplicate_ip, port=port)
        )
        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = server
        model_entrypoint._adb_client = MockAdbClient(state=state)
        model_entrypoint.host.descriptor.network_available = False
        model_entrypoint.host.refresh_network_identity = lambda: None  # type: ignore[method-assign]

        with pytest.raises(DeviceAuthentificationError) as exc_info:
            model_entrypoint.authentificate_device(duplicate_ip, port, code)

        mock_work_cls.assert_not_called()
        assert exc_info.value.reason == "Host network is unavailable"
