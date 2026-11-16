from unittest.mock import patch

import pytest

from firewheel.lib.grpc import firewheel_grpc_pb2
from firewheel.vm_resource_manager.vm_mapping import VMState, VMMapping
from firewheel.lib.grpc.firewheel_grpc_resources import msg_to_dict


class FakeGrpcClient:
    """
    In-memory stand-in for ``FirewheelGrpcClient``.

    Records are stored as real ``firewheel_grpc_pb2.VMMapping`` messages and
    every response is passed through the real ``msg_to_dict`` so that proto
    field coercion (e.g. ``str(None) -> "None" -> None``) matches the real
    client. Server-side bookkeeping such as the not-ready count is deliberately
    not reimplemented here; that is covered against the real servicer in
    ``test_vm_mapping_grpc_integration.py``.
    """

    def __init__(self, _hostname=None, _port=None, db="test"):
        self.db = db
        self.mappings = {}

    def close(self):
        return None

    def set_vm_mapping(self, vmm):
        mapping = firewheel_grpc_pb2.VMMapping(
            server_uuid=vmm["server_uuid"],
            server_name=vmm["server_name"],
            control_ip=vmm["control_ip"],
            state=vmm["state"],
            current_time=vmm["current_time"],
            has_execution_issues=vmm.get("has_execution_issues", False),
            execution_issue_count=vmm.get("execution_issue_count", 0),
            last_execution_issue=vmm.get("last_execution_issue", ""),
            db=self.db,
        )
        self.mappings[mapping.server_uuid] = mapping
        return msg_to_dict(mapping)

    def get_vm_mapping_by_uuid(self, vm_uuid):
        mapping = self.mappings.get(vm_uuid)
        if mapping is None:
            return None
        return msg_to_dict(mapping)

    def destroy_vm_mapping_by_uuid(self, vm_uuid):
        self.mappings.pop(vm_uuid, None)
        return {}

    def destroy_all_vm_mappings(self):
        self.mappings = {}
        return {}

    def list_vm_mappings(self):
        return [msg_to_dict(mapping) for mapping in self.mappings.values()]

    def set_vm_state_by_uuid(self, vmm):
        mapping = self.mappings.get(str(vmm["server_uuid"]))
        if mapping is None:
            return None
        mapping.state = str(vmm["state"])
        return msg_to_dict(mapping)

    def set_vm_time_by_uuid(self, vmm):
        mapping = self.mappings.get(str(vmm["server_uuid"]))
        if mapping is None:
            return None
        mapping.current_time = str(vmm["current_time"])
        return msg_to_dict(mapping)


@pytest.fixture
def vmmapping():
    with patch(
        "firewheel.vm_resource_manager.vm_mapping.FirewheelGrpcClient",
        FakeGrpcClient,
    ):
        mapping = VMMapping(hostname="localhost", port="50051", db="test")
        yield mapping
        mapping.destroy_all()
        mapping.close()


def test_put_schedule_defaults_execution_issue_fields(vmmapping):
    vmmapping.put("1234", "vm-1", server_address="10.0.0.1")

    found = vmmapping.get(server_uuid="1234")

    assert found["db"] == "test"
    assert found["server_uuid"] == "1234"
    assert found["server_name"] == "vm-1"
    assert found["control_ip"] == "10.0.0.1"
    assert found["state"] == VMState.UNINITIALIZED
    assert found["current_time"] == ""
    assert found["has_execution_issues"] is False
    assert found["execution_issue_count"] == 0
    assert found["last_execution_issue"] == ""


def test_put_schedule_with_options_updates_existing_record(vmmapping):
    vmmapping.put(
        "1234",
        "vm-1",
        server_address="10.0.0.1",
        state=VMState.TESTING,
        current_time="0",
    )
    vmmapping.put(
        "1234",
        "vm-1",
        server_address="10.0.0.1",
        state=VMState.CONFIGURING,
        current_time="5",
    )

    found = vmmapping.get(server_uuid="1234")

    assert found["state"] == VMState.CONFIGURING
    assert found["current_time"] == "5"


