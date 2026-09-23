from unittest.mock import Mock, MagicMock, patch

import pytest
from qemu.qmp.legacy import QEMUMonitorProtocol

from firewheel.vm_resource_manager.drivers.qemu_guest_agent_driver import (
    QemuGuestAgentDriver,
)

QGA_DRIVER_MODULE = "firewheel.vm_resource_manager.drivers.qemu_guest_agent_driver"


@pytest.fixture
def mock_driver():
    mock_config = MagicMock(name="config")
    mock_log = Mock(name="log")
    # Mock the driver to omit QMP/sync interactions
    with (
        patch(f"{QGA_DRIVER_MODULE}.QEMUMonitorProtocol", spec=True),
        patch.object(QemuGuestAgentDriver, "sync"),
        patch("time.sleep"),
    ):
        yield QemuGuestAgentDriver(mock_config, mock_log)


class TestQemuGuestAgentDriver:

    def test_initialize(self, mock_driver):
        assert isinstance(mock_driver.qga, QEMUMonitorProtocol)
        mock_driver.qga.connect.assert_called_once()
        mock_driver.sync.assert_called_once()
        assert mock_driver.output_cache == {}

    def test_reboot(self, mock_driver):
        mock_driver.output_cache = Mock(name="cache")
        mock_driver.reboot()
        mock_driver.qga.cmd.assert_called_once()
        assert mock_driver.output_cache == {}
