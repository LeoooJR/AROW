from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.adb_mock import MockAdbClient, MockAdbServer, MockAdbState
from core.devices import Phone
from core.models import CoreRuntimeModel
from core.work.authentificate_device_work import AuthentificateDeviceOutcome
from core.work.close_work import CloseCoreRuntimeWork, CloseOutcome

pytestmark = [pytest.mark.async_jobs]


class TestCloseCoreRuntimeWork:
    def test_apply_main_thread_skips_signal_without_server(self) -> None:
        model = CoreRuntimeModel()
        emitted: list[tuple[object, object]] = []

        def fake_emit(signal: object, payload: object) -> None:
            emitted.append((signal, payload))

        model._signal_bus.emit = fake_emit
        CloseCoreRuntimeWork.apply_main_thread(model, CloseOutcome(adb_server=None))
        assert model.adb_server is None
        assert emitted == []


class TestCoreRuntimeModel:
    def test_authentificate_device_requires_initialized_adb(self) -> None:
        """Pairing is rejected until startup has bound server and client on the model."""
        model = CoreRuntimeModel()
        with pytest.raises(
            AttributeError, match="must be initialized before authentification"
        ):
            model.authentificate_device("127.0.0.1", 5555, "123456")

    @patch("core.models.AuthenticateDeviceWork")
    def test_authentificate_device_skips_work_when_ip_already_paired(
        self, mock_work_cls: MagicMock
    ) -> None:
        """
        :meth:`CoreRuntimeModel.authentificate_device` must not start a new pair attempt
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
        model = CoreRuntimeModel()
        model._adb_server = server
        model._adb_client = client

        outcome = model.authentificate_device(duplicate_ip, port, code)

        mock_work_cls.assert_not_called()
        assert outcome.success_phone is None
        assert outcome.failure is not None
        assert outcome.failure.ip == duplicate_ip
        assert outcome.failure.port == port
        assert outcome.failure.association_code == code
        assert outcome.failure.reason == "Device with this IP address is already paired"

    @patch("core.models.AuthenticateDeviceWork")
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
        expected_outcome = AuthentificateDeviceOutcome(
            success_phone=expected_phone, failure=None
        )
        mock_work_cls.return_value.run.return_value = expected_outcome

        model = CoreRuntimeModel()
        model._adb_server = server
        model._adb_client = client

        outcome = model.authentificate_device(requested_ip, port, code)

        mock_work_cls.assert_called_once_with(
            adb_server=server,
            adb_client=client,
            ip=requested_ip,
            port=port,
            association_code=code,
        )
        assert outcome is expected_outcome
