import unittest

from firewheel.config import config
from firewheel.vm_resource_manager.vm_mapping import VMMapping, VMState


class VMMappingTestCase(unittest.TestCase):
    def setUp(self):
        self.vmmapping = VMMapping(
            hostname=config["grpc"]["hostname"],
            port=config["grpc"]["port"],
            db=config["test"]["grpc_db"],
        )

        # Create valid and invalid repository directories
        self.entries = [
            {
                "db": "test",
                "server_name": "1",
                "control_ip": "2",
                "server_uuid": "1234",
            },
            {
                "db": "test",
                "server_name": "2",
                "control_ip": "3",
                "server_uuid": "12345",
                "state": "test",
                "current_time": "0",
            },
        ]
        self.invalid_entry_1 = {"server_name": "test-invalid", "invalid": "value"}
        self.invalid_entry_2 = {"control_ip": "value"}

    def tearDown(self):
        self.vmmapping.destroy_all()
        self.vmmapping.close()

    def test_put_schedule(self):
        self.vmmapping.put(
            self.entries[0]["server_uuid"],
            self.entries[0]["server_name"],
            server_address=self.entries[0]["control_ip"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[0]["server_uuid"])
        expected = {
            "db": "test",
            "server_name": self.entries[0]["server_name"],
            "control_ip": self.entries[0]["control_ip"],
            "server_uuid": self.entries[0]["server_uuid"],
            "state": "uninitialized",
            "current_time": "",
        }
        self.assertEqual(found, expected)

    def test_put_schedule_with_options(self):
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            state=self.entries[1]["state"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found, self.entries[1])

    def test_batch_put(self):
        self.vmmapping.batch_put(self.entries)

        found1 = self.vmmapping.get(server_uuid=self.entries[0]["server_uuid"])
        found2 = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(self.entries[0]["server_name"], found1["server_name"])
        self.assertEqual(self.entries[0]["control_ip"], found1["control_ip"])
        self.assertEqual("uninitialized", found1["state"])
        self.assertEqual("", found1["current_time"])
        self.assertEqual(self.entries[1], found2)

    def test_batch_put_no_name(self):
        entries = [{"control_ip": "2", "server_uuid": "1234"}]
        with self.assertRaises(ValueError):
            self.vmmapping.batch_put(entries)

    def test_batch_put_no_ip(self):
        entries = [{"server_name": "test", "server_uuid": "1234"}]
        self.vmmapping.batch_put(entries)

        found = self.vmmapping.get("1234")
        self.assertEqual(found["control_ip"], "")

    def test_destroy_one(self):
        self.vmmapping.batch_put(self.entries)
        db_entry = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(db_entry, self.entries[1])
        self.vmmapping.destroy_one(self.entries[1]["server_uuid"])

        db_entry = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(db_entry, None)

    def test_destroy_all(self):
        self.vmmapping.batch_put(self.entries)

        self.vmmapping.destroy_all()
        found = self.vmmapping.get_all()
        self.assertEqual(found, [])

    def test_invalid_get_1(self):
        result = self.vmmapping.get("invalid")
        self.assertIsNone(result)

    def test_get(self):
        self.vmmapping.batch_put(self.entries)

        for entry in self.entries:
            db_entry = self.vmmapping.get(server_uuid=entry["server_uuid"])
            self.assertEqual(entry["server_name"], db_entry["server_name"])
            self.assertEqual(entry["control_ip"], db_entry["control_ip"])
            if "state" in entry:
                self.assertEqual(entry["state"], db_entry["state"])
            else:
                self.assertEqual("uninitialized", db_entry["state"])
            if "current_time" in entry:
                self.assertEqual(entry["current_time"], db_entry["current_time"])
            else:
                self.assertEqual("", db_entry["current_time"])

    def test_update(self):
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            state=self.entries[1]["state"],
            current_time=self.entries[1]["current_time"],
        )
        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found, self.entries[1])

        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            state=VMState.CONFIGURING,
            current_time=self.entries[1]["current_time"],
        )
        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        expected = {
            "db": "test",
            "control_ip": self.entries[1]["control_ip"],
            "server_uuid": self.entries[1]["server_uuid"],
            "server_name": self.entries[1]["server_name"],
            "state": VMState.CONFIGURING,
            "current_time": self.entries[1]["current_time"],
        }
        self.assertEqual(found, expected)

    def test_invalid_batch_put(self):
        with self.assertRaises(ValueError):
            self.vmmapping.batch_put([self.invalid_entry_1])
        with self.assertRaises(ValueError):
            self.vmmapping.batch_put([self.invalid_entry_2])

    def test_delete_not_present(self):
        self.vmmapping.destroy_one(self.entries[0]["server_uuid"])

    def test_double_destroy_all(self):
        self.vmmapping.batch_put(self.entries)
        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found, self.entries[1])

        self.vmmapping.destroy_all()
        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found, None)

        self.vmmapping.destroy_all()
        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found, None)

        found = self.vmmapping.get_all()
        self.assertEqual(found, [])

    # pylint: disable=invalid-name
    def test_get_all(self):
        self.vmmapping.batch_put(self.entries)

        found = self.vmmapping.get_all()
        self.assertEqual(len(found), len(self.entries))

        expected = []
        expected.append(
            {
                "db": "test",
                "control_ip": self.entries[0]["control_ip"],
                "server_uuid": self.entries[0]["server_uuid"],
                "server_name": self.entries[0]["server_name"],
                "state": VMState.UNINITIALIZED,
                "current_time": "",
            }
        )

        expected.append(self.entries[1])

        for f in found:
            self.assertTrue(f in expected)
        for e in expected:
            self.assertTrue(e in found)

    def test_get_all_after_update(self):
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            state=self.entries[1]["state"],
            current_time=self.entries[1]["current_time"],
        )

        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            state=VMState.CONFIGURING,
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get_all()
        self.assertEqual(len(found), 1)

    def test_get_all_filter_time(self):
        self.vmmapping.batch_put(self.entries)

        found = self.vmmapping.get_all(filter_time="0")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0], self.entries[1])

    def test_get_all_filter_state(self):
        self.vmmapping.batch_put(self.entries)

        found = self.vmmapping.get_all(filter_state="test")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0], self.entries[1])

    def test_get_all_filter_time_and_state(self):
        self.vmmapping.batch_put(self.entries)
        self.vmmapping.put(
            "42",
            "decoy",
            state=VMState.UNINITIALIZED,
            current_time="0",
        )

        found = self.vmmapping.get_all(filter_state="test", filter_time="0")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0], self.entries[1])

    def test_invalid_get_2(self):
        with self.assertRaises(ValueError):
            self.vmmapping.get()

    def test_is_vm_state_default(self):
        """
        Determine if a given VM is in the default vm_resources state.
        The default vm_resources state is determined in config, and
        defaults to "uninitialized".
        """
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], VMState.UNINITIALIZED)

    def test_is_vm_state_default_custom(self):
        """
        Determine if a given VM is in the default vm_resources state.
        The default vm_resources state is determined in config, and
        defaults to "uninitialized".
        """
        new_state = VMState.TESTING
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            state=new_state,
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], new_state)

    def test_set_vm_state_by_uuid(self):
        new_state = VMState.TESTING
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], VMState.UNINITIALIZED)

        self.vmmapping.set_vm_state_by_uuid(self.entries[1]["server_uuid"], new_state)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], new_state)

    def test_set_vm_state_by_uuid_int(self):
        new_state = VMState.TESTING
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], VMState.UNINITIALIZED)

        self.vmmapping.set_vm_state_by_uuid(self.entries[1]["server_uuid"], new_state)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], new_state)

    def test_set_vm_state_by_uuid_none(self):
        new_state = None
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], VMState.UNINITIALIZED)

        self.vmmapping.set_vm_state_by_uuid(self.entries[1]["server_uuid"], new_state)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["state"], None)

    def test_set_vm_time_by_uuid(self):
        new_time = "404"
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], self.entries[1]["current_time"])

        self.vmmapping.set_vm_time_by_uuid(self.entries[1]["server_uuid"], new_time)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], new_time)

    def test_set_vm_time_by_uuid_int(self):
        new_time = 404
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], self.entries[1]["current_time"])

        self.vmmapping.set_vm_time_by_uuid(self.entries[1]["server_uuid"], new_time)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], str(new_time))

    def test_set_vm_time_by_uuid_none(self):
        new_time = None
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], self.entries[1]["current_time"])

        self.vmmapping.set_vm_time_by_uuid(self.entries[1]["server_uuid"], new_time)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], None)

    def test_set_vm_time_by_uuid_invalid(self):
        new_time = "string"
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], self.entries[1]["current_time"])

        self.vmmapping.set_vm_time_by_uuid(self.entries[1]["server_uuid"], new_time)

        found = self.vmmapping.get(server_uuid=self.entries[1]["server_uuid"])
        self.assertEqual(found["current_time"], new_time)

    def test_get_count_vm_not_ready(self):
        new_state = VMState.CONFIGURED
        self.vmmapping.put(
            self.entries[1]["server_uuid"],
            self.entries[1]["server_name"],
            server_address=self.entries[1]["control_ip"],
            current_time=self.entries[1]["current_time"],
        )

        found = self.vmmapping.get_count_vm_not_ready()
        self.assertEqual(found, 1)

        self.vmmapping.set_vm_state_by_uuid(self.entries[1]["server_uuid"], new_state)
        found = self.vmmapping.get_count_vm_not_ready()
        self.assertEqual(found, 0)
