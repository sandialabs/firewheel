# test_lib_grpc_server.py
"""Unit tests for :mod:`firewheel.lib.grpc.firewheel_grpc_server`."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import grpc
import pytest

from firewheel.lib.grpc.firewheel_grpc_server import FirewheelServicer


class _AbortContext:
    """Simple gRPC-like context helper for abort testing."""

    def abort(self, code, details):
        """Raise a RuntimeError capturing abort semantics."""
        raise RuntimeError((code, details))


def _build_servicer_without_init() -> FirewheelServicer:
    """Create a servicer instance without running __init__."""
    servicer = object.__new__(FirewheelServicer)
    servicer.log = Mock()
    servicer.server_start_time = datetime.now(timezone.utc)
    servicer.version = "1.2.3"
    servicer.cache_dir = "/tmp/cache"
    servicer.dbs = {
        "prod": {
            "vm_mappings": {},
            "not_ready_vmms": set(),
            "ready_states": {"NA", "CONFIGURED"},
            "experiment_start_times": [],
            "experiment_launch_time": None,
        },
        "test": {
            "vm_mappings": {},
            "not_ready_vmms": set(),
            "ready_states": {"NA", "CONFIGURED"},
            "experiment_start_times": [],
            "experiment_launch_time": None,
        },
    }
    return servicer


def test_get_vm_mapping_found() -> None:
    """Verify get_vm_mapping returns found entries."""
    servicer = _build_servicer_without_init()
    vm = Mock()
    assert servicer.get_vm_mapping({"uuid": vm}, "uuid") is vm


def test_get_vm_mapping_missing() -> None:
    """Verify get_vm_mapping returns None on missing keys."""
    servicer = _build_servicer_without_init()
    assert servicer.get_vm_mapping({}, "uuid") is None


def test_init_db() -> None:
    """Verify _init_db creates expected database structure."""
    servicer = _build_servicer_without_init()
    servicer.dbs = {}
    servicer._init_db("prod")

    assert "prod" in servicer.dbs
    assert servicer.dbs["prod"]["vm_mappings"] == {}
    assert servicer.dbs["prod"]["not_ready_vmms"] == set()


def test_get_info() -> None:
    """Verify server info reports version and experiment status."""
    servicer = _build_servicer_without_init()
    response = servicer.GetInfo(Mock(), Mock())
    assert response.version == "1.2.3"
    assert response.uptime >= 0
    assert response.experiment_running is False


def test_set_and_get_experiment_launch_time() -> None:
    """Verify launch time can be stored and retrieved."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"

    assert servicer.SetExperimentLaunchTime(request, Mock()) is request
    assert servicer.GetExperimentLaunchTime(request, Mock()) is request


def test_get_experiment_launch_time_missing_aborts() -> None:
    """Verify missing launch time aborts with OUT_OF_RANGE."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"

    with pytest.raises(RuntimeError) as exc:
        servicer.GetExperimentLaunchTime(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_set_and_get_experiment_start_time() -> None:
    """Verify start time can be stored and retrieved."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"

    servicer.SetExperimentStartTime(request, Mock())
    assert servicer.GetExperimentStartTime(request, Mock()) is request


