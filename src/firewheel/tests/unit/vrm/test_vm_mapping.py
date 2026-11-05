import copy
import unittest
from unittest.mock import patch

from firewheel.vm_resource_manager.vm_mapping import VMMapping, VMState


class FakeGrpcClient:
    def __init__(self, _hostname=None, _port=None, db="test"):
        self.db = db
        self.mappings = {}

    def close(self):
        return None

    def _serialize(self, vmm):
        serialized = copy.deepcopy(vmm)
        serialized["db"] = self.db
        state = serialized.get("state")
        if isinstance(state, VMState):
            serialized["state"] = state.value
        return serialized

    def set_vm_mapping(self, vmm):
        serialized = self._serialize(vmm)
        self.mappings[serialized["server_uuid"]] = serialized
        return copy.deepcopy(serialized)

    def get_vm_mapping_by_uuid(self, vm_uuid):
        value = self.mappings.get(vm_uuid)
        if value is None:
            return None
        return copy.deepcopy(value)

    def destroy_vm_mapping_by_uuid(self, vm_uuid):
        self.mappings.pop(vm_uuid, None)
        return {}

    def destroy_all_vm_mappings(self):
        self.mappings = {}
        return {}

    def list_vm_mappings(self):
        return [copy.deepcopy(value) for value in self.mappings.values()]

    def set_vm_state_by_uuid(self, vmm):
        current = self.mappings.get(vmm["server_uuid"])
        if current is None:
            return None
        current["state"] = str(vmm["state"])
        return copy.deepcopy(current)

    def set_vm_time_by_uuid(self, vmm):
        current = self.mappings.get(vmm["server_uuid"])
        if current is None:
            return None
        current["current_time"] = str(vmm["current_time"])
        return copy.deepcopy(current)

    def count_vm_mappings_not_ready(self):
        count = 0
        for value in self.mappings.values():
            if value.get("state") not in {VMState.NA.value, VMState.CONFIGURED.value}:
                count += 1
        return {"count": count}


