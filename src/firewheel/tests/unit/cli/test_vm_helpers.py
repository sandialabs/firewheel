import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from firewheel.cli.executable_section import ExecutableSection
from firewheel.cli.helper import Helper
from firewheel.cli.utils import RichDefaultTable, helpers_path


class _InProcessLocalPythonExecutor:
    def __init__(self, _host_list_path, content):
        self.content = content

    def execute(self, cache_file, _session, arguments):
        old_argv = sys.argv
        namespace = {"__name__": "__main__", "__file__": cache_file}

        try:
            sys.argv = [cache_file]
            if arguments is not None:
                sys.argv.extend(arguments)
            exec(compile("\n".join(self.content), cache_file, "exec"), namespace, namespace)
            return 0
        except SystemExit as exp:
            if exp.code in (None, 0):
                return 0
            if isinstance(exp.code, int):
                return exp.code
            return 1
        finally:
            sys.argv = old_argv

    def get_file_extension(self):
        return ".py"


class VmHelperDisplayTestCase(unittest.TestCase):
    def _load_helper(self, helper_name):
        return Helper(helper_name, str(helpers_path))

    def _run_helper(self, helper_name, arguments=None, extra_patches=None):
        extra_patches = extra_patches or []
        session = {"sequence_number": 0}
        helper = self._load_helper(helper_name)

        with patch.object(
            ExecutableSection,
            "_load_executor",
            return_value=_InProcessLocalPythonExecutor,
        ):
            with ExitStack() as stack:
                for patcher in extra_patches:
                    stack.enter_context(patcher)
                return helper.run(session, arguments)

    def _run_vm_list(self, arguments):
        tables = []

        def _capture_console_print(_console, *args, **_kwargs):
            for arg in args:
                if isinstance(arg, RichDefaultTable):
                    tables.append(arg)

        result = self._run_helper(
            "vm/list",
            arguments,
            extra_patches=[patch("rich.console.Console.print", new=_capture_console_print)],
        )

        self.assertEqual(result, 0)
        self.assertEqual(len(tables), 1)
        return tables[0]

    def _run_vm_mix(self):
        tables = []

        class _LiveCapture:
            def __init__(self, renderable, *args, **kwargs):
                del args, kwargs
                tables.append(renderable)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return False

            def update(self, renderable):
                tables.append(renderable)

        result = self._run_helper(
            "vm/mix",
            extra_patches=[
                patch("rich.live.Live", _LiveCapture),
                patch("time.sleep", side_effect=KeyboardInterrupt),
            ],
        )

        self.assertEqual(result, 0)
        self.assertGreaterEqual(len(tables), 1)
        return tables[0]

    @staticmethod
    def _table_headers(table):
        return [column.header for column in table.columns]

    @staticmethod
    def _table_rows(table):
        if not table.columns:
            return []
        return list(zip(*(column._cells for column in table.columns)))

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_start_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_list_displays_execution_issue_count_in_state_column(
        self,
        mock_get_vm_statuses,
        mock_get_experiment_start_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-1": {
                "state": "RUNNING",
                "uuid": "uuid-1",
                "image": "image.qcow2",
                "hostname": "host-1",
                "vnc": "5901",
                "name": "vm-1",
                "control_ip": "10.0.0.1",
                "devices": [],
            }
        }
        mock_get_experiment_start_time.return_value = None
        mock_get_vm_statuses.return_value = {
            "vm-1": {
                "state": "configured",
                "has_execution_issues": True,
                "execution_issue_count": 2,
                "last_execution_issue": "mkdir exited with code 1",
            }
        }

        table = self._run_vm_list(["state"])

        self.assertEqual(self._table_headers(table), ["Name", "State"])
        self.assertEqual(
            self._table_rows(table),
            [
                (
                    "vm-1",
                    "[green]RUNNING[/green]/[green]configured[/green][yellow] (execution issues: 2)[/yellow]",
                )
            ],
        )

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_start_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_list_filters_rows_by_rendered_state_text(
        self,
        mock_get_vm_statuses,
        mock_get_experiment_start_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-issue": {
                "state": "RUNNING",
                "uuid": "uuid-1",
                "image": "image.qcow2",
                "hostname": "host-1",
                "vnc": "5901",
                "name": "vm-issue",
                "control_ip": "10.0.0.1",
                "devices": [],
            },
            "vm-clean": {
                "state": "RUNNING",
                "uuid": "uuid-2",
                "image": "image.qcow2",
                "hostname": "host-2",
                "vnc": "5902",
                "name": "vm-clean",
                "control_ip": "10.0.0.2",
                "devices": [],
            },
        }
        mock_get_experiment_start_time.return_value = None
        mock_get_vm_statuses.return_value = {
            "vm-issue": {
                "state": "configured",
                "has_execution_issues": True,
                "execution_issue_count": 1,
                "last_execution_issue": "mkdir exited with code 1",
            },
            "vm-clean": {
                "state": "configured",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
        }

        table = self._run_vm_list(["state=execution issues"])

        self.assertEqual(self._table_headers(table), ["Name", "State"])
        self.assertEqual(len(self._table_rows(table)), 1)
        self.assertEqual(self._table_rows(table)[0][0], "vm-issue")

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_start_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_times")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_list_renders_time_field_negative_and_na_values(
        self,
        mock_get_vm_statuses,
        mock_get_vm_times,
        mock_get_experiment_start_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-negative": {
                "state": "RUNNING",
                "uuid": "uuid-1",
                "image": "image.qcow2",
                "hostname": "host-1",
                "vnc": "5901",
                "name": "vm-negative",
                "control_ip": "10.0.0.1",
                "devices": [],
            },
            "vm-empty": {
                "state": "RUNNING",
                "uuid": "uuid-2",
                "image": "image.qcow2",
                "hostname": "host-2",
                "vnc": "5902",
                "name": "vm-empty",
                "control_ip": "10.0.0.2",
                "devices": [],
            },
            "vm-missing": {
                "state": "RUNNING",
                "uuid": "uuid-3",
                "image": "image.qcow2",
                "hostname": "host-3",
                "vnc": "5903",
                "name": "vm-missing",
                "control_ip": "10.0.0.3",
                "devices": [],
            },
        }
        mock_get_experiment_start_time.return_value = None
        mock_get_vm_statuses.return_value = {}
        mock_get_vm_times.return_value = {
            "vm-negative": "-50",
            "vm-empty": "",
        }

        table = self._run_vm_list(["time"])

        self.assertEqual(self._table_headers(table), ["Name", "Time"])
        self.assertEqual(
            dict(self._table_rows(table)),
            {
                "vm-empty": "N/A",
                "vm-missing": "N/A",
                "vm-negative": "-50",
            },
        )

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_start_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_times")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_list_renders_smiley_time_after_experiment_start(
        self,
        mock_get_vm_statuses,
        mock_get_vm_times,
        mock_get_experiment_start_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-1": {
                "state": "RUNNING",
                "uuid": "uuid-1",
                "image": "image.qcow2",
                "hostname": "host-1",
                "vnc": "5901",
                "name": "vm-1",
                "control_ip": "10.0.0.1",
                "devices": [],
            }
        }
        mock_get_experiment_start_time.return_value = object()
        mock_get_vm_statuses.return_value = {}
        mock_get_vm_times.return_value = {"vm-1": "-50"}

        table = self._run_vm_list(["time"])

        self.assertEqual(self._table_rows(table), [("vm-1", " :)")])

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_start_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_list_styles_configuring_failed_testing_and_missing_states(
        self,
        mock_get_vm_statuses,
        mock_get_experiment_start_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-configuring": {
                "state": "RUNNING",
                "uuid": "uuid-1",
                "image": "image.qcow2",
                "hostname": "host-1",
                "vnc": "5901",
                "name": "vm-configuring",
                "control_ip": "10.0.0.1",
                "devices": [],
            },
            "vm-failed": {
                "state": "RUNNING",
                "uuid": "uuid-2",
                "image": "image.qcow2",
                "hostname": "host-2",
                "vnc": "5902",
                "name": "vm-failed",
                "control_ip": "10.0.0.2",
                "devices": [],
            },
            "vm-testing": {
                "state": "RUNNING",
                "uuid": "uuid-3",
                "image": "image.qcow2",
                "hostname": "host-3",
                "vnc": "5903",
                "name": "vm-testing",
                "control_ip": "10.0.0.3",
                "devices": [],
            },
            "vm-missing": {
                "state": "RUNNING",
                "uuid": "uuid-4",
                "image": "image.qcow2",
                "hostname": "host-4",
                "vnc": "5904",
                "name": "vm-missing",
                "control_ip": "10.0.0.4",
                "devices": [],
            },
        }
        mock_get_experiment_start_time.return_value = None
        mock_get_vm_statuses.return_value = {
            "vm-configuring": {
                "state": "configuring",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
            "vm-failed": {
                "state": "failed",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
            "vm-testing": {
                "state": "testing",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
        }

        table = self._run_vm_list(["state"])
        row_map = dict(self._table_rows(table))

        self.assertEqual(
            row_map["vm-configuring"],
            "[green]RUNNING[/green]/[yellow]configuring[/yellow]",
        )
        self.assertEqual(
            row_map["vm-failed"],
            "[green]RUNNING[/green]/[red]failed[/red]",
        )
        self.assertEqual(
            row_map["vm-testing"],
            "[green]RUNNING[/green]/[cyan]testing[/cyan]",
        )
        self.assertEqual(
            row_map["vm-missing"],
            "[green]RUNNING[/green]/[red]status missing[/red]",
        )

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_launch_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_mix_groups_clean_issue_and_missing_rows(
        self,
        mock_get_vm_statuses,
        mock_get_experiment_launch_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-clean-1": {"state": "RUNNING", "image": "image.qcow2"},
            "vm-clean-2": {"state": "RUNNING", "image": "image.qcow2"},
            "vm-issue": {"state": "RUNNING", "image": "image.qcow2"},
            "vm-missing": {"state": "RUNNING", "image": "other.qcow2"},
        }
        mock_get_experiment_launch_time.return_value = object()
        mock_get_vm_statuses.return_value = {
            "vm-clean-1": {
                "state": "configured",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
            "vm-clean-2": {
                "state": "configured",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
            "vm-issue": {
                "state": "configured",
                "has_execution_issues": True,
                "execution_issue_count": 1,
                "last_execution_issue": "mkdir exited with code 1",
            },
        }

        table = self._run_vm_mix()

        self.assertEqual(
            self._table_headers(table),
            ["VM Image", "Power State", "VM Resource State", "Count"],
        )
        self.assertEqual(table.columns[3].footer, "[b]4")
        self.assertCountEqual(
            table.columns[0]._cells,
            ["image.qcow2", "image.qcow2", "other.qcow2"],
        )
        self.assertIn("[green]configured[/green]", table.columns[2]._cells)
        self.assertTrue(any("execution issues" in cell for cell in table.columns[2]._cells))
        self.assertIn("[red]status missing[/red]", table.columns[2]._cells)
        self.assertIn("2", table.columns[3]._cells)

    @patch("firewheel.lib.minimega.api.minimegaAPI")
    @patch("firewheel.vm_resource_manager.api.get_experiment_launch_time")
    @patch("firewheel.vm_resource_manager.api.get_vm_statuses")
    def test_vm_mix_styles_configuring_failed_testing_and_missing_states(
        self,
        mock_get_vm_statuses,
        mock_get_experiment_launch_time,
        mock_minimega_api,
    ):
        mock_minimega_api.return_value.mm_vms.return_value = {
            "vm-configuring": {"state": "RUNNING", "image": "a.qcow2"},
            "vm-failed": {"state": "RUNNING", "image": "b.qcow2"},
            "vm-testing": {"state": "RUNNING", "image": "c.qcow2"},
            "vm-missing": {"state": "RUNNING", "image": "d.qcow2"},
        }
        mock_get_experiment_launch_time.return_value = object()
        mock_get_vm_statuses.return_value = {
            "vm-configuring": {
                "state": "configuring",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
            "vm-failed": {
                "state": "failed",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
            "vm-testing": {
                "state": "testing",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
        }

        table = self._run_vm_mix()
        vmr_cells = table.columns[2]._cells

        self.assertIn("[yellow]configuring[/yellow]", vmr_cells)
        self.assertIn("[red]failed[/red]", vmr_cells)
        self.assertIn("[cyan]testing[/cyan]", vmr_cells)
        self.assertIn("[red]status missing[/red]", vmr_cells)
