import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from firewheel.vm_resource_manager import api
from firewheel.vm_resource_manager.vm_mapping import VMState


class APITestCase(unittest.TestCase):
    def test_get_vm_states_returns_legacy_shape(self):
        mapping = Mock()
        mapping.get_all.return_value = [
            {
                "server_name": "vm-1",
                "state": VMState.CONFIGURED,
                "has_execution_issues": True,
                "execution_issue_count": 2,
                "last_execution_issue": "warning text",
            },
            {
                "server_name": "vm-2",
                "state": VMState.UNINITIALIZED,
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            },
        ]

        states = api.get_vm_states(mapping=mapping)

        self.assertEqual(
            states,
            {"vm-1": VMState.CONFIGURED, "vm-2": VMState.UNINITIALIZED},
        )
        mapping.get_all.assert_called_once_with(
            filter_state=None,
            project_dict={
                "_id": 0,
                "server_name": 1,
                "state": 1,
                "has_execution_issues": 1,
                "execution_issue_count": 1,
                "last_execution_issue": 1,
            },
        )
        mapping.close.assert_not_called()

    def test_get_vm_states_passes_filter_to_status_lookup(self):
        mapping = Mock()
        mapping.get_all.return_value = [
            {
                "server_name": "vm-1",
                "state": VMState.TESTING,
                "has_execution_issues": False,
                "execution_issue_count": 0,
                "last_execution_issue": "",
            }
        ]

        states = api.get_vm_states(filter_state=VMState.TESTING, mapping=mapping)

        self.assertEqual(states, {"vm-1": VMState.TESTING})
        mapping.get_all.assert_called_once_with(
            filter_state=VMState.TESTING,
            project_dict={
                "_id": 0,
                "server_name": 1,
                "state": 1,
                "has_execution_issues": 1,
                "execution_issue_count": 1,
                "last_execution_issue": 1,
            },
        )

    def test_get_vm_statuses_returns_execution_issue_metadata(self):
        mapping = Mock()
        mapping.get_all.return_value = [
            {
                "server_name": "vm-1",
                "state": VMState.CONFIGURED,
                "has_execution_issues": True,
                "execution_issue_count": 2,
                "last_execution_issue": "warning text",
            }
        ]

        statuses = api.get_vm_statuses(mapping=mapping)

        self.assertEqual(
            statuses,
            {
                "vm-1": {
                    "state": VMState.CONFIGURED,
                    "has_execution_issues": True,
                    "execution_issue_count": 2,
                    "last_execution_issue": "warning text",
                }
            },
        )

    def test_get_vm_statuses_closes_mapping_when_created_internally(self):
        mapping = Mock()
        mapping.get_all.return_value = []
        mapping.close = Mock()

        with patch("firewheel.vm_resource_manager.api.VMMapping", return_value=mapping):
            statuses = api.get_vm_statuses()

        self.assertEqual(statuses, {})
        mapping.close.assert_called_once()

    def test_get_vm_times_returns_times_by_server_name(self):
        mapping = Mock()
        mapping.get_all.side_effect = [
            [],
            [
                {"server_name": "vm-1", "current_time": "-50"},
                {"server_name": "vm-2", "current_time": "0"},
            ],
        ]

        times = api.get_vm_times(mapping=mapping)

        self.assertEqual(times, {"vm-1": "-50", "vm-2": "0"})
        self.assertEqual(mapping.get_all.call_count, 2)
        mapping.get_all.assert_any_call(filter_time=None)
        mapping.get_all.assert_any_call(
            filter_time=None,
            project_dict={"_id": 0, "server_name": 1, "current_time": 1},
        )

    def test_get_vm_times_passes_filter(self):
        mapping = Mock()
        mapping.get_all.side_effect = [
            [],
            [{"server_name": "vm-1", "current_time": "0"}],
        ]

        times = api.get_vm_times(filter_time="0", mapping=mapping)

        self.assertEqual(times, {"vm-1": "0"})
        mapping.get_all.assert_any_call(filter_time="0")
        mapping.get_all.assert_any_call(
            filter_time="0",
            project_dict={"_id": 0, "server_name": 1, "current_time": 1},
        )

    def test_add_vm_uses_uninitialized_when_vm_manager_enabled(self):
        mapping = Mock()

        api.add_vm(
            "uuid-1",
            "vm-1",
            "10.0.0.1",
            use_vm_manager=True,
            mapping=mapping,
        )

        mapping.put.assert_called_once_with(
            "uuid-1",
            "vm-1",
            state=VMState.UNINITIALIZED,
            server_address="10.0.0.1",
        )

    def test_add_vm_uses_na_when_vm_manager_disabled(self):
        mapping = Mock()

        api.add_vm(
            "uuid-1",
            "vm-1",
            "10.0.0.1",
            use_vm_manager=False,
            mapping=mapping,
        )

        mapping.put.assert_called_once_with(
            "uuid-1",
            "vm-1",
            state=VMState.NA,
            server_address="10.0.0.1",
        )

    def test_add_vm_creates_and_closes_mapping_when_needed(self):
        mapping = Mock()

        with patch("firewheel.vm_resource_manager.api.VMMapping", return_value=mapping):
            api.add_vm("uuid-1", "vm-1", "10.0.0.1")

        mapping.put.assert_called_once_with(
            "uuid-1",
            "vm-1",
            state=VMState.UNINITIALIZED,
            server_address="10.0.0.1",
        )
        mapping.close.assert_called_once()

    def test_destroy_all_clears_all_backends(self):
        mapping = Mock()
        schedule = Mock()
        start = Mock()

        api.destroy_all(mapping=mapping, schedule=schedule, start=start)

        mapping.destroy_all.assert_called_once()
        schedule.destroy_all.assert_called_once()
        start.clear_start_time.assert_called_once()
        schedule.close.assert_not_called()

    def test_destroy_all_ignores_mapping_connection_error_when_requested(self):
        schedule = Mock()
        start = Mock()

        with patch(
            "firewheel.vm_resource_manager.api.VMMapping",
            side_effect=ConnectionError("down"),
        ):
            api.destroy_all(
                schedule=schedule,
                start=start,
                ignore_grpc_connection_errors=True,
            )

        schedule.destroy_all.assert_called_once()
        start.clear_start_time.assert_called_once()

    def test_destroy_all_ignores_start_connection_error_when_requested(self):
        mapping = Mock()
        schedule = Mock()

        with patch(
            "firewheel.vm_resource_manager.api.ExperimentStart",
            side_effect=ConnectionError("down"),
        ):
            api.destroy_all(
                mapping=mapping,
                schedule=schedule,
                ignore_grpc_connection_errors=True,
            )

        mapping.destroy_all.assert_called_once()
        schedule.destroy_all.assert_called_once()

    def test_destroy_all_raises_mapping_connection_error_by_default(self):
        with patch(
            "firewheel.vm_resource_manager.api.VMMapping",
            side_effect=ConnectionError("down"),
        ):
            with self.assertRaises(ConnectionError):
                api.destroy_all()

    def test_destroy_all_creates_and_closes_schedule(self):
        mapping = Mock()
        schedule = Mock()
        start = Mock()

        with (
            patch("firewheel.vm_resource_manager.api.ScheduleDb", return_value=schedule),
            patch("firewheel.vm_resource_manager.api.ExperimentStart", return_value=start),
        ):
            api.destroy_all(mapping=mapping)

        mapping.destroy_all.assert_called_once()
        schedule.destroy_all.assert_called_once()
        schedule.close.assert_called_once()
        start.clear_start_time.assert_called_once()

    def test_get_experiment_launch_time_wrapper(self):
        start = Mock()
        launch_time = datetime.now(timezone.utc)
        start.get_launch_time.return_value = launch_time

        self.assertEqual(api.get_experiment_launch_time(start=start), launch_time)
        start.get_launch_time.assert_called_once_with()

    def test_set_experiment_launch_time_wrapper(self):
        start = Mock()
        launch_time = datetime.now(timezone.utc)
        start.set_launch_time.return_value = launch_time

        self.assertEqual(api.set_experiment_launch_time(start=start), launch_time)
        start.set_launch_time.assert_called_once_with()

    def test_get_experiment_start_time_wrapper(self):
        start = Mock()
        start_time = datetime.now(timezone.utc)
        start.get_start_time.return_value = start_time

        self.assertEqual(api.get_experiment_start_time(start=start), start_time)
        start.get_start_time.assert_called_once_with()

    def test_add_experiment_start_time_wrapper(self):
        start = Mock()
        start_time = datetime.now(timezone.utc)
        start.add_start_time.return_value = start_time

        self.assertEqual(api.add_experiment_start_time(start=start), start_time)
        start.add_start_time.assert_called_once_with()

    def test_get_experiment_time_to_start_wrapper(self):
        start = Mock()
        start.get_time_to_start.return_value = 60

        self.assertEqual(api.get_experiment_time_to_start(start=start), 60)
        start.get_time_to_start.assert_called_once_with()

    def test_get_experiment_time_since_start_wrapper(self):
        start = Mock()
        start.get_time_since_start.return_value = 5

        self.assertEqual(api.get_experiment_time_since_start(start=start), 5)
        start.get_time_since_start.assert_called_once_with()

    def test_experiment_time_wrappers_create_start_when_needed(self):
        start = Mock()
        launch_time = datetime.now(timezone.utc)
        start_time = launch_time + timedelta(seconds=60)
        start.get_launch_time.return_value = launch_time
        start.set_launch_time.return_value = launch_time
        start.get_start_time.return_value = start_time
        start.add_start_time.return_value = start_time
        start.get_time_to_start.return_value = 60
        start.get_time_since_start.return_value = 5

        with patch("firewheel.vm_resource_manager.api.ExperimentStart", return_value=start) as start_cls:
            self.assertEqual(api.get_experiment_launch_time(), launch_time)
            self.assertEqual(api.set_experiment_launch_time(), launch_time)
            self.assertEqual(api.get_experiment_start_time(), start_time)
            self.assertEqual(api.add_experiment_start_time(), start_time)
            self.assertEqual(api.get_experiment_time_to_start(), 60)
            self.assertEqual(api.get_experiment_time_since_start(), 5)

        self.assertEqual(start_cls.call_count, 6)

    def test_vm_resource_list_returns_distinct_contents(self):
        store = Mock()
        store.list_distinct_contents.return_value = ["a.sh", "b.sh"]

        contents = api.vm_resource_list(store=store)

        self.assertEqual(contents, ["a.sh", "b.sh"])
        store.list_distinct_contents.assert_called_once_with()
        store.close.assert_not_called()

    def test_vm_resource_list_creates_and_closes_store(self):
        store = Mock()
        store.list_distinct_contents.return_value = ["a.sh"]

        with patch("firewheel.vm_resource_manager.api.VmResourceStore", return_value=store):
            contents = api.vm_resource_list()

        self.assertEqual(contents, ["a.sh"])
        store.close.assert_called_once()

    def test_add_vm_resource_file_delegates_to_store(self):
        store = Mock()

        api.add_vm_resource_file("/tmp/script.sh", store=store)

        store.add_file.assert_called_once_with("/tmp/script.sh")

    def test_add_vm_resource_file_creates_store_when_needed(self):
        store = Mock()

        with patch("firewheel.vm_resource_manager.api.VmResourceStore", return_value=store):
            api.add_vm_resource_file("/tmp/script.sh")

        store.add_file.assert_called_once_with("/tmp/script.sh")
