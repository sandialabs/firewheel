# test_lib_grpc_client.py
"""Unit tests for :mod:`firewheel.lib.grpc.firewheel_grpc_client`."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import grpc
import pytest

from firewheel.lib.grpc.firewheel_grpc_client import FirewheelGrpcClient


class _RpcException(grpc.RpcError):
    """Simple grpc.RpcError stand-in with a configurable status code."""

    def __init__(self, code):
        super().__init__()
        self._code = code

    def exception(self):
        """Mimic grpc future-style exception wrapper behavior."""
        return self

    def code(self):
        """Return the configured gRPC status code."""
        return self._code


def _build_client_without_init() -> FirewheelGrpcClient:
    """Create a client instance without running __init__."""
    client = object.__new__(FirewheelGrpcClient)
    client.db = "prod"
    client.server_addr = "localhost:50051"
    client.chan = Mock()
    client.stub = Mock()
    client.log = Mock()
    client.connected = True
    return client


def test_init_invalid_port() -> None:
    """Verify invalid gRPC ports raise RuntimeError."""
    with pytest.raises(RuntimeError):
        FirewheelGrpcClient(port="70000", require_connection=False)


def test_check_connection_success() -> None:
    """Verify check_connection returns True when server info is available."""
    client = _build_client_without_init()
    client.get_info = Mock(return_value={"version": "1.0"})
    assert client.check_connection(error=True) is True


def test_check_connection_failure_no_error() -> None:
    """Verify missing connection returns False when error is disabled."""
    client = _build_client_without_init()
    client.get_info = Mock(return_value=None)
    assert client.check_connection(error=False) is False


def test_check_connection_failure_with_error() -> None:
    """Verify missing connection raises ConnectionError when required."""
    client = _build_client_without_init()
    client.get_info = Mock(return_value=None)
    with pytest.raises(ConnectionError):
        client.check_connection(error=True)


def test_get_info_success() -> None:
    """Verify GetInfo response is converted to a dictionary."""
    client = _build_client_without_init()
    response = object()
    client.stub.GetInfo.return_value = response

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"version": "1.2.3"},
    ):
        assert client.get_info() == {"version": "1.2.3"}


def test_get_info_unavailable_returns_none() -> None:
    """Verify unavailable GetInfo calls return None."""
    client = _build_client_without_init()
    client.stub.GetInfo.side_effect = _RpcException(grpc.StatusCode.UNAVAILABLE)
    assert client.get_info() is None


def test_get_experiment_launch_time_success() -> None:
    """Verify launch time responses are converted to UTC datetimes."""
    client = _build_client_without_init()
    launch_time = datetime.now(timezone.utc)

    response = Mock()
    response.launch_time.ToDatetime.return_value = launch_time.replace(tzinfo=None)
    client.stub.GetExperimentLaunchTime.return_value = response

    result = client.get_experiment_launch_time()
    assert result.tzinfo == timezone.utc


def test_get_experiment_launch_time_out_of_range_returns_none() -> None:
    """Verify missing launch time returns None."""
    client = _build_client_without_init()
    client.stub.GetExperimentLaunchTime.side_effect = _RpcException(
        grpc.StatusCode.OUT_OF_RANGE
    )
    assert client.get_experiment_launch_time() is None


def test_get_experiment_start_time_success() -> None:
    """Verify start time responses are converted to UTC datetimes."""
    client = _build_client_without_init()
    start_time = datetime.now(timezone.utc)

    response = Mock()
    response.start_time.ToDatetime.return_value = start_time.replace(tzinfo=None)
    client.stub.GetExperimentStartTime.return_value = response

    result = client.get_experiment_start_time()
    assert result.tzinfo == timezone.utc


def test_set_experiment_launch_time() -> None:
    """Verify launch time setters return the stored UTC time."""
    client = _build_client_without_init()
    now = datetime.now(timezone.utc)

    response = Mock()
    response.launch_time.ToDatetime.return_value = now.replace(tzinfo=None)
    client.stub.SetExperimentLaunchTime.return_value = response

    result = client.set_experiment_launch_time(now)
    assert result.tzinfo == timezone.utc


def test_set_experiment_start_time() -> None:
    """Verify start time setters return the stored UTC time."""
    client = _build_client_without_init()
    now = datetime.now(timezone.utc)

    response = Mock()
    response.start_time.ToDatetime.return_value = now.replace(tzinfo=None)
    client.stub.SetExperimentStartTime.return_value = response

    result = client.set_experiment_start_time(now)
    assert result.tzinfo == timezone.utc


def test_clear_db() -> None:
    """Verify clear_db delegates to both reset helpers."""
    client = _build_client_without_init()
    client.initialize_experiment_start_time = Mock(return_value={})
    client.destroy_all_vm_mappings = Mock(return_value={})

    assert client.clear_db() == ({}, {})


def test_initialize_experiment_start_time() -> None:
    """Verify initialize call returns converted response."""
    client = _build_client_without_init()
    client.stub.InitializeExperimentStartTime.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict", return_value={}
    ):
        assert client.initialize_experiment_start_time() == {}


def test_destroy_all_vm_mappings() -> None:
    """Verify destroy all mappings returns converted response."""
    client = _build_client_without_init()
    client.stub.DestroyAllVMMappings.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict", return_value={}
    ):
        assert client.destroy_all_vm_mappings() == {}


def test_list_vm_mappings() -> None:
    """Verify streamed VM mappings are converted to dictionaries."""
    client = _build_client_without_init()
    client.stub.ListVMMappings.return_value = [object(), object()]

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        side_effect=[{"a": 1}, {"b": 2}],
    ):
        assert client.list_vm_mappings() == [{"a": 1}, {"b": 2}]


def test_set_vm_mapping() -> None:
    """Verify VM mapping set requests return converted responses."""
    client = _build_client_without_init()
    client.stub.SetVMMapping.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"server_uuid": "uuid"},
    ):
        result = client.set_vm_mapping(
            {
                "server_uuid": "uuid",
                "server_name": "vm",
                "control_ip": "1.2.3.4",
                "state": "READY",
                "current_time": "10",
            }
        )

    assert result["server_uuid"] == "uuid"


def test_get_vm_mapping_by_uuid_success() -> None:
    """Verify lookup by UUID returns converted response."""
    client = _build_client_without_init()
    client.stub.GetVMMappingByUUID.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"server_uuid": "uuid"},
    ):
        assert client.get_vm_mapping_by_uuid("uuid") == {"server_uuid": "uuid"}


def test_get_vm_mapping_by_uuid_missing_returns_none() -> None:
    """Verify missing UUID lookup returns None."""
    client = _build_client_without_init()
    client.stub.GetVMMappingByUUID.side_effect = _RpcException(grpc.StatusCode.OUT_OF_RANGE)
    assert client.get_vm_mapping_by_uuid("uuid") is None


def test_destroy_vm_mapping_by_uuid() -> None:
    """Verify destroy-by-UUID returns converted response."""
    client = _build_client_without_init()
    client.stub.DestroyVMMappingByUUID.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict", return_value={}
    ):
        assert client.destroy_vm_mapping_by_uuid("uuid") == {}


def test_count_vm_mappings_not_ready() -> None:
    """Verify not-ready count returns converted response."""
    client = _build_client_without_init()
    client.stub.CountVMMappingsNotReady.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"count": 3},
    ):
        assert client.count_vm_mappings_not_ready() == {"count": 3}


def test_set_vm_time_by_uuid_success() -> None:
    """Verify VM time updates return converted response."""
    client = _build_client_without_init()
    client.stub.SetVMTimeByUUID.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"current_time": "12"},
    ):
        assert client.set_vm_time_by_uuid(
            {"server_uuid": "uuid", "current_time": "12"}
        ) == {"current_time": "12"}


def test_set_vm_time_by_uuid_missing_returns_none() -> None:
    """Verify missing VM time update target returns None."""
    client = _build_client_without_init()
    client.stub.SetVMTimeByUUID.side_effect = _RpcException(grpc.StatusCode.OUT_OF_RANGE)
    assert client.set_vm_time_by_uuid({"server_uuid": "uuid", "current_time": "12"}) is None


def test_set_vm_state_by_uuid_success() -> None:
    """Verify VM state updates return converted response."""
    client = _build_client_without_init()
    client.stub.SetVMStateByUUID.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"state": "READY"},
    ):
        assert client.set_vm_state_by_uuid(
            {"server_uuid": "uuid", "state": "READY"}
        ) == {"state": "READY"}


def test_set_vm_state_by_uuid_missing_returns_none() -> None:
    """Verify missing VM state update target returns None."""
    client = _build_client_without_init()
    client.stub.SetVMStateByUUID.side_effect = _RpcException(grpc.StatusCode.OUT_OF_RANGE)
    assert client.set_vm_state_by_uuid({"server_uuid": "uuid", "state": "READY"}) is None


def test_close() -> None:
    """Verify the client closes its gRPC channel."""
    client = _build_client_without_init()
    client.close()
    client.chan.close.assert_called_once()