def test_batch_put_preserves_execution_issue_fields(vmmapping):
    vmmapping.batch_put(
        [
            {
                "server_uuid": "1234",
                "server_name": "vm-1",
                "control_ip": "10.0.0.1",
                "has_execution_issues": True,
                "execution_issue_count": 2,
                "last_execution_issue": "copy failed once",
            }
        ]
    )

    found = vmmapping.get(server_uuid="1234")

    assert found["has_execution_issues"] is True
    assert found["execution_issue_count"] == 2
    assert found["last_execution_issue"] == "copy failed once"


def test_prepare_put_sets_defaults(vmmapping):
    prepared = vmmapping.prepare_put({"server_uuid": "1234", "server_name": "vm-1"})

    assert prepared["server_uuid"] == "1234"
    assert prepared["server_name"] == "vm-1"
    assert prepared["state"] == VMState.UNINITIALIZED
    assert prepared["current_time"] == ""
    assert prepared["control_ip"] == ""
    assert prepared["has_execution_issues"] is False
    assert prepared["execution_issue_count"] == 0
    assert prepared["last_execution_issue"] == ""


@pytest.mark.parametrize(
    "entry",
    [
        {"server_name": "vm-1"},
        {"server_uuid": "1234"},
    ],
)
def test_prepare_put_requires_uuid_and_name(vmmapping, entry):
    with pytest.raises(ValueError):
        vmmapping.prepare_put(entry)


@pytest.mark.parametrize(
    "entry",
    [
        {"server_name": "vm-1", "control_ip": "10.0.0.1"},
        {"server_uuid": "1234", "control_ip": "10.0.0.1"},
    ],
)
def test_batch_put_requires_uuid_and_name(vmmapping, entry):
    with pytest.raises(ValueError):
        vmmapping.batch_put([entry])

    assert vmmapping.get_all() == []


def test_get_requires_server_uuid(vmmapping):
    with pytest.raises(ValueError):
        vmmapping.get()


def test_get_returns_none_for_missing_uuid(vmmapping):
    assert vmmapping.get(server_uuid="missing") is None


def test_get_all_returns_all_entries(vmmapping):
    vmmapping.batch_put(
        [
            {"server_uuid": "1234", "server_name": "vm-1", "control_ip": "10.0.0.1"},
            {
                "server_uuid": "5678",
                "server_name": "vm-2",
                "control_ip": "10.0.0.2",
                "state": VMState.TESTING,
                "current_time": "0",
            },
        ]
    )

    found = vmmapping.get_all()

    assert len(found) == 2
    assert {entry["server_name"] for entry in found} == {"vm-1", "vm-2"}


def test_get_all_length_returns_count(vmmapping):
    vmmapping.batch_put(
        [
            {"server_uuid": "1234", "server_name": "vm-1"},
            {"server_uuid": "5678", "server_name": "vm-2"},
        ]
    )

    assert vmmapping.get_all(length=True) == 2


