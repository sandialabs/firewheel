"""
Integration tests for :class:`VMMapping` against a real, in-process gRPC server.

Unlike ``test_vm_mapping.py`` (which uses an in-memory fake client), these tests
exercise the full stack: ``VMMapping`` -> ``FirewheelGrpcClient`` -> protobuf
serialization -> ``FirewheelServicer``. They catch edge issues the fake cannot,
such as proto field coercion and server-side not-ready bookkeeping.

The server binds an ephemeral localhost port and uses no on-disk state, so no
external FIREWHEEL infrastructure is required. Deselect with
``-m "not integration"`` if needed.
"""

from datetime import datetime, timezone
from concurrent import futures
from unittest.mock import Mock

import grpc
import pytest

from firewheel.lib.grpc import firewheel_grpc_pb2_grpc
from firewheel.vm_resource_manager import api, utils
from firewheel.lib.grpc.firewheel_grpc_server import FirewheelServicer
from firewheel.vm_resource_manager.vm_mapping import VMState, VMMapping

pytestmark = pytest.mark.integration


def _build_servicer():
    """Create a servicer with fresh in-memory DBs, skipping on-disk cache setup."""
    servicer = object.__new__(FirewheelServicer)
    servicer.log = Mock()
    servicer.server_start_time = datetime.now(timezone.utc)
    servicer.version = "test"
    servicer.cache_dir = None
    servicer.dbs = {}
    for db in ("test", "prod"):
        servicer._init_db(db)  # pylint: disable=protected-access
    return servicer


@pytest.fixture
def grpc_server():
    """Start a real gRPC server on an ephemeral localhost port."""
    servicer = _build_servicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    firewheel_grpc_pb2_grpc.add_FirewheelServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield servicer, port
    finally:
        server.stop(grace=None)


@pytest.fixture
def vmmapping(grpc_server):
    _servicer, port = grpc_server
    mapping = VMMapping(hostname="127.0.0.1", port=str(port), db="test")
    yield mapping
    mapping.close()


def test_put_get_round_trips_all_fields(vmmapping):
    vmmapping.put(
        "1234",
        "vm-1",
        state=VMState.TESTING,
        current_time="0",
        server_address="10.0.0.1",
        has_execution_issues=True,
        execution_issue_count=2,
        last_execution_issue="copy failed once",
    )

    assert vmmapping.get(server_uuid="1234") == {
        "db": "test",
        "server_uuid": "1234",
        "server_name": "vm-1",
        "control_ip": "10.0.0.1",
        "state": VMState.TESTING,
        "current_time": "0",
        "has_execution_issues": True,
        "execution_issue_count": 2,
        "last_execution_issue": "copy failed once",
    }


def test_put_defaults_round_trip(vmmapping):
    vmmapping.put("1234", "vm-1")

    found = vmmapping.get(server_uuid="1234")

    assert found["state"] == VMState.UNINITIALIZED
    assert found["current_time"] == ""
    assert found["control_ip"] == ""
    assert found["has_execution_issues"] is False
    assert found["execution_issue_count"] == 0
    assert found["last_execution_issue"] == ""


def test_set_vm_time_by_uuid_none_round_trips_as_none(vmmapping):
    vmmapping.put("1234", "vm-1", current_time="0")

    result = vmmapping.set_vm_time_by_uuid("1234", None)

    assert result["current_time"] is None
    assert vmmapping.get(server_uuid="1234")["current_time"] is None


def test_missing_uuid_returns_none(vmmapping):
    vmmapping.grpc_client.log = Mock()

    assert vmmapping.get(server_uuid="missing") is None
    assert vmmapping.set_vm_state_by_uuid("missing", VMState.TESTING) is None
    assert vmmapping.set_vm_time_by_uuid("missing", "10") is None
    assert vmmapping.add_execution_issue_by_uuid("missing", "copy failed") is None

    # The client only logs non-OUT_OF_RANGE errors, so silence here means the
    # server reported "not found" for every call rather than an internal error.
    vmmapping.grpc_client.log.exception.assert_not_called()


def test_set_state_on_missing_uuid_does_not_block_readiness(vmmapping):
    vmmapping.put("1234", "vm-1", state=VMState.CONFIGURED)

    assert vmmapping.set_vm_state_by_uuid("ghost", VMState.CONFIGURING) is None

    assert vmmapping.get_count_vm_not_ready() == 0
    assert vmmapping.get(server_uuid="ghost") is None


