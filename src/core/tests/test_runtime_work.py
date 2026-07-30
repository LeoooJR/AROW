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


class TestModelEntrypoint:
    def test_authentificate_device_requires_initialized_adb(self) -> None:
        """Missing runtime references are rejected by AuthenticateDeviceWork preflight."""
        model_entrypoint = ModelEntrypoint()

        with pytest.raises(DeviceAuthentificationError) as exc_info:
            model_entrypoint.authentificate_device("127.0.0.1", 5555, "123456")

        assert exc_info.value.reason == "ADB runtime preflight failed"
        assert exc_info.value.ip == "127.0.0.1"
        assert exc_info.value.port == 5555
        assert exc_info.value.association_code == "123456"

    def test_authentificate_device_missing_client_uses_work_preflight(self) -> None:
        state = MockAdbState(seed=10, initial_devices=0)
        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = MockAdbServer(state=state)
        model_entrypoint._adb_client = None

        with pytest.raises(DeviceAuthentificationError) as exc_info:
            model_entrypoint.authentificate_device("192.168.1.10", 37777, "123456")

        assert exc_info.value.reason == "ADB runtime preflight failed"
        assert exc_info.value.ip == "192.168.1.10"
        assert exc_info.value.port == 37777

    @patch("core.entrypoint.AuthenticateDeviceWork")
    def test_authentificate_device_delegates_duplicate_endpoint_to_work(
        self, mock_work_cls: MagicMock
    ) -> None:
        """Duplicate endpoint rejection belongs to AuthenticateDeviceWork preflight."""
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
        expected_outcome = AuthentificateDeviceOutcome(success_phone=Phone(id="unused"))
        mock_work_cls.return_value.run.return_value = expected_outcome

        outcome = model_entrypoint.authentificate_device(duplicate_ip, port, code)

        mock_work_cls.assert_called_once_with(
            adb_server=server,
            adb_client=client,
            ip=duplicate_ip,
            port=port,
            association_code=code,
        )
        assert outcome is expected_outcome

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
    def test_authentificate_device_leaves_network_gate_to_work_preflight(
        self, mock_work_cls: MagicMock
    ) -> None:
        state = MockAdbState(seed=13, initial_devices=0)
        model_entrypoint = ModelEntrypoint()
        model_entrypoint._adb_server = MockAdbServer(state=state)
        model_entrypoint._adb_client = MockAdbClient(state=state)
        model_entrypoint.host.descriptor.network_available = False
        expected_phone = Phone(id="paired", state="device")
        expected_outcome = AuthentificateDeviceOutcome(success_phone=expected_phone)
        mock_work_cls.return_value.run.return_value = expected_outcome

        outcome = model_entrypoint.authentificate_device(
            "192.168.1.42", 37777, "123456"
        )

        mock_work_cls.assert_called_once()
        assert outcome is expected_outcome
