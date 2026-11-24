from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, create_autospec

import pytest

from firewheel.vm_resource_manager import api
from firewheel.vm_resource_manager.vm_mapping import VMState
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore

VM_STATUS_PROJECT_DICT = {
    "_id": 0,
    "server_name": 1,
    "state": 1,
    "has_execution_issues": 1,
    "execution_issue_count": 1,
    "last_execution_issue": 1,
}


def test_get_vm_states_returns_legacy_shape():
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

    assert states == {"vm-1": VMState.CONFIGURED, "vm-2": VMState.UNINITIALIZED}
    mapping.get_all.assert_called_once_with(
        filter_state=None,
        project_dict=VM_STATUS_PROJECT_DICT,
    )
    mapping.close.assert_not_called()


def test_get_vm_states_passes_filter_to_status_lookup():
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

    assert states == {"vm-1": VMState.TESTING}
    mapping.get_all.assert_called_once_with(
        filter_state=VMState.TESTING,
        project_dict=VM_STATUS_PROJECT_DICT,
    )


def test_get_vm_statuses_returns_execution_issue_metadata():
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

    assert statuses == {
        "vm-1": {
            "state": VMState.CONFIGURED,
            "has_execution_issues": True,
            "execution_issue_count": 2,
            "last_execution_issue": "warning text",
        }
    }


def test_get_vm_statuses_closes_mapping_when_created_internally():
    mapping = Mock()
    mapping.get_all.return_value = []
    mapping.close = Mock()

    with patch("firewheel.vm_resource_manager.api.VMMapping", return_value=mapping):
        statuses = api.get_vm_statuses()

    assert statuses == {}
    mapping.close.assert_called_once()


def test_get_vm_times_returns_times_by_server_name():
    mapping = Mock()
    mapping.get_all.return_value = [
        {"server_name": "vm-1", "current_time": "-50"},
        {"server_name": "vm-2", "current_time": "0"},
    ]

    times = api.get_vm_times(mapping=mapping)

    assert times == {"vm-1": "-50", "vm-2": "0"}
    mapping.get_all.assert_called_once_with(
        filter_time=None,
        project_dict={"_id": 0, "server_name": 1, "current_time": 1},
    )
    mapping.close.assert_not_called()


def test_get_vm_times_passes_filter():
    mapping = Mock()
    mapping.get_all.return_value = [{"server_name": "vm-1", "current_time": "0"}]

    times = api.get_vm_times(filter_time="0", mapping=mapping)

    assert times == {"vm-1": "0"}
    mapping.get_all.assert_called_once_with(
        filter_time="0",
        project_dict={"_id": 0, "server_name": 1, "current_time": 1},
    )


def test_get_vm_times_closes_mapping_when_created_internally():
    mapping = Mock()
    mapping.get_all.return_value = []

    with patch("firewheel.vm_resource_manager.api.VMMapping", return_value=mapping):
        assert api.get_vm_times() == {}

    mapping.close.assert_called_once()


def test_add_vm_uses_uninitialized_when_vm_manager_enabled():
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


def test_add_vm_uses_na_when_vm_manager_disabled():
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


def test_add_vm_creates_and_closes_mapping_when_needed():
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


def test_destroy_all_clears_all_backends():
    mapping = Mock()
    schedule = Mock()
    start = Mock()

    api.destroy_all(mapping=mapping, schedule=schedule, start=start)

    mapping.destroy_all.assert_called_once()
    schedule.destroy_all.assert_called_once()
    start.clear_start_time.assert_called_once()
    schedule.close.assert_not_called()


def test_destroy_all_ignores_mapping_connection_error_when_requested():
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


def test_destroy_all_ignores_start_connection_error_when_requested():
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


def test_destroy_all_raises_mapping_connection_error_by_default():
    with patch(
        "firewheel.vm_resource_manager.api.VMMapping",
        side_effect=ConnectionError("down"),
    ):
        with pytest.raises(ConnectionError):
            api.destroy_all()


def test_destroy_all_does_not_close_caller_mapping():
    mapping = Mock()

    api.destroy_all(mapping=mapping, schedule=Mock(), start=Mock())

    mapping.close.assert_not_called()


def test_destroy_all_creates_and_closes_mapping():
    mapping = Mock()

    with patch("firewheel.vm_resource_manager.api.VMMapping", return_value=mapping):
        api.destroy_all(schedule=Mock(), start=Mock())

    mapping.destroy_all.assert_called_once()
    mapping.close.assert_called_once()


def test_destroy_all_creates_and_closes_schedule():
    mapping = Mock()
    schedule = Mock()
    start = Mock()

    with (
        patch("firewheel.vm_resource_manager.api.ScheduleDb", return_value=schedule),
        patch("firewheel.vm_resource_manager.api.ExperimentStart", return_value=start),
    ):
        api.destroy_all(mapping=mapping)

    mapping.destroy_all.assert_called_once()
    mapping.close.assert_not_called()
    schedule.destroy_all.assert_called_once()
    schedule.close.assert_called_once()
    start.clear_start_time.assert_called_once()


