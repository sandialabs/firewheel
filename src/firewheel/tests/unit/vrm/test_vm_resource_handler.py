from unittest.mock import Mock, patch

import pytest

from firewheel.vm_resource_manager.vm_resource_handler import VMResourceHandler
from firewheel.vm_resource_manager.schedule_event import ScheduleEventType
from firewheel.vm_resource_manager.vm_mapping import VMState


@pytest.fixture
def mock_config():
    return {"vm_name": "test_name", "path": "test/path", "vm_uuid": "test-uuid"}


@pytest.fixture
def vmr_handler(mock_config):
    mock_driver = Mock(name="driver")
    mock_driver.get_os.return_value = "Linux"
    mock_driver.set_time.return_value = None

    def _connect_to_driver(handler):
        handler.driver = mock_driver
        return True

    with patch("firewheel.vm_resource_manager.vm_resource_handler.time"), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.os"
    ), patch("firewheel.vm_resource_manager.vm_resource_handler.Path.mkdir"), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.UTCLog"
    ), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.RepositoryDb"
    ), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.VMMapping"
    ), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.ScheduleDb"
    ), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.ScheduleUpdater"
    ), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.VmResourceStore"
    ), patch(
        "firewheel.vm_resource_manager.vm_resource_handler.minimegaAPI"
    ) as mock_minimega_api, patch.object(
        VMResourceHandler, "import_driver"
    ), patch.object(
        VMResourceHandler, "set_state"
    ), patch.object(
        VMResourceHandler, "connect_to_driver", _connect_to_driver
    ):
        mock_minimega_api.return_value.get_cpu_commit_ratio.return_value = 0
        yield VMResourceHandler(mock_config)


