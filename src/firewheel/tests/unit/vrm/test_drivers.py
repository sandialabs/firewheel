from unittest.mock import ANY, Mock, MagicMock, call, patch

import pytest
from qemu.qmp.legacy import QEMUMonitorProtocol

from firewheel.vm_resource_manager.drivers.qemu_guest_agent_driver import (
    QemuGuestAgentDriver,
    _GUEST_FILE_WRITE_TIMEOUT_SEC,
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

    def test_file_write_from_file_aborts_after_transient_write_exception(
        self, mock_driver, tmp_path
    ):
        local_file = tmp_path / "resource.tar"
        local_file.write_bytes(b"abc")
        mock_driver.qga.cmd.side_effect = [
            TimeoutError("guest-file-write timed out"),
            {"return": {"count": 3}},
        ]

        with pytest.raises(OSError, match="guest-file-write timed out"):
            mock_driver.file_write_from_file(10, local_file)
        mock_driver.qga.cmd.assert_called_once_with(
            "guest-file-write",
            {"handle": 10, "buf-b64": "YWJj", "count": 3},
        )

    def test_file_write_from_file_skips_empty_chunk_at_eof(self, mock_driver, tmp_path):
        local_file = tmp_path / "resource.tar"
        local_file.write_bytes(b"abc")
        content = b"a" * 1024000
        mock_driver.qga.cmd.side_effect = [
            {"return": {"count": len(content)}},
            AssertionError("empty EOF chunk should not be written"),
        ]

        with patch(
            f"{QGA_DRIVER_MODULE}.open",
            MagicMock(
                return_value=MagicMock(
                    __enter__=Mock(
                        return_value=Mock(read=Mock(side_effect=[content, b""]))
                    )
                )
            ),
        ):
            assert mock_driver.file_write_from_file(10, local_file) is True

        mock_driver.qga.cmd.assert_called_once_with(
            "guest-file-write",
            {"handle": 10, "buf-b64": ANY, "count": len(content)},
        )

    def test_write_from_file_closes_handle_when_write_raises(self, mock_driver):
        handle = 123

        def qga_cmd(command, *args, **kwargs):
            if command == "guest-file-open":
                return {"return": handle}
            if command == "guest-file-close":
                return {"return": {}}
            raise AssertionError(f"Unexpected QGA command: {command}")

        mock_driver.qga.cmd.side_effect = qga_cmd

        with (
            patch.object(
                mock_driver, "file_write_from_file", side_effect=OSError("write failed")
            ),
            pytest.raises(OSError),
        ):
            mock_driver.write_from_file("/guest/resource.tar", "/host/resource.tar")

        mock_driver.qga.cmd.assert_has_calls(
            [
                call("guest-file-open", {"path": "/guest/resource.tar", "mode": "w"}),
                call("guest-file-close", {"handle": handle}),
            ]
        )

    def test_file_write_from_file_raises_oserror_for_write_exception(
        self, mock_driver, tmp_path
    ):
        local_file = tmp_path / "resource.tar"
        local_file.write_bytes(b"abc")
        mock_driver.qga.cmd.side_effect = TimeoutError("timed out")

        with pytest.raises(OSError, match="timed out"):
            mock_driver.file_write_from_file(10, local_file)
        mock_driver.qga.cmd.assert_called_once_with(
            "guest-file-write",
            {"handle": 10, "buf-b64": "YWJj", "count": 3},
        )
        mock_driver.log.error.assert_any_call(
            "QGA file write failed for %s at chunk=%s, bytes_written=%s, "
            "elapsed_sec=%.2f",
            local_file,
            1,
            0,
            ANY,
        )

    def test_file_write_from_file_logs_start_and_success(self, mock_driver, tmp_path):
        local_file = tmp_path / "resource.tar"
        local_file.write_bytes(b"abc")
        mock_driver.qga.cmd.return_value = {"return": {"count": 3}}

        assert mock_driver.file_write_from_file(10, local_file) is True

        mock_driver.log.info.assert_any_call(
            "Starting QGA file write from %s: total_bytes=%s, chunk_size=%s, "
            "timeout_sec=%s, estimated_chunks=%s",
            local_file,
            3,
            1024000,
            _GUEST_FILE_WRITE_TIMEOUT_SEC,
            1,
        )
        mock_driver.log.info.assert_any_call(
            "Completed QGA file write from %s: chunks_written=%s, bytes_written=%s, "
            "total_bytes=%s, elapsed_sec=%.2f, throughput_mib_sec=%.2f",
            local_file,
            1,
            3,
            3,
            ANY,
            ANY,
        )

    def test_file_write_from_file_raises_oserror_for_missing_return_response(
        self, mock_driver, tmp_path
    ):
        local_file = tmp_path / "resource.tar"
        local_file.write_bytes(b"abc")
        mock_driver.qga.cmd.side_effect = [{}, {"return": {"count": 3}}]

        with pytest.raises(OSError, match="guest-file-write"):
            mock_driver.file_write_from_file(10, local_file)
        mock_driver.qga.cmd.assert_called_once_with(
            "guest-file-write",
            {"handle": 10, "buf-b64": "YWJj", "count": 3},
        )

    def test_write_from_file_raises_oserror_for_missing_open_return(self, mock_driver):
        mock_driver.qga.cmd.return_value = {}

        with pytest.raises(OSError, match="guest-file-open"):
            mock_driver.write_from_file("/guest/resource.tar", "/host/resource.tar")

    def test_write_from_file_raises_oserror_for_mismatched_write_count(
        self, mock_driver
    ):
        handle = 123

        def qga_cmd(command, *args, **kwargs):
            if command == "guest-file-open":
                return {"return": handle}
            if command == "guest-file-close":
                return {"return": {}}
            raise AssertionError(f"Unexpected QGA command: {command}")

        mock_driver.qga.cmd.side_effect = qga_cmd
        with (
            patch.object(
                mock_driver,
                "file_write_from_file",
                side_effect=RuntimeError(
                    "File write: Returned size of 1024000 does not match read size of 613888"
                ),
            ),
            pytest.raises(OSError, match="Returned size"),
        ):
            mock_driver.write_from_file("/guest/resource.tar", "/host/resource.tar")

        mock_driver.qga.cmd.assert_has_calls(
            [
                call("guest-file-open", {"path": "/guest/resource.tar", "mode": "w"}),
                call("guest-file-close", {"handle": handle}),
            ]
        )

    def test_file_write_from_file_resets_timeout_after_failed_attempt(
        self, mock_driver, tmp_path
    ):
        local_file = tmp_path / "resource.tar"
        local_file.write_bytes(b"abc")
        mock_driver.qga.cmd.side_effect = TimeoutError("guest-file-write timed out")

        with pytest.raises(OSError, match="guest-file-write timed out"):
            mock_driver.file_write_from_file(10, local_file)
        assert mock_driver.qga.settimeout.mock_calls == [
            call(_GUEST_FILE_WRITE_TIMEOUT_SEC),
            call(None),
        ]