def test_get_experiment_launch_time_wrapper():
    start = Mock()
    launch_time = datetime.now(timezone.utc)
    start.get_launch_time.return_value = launch_time

    assert api.get_experiment_launch_time(start=start) == launch_time
    start.get_launch_time.assert_called_once_with()


def test_set_experiment_launch_time_wrapper():
    start = Mock()
    launch_time = datetime.now(timezone.utc)
    start.set_launch_time.return_value = launch_time

    assert api.set_experiment_launch_time(start=start) == launch_time
    start.set_launch_time.assert_called_once_with()


def test_get_experiment_start_time_wrapper():
    start = Mock()
    start_time = datetime.now(timezone.utc)
    start.get_start_time.return_value = start_time

    assert api.get_experiment_start_time(start=start) == start_time
    start.get_start_time.assert_called_once_with()


def test_add_experiment_start_time_wrapper():
    start = Mock()
    start_time = datetime.now(timezone.utc)
    start.add_start_time.return_value = start_time

    assert api.add_experiment_start_time(start=start) == start_time
    start.add_start_time.assert_called_once_with()


def test_get_experiment_time_to_start_wrapper():
    start = Mock()
    start.get_time_to_start.return_value = 60

    assert api.get_experiment_time_to_start(start=start) == 60
    start.get_time_to_start.assert_called_once_with()


def test_get_experiment_time_since_start_wrapper():
    start = Mock()
    start.get_time_since_start.return_value = 5

    assert api.get_experiment_time_since_start(start=start) == 5
    start.get_time_since_start.assert_called_once_with()


def test_experiment_time_wrappers_create_start_when_needed():
    start = Mock()
    launch_time = datetime.now(timezone.utc)
    start_time = launch_time + timedelta(seconds=60)
    start.get_launch_time.return_value = launch_time
    start.set_launch_time.return_value = launch_time
    start.get_start_time.return_value = start_time
    start.add_start_time.return_value = start_time
    start.get_time_to_start.return_value = 60
    start.get_time_since_start.return_value = 5

    with patch(
        "firewheel.vm_resource_manager.api.ExperimentStart",
        return_value=start,
    ) as start_cls:
        assert api.get_experiment_launch_time() == launch_time
        assert api.set_experiment_launch_time() == launch_time
        assert api.get_experiment_start_time() == start_time
        assert api.add_experiment_start_time() == start_time
        assert api.get_experiment_time_to_start() == 60
        assert api.get_experiment_time_since_start() == 5

    assert start_cls.call_count == 6


def test_vm_resource_list_returns_distinct_contents():
    store = create_autospec(VmResourceStore, instance=True)
    store.list_distinct_contents.return_value = ["a.sh", "b.sh"]

    contents = api.vm_resource_list(store=store)

    assert contents == ["a.sh", "b.sh"]
    store.list_distinct_contents.assert_called_once_with()


def test_vm_resource_list_collapses_duplicate_store_entries():
    # Use the real list_distinct_contents with a stubbed minimega file list in
    # which the same file is present on multiple mesh hosts.
    store = object.__new__(VmResourceStore)
    store.store = "vm_resources"
    store.log = Mock()
    store.mm_api = Mock()
    store.mm_api.mm.file_list.return_value = [
        {
            "Tabular": [
                ["host1", "vm_resources/a.sh", "10"],
                ["host2", "vm_resources/a.sh", "10"],
                ["host1", "vm_resources/b.sh", "20"],
            ]
        }
    ]

    contents = api.vm_resource_list(store=store)

    assert sorted(contents) == ["a.sh", "b.sh"]


def test_vm_resource_list_creates_store_when_needed():
    store = create_autospec(VmResourceStore, instance=True)
    store.list_distinct_contents.return_value = ["a.sh"]

    with patch("firewheel.vm_resource_manager.api.VmResourceStore", return_value=store):
        contents = api.vm_resource_list()

    assert contents == ["a.sh"]


def test_add_vm_resource_file_delegates_to_store():
    store = create_autospec(VmResourceStore, instance=True)

    api.add_vm_resource_file("/tmp/script.sh", store=store)

    store.add_file.assert_called_once_with("/tmp/script.sh")


def test_add_vm_resource_file_creates_store_when_needed():
    store = create_autospec(VmResourceStore, instance=True)

    with patch("firewheel.vm_resource_manager.api.VmResourceStore", return_value=store):
        api.add_vm_resource_file("/tmp/script.sh")

    store.add_file.assert_called_once_with("/tmp/script.sh")