class VMMappingTestCase(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            "firewheel.vm_resource_manager.vm_mapping.FirewheelGrpcClient",
            FakeGrpcClient,
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.vmmapping = VMMapping(hostname="localhost", port="50051", db="test")

    def tearDown(self):
        self.vmmapping.destroy_all()
        self.vmmapping.close()

    def test_put_schedule_defaults_execution_issue_fields(self):
        self.vmmapping.put("1234", "vm-1", server_address="10.0.0.1")

        found = self.vmmapping.get(server_uuid="1234")
        self.assertEqual(found["db"], "test")
        self.assertEqual(found["server_uuid"], "1234")
        self.assertEqual(found["server_name"], "vm-1")
        self.assertEqual(found["control_ip"], "10.0.0.1")
        self.assertEqual(found["state"], VMState.UNINITIALIZED)
        self.assertEqual(found["current_time"], "")
        self.assertFalse(found["has_execution_issues"])
        self.assertEqual(found["execution_issue_count"], 0)
        self.assertEqual(found["last_execution_issue"], "")

    def test_put_schedule_with_options_updates_existing_record(self):
        self.vmmapping.put(
            "1234",
            "vm-1",
            server_address="10.0.0.1",
            state=VMState.TESTING,
            current_time="0",
        )
        self.vmmapping.put(
            "1234",
            "vm-1",
            server_address="10.0.0.1",
            state=VMState.CONFIGURING,
            current_time="5",
        )

        found = self.vmmapping.get(server_uuid="1234")
        self.assertEqual(found["state"], VMState.CONFIGURING)
        self.assertEqual(found["current_time"], "5")

    def test_batch_put_preserves_execution_issue_fields(self):
        self.vmmapping.batch_put(
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

        found = self.vmmapping.get(server_uuid="1234")
        self.assertTrue(found["has_execution_issues"])
        self.assertEqual(found["execution_issue_count"], 2)
        self.assertEqual(found["last_execution_issue"], "copy failed once")

    def test_prepare_put_sets_defaults(self):
        prepared = self.vmmapping.prepare_put(
            {"server_uuid": "1234", "server_name": "vm-1"}
        )

        self.assertEqual(prepared["server_uuid"], "1234")
        self.assertEqual(prepared["server_name"], "vm-1")
        self.assertEqual(prepared["state"], VMState.UNINITIALIZED)
        self.assertEqual(prepared["current_time"], "")
        self.assertEqual(prepared["control_ip"], "")
        self.assertFalse(prepared["has_execution_issues"])
        self.assertEqual(prepared["execution_issue_count"], 0)
        self.assertEqual(prepared["last_execution_issue"], "")

    def test_prepare_put_requires_server_uuid(self):
        with self.assertRaises(ValueError):
            self.vmmapping.prepare_put({"server_name": "vm-1"})

    def test_prepare_put_requires_server_name(self):
        with self.assertRaises(ValueError):
            self.vmmapping.prepare_put({"server_uuid": "1234"})

    def test_get_requires_server_uuid(self):
        with self.assertRaises(ValueError):
            self.vmmapping.get()

    def test_get_returns_none_for_missing_uuid(self):
        self.assertIsNone(self.vmmapping.get(server_uuid="missing"))

    def test_get_all_returns_all_entries(self):
        self.vmmapping.batch_put(
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

        found = self.vmmapping.get_all()
        self.assertEqual(len(found), 2)
        self.assertCountEqual(
            [entry["server_name"] for entry in found], ["vm-1", "vm-2"]
        )

    def test_get_all_length_returns_count(self):
        self.vmmapping.batch_put(
            [
                {"server_uuid": "1234", "server_name": "vm-1"},
                {"server_uuid": "5678", "server_name": "vm-2"},
            ]
        )

        self.assertEqual(self.vmmapping.get_all(length=True), 2)

    def test_get_all_filter_time_works(self):
        self.vmmapping.batch_put(
            [
                {"server_uuid": "1234", "server_name": "vm-1"},
                {
                    "server_uuid": "5678",
                    "server_name": "vm-2",
                    "state": VMState.TESTING,
                    "current_time": "0",
                },
            ]
        )

        found = self.vmmapping.get_all(filter_time="0")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["server_name"], "vm-2")

    def test_get_all_filter_state_works_with_substrings(self):
        self.vmmapping.put("1234", "vm-1", state=VMState.CONFIGURING)
        self.vmmapping.put("5678", "vm-2", state=VMState.CONFIGURED)

        found = self.vmmapping.get_all(filter_state="configur")

        self.assertEqual(len(found), 2)
        self.assertCountEqual(
            [entry["server_name"] for entry in found], ["vm-1", "vm-2"]
        )

    def test_get_all_filter_state_works_with_enum(self):
        self.vmmapping.put("1234", "vm-1", state=VMState.CONFIGURING)
        self.vmmapping.put("5678", "vm-2", state=VMState.CONFIGURED)

        found = self.vmmapping.get_all(filter_state=VMState.CONFIGURED)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["server_name"], "vm-2")

    def test_get_all_filter_time_and_state_combines_filters(self):
        self.vmmapping.batch_put(
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

        found = self.vmmapping.get_all(filter_time="0", filter_state=VMState.TESTING)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["server_name"], "vm-1")

    def test_destroy_one_is_idempotent(self):
        self.vmmapping.put("1234", "vm-1")

        self.vmmapping.destroy_one("1234")
        self.vmmapping.destroy_one("1234")

        self.assertIsNone(self.vmmapping.get(server_uuid="1234"))

    def test_destroy_all_is_idempotent(self):
        self.vmmapping.batch_put(
            [
                {"server_uuid": "1234", "server_name": "vm-1"},
                {"server_uuid": "5678", "server_name": "vm-2"},
            ]
        )

        self.vmmapping.destroy_all()
        self.vmmapping.destroy_all()

        self.assertEqual(self.vmmapping.get_all(), [])

    def test_set_vm_state_by_uuid_updates_state(self):
        self.vmmapping.put("1234", "vm-1")

        result = self.vmmapping.set_vm_state_by_uuid("1234", VMState.TESTING)

        self.assertEqual(result["state"], VMState.TESTING)
        self.assertEqual(self.vmmapping.get(server_uuid="1234")["state"], VMState.TESTING)

    def test_set_vm_state_by_uuid_returns_none_when_missing(self):
        self.assertIsNone(
            self.vmmapping.set_vm_state_by_uuid("missing", VMState.TESTING)
        )

    def test_set_vm_state_by_uuid_rejects_invalid_state(self):
        self.vmmapping.put("1234", "vm-1")

        with self.assertRaises(ValueError):
            self.vmmapping.set_vm_state_by_uuid("1234", None)

    def test_set_vm_time_by_uuid_updates_time(self):
        self.vmmapping.put("1234", "vm-1", current_time="0")

        result = self.vmmapping.set_vm_time_by_uuid("1234", 404)

        self.assertEqual(result["current_time"], "404")
        self.assertEqual(self.vmmapping.get(server_uuid="1234")["current_time"], "404")

    def test_set_vm_time_by_uuid_stringifies_none(self):
        self.vmmapping.put("1234", "vm-1", current_time="0")

        result = self.vmmapping.set_vm_time_by_uuid("1234", None)

        self.assertEqual(result["current_time"], "None")
        self.assertEqual(
            self.vmmapping.get(server_uuid="1234")["current_time"], "None"
        )

    def test_set_vm_time_by_uuid_returns_none_when_missing(self):
        self.assertIsNone(self.vmmapping.set_vm_time_by_uuid("missing", "10"))

    def test_add_execution_issue_by_uuid_increments_metadata(self):
        self.vmmapping.put("1234", "vm-1", state=VMState.CONFIGURED)

        first = self.vmmapping.add_execution_issue_by_uuid("1234", "first issue")
        second = self.vmmapping.add_execution_issue_by_uuid("1234", "second issue")

        self.assertTrue(first["has_execution_issues"])
        self.assertEqual(first["execution_issue_count"], 1)
        self.assertEqual(first["last_execution_issue"], "first issue")
        self.assertTrue(second["has_execution_issues"])
        self.assertEqual(second["execution_issue_count"], 2)
        self.assertEqual(second["last_execution_issue"], "second issue")

    def test_add_execution_issue_by_uuid_returns_none_when_missing(self):
        self.assertIsNone(
            self.vmmapping.add_execution_issue_by_uuid("missing", "copy failed")
        )

    def test_get_count_vm_not_ready_ignores_execution_issue_only_updates(self):
        self.vmmapping.put("1234", "vm-1", state=VMState.CONFIGURED)
        self.vmmapping.add_execution_issue_by_uuid("1234", "copy failed")

        self.assertEqual(self.vmmapping.get_count_vm_not_ready(), 0)
