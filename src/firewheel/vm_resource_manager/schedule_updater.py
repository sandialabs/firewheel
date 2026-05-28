import sys
import math
import pickle
import random
from time import sleep
from queue import PriorityQueue
from threading import Thread

# pylint: disable=unused-import
from firewheel.vm_resource_manager import api
from firewheel.vm_resource_manager.schedule_entry import ScheduleEntry  # noqa: F401
from firewheel.vm_resource_manager.schedule_event import (
    ScheduleEvent,
    ScheduleEventType,
)
from firewheel.vm_resource_manager.experiment_start import ExperimentStart


class ScheduleUpdater(Thread):
    """
    ScheduleUpdater checks for updates to a VM's schedule at specified intervals.

    It then passes those updates to the main processing loop via a :py:class:`queue.PriorityQueue`
    of :py:class:`ScheduleEvents <firewheel.vm_resource_manager.schedule_event.ScheduleEvent>`.
    """

    def __init__(
        self,
        config,
        priority_queue,
        condition,
        vm_resource_store,
        schedule_db,
        repository_db,
        log,
        log_filename,
        load_balance_factor,
        interval_time=5,
    ):
        """
        Initialize the updater class.

        Args:
            config (dict): config for the VM
            priority_queue (PriorityQueue): Queue to place new vm_resource events
                to get picked up by the VMResourceHandler
            condition (Condition): Lock for the priority queue
            vm_resource_store (VmResourceStore): A resource store to use.
            schedule_db (ScheduleDb): A ScheduleDb to use.
            repository_db (RepositoryDb): A RepositoryDb to use.
            log (Logger): The vm_resource launcher's logger for output
            log_filename (str): A filename for the log.
            load_balance_factor (float): Amount of time to scale sleeps by.
            interval_time (int): Amount of time to sleep between checking for updates
        """

        # Must call the __init__ function of Thread
        super().__init__()

        self.log_filename = log_filename
        self.experiment_start_time_object = ExperimentStart()
        self.vm_resource_store = vm_resource_store
        self.schedule_db = schedule_db
        self.repository_db = repository_db

        self.config = config
        self.log = log
        self.prior_q = priority_queue
        self.condition = condition
        self.load_balance_factor = load_balance_factor
        self.interval_time = interval_time

        self.start_time = None
        self.schedule_not_received = True
        self.saved_schedule = []
        self.break_items = []

        self.stop = False

    def run(self):
        """
        Main loop for the thread. Checks for updates and adds events to the event
        queue for processing by the `vm_resource` launcher.
        queue for processing by the VM Resource Handler. The logic for this function
        gets rather complex and provides for the ability to accommodate all event types
        include
        :py:attr:`PAUSE <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.PAUSE>`
        and
        :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>`
        events.
        """
        try:
            self.log.info("ScheduleUpdater: Starting the _run function")
            self._run()
            self.log.info("ScheduleUpdater: Finished the _run function.")
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.info("ScheduleUpdater: Stopping due to an exception.")
            self.log.exception(exp)
        finally:
            self.log.info("ScheduleUpdater: Exiting.")

    def _run(self):
        """
        Main loop for the thread. Checks for updates and adds events to the event
        queue for processing by the VM Resource Handler. The logic for this function
        gets rather complex and provides for the ability to accommodate all event types
        include
        :py:attr:`PAUSE <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.PAUSE>`
        and
        :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>`
        events.
        """

        self.log.debug("Schedule Updater: Entering schedule check loop")
        # This loop checks for schedule updates and then queues
        # the schedule items to be picked up by the consumer
        #
        # The break start keeps track of the break start time
        # while found_break is a method-wide counter of if there
        # is an active break ongoing.
        break_start = 0
        found_break = False
        while True:
            if self.stop:
                self.log.debug("Updater returning")
                return

            try:
                sched_items = self.get_schedule(self.config["vm_name"])
            except RuntimeError:
                self.log.debug(
                    "Error while getting schedule. Sleep random amount of time"
                )
                # Try again after random amount of sleep time
                sleep(self.load_balance_factor * random.SystemRandom().randint(2, 15))
                continue

            if sched_items is None:
                self.log.debug(
                    "Error while getting schedule. Sleep random amount of time"
                )
                # Try again after random amount of sleep time
                sleep(self.load_balance_factor * random.SystemRandom().randint(2, 15))
                continue

            # Load local cache with vm_resource files
            # Getting just the path ensures that the file will be
            # available when the launcher needs to load it into
            # the VM.
            # This is best effort and if it fails, then it'll be
            # handled when the file is required for use
            for item in sched_items:
                if not item.data:
                    # If there is no data required to run the schedule
                    # entry then continue on
                    continue

                for data_entry in item.data:
                    if "filename" in data_entry:
                        try:
                            local_path = self.vm_resource_store.get_path(
                                data_entry["filename"]
                            )
                            if not local_path:
                                self.log.error(
                                    "Unable to get file: %s. Will try"
                                    " again just-in-time",
                                    data_entry["filename"],
                                )
                        # pylint: disable=broad-except
                        except Exception as exp:
                            self.log.error(
                                "Unable to get file: %s", data_entry["filename"]
                            )
                            self.log.exception(exp)

            # Don't use enqueue_event() here since all the schedule items need
            # to be in the queue before releasing control. This is needed so
            # that threading.Barrier can be used by the main processing loop.
            self.condition.acquire()

            # Loop through all the schedule items we have, adding them to the
            # priority queue. The priority queue handles sorting by start time.
            # We use a temporary queue to handle all pause/break cases prior to adding
            # to the queue shared with the VM Resource Handler to prevent cross-thread
            # contamination (though the condition should prevent that).
            temp_q = PriorityQueue()

            # A loop-wide variable of whether any items are RESUME items.
            found_resume = False
            for item in sched_items:
                # Create TRANSFER items
                if (
                    item.data
                    and "location" in item.data[0]
                    and "interval" in item.data[0]
                ):
                    event = ScheduleEvent(ScheduleEventType.TRANSFER, item)
                    temp_q.put((item.start_time, event))
                    continue

                # Check for pause events
                if item.pause:
                    event = ScheduleEvent(ScheduleEventType.PAUSE, item)
                    temp_q.put((item.start_time, event))
                    continue

                # Check for resume events.
                if item.data and "resume" in item.data[0]:
                    # Update our flag to indicate a resume event has been found
                    found_resume = True
                    event = ScheduleEvent(ScheduleEventType.RESUME, item)
                    temp_q.put((item.start_time, event))
                    continue

                # All other events should be of type NEW_ITEM
                event = ScheduleEvent(ScheduleEventType.NEW_ITEM, item)
                temp_q.put((item.start_time, event))

            # If we found a resume event and we have items that occur
            # after the break event which haven't been processed, then
            # we should process them now.
            if found_resume and self.break_items:
                for item in self.break_items:
                    # Create TRANSFER items
                    if (
                        item.data
                        and "location" in item.data[0]
                        and "interval" in item.data[0]
                    ):
                        event = ScheduleEvent(ScheduleEventType.TRANSFER, item)
                        temp_q.put((item.start_time, event))
                        continue

                    # Check for pause events which occur after the break
                    if item.pause:
                        event = ScheduleEvent(ScheduleEventType.PAUSE, item)
                        temp_q.put((item.start_time, event))
                        continue

                    # All other events are NEW_ITEM
                    event = ScheduleEvent(ScheduleEventType.NEW_ITEM, item)
                    temp_q.put((item.start_time, event))

                # Zero out break items as they have been processed
                self.break_items = []

            # We need to empty the temporary queue to identify pauses/breaks/resumes.
            # Once these are identified/handled, other items are queued into the shared
            # queue with possible start time modifications. Items occurring after a break
            # will not be queued, but instead be added to ``self.break_items``
            #
            # `pause_amount` is the loop counter of the cumulative amount of pauses
            # `resume_time` is the experiment time of when a RESUME has been issued.
            # `resume` is a loop flag indicating if we should resume paused events.
            # `break_event` is a loop variable of if a break was found.
            pause_amount = 0
            resume_time = 0
            resume = False
            break_event = False
            while not temp_q.empty():
                # Get event off the queue
                start_time, event = temp_q.get()

                # If there is a break in the temp_q then prevent
                # each following event from being added to the shared queue.
                # Instead, add it to the `self.break_items` list.
                if break_event:
                    # Do not add the event until until a resume has occurred
                    self.break_items.append(event.data)
                    continue

                # If event is a PAUSE event and there is not an existing BREAK
                # then find the duration of the pause. If the duration is infinity
                # than we know it is a break.
                if not found_break and event.event_type == ScheduleEventType.PAUSE:
                    if "pause_duration" in event.data.data[0]:
                        duration = event.data.data[0]["pause_duration"]
                        if math.isinf(duration):
                            # This is a break, so set a number of flags/variables
                            found_break = True
                            break_event = True
                            resume = False
                            if math.isinf(start_time):
                                break_start = 0
                            else:
                                break_start = start_time
                        else:
                            # If the PAUSE has a duration, than we need to increase the
                            # `pause_amount` variable by that amount.
                            pause_amount += duration

                        # Purposely do not include this event in the queue
                        continue

                # If event is a RESUME, than reset our flags and identify
                # the time at which the experiment has resumed.
                if event.event_type == ScheduleEventType.RESUME:
                    # Reset some loop/method-specific flags and identify
                    # the time at which the loop resumed
                    resume = True
                    found_break = False
                    break_event = False
                    # API
                    resume_time = api.get_experiment_time_since_start(
                        start=self.experiment_start_time_object
                    )
                    if resume_time is None:
                        resume_time = 0
                    continue

                # Calculate how many seconds after the break this event would have
                # occurred. Then add that to the experiment time. This ensures that
                # the scheduled events are unaware of anything which happened and it
                # is almost as if the break took 0 seconds. Note that VM time has
                # continued...
                if resume:
                    start_time = event.data.start_time - break_start + resume_time
                    event.data.start_time = start_time

                # If there is a pause amount in this queue,
                # update the start time of all following events to account
                # for the pause.
                if pause_amount > 0:
                    event.data.start_time += pause_amount
                    start_time += pause_amount

                # Add all remaining events to the shared queue
                self.prior_q.put((start_time, event))

            # Only notify if new schedule items were received
            if sched_items:
                self.condition.notify()
                if self.schedule_not_received:
                    self.schedule_not_received = False

            # Release the lock
            self.condition.release()

            # Handle the case where there are no vm_resources and this is an
            # initially downloaded schedule
            if not sched_items and self.schedule_not_received:
                event = ScheduleEvent(ScheduleEventType.EMPTY_SCHEDULE, None)
                # Put the empty schedule event in the queue at MIN_INT time.
                # Since the schedule is empty there won't be anything else in
                # there so it doesn't really matter, but just put all
                # non ScheduleEntry events at the beginning of the queue
                self.enqueue_event(-sys.maxsize - 1, event)
                self.schedule_not_received = False

            # See if everyone has checked in and a start time has been set
            if not self.start_time:
                self.start_time = self.get_start_time()

                if self.start_time:
                    event = ScheduleEvent(
                        ScheduleEventType.EXPERIMENT_START_TIME_SET, self.start_time
                    )
                    self.enqueue_event(-sys.maxsize - 1, event)

            # Sleep for a specified amount of time before checking for
            # updates
            sleep(self.load_balance_factor * int(self.interval_time))

    def stop_thread(self):
        """
        Tell the thread to stop. This is used for unit testing.
        """
        self.stop = True

    def enqueue_event(self, priority, event):
        """
        Put a single event in the priority queue to pass information back
        to the main processing loop.

        Args:
            priority (int): The priority of the event.
            event (ScheduleEvent): Event to be processed.
        """
        self.condition.acquire()
        self.prior_q.put((priority, event))
        self.condition.notify()
        self.condition.release()

    def get_schedule(self, name):
        """
        Get the schedule for a specified VM.

        Note:
            In general, loading pickle data can have some serious security
            implications. Please review :ref:`firewheel_security` for more details.

        Args:
            name (str): Name of the VM.

        Returns:
            list: List of ScheduleEntry objects.

        Raises:
            RuntimeError: If there is an exception getting the schedule.
        """
        try:
            pickled_schedule = self.schedule_db.get(name)
            full_schedule = pickle.loads(pickled_schedule)  # nosec

            # It's possible there is not a schedule for this VM
            if not full_schedule:
                return []

            new_items = full_schedule[len(self.saved_schedule) :]
            self.saved_schedule = full_schedule

            return new_items
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.error("Exception getting schedule for VM: %s", name)
            self.log.exception(exp)
            raise RuntimeError(f"Exception getting schedule for VM: {name}") from exp

        return None

    def get_start_time(self):
        """
        Queries the database to see if a start time for the experiment has
        been set.

        Returns:
            int: Experiment start time if available, None if start time has
                not been set yet
        """
        try:
            experiment_time = api.get_experiment_start_time(
                self.experiment_start_time_object
            )
            self.log.debug("ScheduleUpdater.get_start_time() -> %s", experiment_time)
            if experiment_time:
                self.experiment_start_time_object.close()
                self.experiment_start_time_object = None
            return experiment_time
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.error("Unable to get experiment start time")
            self.log.exception(exp)
            return None
