import base64
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
    # Note: In Python 3.10, we can stack these context managers
    #       https://docs.python.org/3/whatsnew/3.10.html#parenthesized-context-managers
    with patch(f"{QGA_DRIVER_MODULE}.QEMUMonitorProtocol", spec=True):
        with patch.object(QemuGuestAgentDriver, "sync"):
            with patch("time.sleep"):
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

    def test_store_captured_output_decodes_with_backslashreplace(self, mock_driver):
        pid = 42
        smart_quotes = "mkdir: cannot create directory ‘/tmp/t2/True’\n".encode(
            "utf-8"
        )
        invalid_bytes = b"bad\xffbytes"

        mock_driver.store_captured_output(
            pid,
            {
                "out-data": base64.b64encode(smart_quotes).decode("ascii"),
                "err-data": base64.b64encode(invalid_bytes).decode("ascii"),
            },
        )

        assert mock_driver.output_cache[pid]["stdout"] == (
            "mkdir: cannot create directory ‘/tmp/t2/True’\n"
        )
        assert mock_driver.output_cache[pid]["stderr"] == r"bad\xffbytes"
