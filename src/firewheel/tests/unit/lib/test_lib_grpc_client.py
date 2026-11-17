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

    with patch("firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict", return_value={}):
        assert client.initialize_experiment_start_time() == {}


def test_destroy_all_vm_mappings() -> None:
    """Verify destroy all mappings returns converted response."""
    client = _build_client_without_init()
    client.stub.DestroyAllVMMappings.return_value = object()

    with patch("firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict", return_value={}):
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
                "has_execution_issues": True,
                "execution_issue_count": 2,
                "last_execution_issue": "warning text",
            }
        )

    assert result["server_uuid"] == "uuid"
    mapping = client.stub.SetVMMapping.call_args.args[0]
    assert mapping.has_execution_issues is True
    assert mapping.execution_issue_count == 2
    assert mapping.last_execution_issue == "warning text"


def test_set_vm_mapping_uses_execution_issue_defaults_when_fields_missing() -> None:
    """Verify VM mapping defaults execution issue metadata when omitted."""
    client = _build_client_without_init()
    client.stub.SetVMMapping.return_value = object()

    with patch(
        "firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict",
        return_value={"server_uuid": "uuid"},
    ):
        client.set_vm_mapping(
            {
                "server_uuid": "uuid",
                "server_name": "vm",
                "control_ip": "1.2.3.4",
                "state": "READY",
                "current_time": "10",
            }
        )

    mapping = client.stub.SetVMMapping.call_args.args[0]
    assert mapping.has_execution_issues is False
    assert mapping.execution_issue_count == 0
    assert mapping.last_execution_issue == ""


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
    client.stub.GetVMMappingByUUID.side_effect = _RpcException(
        grpc.StatusCode.OUT_OF_RANGE
    )
    assert client.get_vm_mapping_by_uuid("uuid") is None


def test_destroy_vm_mapping_by_uuid() -> None:
    """Verify destroy-by-UUID returns converted response."""
    client = _build_client_without_init()
    client.stub.DestroyVMMappingByUUID.return_value = object()

    with patch("firewheel.lib.grpc.firewheel_grpc_client.msg_to_dict", return_value={}):
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
    client.stub.SetVMTimeByUUID.side_effect = _RpcException(
        grpc.StatusCode.OUT_OF_RANGE
    )
    assert (
        client.set_vm_time_by_uuid({"server_uuid": "uuid", "current_time": "12"})
        is None
    )


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
    client.stub.SetVMStateByUUID.side_effect = _RpcException(
        grpc.StatusCode.OUT_OF_RANGE
    )
    assert (
        client.set_vm_state_by_uuid({"server_uuid": "uuid", "state": "READY"}) is None
    )


def test_close() -> None:
    """Verify the client closes its gRPC channel."""
    client = _build_client_without_init()
    client.close()
    client.chan.close.assert_called_once()


def test_init_with_explicit_logger_and_no_required_connection(monkeypatch) -> None:
    """Verify constructor accepts an injected logger."""
    fake_channel = Mock()
    fake_stub = Mock()
    fake_log = Mock()

    from firewheel.config import config

    monkeypatch.setitem(config["grpc"], "hostname", "127.0.0.1")
    monkeypatch.setitem(config["grpc"], "port", "50051")
    monkeypatch.setitem(config["grpc"], "db", "prod")

    import firewheel.lib.grpc.firewheel_grpc_client as module

    original_check = module.FirewheelGrpcClient.check_connection
    module.FirewheelGrpcClient.check_connection = lambda self, error=True: False
    try:
        import unittest.mock as umock

        with (
            umock.patch(
                "firewheel.lib.grpc.firewheel_grpc_client.grpc.insecure_channel",
                return_value=fake_channel,
            ),
            umock.patch(
                "firewheel.lib.grpc.firewheel_grpc_client.firewheel_grpc_pb2_grpc.FirewheelStub",
                return_value=fake_stub,
            ),
        ):
            client = FirewheelGrpcClient(log=fake_log, require_connection=False)
    finally:
        module.FirewheelGrpcClient.check_connection = original_check

    assert client.log is fake_log
    assert client.connected is False


def test_get_info_logs_non_unavailable_rpc_error() -> None:
    """Verify unexpected RPC errors are logged."""
    client = _build_client_without_init()
    client.stub.GetInfo.side_effect = _RpcException(grpc.StatusCode.INTERNAL)

    assert client.get_info() is None
    assert client.log.exception.called


def test_get_experiment_launch_time_logs_unexpected_rpc_error() -> None:
    """Verify unexpected launch time RPC errors are logged."""
    client = _build_client_without_init()
    client.stub.GetExperimentLaunchTime.side_effect = _RpcException(
        grpc.StatusCode.INTERNAL
    )

    assert client.get_experiment_launch_time() is None
    assert client.log.exception.called


def test_get_experiment_start_time_logs_unexpected_rpc_error() -> None:
    """Verify unexpected start time RPC errors are logged."""
    client = _build_client_without_init()
    client.stub.GetExperimentStartTime.side_effect = _RpcException(
        grpc.StatusCode.INTERNAL
    )

    assert client.get_experiment_start_time() is None
    assert client.log.exception.called


def test_get_vm_mapping_by_uuid_logs_unexpected_rpc_error() -> None:
    """Verify unexpected UUID lookup RPC errors are logged."""
    client = _build_client_without_init()
    client.stub.GetVMMappingByUUID.side_effect = _RpcException(grpc.StatusCode.INTERNAL)

    assert client.get_vm_mapping_by_uuid("uuid") is None
    assert client.log.exception.called


def test_set_vm_time_by_uuid_logs_unexpected_rpc_error() -> None:
    """Verify unexpected VM time RPC errors are logged."""
    client = _build_client_without_init()
    client.stub.SetVMTimeByUUID.side_effect = _RpcException(grpc.StatusCode.INTERNAL)

    assert client.set_vm_time_by_uuid({"server_uuid": "u", "current_time": "1"}) is None
    assert client.log.exception.called


def test_set_vm_state_by_uuid_logs_unexpected_rpc_error() -> None:
    """Verify unexpected VM state RPC errors are logged."""
    client = _build_client_without_init()
    client.stub.SetVMStateByUUID.side_effect = _RpcException(grpc.StatusCode.INTERNAL)

    assert client.set_vm_state_by_uuid({"server_uuid": "u", "state": "READY"}) is None
    assert client.log.exception.called
