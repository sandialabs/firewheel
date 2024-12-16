"""
Utilities for VM helpers.
"""
import pickle

from rich.progress import (
    Progress, TextColumn, BarColumn, MofNCompleteColumn, TaskProgressColumn
)

import firewheel.vm_resource_manager.api as vmr_api
from firewheel.vm_resource_manager.schedule_db import ScheduleDb
from firewheel.cli.utils import RichDefaultTable
from firewheel.lib.minimega.api import minimegaAPI


class VMMixTable(RichDefaultTable):
    """A table containing rows of VM information."""

    mm_api = minimegaAPI()
    mm_state_colors = {
        "run": "green",
        "error": "red",
    }
    vmr_state_colors = {
        "configuring": "yellow",
        "configured": "green",
        "uninitialized": "yellow",
        "error": "red",
    }

    def __init__(self):
        """
        Create a table containing rows of VM information.
        """
        # Prepare custom rows for the table
        self._total_scheduled = 0
        rows = self._prepare_rows() or [["N/A", "N/A", "N/A", "0"]]
        # Build the table
        super().__init__(title="VM Mix", show_footer=True)
        self.add_column("VM Image")
        self.add_column("Power State")
        self.add_column("VM Resource State", footer="[b]Total Scheduled")
        self.add_column("Count", footer=f"[b]{self._total_scheduled}")
        for row in rows:
            self.add_row(*row)

    @classmethod
    def get_mm_vms(cls):
        """Get minimega VM information using the minimega API."""
        return cls.mm_api.mm_vms()

    @classmethod
    def get_mm_states(cls):
        """Get state information for the minimega VMs."""
        mm_state_dict = {}
        if cls.check_is_active_experiment():
            vm_resource_vms = vmr_api.get_vm_states()

            for vm_name, vm_dict in cls.get_mm_vms().items():
                mm_state = vm_dict["state"]
                vmr_state = vm_resource_vms.get(vm_name, "None")

                mm_state_info = mm_state_dict.setdefault(mm_state, {})
                vmr_states = mm_state_info.setdefault(vmr_state, [])
                vmr_states.append(vm_dict["image"])

        return mm_state_dict

    @classmethod
    def check_is_active_experiment(cls):
        """Check if an experiment is currently active."""
        # Active experiments have a launch time set or know of VMs
        has_vms = bool(cls.get_mm_vms())
        return vmr_api.get_experiment_launch_time() is not None or has_vms

    def _prepare_rows(self):
        rows = []
        for mm_state, mm_state_info in sorted(self.get_mm_states().items()):
            vmr_states = filter(lambda info: info[0] != "None", mm_state_info.items())
            for vmr_state, vmr_state_info in sorted(vmr_states):
                for operating_system in sorted(set(vmr_state_info)):
                    count = vmr_state_info.count(operating_system)
                    rows.append(
                        self._format_row(operating_system, mm_state, vmr_state, count)
                    )
                    self._total_scheduled += count
        return rows

    @staticmethod
    def _color_state(state, color_map):
        for state_key, color in color_map.items():
            if state_key in state:
                return f"[{color}]{state}"
        return state

    @classmethod
    def _format_row(cls, operating_system, mm_state, vmr_state, count):
        return [
            operating_system,
            cls._color_state(mm_state, cls.mm_state_colors),
            cls._color_state(vmr_state, cls.vmr_state_colors),
            str(count),
        ]


class ScheduleProgress(Progress):
    """A progress display for the experiment schedule."""

    def __init__(self, **kwargs):
        """
        Create a progress bar for negative time schedule entries.

        This is a subclass of the default ``rich.progress.Progress``
        object that provides methods for displaying the progress status
        of (negative time) schedule entries across nodes in a FIREWHEEL
        experiment.

        Notes:
            Progress through negative time in a FIREWHEEL experiment is
            not necessarily linear or well-defined. This object uses a
            heuristic to estimate the completion progress. First, it
            calculates (and updates) the total number of negative time
            schedule entries in the expriment by querying the schedule
            database and counting the total number of entries across all
            nodes. Then, completed entries for a given VM are considered
            to be all those that were scheduled for a time before the
            current VMs experiment time. This is a conservative estimate
            of the completed events, since it potentially omits events
            that are scheduled at the VMs current time but which have
            already completed.

        Arguments:
            **kwargs: Keyword arguments that are passed to the
                ``Progress`` superclass upon instantiation.
        """
        columns = [
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
        ]
        super().__init__(*columns, **kwargs)
        self._schedule_db = ScheduleDb()
        self._negative_time_task_id = None

    @property
    def experiment_has_begun(self):
        return not all(time == "" for time in vmr_api.get_vm_times().values())

    @property
    def experiment_in_negative_time(self):
        return vmr_api.get_experiment_start_time() is None

    @property
    def visible(self):
        return self.experiment_has_begun and self.experiment_in_negative_time

    @property
    def schedules(self):
        return {
            schedule["server_name"]: pickle.loads(schedule["text"])
            for schedule in self._schedule_db.list_all()
        }

    @property
    def total_negative_event_count(self):
        if self.experiment_has_begun:
            return sum(
                self._count_negative_entries(schedule)
                for schedule in self.schedules.values()
            )
        return None

    @property
    def completed_negative_event_count(self):
        # A conservative estimate; does not include completed events at the current time
        if self.experiment_has_begun:
            vm_times = {
                server_name: float('-inf') if time == "" else int(time)
                for server_name, time in vmr_api.get_vm_times().items()
            }
            return sum(
                self._count_negative_entries(schedule, filter_time=vm_times[server_name])
                for server_name, schedule in self.schedules.items()
            )
        return None

    @property
    def remaining_negative_event_count(self):
        return self.total_negative_event_count - self.completed_negative_event_count

    def _count_negative_entries(self, schedule, filter_time=0):
	# Only count negative entries
        filter_time = min(filter_time, 0)
        return len([entry for entry in schedule if entry.start_time < filter_time])

    def add_negative_time_task(self, **kwargs):
        """Add a specific task for tracking negative time event progress."""
        kwargs.setdefault("visible", False)
        kwargs.setdefault("total", self.total_negative_event_count)
        self._negative_time_task_id = self.add_task(
            "Working through experiment negative time", **kwargs
        )
        return self._negative_time_task_id

    def update_negative_time_task(self, **kwargs):
        """Update the task for tracking negative time event progress."""
        if kwargs.setdefault("visible", self.visible):
            kwargs.setdefault("total", self.total_negative_event_count)
            kwargs.setdefault("completed", self.completed_negative_event_count)
        self.update(self._negative_time_task_id, **kwargs)