def test_get_experiment_start_time_missing_aborts() -> None:
    """Verify missing start time aborts with OUT_OF_RANGE."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"

    with pytest.raises(RuntimeError) as exc:
        servicer.GetExperimentStartTime(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_initialize_experiment_start_time() -> None:
    """Verify initialization clears launch/start time state."""
    servicer = _build_servicer_without_init()
    servicer.dbs["prod"]["experiment_launch_time"] = Mock()
    servicer.dbs["prod"]["experiment_start_times"] = [Mock()]

    request = Mock()
    request.db = "prod"

    response = servicer.InitializeExperimentStartTime(request, Mock())
    assert response is not None
    assert servicer.dbs["prod"]["experiment_launch_time"] is None
    assert servicer.dbs["prod"]["experiment_start_times"] == []


def test_count_vm_mappings_not_ready() -> None:
    """Verify not-ready VM count is returned."""
    servicer = _build_servicer_without_init()
    servicer.dbs["prod"]["not_ready_vmms"] = {"a", "b"}
    request = Mock()
    request.db = "prod"

    response = servicer.CountVMMappingsNotReady(request, Mock())
    assert response.count == 2


def test_get_vm_mapping_by_uuid_found() -> None:
    """Verify UUID lookup returns the stored mapping."""
    servicer = _build_servicer_without_init()
    vm = Mock()
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm
    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"

    assert servicer.GetVMMappingByUUID(request, Mock()) is vm


def test_get_vm_mapping_by_uuid_missing_aborts() -> None:
    """Verify missing UUID lookup aborts with OUT_OF_RANGE."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"
    request.server_uuid = "missing"

    with pytest.raises(RuntimeError) as exc:
        servicer.GetVMMappingByUUID(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_set_vm_time_by_uuid() -> None:
    """Verify VM current time can be updated."""
    servicer = _build_servicer_without_init()
    vm = Mock()
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm

    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"
    request.current_time = "123"

    result = servicer.SetVMTimeByUUID(request, Mock())
    assert result is vm
    assert vm.current_time == "123"


def test_update_not_ready_vmms_add_and_remove() -> None:
    """Verify VM readiness tracking set updates correctly."""
    servicer = _build_servicer_without_init()

    vmm = Mock()
    vmm.state = "BOOTING"
    vmm.server_uuid = "uuid"
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" in servicer.dbs["prod"]["not_ready_vmms"]

    vmm.state = "CONFIGURED"
    servicer._update_not_ready_vmms(vmm, "prod")
    assert "uuid" not in servicer.dbs["prod"]["not_ready_vmms"]


def test_set_vm_state_by_uuid() -> None:
    """Verify VM state updates modify stored mappings."""
    servicer = _build_servicer_without_init()
    vm = Mock()
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = vm

    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"
    request.state = "RUNNING"

    result = servicer.SetVMStateByUUID(request, Mock())
    assert result is vm
    assert vm.state == "RUNNING"


def test_set_vm_state_by_uuid_missing_aborts() -> None:
    """Verify missing VM state targets abort."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"
    request.server_uuid = "missing"
    request.state = "RUNNING"

    with pytest.raises(RuntimeError) as exc:
        servicer.SetVMStateByUUID(request, _AbortContext())

    assert exc.value.args[0][0] == grpc.StatusCode.OUT_OF_RANGE


def test_destroy_vm_mapping_by_uuid() -> None:
    """Verify a VM mapping and readiness entry can be removed."""
    servicer = _build_servicer_without_init()
    servicer.dbs["prod"]["vm_mappings"]["uuid"] = Mock()
    servicer.dbs["prod"]["not_ready_vmms"].add("uuid")

    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"

    response = servicer.DestroyVMMappingByUUID(request, Mock())
    assert response is not None
    assert "uuid" not in servicer.dbs["prod"]["vm_mappings"]
    assert "uuid" not in servicer.dbs["prod"]["not_ready_vmms"]


def test_set_vm_mapping() -> None:
    """Verify SetVMMapping stores the provided request object."""
    servicer = _build_servicer_without_init()
    request = Mock()
    request.db = "prod"
    request.server_uuid = "uuid"
    request.state = "BOOTING"

    response = servicer.SetVMMapping(request, Mock())
    assert response is request
    assert servicer.dbs["prod"]["vm_mappings"]["uuid"] is request


def test_destroy_all_vm_mappings() -> None:
    """Verify all VM mappings and readiness tracking are cleared."""
    servicer = _build_servicer_without_init()
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
    with patch(
        "firewheel.lib.grpc.firewheel_grpc_server.FirewheelServicer"
    ) as servicer_cls, patch(
        "firewheel.lib.grpc.firewheel_grpc_server.Config"
    ) as config_cls, patch(
        "firewheel.lib.grpc.firewheel_grpc_server.grpc.server",
        return_value=server,
    ), patch(
        "firewheel.lib.grpc.firewheel_grpc_server.firewheel_grpc_pb2_grpc.add_FirewheelServicer_to_server"
    ), patch(
        "firewheel.lib.grpc.firewheel_grpc_server.time.sleep",
        side_effect=KeyboardInterrupt,
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