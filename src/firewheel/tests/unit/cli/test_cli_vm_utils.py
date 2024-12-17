from unittest.mock import Mock, PropertyMock, patch

import pytest

from firewheel.cli.vm_utils import VMMixTable, ScheduleProgress


@patch.object(VMMixTable, "mm_api", new=Mock())
class TestVMMixTable:
    """Tests for the ``VMMixTable`` object."""

    sample_mm_vms = {
        "vm0": {"state": "RUNNING", "image": "img_A"},
        "vm1": {"state": "RUNNING", "image": "img_A"},
        "vm2": {"state": "RUNNING", "image": "img_B"},
        "vm3": {"state": "RUNNING", "image": "img_C"},
        "vm4": {"state": "ERROR", "image": "img_C"},
    }
    sample_vmr_states = {
        "vm0": "configured",
        "vm1": "configured",
        "vm2": "configuring",
        "vm3": "uninitialized",
        "vm4": "error",
    }
    sample_mm_states = {
        "RUNNING": {
            "configured": ["img_A", "img_A"],
            "configuring": ["img_B"],
            "uninitialized": ["img_C"],
        },
        "ERROR": {"error": ["img_C"]},
    }

    @patch.object(VMMixTable, "get_mm_states", new=Mock(return_value=sample_mm_states))
    def test_initialization(self):
        assert VMMixTable().row_count == 4

    @patch.object(VMMixTable, "get_mm_states", new=Mock(return_value={}))
    def test_initialization_empty(self):
        # The table is a single row of N/A values if the minimega API finds no states
        assert VMMixTable().row_count == 1

    def test_get_mm_vms(self):
        assert VMMixTable.get_mm_vms() == VMMixTable.mm_api.mm_vms()

    @patch.object(
        VMMixTable, "check_is_active_experiment", new=Mock(return_value=True)
    )
    @patch.object(
        VMMixTable, "get_mm_vms", new=Mock(return_value=sample_mm_vms)
    )
    @patch(
        "firewheel.cli.vm_utils.vmr_api.get_vm_states",
        new=Mock(return_value=sample_vmr_states),
    )
    def test_get_mm_states(self):
        assert VMMixTable.get_mm_states() == self.sample_mm_states

    @patch.object(
        VMMixTable, "check_is_active_experiment", new=Mock(return_value=False)
    )
    def test_get_mm_states_inactive_experiment(self):
        assert VMMixTable.get_mm_states() == {}

    @pytest.mark.parametrize(
        ["launch_time", "mm_vms", "active"],
        [
            [100, {}, True],
            [None, sample_mm_vms, True],
            [None, {}, False],
        ],
    )
    @patch("firewheel.cli.vm_utils.vmr_api.get_experiment_launch_time")
    @patch.object(VMMixTable, "get_mm_vms")
    def test_check_is_active_experiment(
        self, mock_get_mm_vms, mock_get_launch_time, launch_time, mm_vms, active
    ):
        mock_get_launch_time.return_value = launch_time
        mock_get_mm_vms.return_value = mm_vms
        assert VMMixTable.check_is_active_experiment() == active


