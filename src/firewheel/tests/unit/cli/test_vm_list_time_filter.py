"""
End-to-end tests for ``firewheel vm list time[=filter]``.

The real Helper and the real ``vm_resource_manager.api`` are used; only
minimega is mocked and ``VMMapping``/``ExperimentStart`` are pointed at an
in-process gRPC server.
"""

from functools import partial
from unittest.mock import patch

import pytest

from firewheel.cli.utils import RichDefaultTable, helpers_path
from firewheel.cli.helper import Helper
from firewheel.cli.executable_section import ExecutableSection
from firewheel.tests.unit.grpc_test_server import running_grpc_server
from firewheel.tests.unit.cli.test_vm_helpers import _InProcessLocalPythonExecutor
from firewheel.vm_resource_manager.vm_mapping import VMMapping
from firewheel.vm_resource_manager.experiment_start import ExperimentStart

pytestmark = pytest.mark.integration

VM_TIMES = {"vm-zero": "0", "vm-neg": "-50", "vm-unset": ""}


def _minimega_vm(name):
    return {
        "state": "RUNNING",
        "uuid": f"uuid-{name}",
        "image": "image.qcow2",
        "hostname": "host-1",
        "vnc": "5901",
        "name": name,
        "control_ip": "10.0.0.1",
        "devices": [],
    }


@pytest.fixture
def run_vm_list():
    with running_grpc_server() as (_servicer, port):
        connect = {"hostname": "127.0.0.1", "port": str(port), "db": "test"}
        with VMMapping(**connect) as mapping:
            for name, current_time in VM_TIMES.items():
                mapping.put(f"uuid-{name}", name, current_time=current_time)

        def _run(arguments):
            tables = []

            def _capture(_console, *args, **_kwargs):
                tables.extend(arg for arg in args if isinstance(arg, RichDefaultTable))

            with (
                patch.object(
                    ExecutableSection,
                    "_load_executor",
                    return_value=_InProcessLocalPythonExecutor,
                ),
                patch("rich.console.Console.print", new=_capture),
                patch("firewheel.lib.minimega.api.minimegaAPI") as mm_api,
                patch(
                    "firewheel.vm_resource_manager.api.VMMapping",
                    partial(VMMapping, **connect),
                ),
                patch(
                    "firewheel.vm_resource_manager.api.ExperimentStart",
                    partial(ExperimentStart, **connect),
                ),
            ):
                mm_api.return_value.mm_vms.return_value = {
                    name: _minimega_vm(name) for name in VM_TIMES
                }
                helper = Helper("vm/list", str(helpers_path))
                assert helper.run({"sequence_number": 0}, arguments) == 0

            (table,) = tables
            return dict(zip(*(column._cells for column in table.columns)))

        yield _run


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        ("time", {"vm-zero": "0", "vm-neg": "-50", "vm-unset": "N/A"}),
        ("time=", {"vm-zero": "0", "vm-neg": "-50", "vm-unset": "N/A"}),
        ("time=0", {"vm-zero": "0"}),
        ("time=-50", {"vm-neg": "-50"}),
        ("time=7", {}),
    ],
)
def test_vm_list_time_filter(run_vm_list, argument, expected):
    assert run_vm_list([argument]) == expected
