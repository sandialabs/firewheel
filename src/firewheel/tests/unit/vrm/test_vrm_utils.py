import unittest
from unittest.mock import Mock, patch

from firewheel.vm_resource_manager import utils
from firewheel.vm_resource_manager.vm_mapping import VMState


class UtilsTestCase(unittest.TestCase):
    def test_vm_state_update(self):
        mapping = Mock()
        mapping.set_vm_state_by_uuid.return_value = {
            "server_uuid": "uuid-1",
            "state": VMState.FAILED,
        }

        utils.set_vm_state("uuid-1", VMState.FAILED, mapping=mapping)

        mapping.set_vm_state_by_uuid.assert_called_once_with("uuid-1", VMState.FAILED)
        mapping.close.assert_not_called()

    def test_vm_state_update_creates_and_closes_mapping(self):
        mapping = Mock()
        mapping.set_vm_state_by_uuid.return_value = {
            "server_uuid": "uuid-1",
            "state": VMState.FAILED,
        }

        with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
            utils.set_vm_state("uuid-1", VMState.FAILED)

        mapping.set_vm_state_by_uuid.assert_called_once_with("uuid-1", VMState.FAILED)
        mapping.close.assert_called_once()

    def test_vm_state_invalid(self):
        mapping = Mock()
        mapping.set_vm_state_by_uuid.return_value = None

        with self.assertRaises(RuntimeError):
            utils.set_vm_state("invalid", VMState.FAILED, mapping=mapping)

    def test_vm_time_update(self):
        mapping = Mock()
        mapping.set_vm_time_by_uuid.return_value = {
            "server_uuid": "uuid-1",
            "current_time": "100",
        }

        utils.set_vm_time("uuid-1", "100", mapping=mapping)

        mapping.set_vm_time_by_uuid.assert_called_once_with("uuid-1", "100")
        mapping.close.assert_not_called()

    def test_vm_time_update_creates_and_closes_mapping(self):
        mapping = Mock()
        mapping.set_vm_time_by_uuid.return_value = {
            "server_uuid": "uuid-1",
            "current_time": "100",
        }

        with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
            utils.set_vm_time("uuid-1", 100)

        mapping.set_vm_time_by_uuid.assert_called_once_with("uuid-1", "100")
        mapping.close.assert_called_once()

    def test_vm_time_invalid(self):
        mapping = Mock()
        mapping.set_vm_time_by_uuid.return_value = None

        with self.assertRaises(RuntimeError):
            utils.set_vm_time("invalid", "100", mapping=mapping)

    def test_add_execution_issue(self):
        mapping = Mock()
        mapping.add_execution_issue_by_uuid.return_value = {
            "server_uuid": "uuid-1",
            "has_execution_issues": True,
        }

        utils.add_execution_issue("uuid-1", "warning text", mapping=mapping)

        mapping.add_execution_issue_by_uuid.assert_called_once_with("uuid-1", "warning text")
        mapping.close.assert_not_called()

    def test_add_execution_issue_creates_and_closes_mapping(self):
        mapping = Mock()
        mapping.add_execution_issue_by_uuid.return_value = {
            "server_uuid": "uuid-1",
            "has_execution_issues": True,
        }

        with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
            utils.add_execution_issue("uuid-1", "warning text")

        mapping.add_execution_issue_by_uuid.assert_called_once_with("uuid-1", "warning text")
        mapping.close.assert_called_once()

    def test_add_execution_issue_invalid(self):
        mapping = Mock()
        mapping.add_execution_issue_by_uuid.return_value = None

        with self.assertRaises(RuntimeError):
            utils.add_execution_issue("invalid", "warning text", mapping=mapping)

    def test_not_ready_count_not_zero(self):
        mapping = Mock()
        mapping.get_count_vm_not_ready.return_value = 2

        count = utils.get_vm_count_not_ready(mapping=mapping)
        self.assertEqual(count, 2)
        mapping.close.assert_not_called()

    def test_not_ready_count_with_ready(self):
        mapping = Mock()
        mapping.get_count_vm_not_ready.return_value = 0

        count = utils.get_vm_count_not_ready(mapping=mapping)
        self.assertEqual(count, 0)

    def test_not_ready_count_creates_and_closes_mapping(self):
        mapping = Mock()
        mapping.get_count_vm_not_ready.return_value = 3

        with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
            count = utils.get_vm_count_not_ready()

        self.assertEqual(count, 3)
        mapping.close.assert_called_once()
