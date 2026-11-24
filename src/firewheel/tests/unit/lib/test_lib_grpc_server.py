# test_lib_grpc_server.py
"""Unit tests for :mod:`firewheel.lib.grpc.firewheel_grpc_server`."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

import grpc
import pytest

from firewheel.lib.grpc import firewheel_grpc_pb2
from firewheel.lib.grpc.firewheel_grpc_server import FirewheelServicer
from firewheel.vm_resource_manager.vm_mapping import VMState


class _AbortContext:
    """Simple gRPC-like context helper for abort testing."""

    def abort(self, code, details):
        """Raise a RuntimeError capturing abort semantics."""
        raise RuntimeError((code, details))


def _build_servicer_without_init() -> FirewheelServicer:
    """Create a servicer instance without running __init__."""
    servicer = object.__new__(FirewheelServicer)
    servicer.log = Mock()
    servicer._db_lock = threading.RLock()
    servicer.server_start_time = datetime.now(timezone.utc)
    servicer.version = "1.2.3"
    servicer.cache_dir = "/tmp/cache"
    servicer.dbs = {
        "prod": {
            "vm_mappings": {},
            "not_ready_vmms": set(),
            "ready_states": {"NA", "CONFIGURED"},
            "experiment_start_time": None,
            "experiment_launch_time": None,
        },
        "test": {
            "vm_mappings": {},
            "not_ready_vmms": set(),
            "ready_states": {"NA", "CONFIGURED"},
            "experiment_start_time": None,
            "experiment_launch_time": None,
        },
    }
    return servicer


@pytest.fixture
def servicer() -> FirewheelServicer:
    """Create a fresh ``FirewheelServicer`` test instance for each test."""
    return _build_servicer_without_init()


def test_get_vm_mapping_found(servicer) -> None:
    """Verify get_vm_mapping returns found entries."""
    vm = Mock()
    assert servicer.get_vm_mapping({"uuid": vm}, "uuid") is vm


def test_get_vm_mapping_missing(servicer) -> None:
    """Verify get_vm_mapping returns None on missing keys."""
    assert servicer.get_vm_mapping({}, "uuid") is None


def test_init_db(servicer) -> None:
    """Verify _init_db creates expected database structure."""
    servicer.dbs = {}
    servicer._init_db("prod")

    assert servicer.dbs["prod"] == {
        "vm_mappings": {},
        "not_ready_vmms": set(),
        "ready_states": {VMState.NA.value, VMState.CONFIGURED.value},
        "experiment_start_time": None,
        "experiment_launch_time": None,
    }


def test_get_info(servicer) -> None:
    """Verify server info reports version and experiment status."""
    response = servicer.GetInfo(Mock(), Mock())
    assert response.version == "1.2.3"
    assert response.uptime >= 0
    assert response.experiment_running is False


def test_set_and_get_experiment_launch_time(servicer) -> None:
    """Verify launch time can be stored and retrieved."""
    request = Mock()
    request.db = "prod"

    assert servicer.SetExperimentLaunchTime(request, Mock()) is request
    assert servicer.GetExperimentLaunchTime(request, Mock()) is request


def test_get_experiment_launch_time_missing_aborts(servicer) -> None:
    """Verify missing launch time aborts with OUT_OF_RANGE."""
    request = Mock()
    request.db = "prod"

    with pytest.raises(RuntimeError) as exc:
        servicer.GetExperimentLaunchTime(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_set_and_get_experiment_start_time(servicer) -> None:
    """Verify start time can be stored and retrieved."""
    request = Mock()
    request.db = "prod"

    assert servicer.SetExperimentStartTime(request, Mock()) is request
    assert servicer.GetExperimentStartTime(request, Mock()) is request


def test_set_experiment_start_time_keeps_first_value(servicer) -> None:
    """Verify only the first reported start time is stored and returned."""
    first = Mock(db="prod")
    second = Mock(db="prod")

    assert servicer.SetExperimentStartTime(first, Mock()) is first
    assert servicer.SetExperimentStartTime(second, Mock()) is first
    assert servicer.GetExperimentStartTime(Mock(db="prod"), Mock()) is first


def test_get_experiment_start_time_missing_aborts(servicer) -> None:
    """Verify missing start time aborts with OUT_OF_RANGE."""
    request = Mock()
    request.db = "prod"

    with pytest.raises(RuntimeError) as exc:
        servicer.GetExperimentStartTime(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_initialize_experiment_start_time(servicer) -> None:
    """Verify initialization clears launch/start time state."""
    servicer.dbs["prod"]["experiment_launch_time"] = Mock()
    servicer.dbs["prod"]["experiment_start_time"] = Mock()

    request = Mock()
    request.db = "prod"

    response = servicer.InitializeExperimentStartTime(request, Mock())
    assert response is not None
    assert servicer.dbs["prod"]["experiment_launch_time"] is None
    assert servicer.dbs["prod"]["experiment_start_time"] is None


def test_count_vm_mappings_not_ready(servicer) -> None:
    """Verify not-ready VM count is returned."""
    servicer.dbs["prod"]["not_ready_vmms"] = {"a", "b"}
    request = Mock()
    request.db = "prod"

    response = servicer.CountVMMappingsNotReady(request, Mock())
    assert response.count == 2


def test_get_vm_mapping_by_uuid_found(servicer) -> None:
    """Verify UUID lookup returns a copy of the stored mapping."""
    vm = firewheel_grpc_pb2.VMMapping(server_uuid="uuid", server_name="vm-1")
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm
    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"

    result = servicer.GetVMMappingByUUID(request, Mock())
    assert result == vm
    assert result is not vm


def test_get_vm_mapping_by_uuid_missing_aborts(servicer) -> None:
    """Verify missing UUID lookup aborts with OUT_OF_RANGE."""
    request = Mock()
    request.db = "prod"
    request.server_uuid = "missing"

    with pytest.raises(RuntimeError) as exc:
        servicer.GetVMMappingByUUID(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_set_vm_time_by_uuid(servicer) -> None:
    """Verify VM current time is updated and a copy is returned."""
    vm = firewheel_grpc_pb2.VMMapping(server_uuid="uuid")
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm

    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"
    request.current_time = "123"

    result = servicer.SetVMTimeByUUID(request, Mock())
    assert vm.current_time == "123"
    assert result == vm
    assert result is not vm


def test_update_not_ready_vmms_add_and_remove(servicer) -> None:
    """Verify VM readiness tracking set updates correctly."""
    vmm = Mock()
    vmm.state = "BOOTING"
    vmm.server_uuid = "uuid"
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" in servicer.dbs["prod"]["not_ready_vmms"]

    vmm.state = "CONFIGURED"
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" not in servicer.dbs["prod"]["not_ready_vmms"]


def test_update_not_ready_vmms_accepts_vmstate_enum(servicer) -> None:
    """Verify VMState enum input is normalized for readiness tracking."""
    vmm = Mock()
    vmm.state = VMState.CONFIGURING
    vmm.server_uuid = "uuid"
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" in servicer.dbs["prod"]["not_ready_vmms"]

    vmm.state = VMState.CONFIGURED
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" not in servicer.dbs["prod"]["not_ready_vmms"]


def test_update_not_ready_vmms_ignores_execution_issue_fields(servicer) -> None:
    """Verify execution-issue metadata does not affect readiness accounting."""
    vmm = Mock()
    vmm.state = "configured"
    vmm.server_uuid = "uuid"
    vmm.has_execution_issues = True
    vmm.execution_issue_count = 3
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" not in servicer.dbs["prod"]["not_ready_vmms"]


def test_set_vm_state_by_uuid(servicer) -> None:
    """Verify VM state updates modify stored mappings and return a copy."""
    vm = firewheel_grpc_pb2.VMMapping(server_uuid="uuid")
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm

    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"
    request.state = "RUNNING"

    result = servicer.SetVMStateByUUID(request, Mock())
    assert vm.state == "RUNNING"
    assert result == vm
    assert result is not vm


def test_add_vm_execution_issue_by_uuid_updates_only_issue_fields(servicer) -> None:
    """Verify recording an issue increments the count and leaves state alone."""
    vm = firewheel_grpc_pb2.VMMapping(
        server_uuid="uuid",
        server_name="vm-1",
        state="configured",
        current_time="-5",
        execution_issue_count=2,
        last_execution_issue="old",
    )
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm

    request = firewheel_grpc_pb2.AddVMExecutionIssueByUUIDRequest(
        db="prod", server_uuid="uuid", issue_message="new"
    )
    result = servicer.AddVMExecutionIssueByUUID(request, Mock())

    assert vm.has_execution_issues is True
    assert vm.execution_issue_count == 3
    assert vm.last_execution_issue == "new"
    assert vm.state == "configured"
    assert vm.current_time == "-5"
    assert result == vm
    assert result is not vm
    assert servicer.dbs["prod"]["not_ready_vmms"] == set()


def test_add_vm_execution_issue_by_uuid_missing_aborts(servicer) -> None:
    """Verify an unknown UUID aborts and does not create readiness entries."""
    request = firewheel_grpc_pb2.AddVMExecutionIssueByUUIDRequest(
        db="prod", server_uuid="missing", issue_message="x"
    )

    with pytest.raises(RuntimeError) as exc:
        servicer.AddVMExecutionIssueByUUID(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE
    assert servicer.dbs["prod"]["vm_mappings"] == {}
    assert servicer.dbs["prod"]["not_ready_vmms"] == set()


@pytest.mark.parametrize(
    ("handler", "request_kwargs"),
    [
        ("GetInfo", {}),
        ("SetExperimentLaunchTime", {}),
        ("GetExperimentLaunchTime", {}),
        ("SetExperimentStartTime", {}),
        ("GetExperimentStartTime", {}),
        ("InitializeExperimentStartTime", {}),
        ("CountVMMappingsNotReady", {}),
        ("GetVMMappingByUUID", {}),
        ("SetVMTimeByUUID", {"current_time": "1"}),
        ("SetVMStateByUUID", {"state": "configured"}),
        ("AddVMExecutionIssueByUUID", {"issue_message": "x"}),
        ("DestroyVMMappingByUUID", {}),
        ("SetVMMapping", {"state": "configured"}),
        ("DestroyAllVMMappings", {}),
    ],
)
def test_handlers_hold_db_lock(servicer, handler, request_kwargs) -> None:
    """Verify every handler that touches shared state serializes on ``_db_lock``."""
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = firewheel_grpc_pb2.VMMapping(
        server_uuid="uuid"
    )
    servicer.dbs["prod"]["experiment_launch_time"] = Mock()
    servicer.dbs["prod"]["experiment_start_time"] = Mock()
    servicer.server_start_time = datetime.now(timezone.utc)
    servicer._db_lock = MagicMock()
    request = Mock(db="prod", server_uuid="uuid", **request_kwargs)

    getattr(servicer, handler)(request, Mock())

    servicer._db_lock.__enter__.assert_called_once()
    servicer._db_lock.__exit__.assert_called_once()


def test_list_vm_mappings_holds_db_lock(servicer) -> None:
    """Verify the list snapshot is taken under ``_db_lock``."""
    servicer._db_lock = MagicMock()

    list(servicer.ListVMMappings(Mock(db="prod"), Mock()))

    servicer._db_lock.__enter__.assert_called_once()


def test_destroy_vm_mapping_by_uuid(servicer) -> None:
    """Verify a VM mapping and readiness entry can be removed."""
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = Mock()
    servicer.dbs["prod"]["not_ready_vmms"].add("uuid")

    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"

    response = servicer.DestroyVMMappingByUUID(request, Mock())
    assert response is not None
    assert "uuid" not in servicer.dbs["prod"]["vm_mappings"]
    assert "uuid" not in servicer.dbs["prod"]["not_ready_vmms"]


def test_set_vm_mapping(servicer) -> None:
    """Verify SetVMMapping stores an independent copy of the request."""
    request = firewheel_grpc_pb2.VMMapping(
        db="prod",
        server_uuid="uuid",
        state="BOOTING",
        has_execution_issues=True,
        execution_issue_count=2,
        last_execution_issue="warning text",
    )

    response = servicer.SetVMMapping(request, Mock())
    stored = servicer.dbs["prod"]["vm_mappings"]["uuid"]
    assert stored == request
    assert response == request
    assert stored is not request
    assert response is not stored
    assert "uuid" in servicer.dbs["prod"]["not_ready_vmms"]


def test_destroy_all_vm_mappings(servicer) -> None:
    """Verify all VM mappings and readiness tracking are cleared."""
    servicer.dbs["prod"]["vm_mappings"] = {"uuid": Mock()}
    servicer.dbs["prod"]["not_ready_vmms"] = {"uuid"}

    request = Mock()
    request.db = "prod"

    response = servicer.DestroyAllVMMappings(request, Mock())
    assert response is not None
    assert servicer.dbs["prod"]["vm_mappings"] == {}
    assert servicer.dbs["prod"]["not_ready_vmms"] == set()


def test_serve_startup_path() -> None:
    """Verify serve wires up and starts a gRPC server."""
    server = Mock()
    with (
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.FirewheelServicer"
        ) as servicer_cls,
        patch("firewheel.lib.grpc.firewheel_grpc_server.Config") as config_cls,
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.grpc.server",
            return_value=server,
        ),
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.firewheel_grpc_pb2_grpc.add_FirewheelServicer_to_server"
        ),
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.time.sleep",
            side_effect=KeyboardInterrupt,
        ),
    ):
        servicer = servicer_cls.return_value
        config_cls.return_value.get_config.return_value = {
            "grpc": {"hostname": "127.0.0.1", "port": "50051", "threads": 2}
        }
        serve_result = __import__(
            "firewheel.lib.grpc.firewheel_grpc_server",
            fromlist=["serve"],
        ).serve()

    assert serve_result is None
    server.start.assert_called_once()
    server.stop.assert_called_once_with(0)


def test_set_vm_state_by_uuid_missing_aborts(servicer) -> None:
    """Verify missing VM mapping during state update aborts."""
    request = __import__("unittest").mock.Mock()
    request.db = "prod"
    request.server_uuid = "missing"
    request.state = "RUNNING"

    with pytest.raises(RuntimeError) as exc:
        servicer.SetVMStateByUUID(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_set_vm_state_by_uuid_missing_does_not_mark_not_ready(servicer) -> None:
    """Verify an unknown uuid does not leave a phantom not-ready entry."""
    request = Mock()
    request.db = "prod"
    request.server_uuid = "missing"
    request.state = "configuring"

    with pytest.raises(RuntimeError):
        servicer.SetVMStateByUUID(request, _AbortContext())

    assert servicer.dbs["prod"]["not_ready_vmms"] == set()


def test_set_vm_time_by_uuid_missing_aborts(servicer) -> None:
    """Verify missing VM mapping during time update aborts with OUT_OF_RANGE."""
    request = Mock()
    request.db = "prod"
    request.server_uuid = "missing"
    request.current_time = "10"

    with pytest.raises(RuntimeError) as exc:
        servicer.SetVMTimeByUUID(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE
    assert servicer.dbs["prod"]["vm_mappings"] == {}


def test_serve_returns_when_bind_fails() -> None:
    """Verify serve returns cleanly when add_insecure_port fails."""
    server = __import__("unittest").mock.Mock()
    server.add_insecure_port.side_effect = RuntimeError("bind fail")

    with (
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.FirewheelServicer"
        ) as servicer_cls,
        patch("firewheel.lib.grpc.firewheel_grpc_server.Config") as config_cls,
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.grpc.server",
            return_value=server,
        ),
        patch(
            "firewheel.lib.grpc.firewheel_grpc_server.firewheel_grpc_pb2_grpc.add_FirewheelServicer_to_server"
        ),
    ):
        config_cls.return_value.get_config.return_value = {
            "grpc": {"hostname": "127.0.0.1", "port": "50051", "threads": 2}
        }
        result = __import__(
            "firewheel.lib.grpc.firewheel_grpc_server",
            fromlist=["serve"],
        ).serve()

    assert result is None
    servicer_cls.return_value.log.warning.assert_called_once()