def test_get_all_filter_time_works(vmmapping):
    vmmapping.batch_put(
        [
            {"server_uuid": "1234", "server_name": "vm-1"},
            {
                "server_uuid": "5678",
                "server_name": "vm-2",
                "state": VMState.TESTING,
                "current_time": "0",
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
        ]
    )

    found = vmmapping.get_all(filter_time="0")

    assert len(found) == 1
    assert found[0]["server_name"] == "vm-2"


def test_get_all_filter_state_works_with_substrings(vmmapping):
    vmmapping.put("1234", "vm-1", state=VMState.CONFIGURING)
    vmmapping.put("5678", "vm-2", state=VMState.CONFIGURED)

    found = vmmapping.get_all(filter_state="configur")

    assert len(found) == 2
    assert {entry["server_name"] for entry in found} == {"vm-1", "vm-2"}


def test_get_all_filter_state_works_with_enum(vmmapping):
    vmmapping.put("1234", "vm-1", state=VMState.CONFIGURING)
    vmmapping.put("5678", "vm-2", state=VMState.CONFIGURED)

    found = vmmapping.get_all(filter_state=VMState.CONFIGURED)

    assert len(found) == 1
    assert found[0]["server_name"] == "vm-2"


def test_get_all_filter_time_and_state_combines_filters(vmmapping):
    vmmapping.batch_put(
        [
            {
                "server_uuid": "1234",
                "server_name": "vm-1",
                "state": VMState.TESTING,
                "current_time": "0",
            },
            {
                "server_uuid": "5678",
                "server_name": "vm-2",
                "state": VMState.TESTING,
                "current_time": "5",
            },
            {
                "server_uuid": "9012",
                "server_name": "vm-3",
                "state": VMState.CONFIGURING,
                "current_time": "0",
            },
        ]
    )

    found = vmmapping.get_all(filter_time="0", filter_state=VMState.TESTING)

    assert len(found) == 1
    assert found[0]["server_name"] == "vm-1"


def test_destroy_one_is_idempotent(vmmapping):
    vmmapping.put("1234", "vm-1")

    vmmapping.destroy_one("1234")
    vmmapping.destroy_one("1234")

    assert vmmapping.get(server_uuid="1234") is None


def test_destroy_all_is_idempotent(vmmapping):
    vmmapping.batch_put(
        [
            {"server_uuid": "1234", "server_name": "vm-1"},
            {"server_uuid": "5678", "server_name": "vm-2"},
        ]
    )

    vmmapping.destroy_all()
    vmmapping.destroy_all()

    assert vmmapping.get_all() == []


def test_set_vm_state_by_uuid_updates_state(vmmapping):
    vmmapping.put("1234", "vm-1")

    result = vmmapping.set_vm_state_by_uuid("1234", VMState.TESTING)

    assert result["state"] == VMState.TESTING
    assert vmmapping.get(server_uuid="1234")["state"] == VMState.TESTING


def test_set_vm_state_by_uuid_returns_none_when_missing(vmmapping):
    assert vmmapping.set_vm_state_by_uuid("missing", VMState.TESTING) is None


def test_set_vm_state_by_uuid_rejects_invalid_state(vmmapping):
    vmmapping.put("1234", "vm-1")

    with pytest.raises(ValueError):
        vmmapping.set_vm_state_by_uuid("1234", None)


def test_set_vm_time_by_uuid_updates_time(vmmapping):
    vmmapping.put("1234", "vm-1", current_time="0")

    result = vmmapping.set_vm_time_by_uuid("1234", 404)

    assert result["current_time"] == "404"
    assert vmmapping.get(server_uuid="1234")["current_time"] == "404"


def test_set_vm_time_by_uuid_none(vmmapping):
    vmmapping.put("1234", "vm-1", current_time="0")

    result = vmmapping.set_vm_time_by_uuid("1234", None)

    assert result["current_time"] is None
    assert vmmapping.get(server_uuid="1234")["current_time"] is None


def test_set_vm_time_by_uuid_returns_none_when_missing(vmmapping):
    assert vmmapping.set_vm_time_by_uuid("missing", "10") is None


def test_add_execution_issue_by_uuid_increments_metadata(vmmapping):
    vmmapping.put("1234", "vm-1", state=VMState.CONFIGURED)

    first = vmmapping.add_execution_issue_by_uuid("1234", "first issue")
    second = vmmapping.add_execution_issue_by_uuid("1234", "second issue")

    assert first["has_execution_issues"] is True
    assert first["execution_issue_count"] == 1
    assert first["last_execution_issue"] == "first issue"
    assert second["has_execution_issues"] is True
    assert second["execution_issue_count"] == 2
    assert second["last_execution_issue"] == "second issue"


def test_add_execution_issue_by_uuid_returns_none_when_missing(vmmapping):
    assert vmmapping.add_execution_issue_by_uuid("missing", "copy failed") is None


def test_get_count_vm_not_ready_returns_server_count(vmmapping):
    # The not-ready rule lives on the server; VMMapping only unwraps the count.
    with patch.object(
        vmmapping.grpc_client,
        "count_vm_mappings_not_ready",
        create=True,
        return_value={"count": 3},
    ) as count:
        assert vmmapping.get_count_vm_not_ready() == 3

    count.assert_called_once_with()