def test_set_time_on_missing_uuid_is_out_of_range(vmmapping):
    # The client only logs for non-OUT_OF_RANGE errors, so a quiet None here
    # means the server reported "not found" rather than an internal error.
    vmmapping.grpc_client.log = Mock()

    assert vmmapping.set_vm_time_by_uuid("ghost", "10") is None

    vmmapping.grpc_client.log.exception.assert_not_called()


def test_get_all_filters_through_server(vmmapping):
    vmmapping.batch_put(
        [
            {"server_uuid": "1", "server_name": "vm-1", "state": VMState.TESTING},
            {
                "server_uuid": "2",
                "server_name": "vm-2",
                "state": VMState.TESTING,
                "current_time": "0",
            },
            {"server_uuid": "3", "server_name": "vm-3", "state": VMState.CONFIGURED},
        ]
    )

    assert vmmapping.get_all(length=True) == 3
    found = vmmapping.get_all(filter_time="0", filter_state=VMState.TESTING)
    assert [vm["server_name"] for vm in found] == ["vm-2"]


def test_not_ready_count_tracks_state_transitions(vmmapping):
    vmmapping.put("1", "vm-1")
    vmmapping.put("2", "vm-2", state=VMState.NA)
    assert vmmapping.get_count_vm_not_ready() == 1

    vmmapping.set_vm_state_by_uuid("1", VMState.CONFIGURING)
    assert vmmapping.get_count_vm_not_ready() == 1

    vmmapping.set_vm_state_by_uuid("1", VMState.CONFIGURED)
    assert vmmapping.get_count_vm_not_ready() == 0

    vmmapping.put("3", "vm-3")
    assert vmmapping.get_count_vm_not_ready() == 1
    vmmapping.destroy_one("3")
    assert vmmapping.get_count_vm_not_ready() == 0


def test_not_ready_count_ignores_execution_issue_only_updates(vmmapping):
    vmmapping.put("1234", "vm-1", state=VMState.CONFIGURED)

    vmmapping.add_execution_issue_by_uuid("1234", "copy failed")

    assert vmmapping.get_count_vm_not_ready() == 0
    found = vmmapping.get(server_uuid="1234")
    assert found["state"] == VMState.CONFIGURED
    assert found["execution_issue_count"] == 1


def test_destroy_all_clears_records_and_not_ready_count(vmmapping):
    vmmapping.put("1", "vm-1")
    vmmapping.put("2", "vm-2")

    vmmapping.destroy_all()

    assert vmmapping.get_all() == []
    assert vmmapping.get_count_vm_not_ready() == 0


def test_dbs_are_isolated(grpc_server, vmmapping):
    _servicer, port = grpc_server
    prod = VMMapping(hostname="127.0.0.1", port=str(port), db="prod")
    try:
        vmmapping.put("1234", "vm-1")

        assert prod.get(server_uuid="1234") is None
        assert prod.get_count_vm_not_ready() == 0
    finally:
        prod.close()


def test_api_and_utils_over_real_server(vmmapping):
    api.add_vm("1234", "vm-1", "10.0.0.1", mapping=vmmapping)
    api.add_vm("5678", "vm-2", "10.0.0.2", use_vm_manager=False, mapping=vmmapping)
    assert utils.get_vm_count_not_ready(mapping=vmmapping) == 1

    utils.set_vm_time("1234", -50, mapping=vmmapping)
    utils.set_vm_state("1234", VMState.CONFIGURED, mapping=vmmapping)
    utils.add_execution_issue("1234", "warning text", mapping=vmmapping)

    assert utils.get_vm_count_not_ready(mapping=vmmapping) == 0
    assert api.get_vm_times(mapping=vmmapping) == {"vm-1": "-50", "vm-2": ""}
    assert api.get_vm_statuses(mapping=vmmapping) == {
        "vm-1": {
            "state": VMState.CONFIGURED,
            "has_execution_issues": True,
            "execution_issue_count": 1,
            "last_execution_issue": "warning text",
        },
        "vm-2": {
            "state": VMState.NA,
            "has_execution_issues": False,
            "execution_issue_count": 0,
            "last_execution_issue": "",
        },
    }