class TestVMRHandler:
    @patch.object(VMResourceHandler, "print_output", new=Mock())
    def test_run_vm_resource(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.async_exec.return_value = Mock(spec=int)
        vmr_handler.driver.get_exitcode.return_value = 0
        vmr_handler.driver.file_exists.return_value = False

        mock_call_args_filename = "test_filename.sh"
        mock_schedule_entry = Mock(name="schedule_entry")
        mock_schedule_entry.call_args_filename = mock_call_args_filename
        mock_schedule_entry.reboot = False
        mock_schedule_entry.executable = "Test/Executable.exe"
        mock_schedule_entry.preloaded = True
        mock_schedule_entry.data = []

        vmr_handler.run_vm_resource(mock_schedule_entry)
        mock_pid = vmr_handler.driver.async_exec.return_value
        vmr_handler.driver.async_exec.assert_called_once_with(mock_call_args_filename)
        vmr_handler.driver.get_exitcode.assert_called_once_with(mock_pid)
        vmr_handler.print_output.assert_called_once_with(mock_schedule_entry, mock_pid)

    @patch("firewheel.vm_resource_manager.vm_resource_handler.utils.add_execution_issue")
    def test_run_vm_resource_records_nonfatal_execution_issue(
        self, mock_add_execution_issue, vmr_handler
    ):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.async_exec.return_value = 42
        vmr_handler.driver.get_exitcode.return_value = 1
        vmr_handler.driver.file_exists.return_value = False
        vmr_handler.print_output = Mock(name="print_output")

        mock_schedule_entry = Mock(name="schedule_entry")
        mock_schedule_entry.call_args_filename = "test_filename.sh"
        mock_schedule_entry.reboot = False
        mock_schedule_entry.executable = "mkdir"
        mock_schedule_entry.preloaded = True
        mock_schedule_entry.data = []

        vmr_handler.run_vm_resource(mock_schedule_entry)

        mock_add_execution_issue.assert_called_once_with(
            "test-uuid",
            "mkdir exited with code 1",
            mapping=vmr_handler.vm_mapping,
            log=vmr_handler.log,
        )
        vmr_handler.print_output.assert_called_once_with(mock_schedule_entry, 42)

    @patch("firewheel.vm_resource_manager.vm_resource_handler.utils.add_execution_issue")
    def test_run_vm_resource_does_not_record_execution_issue_on_success(
        self, mock_add_execution_issue, vmr_handler
    ):
        vmr_handler.driver = Mock(name="driver")
        vmr_handler.driver.async_exec.return_value = 42
        vmr_handler.driver.get_exitcode.return_value = 0
        vmr_handler.driver.file_exists.return_value = False
        vmr_handler.print_output = Mock(name="print_output")

        mock_schedule_entry = Mock(name="schedule_entry")
        mock_schedule_entry.call_args_filename = "test_filename.sh"
        mock_schedule_entry.reboot = False
        mock_schedule_entry.executable = "mkdir"
        mock_schedule_entry.preloaded = True
        mock_schedule_entry.data = []

        vmr_handler.run_vm_resource(mock_schedule_entry)

        mock_add_execution_issue.assert_not_called()

    @patch("firewheel.vm_resource_manager.vm_resource_handler.utils.add_execution_issue")
    def test_run_loop_records_nonfatal_execution_issue_for_ignored_load_failure(
        self, mock_add_execution_issue, vmr_handler
    ):
        event = Mock(name="event")
        schedule_entry = Mock(name="schedule_entry")
        schedule_entry.on_host = False
        schedule_entry.ignore_failure = True
        schedule_entry.executable = "push_file"
        schedule_entry.start_time = 0
        event.get_type.return_value = ScheduleEventType.NEW_ITEM
        event.get_data.return_value = schedule_entry

        with patch.object(
            vmr_handler, "preload_files"
        ), patch.object(
            vmr_handler, "get_events", side_effect=[[event], KeyboardInterrupt]
        ), patch.object(
            vmr_handler.driver, "create_paths"
        ), patch.object(
            vmr_handler, "load_files_in_target", return_value=False
        ):
            with pytest.raises(KeyboardInterrupt):
                vmr_handler._run()

        mock_add_execution_issue.assert_called_once_with(
            "test-uuid",
            "Unable to load files into VM for push_file",
            mapping=vmr_handler.vm_mapping,
            log=vmr_handler.log,
        )

    def test_run_loop_marks_failed_and_exits_for_fatal_load_failure(self, vmr_handler):
        event = Mock(name="event")
        schedule_entry = Mock(name="schedule_entry")
        schedule_entry.on_host = False
        schedule_entry.ignore_failure = False
        schedule_entry.executable = "push_file"
        schedule_entry.start_time = 0
        event.get_type.return_value = ScheduleEventType.NEW_ITEM
        event.get_data.return_value = schedule_entry
        vmr_handler.set_state = Mock(name="set_state")

        with patch.object(
            vmr_handler, "preload_files"
        ), patch.object(
            vmr_handler, "get_events", return_value=[event]
        ), patch.object(
            vmr_handler.driver, "create_paths"
        ), patch.object(
            vmr_handler, "load_files_in_target", return_value=False
        ), patch(
            "firewheel.vm_resource_manager.vm_resource_handler.sys.exit",
            side_effect=SystemExit(1),
        ) as mock_exit:
            with pytest.raises(SystemExit):
                vmr_handler._run()

        vmr_handler.set_state.assert_called_once_with(VMState.FAILED)
        mock_exit.assert_called_once_with(1)

    def test_record_execution_issue_swallows_metadata_errors(self, vmr_handler):
        vmr_handler.log = Mock(name="log")

        with patch(
            "firewheel.vm_resource_manager.vm_resource_handler.utils.add_execution_issue",
            side_effect=RuntimeError("boom"),
        ):
            vmr_handler._record_execution_issue("mkdir exited with code 1")

        vmr_handler.log.error.assert_called_once_with(
            "Unable to record vm_resource execution issue: %s",
            "mkdir exited with code 1",
        )
        vmr_handler.log.exception.assert_called_once()

    @patch.object(VMResourceHandler, "set_state", new=Mock())
    def test_check_for_reboot(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        file_exists_method = vmr_handler.driver.file_exists
        mock_reboot_filepath = Mock(name="reboot_filepath")
        need_reboot = vmr_handler.check_for_reboot(mock_reboot_filepath)
        assert need_reboot == file_exists_method.return_value
        file_exists_method.assert_called_once_with(mock_reboot_filepath)

    def test_check_for_reboot_with_reconnect(self, vmr_handler):
        vmr_handler.driver = Mock(name="driver")
        file_exists_method = vmr_handler.driver.file_exists
        file_exists_query_results = [None, None, None, True]
        file_exists_method.side_effect = file_exists_query_results
        mock_reboot_filepath = Mock(name="reboot_filepath")
        with patch.object(vmr_handler, "connect_to_driver"):
            need_reboot = vmr_handler.check_for_reboot(mock_reboot_filepath)
        assert need_reboot == file_exists_query_results[-1]
        file_exists_method.assert_called_with(mock_reboot_filepath)
        assert file_exists_method.call_count == len(file_exists_query_results)

    def test_print_stream_logs_human_readable_text(self, vmr_handler):
        vmr_handler.log = Mock(name="log")
        vmr_handler.log_json = Mock(name="log_json")
        output = {}
        stream = "mkdir: cannot create directory ‘/tmp/t2/True’\n"

        vmr_handler._print_stream(output, stream, "stderr")

        assert output == {"fd": "stderr", "output": stream}
        vmr_handler.log.info.assert_called_once_with(stream)
        vmr_handler.log_json.assert_called_once_with(
            stream.encode("utf-8", errors="backslashreplace")
        )

    def test_best_effort_set_failed_state_marks_vm_failed(self, vmr_handler):
        vmr_handler.set_state = Mock(name="set_state")

        vmr_handler._best_effort_set_failed_state("boom")

        vmr_handler.set_state.assert_called_once()
        assert vmr_handler.set_state.call_args.args[0].value == "failed"

    def test_best_effort_set_failed_state_swallows_set_state_errors(self, vmr_handler):
        vmr_handler.log = Mock(name="log")
        vmr_handler.set_state = Mock(name="set_state", side_effect=RuntimeError("boom"))

        vmr_handler._best_effort_set_failed_state("boom")

        vmr_handler.log.error.assert_any_call("Marking VM as failed: %s", "boom")
        vmr_handler.log.error.assert_any_call(
            "Unable to set failed VM state after fatal error"
        )
        vmr_handler.log.exception.assert_called_once()

    def test_run_marks_failed_on_unexpected_handler_exception(self, vmr_handler):
        vmr_handler._run = Mock(name="_run", side_effect=RuntimeError("boom"))
        vmr_handler._best_effort_set_failed_state = Mock(
            name="_best_effort_set_failed_state"
        )

        vmr_handler.run()

        vmr_handler._best_effort_set_failed_state.assert_called_once_with(
            "VMResourceHandler stopped due to an unexpected exception"
        )

    def test_run_vm_resource_marks_failed_on_unexpected_exception(self, vmr_handler):
        schedule_entry = Mock(name="schedule_entry")
        schedule_entry.executable = "mkdir"
        vmr_handler._run_vm_resource = Mock(
            name="_run_vm_resource", side_effect=RuntimeError("boom")
        )
        vmr_handler._best_effort_set_failed_state = Mock(
            name="_best_effort_set_failed_state"
        )

        vmr_handler.run_vm_resource(schedule_entry)

        vmr_handler._best_effort_set_failed_state.assert_called_once_with(
            "mkdir raised an unexpected exception"
        )

    def test_run_vm_resource_host_marks_failed_on_unexpected_exception(
        self, vmr_handler
    ):
        schedule_entry = Mock(name="schedule_entry")
        schedule_entry.executable = "/usr/bin/echo"
        vmr_handler._run_vm_resource_host = Mock(
            name="_run_vm_resource_host", side_effect=RuntimeError("boom")
        )
        vmr_handler._best_effort_set_failed_state = Mock(
            name="_best_effort_set_failed_state"
        )

        vmr_handler.run_vm_resource_host(schedule_entry)

        vmr_handler._best_effort_set_failed_state.assert_called_once_with(
            "host vm_resource /usr/bin/echo raised an unexpected exception"
        )