class TestScheduleProgress:
    """Tests for the ``ScheduleProgress`` object."""

    sample_schedule_db_list = [
        {"server_name": "vmA", "text": Mock("schedule A")},
        {"server_name": "vmB", "text": Mock("schedule B")},
        {"server_name": "vmC", "text": Mock("schedule C")},
    ]
    sample_schedules = {
        "vmA": [
            Mock(name="entry-1a", start_time=-10),
            Mock(name="entry-2a", start_time=-5),
            Mock(name="entry-3a", start_time=10),
        ],
        "vmB": [
            Mock(name="entry-1b", start_time=-10),
            Mock(name="entry-2b", start_time=-5),
            Mock(name="entry-3b", start_time=-1),
        ],
        "vmC": [
            Mock(name="entry-1b", start_time=-100),
            Mock(name="entry-2b", start_time=1),
            Mock(name="entry-3b", start_time=2),
            Mock(name="entry-4b", start_time=3),
        ],
    }

    def test_initialization(self):
        schedule_progress = ScheduleProgress()
        assert len(schedule_progress.columns) == 4

    @pytest.mark.parametrize(
        ["vm_times", "has_begun"],
        [
            ({"vmA": "0", "vmB": "1", "vmC": "2"}, True),
            ({"vmA": "0", "vmB": "1", "vmC": ""}, True),
            ({"vmA": "", "vmB": "", "vmC": ""}, False),
        ],
    )
    @patch("firewheel.cli.vm_utils.vmr_api.get_vm_times")
    def test_experiment_has_begun(self, mock_get_vm_times, vm_times, has_begun):
        mock_get_vm_times.return_value = vm_times
        assert ScheduleProgress().experiment_has_begun == has_begun

    @pytest.mark.parametrize(
        ["experiment_start_time", "in_negative_time"],
        [(0, False), (1, False), (None, True)],
    )
    @patch("firewheel.cli.vm_utils.vmr_api.get_experiment_start_time")
    def test_experiment_in_negative_time(
        self, mock_get_experiment_start_time, experiment_start_time, in_negative_time
    ):
        mock_get_experiment_start_time.return_value = experiment_start_time
        assert ScheduleProgress().experiment_in_negative_time == in_negative_time

    @pytest.mark.parametrize(
        ["has_begun", "in_negative_time", "visible"],
        [
            (False, False, False),
            (False, True, False),
            (True, False, False),
            (True, True, True),
        ],
    )
    @patch.object(ScheduleProgress, "experiment_has_begun", new_callable=PropertyMock)
    @patch.object(
        ScheduleProgress, "experiment_in_negative_time", new_callable=PropertyMock
    )
    def test_visible(
        self,
        mock_has_begun_property,
        mock_in_negative_time_property,
        has_begun,
        in_negative_time,
        visible,
    ):
        mock_has_begun_property.return_value = has_begun
        mock_in_negative_time_property.return_value = in_negative_time
        assert ScheduleProgress().visible == visible

    @patch(
        "firewheel.cli.vm_utils.ScheduleDb.list_all",
        new=Mock(return_value=sample_schedule_db_list),
    )
    @patch("firewheel.cli.vm_utils.pickle.loads")
    def test_schedules(self, mock_pickle_loads):
        assert ScheduleProgress().schedules == {
                "vmA": mock_pickle_loads.return_value,
                "vmB": mock_pickle_loads.return_value,
                "vmC": mock_pickle_loads.return_value,
        }

    @pytest.mark.parametrize(
        ["has_begun", "event_count"],
        [
            (False, None),
            (True, 6),
            (True, 6),
        ],
    )
    @patch.object(ScheduleProgress, "experiment_has_begun", new_callable=PropertyMock)
    @patch.object(
        ScheduleProgress,
        "schedules",
        new_callable=PropertyMock,
        return_value=sample_schedules,
    )
    def test_total_negative_event_count(
        self, mock_schedules, mock_has_begun_property, has_begun, event_count
    ):
        mock_has_begun_property.return_value = has_begun
        assert ScheduleProgress().total_negative_event_count == event_count

    @pytest.mark.parametrize(
        ["vm_times", "event_count"],
        [
            ({"vmA": "-50", "vmB": "-50", "vmC": "-50"}, 0 + 0 + 1),
            ({"vmA": "-1", "vmB": "-1", "vmC": "0"}, 2 + 2 + 1),
            ({"vmA": "0", "vmB": "1", "vmC": "2"}, 2 + 3 + 1),
            ({"vmA": "0", "vmB": "1", "vmC": ""}, 2 + 3 + 0),
            ({"vmA": "", "vmB": "", "vmC": ""}, None),  # experiment has not yet begun
        ],
    )
    @patch("firewheel.cli.vm_utils.vmr_api.get_vm_times")
    @patch.object(
        ScheduleProgress,
        "schedules",
        new_callable=PropertyMock,
        return_value=sample_schedules,
    )
    def test_completed_negative_event_count(
        self, mock_schedules, mock_get_vm_times, vm_times, event_count
    ):
        mock_get_vm_times.return_value = vm_times
        assert ScheduleProgress().completed_negative_event_count == event_count

    @pytest.mark.parametrize(
        ["total_events", "completed_events", "remaining_events"],
        [
            (1, 1, 0),
            (1, 0, 1),
            (10, 7, 3),
            (100, 70, 30),
            (100, 30, 70),
        ],
    )
    @patch.object(
        ScheduleProgress, "completed_negative_event_count", new_callable=PropertyMock
    )
    @patch.object(
        ScheduleProgress, "total_negative_event_count", new_callable=PropertyMock
    )
    def test_remaining_negative_event_count(
        self,
        mock_total_count_property,
        mock_completed_count_property,
        total_events,
        completed_events,
        remaining_events,
    ):
        mock_total_count_property.return_value = total_events
        mock_completed_count_property.return_value = completed_events
        assert ScheduleProgress().remaining_negative_event_count == remaining_events

    @patch("firewheel.cli.vm_utils.Progress.add_task")
    def test_add_negative_time_task(self, mock_add_task_method):
        task_id = ScheduleProgress().add_negative_time_task()
        assert task_id == mock_add_task_method.return_value
        mock_add_task_method.assert_called_once()

    @pytest.mark.parametrize(
        "kwargs",
        [{"visible": False}, {"visible": True, "total": 100, "completed": 10}],
    )
    @patch.object(
        ScheduleProgress, "completed_negative_event_count", new_callable=PropertyMock
    )
    @patch.object(
        ScheduleProgress, "total_negative_event_count", new_callable=PropertyMock
    )
    @patch("firewheel.cli.vm_utils.Progress.update")
    def test_update_negative_time_task(
        self,
        mock_update_task_method,
        mock_total_count_property,
        mock_completed_count_property,
        kwargs,
    ):
        schedule_progress = ScheduleProgress()
        with patch.object(schedule_progress, "_negative_time_task_id") as mock_task_id:
            schedule_progress.update_negative_time_task(**kwargs)
        mock_update_task_method.assert_called_once_with(mock_task_id, **kwargs)
