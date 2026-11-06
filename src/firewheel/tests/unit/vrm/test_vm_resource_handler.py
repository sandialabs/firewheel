from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from firewheel.vm_resource_manager.schedule_event import (
    ScheduleEvent,
    ScheduleEventType,
)
from firewheel.vm_resource_manager.vm_resource_handler import VMResourceHandler


@pytest.fixture
def mock_config():
    return {"vm_name": "test_name", "path": "test/path"}


@pytest.fixture
def vmr_handler(mock_config):
    with (
        patch("firewheel.vm_resource_manager.vm_resource_handler.time"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.os"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.Path.mkdir"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.UTCLog"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.RepositoryDb"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.VMMapping"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.ScheduleDb"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.ScheduleUpdater"),
        patch("firewheel.vm_resource_manager.vm_resource_handler.VmResourceStore"),
        patch(
            "firewheel.vm_resource_manager.vm_resource_handler.minimegaAPI"
        ) as mock_minimega_api,
        patch.object(VMResourceHandler, "import_driver"),
        patch.object(VMResourceHandler, "set_state"),
    ):
        mock_minimega_api.return_value.get_cpu_commit_ratio.return_value = 0
        yield VMResourceHandler(mock_config)


def make_file_schedule_entry():
    return SimpleNamespace(
        data=[{"location": "/var/tmp/resource.tar", "filename": "resource.tar"}],
        working_dir=Path("/var/tmp"),
        executable=None,
        on_host=False,
        preloaded=False,
        reboot=False,
    )


class TestVMRHandler:
    @patch.object(VMResourceHandler, "print_output", new=Mock())
    def test_run_vm_resource(self, vmr_handler):
        # Tests minimum viable behavior of `run_vm_resource method`.
        # Minimum viable behavior consists of the following:
        #   - no need to reboot
        #   - preloaded data (no need to create directories or write call args)
        #   - immediate success of `async_exec` when running the `call_args` script
        #   - no use of powershell
        # Mock driver and return values
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.async_exec.return_value = Mock(spec=int)
        # Mock the VM resource inputs
        mock_call_args_filename = "test_filename.sh"
        mock_schedule_entry = Mock(name="schedule_entry")
        mock_schedule_entry.call_args_filename = mock_call_args_filename
        mock_schedule_entry.reboot = False
        mock_schedule_entry.executable = "Test/Executable.exe"
        # Check that correct behavior occurred
        # (methods always succeed, so they are only ever called once)
        vmr_handler.run_vm_resource(mock_schedule_entry)
        mock_pid = vmr_handler.driver.async_exec.return_value
        vmr_handler.driver.async_exec.assert_called_once_with(mock_call_args_filename)
        vmr_handler.driver.get_exitcode.assert_called_once_with(mock_pid)
        vmr_handler.print_output.assert_called_once_with(mock_schedule_entry, mock_pid)

    @patch.object(VMResourceHandler, "set_state", new=Mock())
    def test_check_for_reboot(self, vmr_handler):
        # Mock driver and return values
        vmr_handler.driver = Mock(name="driver")
        file_exists_method = vmr_handler.driver.file_exists
        # Mock the VM resource inputs
        mock_reboot_filepath = Mock(name="reboot_filepath")
        # Check that correct behavior occurred
        need_reboot = vmr_handler.check_for_reboot(mock_reboot_filepath)
        assert need_reboot == file_exists_method.return_value
        file_exists_method.assert_called_once_with(mock_reboot_filepath)

    def test_check_for_reboot_with_reconnect(self, vmr_handler):
        # Mock driver and return values
        vmr_handler.driver = Mock(name="driver")
        file_exists_method = vmr_handler.driver.file_exists
        file_exists_query_results = [None, None, None, True]
        file_exists_method.side_effect = file_exists_query_results
        # Mock the VM resource inputs
        mock_reboot_filepath = Mock(name="reboot_filepath")
        # Check that correct behavior occurred
        need_reboot = vmr_handler.check_for_reboot(mock_reboot_filepath)
        assert need_reboot == file_exists_query_results[-1]
        file_exists_method.assert_called_with(mock_reboot_filepath)
        assert file_exists_method.call_count == len(file_exists_query_results)

    def test_load_files_in_target_reconnects_after_write_failure(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_directories.return_value = True
        vmr_handler.driver.file_exists.return_value = False
        vmr_handler.driver.write_from_file.side_effect = [False, True]
        vmr_handler.vm_resource_store = Mock(name="vm_resource_store")
        vmr_handler.vm_resource_store.get_path.return_value = "/host/resource.tar"
        vmr_handler.connect_to_driver = Mock(name="connect_to_driver")
        schedule_entry = make_file_schedule_entry()

        assert vmr_handler.load_files_in_target(schedule_entry) is True
        assert vmr_handler.driver.write_from_file.call_count == 2
        vmr_handler.connect_to_driver.assert_called_once()

    def test_load_files_in_target_stops_after_bounded_write_failures(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_directories.return_value = True
        vmr_handler.driver.file_exists.return_value = False
        vmr_handler.driver.write_from_file.side_effect = [False] * 10 + [
            AssertionError("write retry loop was not bounded")
        ]
        vmr_handler.vm_resource_store = Mock(name="vm_resource_store")
        vmr_handler.vm_resource_store.get_path.return_value = "/host/resource.tar"
        vmr_handler.connect_to_driver = Mock(name="connect_to_driver")
        schedule_entry = make_file_schedule_entry()

        assert vmr_handler.load_files_in_target(schedule_entry) is False
        assert vmr_handler.driver.write_from_file.call_count == 10
        assert vmr_handler.connect_to_driver.call_count == 9

    def test_preload_files_does_not_mark_failed_preload_complete(self, vmr_handler):
        schedule_entry = make_file_schedule_entry()
        event = ScheduleEvent(ScheduleEventType.NEW_ITEM, schedule_entry)
        vmr_handler.prior_q.put((-1, event))
        vmr_handler.load_files_in_target = Mock(return_value=False)
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_paths.return_value = True

        vmr_handler.preload_files()

        assert schedule_entry.preloaded is False

    def test_load_files_in_target_skips_write_when_target_exists(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_directories.return_value = True
        vmr_handler.driver.file_exists.return_value = True
        vmr_handler.vm_resource_store = Mock(name="vm_resource_store")
        vmr_handler.vm_resource_store.get_path.return_value = "/host/resource.tar"
        schedule_entry = make_file_schedule_entry()

        assert vmr_handler.load_files_in_target(schedule_entry) is True
        vmr_handler.driver.write_from_file.assert_not_called()

    def test_load_files_in_target_reconnects_after_write_oserror(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_directories.return_value = True
        vmr_handler.driver.file_exists.return_value = False
        vmr_handler.driver.write_from_file.side_effect = [OSError("lost qga"), True]
        vmr_handler.vm_resource_store = Mock(name="vm_resource_store")
        vmr_handler.vm_resource_store.get_path.return_value = "/host/resource.tar"
        vmr_handler.connect_to_driver = Mock(name="connect_to_driver")
        schedule_entry = make_file_schedule_entry()

        assert vmr_handler.load_files_in_target(schedule_entry) is True
        assert vmr_handler.driver.write_from_file.call_count == 2
        vmr_handler.connect_to_driver.assert_called_once()

    def test_load_files_in_target_retries_write_when_partial_target_exists(
        self, vmr_handler
    ):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_directories.return_value = True
        vmr_handler.driver.file_exists.side_effect = [False, True]
        vmr_handler.driver.write_from_file.side_effect = [OSError("partial write"), True]
        vmr_handler.vm_resource_store = Mock(name="vm_resource_store")
        vmr_handler.vm_resource_store.get_path.return_value = "/host/resource.tar"
        vmr_handler.connect_to_driver = Mock(name="connect_to_driver")
        schedule_entry = make_file_schedule_entry()

        assert vmr_handler.load_files_in_target(schedule_entry) is True
        assert vmr_handler.driver.write_from_file.call_count == 2
        assert vmr_handler.driver.file_exists.call_count == 1
        vmr_handler.connect_to_driver.assert_called_once()

    def test_load_files_in_target_rewrites_previously_failed_target(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_directories.return_value = True
        vmr_handler.driver.file_exists.return_value = True
        vmr_handler.driver.write_from_file.return_value = True
        vmr_handler.vm_resource_store = Mock(name="vm_resource_store")
        vmr_handler.vm_resource_store.get_path.return_value = "/host/resource.tar"
        schedule_entry = make_file_schedule_entry()
        schedule_entry.failed_preload_paths = {"/var/tmp/resource.tar"}

        assert vmr_handler.load_files_in_target(schedule_entry) is True
        vmr_handler.driver.file_exists.assert_not_called()
        vmr_handler.driver.write_from_file.assert_called_once_with(
            "/var/tmp/resource.tar", "/host/resource.tar"
        )
        assert schedule_entry.failed_preload_paths == set()

    def test_preload_files_marks_successful_preload_complete(self, vmr_handler):
        schedule_entry = make_file_schedule_entry()
        event = ScheduleEvent(ScheduleEventType.NEW_ITEM, schedule_entry)
        vmr_handler.prior_q.put((-1, event))
        vmr_handler.load_files_in_target = Mock(return_value=True)
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.create_paths.return_value = True

        vmr_handler.preload_files()

        assert schedule_entry.preloaded is True
