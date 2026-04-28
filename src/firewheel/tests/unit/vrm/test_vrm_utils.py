import unittest

from firewheel.config import config
from firewheel.vm_resource_manager import utils
from firewheel.vm_resource_manager.vm_mapping import VMMapping, VMState


class UtilsTestCase(unittest.TestCase):
    def setUp(self):
        # Create valid and invalid repository directories
        self.vmmapping_entries = [
            {"server_name": "1", "control_ip": "2", "server_uuid": "1234"},
            {
                "server_name": "2",
                "control_ip": "3",
                "state": "testing",
                "current_time": "0",
                "server_uuid": "12345",
            },
        ]

        self.vmmapping = VMMapping(
            hostname=config["grpc"]["hostname"],
            port=config["grpc"]["port"],
            db=config["test"]["grpc_db"],
        )

        self.vmmapping.batch_put(self.vmmapping_entries)

    def tearDown(self):
        self.vmmapping.destroy_all()

    def test_vm_state_update(self):
        pre = self.vmmapping.get(server_uuid=self.vmmapping_entries[1]["server_uuid"])
        self.assertNotEqual(pre, None)

        new_state = VMState.FAILED
        utils.set_vm_state(
            self.vmmapping_entries[1]["server_uuid"], new_state, mapping=self.vmmapping
        )

        post = self.vmmapping.get(server_uuid=self.vmmapping_entries[1]["server_uuid"])
        self.assertNotEqual(post, None)

        self.assertNotEqual(pre, post)
        self.assertEqual(post["state"], new_state)

    def test_vm_state_invalid(self):
        with self.assertRaises(RuntimeError):
            utils.set_vm_state("invalid", VMState.FAILED, mapping=self.vmmapping)

    def test_vm_time_update(self):
        pre = self.vmmapping.get(server_uuid=self.vmmapping_entries[1]["server_uuid"])
        self.assertNotEqual(pre, None)
        self.assertEqual(pre["current_time"], "0")

        new_time = "100"
        utils.set_vm_time(
            self.vmmapping_entries[1]["server_uuid"], new_time, mapping=self.vmmapping
        )

        post = self.vmmapping.get(server_uuid=self.vmmapping_entries[1]["server_uuid"])
        self.assertNotEqual(post, None)

        self.assertNotEqual(pre, post)
        self.assertEqual(post["current_time"], "100")

    def test_vm_time_invalid(self):
        with self.assertRaises(RuntimeError):
            utils.set_vm_time("invalid", "100", mapping=self.vmmapping)

    def test_not_ready_count_not_zero(self):
        count = utils.get_vm_count_not_ready(mapping=self.vmmapping)
        self.assertEqual(count, len(self.vmmapping_entries))

    def test_not_ready_count_with_ready(self):
        self.vmmapping.put("5", "ready1", state=VMState.CONFIGURED)
        self.vmmapping.put("6", "noresources1", state=VMState.NA)

        count = utils.get_vm_count_not_ready(mapping=self.vmmapping)
        self.assertEqual(count, len(self.vmmapping_entries))
