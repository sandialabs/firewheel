#!/usr/bin/env python

"""
This module contains the class enable the ``vm_resource_handler`` to
run. This runs as a process for each VM that is launched with FIREWHEEL and
controls the interaction with the QEMU Guest Agent.
"""

import os
import sys
import json
import time
import random
import socket
import asyncio
import inspect
import contextlib
import importlib.util
from queue import Queue, PriorityQueue
from pathlib import Path, PureWindowsPath
from datetime import datetime, timezone, timedelta
from threading import Timer, Thread, Condition

from firewheel.config import config as global_config
from firewheel.lib.log import UTCLog
from firewheel.lib.minimega.api import minimegaAPI
from firewheel.vm_resource_manager import api, utils
from firewheel.control.repository_db import RepositoryDb
from firewheel.vm_resource_manager.vm_mapping import VMMapping
from firewheel.vm_resource_manager.schedule_db import ScheduleDb
from firewheel.vm_resource_manager.schedule_event import (
    ScheduleEvent,
    ScheduleEventType,
)
from firewheel.vm_resource_manager.abstract_driver import AbstractDriver
from firewheel.vm_resource_manager.schedule_updater import ScheduleUpdater
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


class VMResourceHandler:
    """
    Main class for communicating with a VM. Kicks off the ScheduleUpdater thread
    and handles all ScheduleEvents and their side effects.
    """

    def __init__(self, config, check_interval=10):
        """
        Args:
            config (dict): VM configuration.
            check_interval (int): Seconds between checks for an updated schedule
                This gets passed to the ScheduleUpdater. Defaults to 10.
        """

        # Class variable initialization
        self.log_directory = (
            Path(global_config["logging"]["root_dir"])
            / global_config["logging"]["vmr_log_dir"]
        )
        self.driver_directory = Path(__file__).resolve().parent / "drivers"
        self.driver = None
        self.experiment_start_time = None
        self.current_time = None
        self.state = None

        # Make sure the directory for logs exists
        self.log_directory.mkdir(exist_ok=True, parents=True)

        self.config = config

        # Set up the logging file
        self.log_filename = self.log_directory / (f"{self.config['vm_name']}.log")
        self.json_log_filename = str(
            self.log_directory / (f"{self.config['vm_name']}.json")
        )

        # We want VM Resource logs to be in UTC
        log_format = "[%(asctime)s %(levelname)s] %(message)s"
        log_level = global_config["logging"]["level"]
        self.log = UTCLog(
            "VMResourceHandler",
            log_file=self.log_filename,
            log_format=log_format,
            log_level=log_level,
        ).log

        self.json_log = UTCLog(
            "VMResourceHandlerJSON",
            log_file=self.json_log_filename,
            log_format="%(message)s",
            log_level=log_level,
        ).log

        self.log.info("Starting RESOURCE HANDLER")
        self.log.info("Using Python %s", sys.version)

        self.log.info(self.config)

        # Start the current time to be the most negative
        self.initial_time = -(sys.maxsize - 1)
        self.current_time = self.initial_time

        # Get a handle to the vm_resources store
        self.vm_resource_store = VmResourceStore()

        # Get a handle to the ScheduleDb
        self.schedule_db = ScheduleDb(log=self.log)

        # Get a handle to vm_mapping
        self.vm_mapping = VMMapping()

        # Get a handle to repository_db
        self.repository_db = RepositoryDb()

        # Priority Queue to hold on to ScheduleEvents
        self.prior_q = PriorityQueue()
        self.mma = minimegaAPI()
        self.load_balance_factor = self.mma.get_cpu_commit_ratio() + 1
        self.log.info("Using load_balance_factor of %s", self.load_balance_factor)

        # Kick off the schedule updater thread that
        # periodically checks for schedule updates and
        # the experiment start time. Updates get placed
        # in the priority queue
        self.condition = Condition()
        self.schedule_updater = ScheduleUpdater(
            self.config,
            self.prior_q,
            self.condition,
            self.vm_resource_store,
            self.schedule_db,
            self.repository_db,
            self.log,
            self.log_filename,
            self.load_balance_factor,
            check_interval,
        )

        # Make sure the path is available
        socket_path = Path(self.config["path"])
        try:
            os.stat(socket_path)
        except FileNotFoundError:
            self.log.debug("Waiting for path: %s", socket_path)
            time.sleep(self.load_balance_factor * 1)
        except PermissionError:
            self.log.info(
                "PermissionError: Trying to update permissions for %s through minimega",
                socket_path,
            )
            parent_dir = socket_path.parent
            self.mma.set_group_perms(parent_dir)

        self.log.debug("Found path")

        # load the driver for the virtualization engine
        try:
            self.driver_class = self.import_driver()
        except Exception as exp:  # noqa: BLE001
            self.log.exception(exp)

        connected = self.connect_to_driver()

        if connected:
            self.set_state("configuring")
        else:
            sys.exit(1)

        # Don't kick off the updater until we're connected to the VM
        self.schedule_updater.start()

        # Grab the target OS
        self.target_os = self.driver.get_os()

        # Windows allow QGA connections before the system is actually fully functional.
        # Because the resource handler starts executing tasks on connect, it is important
        # that the VM is fully functional first. Without this, Windows VMs will not
        # be ready to have processes modifying disk and issues could arise.
        if "Windows" in self.target_os:
            time.sleep(self.load_balance_factor * 10)

        self.log.info("Setting time")
        # Set the time in the VM
        self.driver.set_time()
        self.log.info("Done setting time")

    def connect_to_driver(self):
        """
        Instantiate the driver class to communicate to the VM

        Returns:
            bool: True if the driver is connected, False otherwise.
        """
        if self.driver:
            self.driver.close()
        while True:
            try:
                if not self.driver:
                    # Establish connectivity to the VM
                    self.log.info("New driver connection")
                    self.driver = self.driver_class(self.config, self.log)
                else:
                    # Reestablish connectivity to the VM
                    self.log.info("Resetting driver connection")
                    sync = self.driver.connect()
                    self.log.info("Synced: %s", sync)
                return True
            except Exception as exp:  # noqa: BLE001
                # Sleep another timeout amount of time
                self.log.exception(exp)
                time.sleep(
                    self.load_balance_factor * random.SystemRandom().randint(3, 10)
                )

    def run(self):
        """
        Run the VMResourceHandler.
        """
        try:
            self.log.info("VmResourceHandler: Starting the _run function")
            self._run()
            self.log.info("VmResourceHandler: Finished the _run function.")
        except Exception as exp:  # noqa: BLE001
            self.log.info("VmResourceHandler: Stopping due to an exception.")
            self.log.exception(exp)
        finally:
            self.log.info("VmResourceHandler: Exiting.")

    def _run(self):
        """
        This is the main processing loop for the VMResourceHandler.

        It kicks off the ScheduleUpdater thread and threads to run the individual
        vm_resources.
        """
        self.preload_files()
        while True:
            # This function will block if there are not events
            # in the priority queue
            events = self.get_events()

            threads = []
            reboot_queue = Queue()

            for event in events:
                if event.get_type() == ScheduleEventType.EXPERIMENT_START_TIME_SET:
                    self.log.debug("PROCESSING EXPERIMENT START EVENT")
                    # Set the experiment start time
                    self.experiment_start_time = event.get_data()

                elif event.get_type() == ScheduleEventType.EMPTY_SCHEDULE:
                    # If there is an empty schedule returned by the downloader
                    # at the beginning of the downloaded ordered schedule list,
                    # then we have no negative time vm_resources at this point and
                    # need to pass the global barrier
                    self.log.debug("PROCESSING NO SCHEDULE EVENT")
                    self.current_time = 0
                    self.set_state("configured")

                elif event.get_type() == ScheduleEventType.NEW_ITEM:
                    self.log.debug("PROCESSING NEW ITEM EVENT")
                    schedule_entry = event.get_data()

                    # Determine the paths inside the VM for this vm_resource
                    try:
                        self.driver.create_paths(schedule_entry)
                    except OSError as exp:
                        self.log.exception(exp)

                    success = self.load_files_in_target(schedule_entry)
                    if not success:
                        self.log.error(
                            "Unable to load files into the VM: %s", schedule_entry
                        )

                        # Ignoring a failure typically will happen by a helper
                        # (e.g. push file) where we don't want the VM resource
                        # handler to exit on failure
                        if not schedule_entry.ignore_failure:
                            self.set_state("FAILED")
                            sys.exit(1)

                    if not schedule_entry.executable:
                        # No executable means that we're done
                        # once the data is loaded into the VM
                        continue

                    # Handle negative time vm_resources by kicking them off
                    # immediately
                    if schedule_entry.start_time < 0:
                        args = {"schedule_entry": schedule_entry, "queue": reboot_queue}
                        # rate limit by some small random time
                        time.sleep(
                            self.load_balance_factor
                            * random.SystemRandom().randint(1, 5)
                        )
                        thread = Thread(target=self.run_vm_resource, kwargs=args)
                        # Keep track of negative time vm_resource threads
                        threads.append(thread)
                        # Start the vm_resource
                        thread.start()

                    elif schedule_entry.start_time > 0:
                        if not self.experiment_start_time:
                            self.log.error(
                                "Processing positive time vm_resource "
                                "but no experiment start time!"
                            )
                            continue

                        # Determine when to fire the timer
                        runtime = self.experiment_start_time + timedelta(
                            seconds=schedule_entry.start_time
                        )

                        curtime = datetime.now(timezone.utc)
                        delay = (runtime - curtime).total_seconds()
                        start_seconds = (
                            self.experiment_start_time - curtime
                        ).total_seconds()

                        self.log.debug(
                            "Experiment will start in %s seconds", start_seconds
                        )
                        self.log.debug(
                            "The `ScheduleEntry` '%s' with start time %s will start in %s seconds",
                            schedule_entry.executable,
                            schedule_entry.start_time,
                            delay,
                        )

                        # Set a timer to kick off the vm_resource runner with
                        # the vm_resource
                        thread = Timer(
                            delay, self.run_vm_resource, args=(schedule_entry,)
                        )
                        # Positive time vm_resources don't get held onto since
                        # they can be long running
                        thread.start()

                elif event.get_type() == ScheduleEventType.TRANSFER:
                    schedule_entry = event.get_data()
                    data = schedule_entry.data
                    if schedule_entry.start_time < 0:
                        for entry in data:
                            entry["name"] = self.config["vm_name"]
                            thread = Thread(target=self.transfer_data, kwargs=entry)
                            thread.start()
                    else:
                        if not self.experiment_start_time:
                            self.log.error(
                                "Processing positive time file transfer "
                                "but no experiment start time!"
                            )
                            continue

                        # Determine when to fire the timer
                        runtime = self.experiment_start_time + timedelta(
                            seconds=schedule_entry.start_time
                        )

                        curtime = datetime.now(timezone.utc)
                        delay = (runtime - curtime).total_seconds()
                        start_seconds = (
                            self.experiment_start_time - curtime
                        ).total_seconds()

                        self.log.debug(
                            "Experiment will start in %s seconds", start_seconds
                        )
                        self.log.debug(
                            "Transfer of `%s` with start time %s will start in %s seconds.",
                            schedule_entry.executable,
                            schedule_entry.start_time,
                            delay,
                        )

                        for entry in data:
                            entry["name"] = self.config["vm_name"]
                            # Set a timer to kick off the transfer
                            thread = Timer(delay, self.transfer_data, kwargs=entry)
                            thread.start()
                elif event.get_type() == ScheduleEventType.EXIT:
                    self.stop(event.get_data())

            # Wait for all threads to finish
            for thread in threads:
                thread.join()

            # Check for reboot requests before moving on
            # Don't need to lock on reboot_queue since all threads have
            # finished by this point.
            if not reboot_queue.empty():
                self.log.debug("Reboot has been requested")
                self.reboot()
                # Do need to lock on the main priority queue of events
                self.condition.acquire()
                while not reboot_queue.empty():
                    schedule_entry = reboot_queue.get()
                    self.log.debug(
                        "Putting vm_resource back in event queue: %s",
                        schedule_entry.executable,
                    )
                    event = ScheduleEvent(ScheduleEventType.NEW_ITEM, schedule_entry)
                    # recycle vm_resource into the main processing queue
                    self.prior_q.put((schedule_entry.start_time, event))
                self.condition.release()

    def stop(self, exitcode):
        """
        Stop the vm resource handler. This is used for unit testing.

        Args:
            exitcode (int): exit code to use when exiting the program
        """
        self.schedule_updater.stop_thread()
        self.log.debug("Wait for join")
        self.schedule_updater.join()
        self.driver.close()
        self.log.debug("Exiting: %d", exitcode)
        sys.exit(exitcode)

    def run_vm_resource(self, schedule_entry, queue=None):
        """
        Wrapper around the logic of running an vm_resource.

        The new thread calls this wrapper, which can output errors to the
        log file. This gives a convenient way to pass information back to
        the user via the log (with few good alternatives).

        Args:
            schedule_entry (ScheduleEntry): ``ScheduleEntry`` object
                specifying the VM resource to run.
            queue (Queue): Queue to pass messages, specifically reboot
                requests, back to the main processing loop. Defaults to
                ``None``.
        """
        try:
            self._run_vm_resource(schedule_entry, queue)
        except Exception as exp:  # noqa: BLE001
            self.log.exception(exp)

    def _run_vm_resource(self, schedule_entry, queue=None):
        """
        Function to handle starting a VM resource.

        Args:
            schedule_entry (ScheduleEntry): ``ScheduleEntry`` object
                specifying the VM resource to run.
            queue (Queue): Queue to pass messages, specifically reboot
                requests, back to the main processing loop. Defaults to
                ``None``.
        """

        if not hasattr(schedule_entry, "reboot"):
            schedule_entry.reboot = False

        # Create the call arguments script in the VM
        if not schedule_entry.reboot:
            try:
                preload = schedule_entry.preloaded
            except AttributeError:
                preload = False

            if not schedule_entry.data and not preload:
                # If there isn't data then the CWD hasn't been
                # created inside the VM, so create them here
                self.log.info("FILES NOT PRELOADED, CREATING DIRS")
                ret_value = self.driver.create_directories(
                    str(schedule_entry.working_dir)
                )
                while not ret_value:
                    self.log.error(
                        "Unable to create directories to write call arguments"
                    )
                    self.connect_to_driver()
                    ret_value = self.driver.create_directories(
                        str(schedule_entry.working_dir)
                    )

            ret_value = False
            while not ret_value and not preload:
                self.log.info("FILES NOT PRELOADED, WRITING CALL ARGS")
                ret_value = self.driver.create_directories(
                    str(schedule_entry.working_dir)
                )
                ret_value = self.driver.write(
                    str(schedule_entry.call_args_filename),
                    schedule_entry.call_arguments,
                )
                if not ret_value:
                    self.log.error("WRITE FAILED WHEN WRITING CALL ARGS")
                    time.sleep(self.load_balance_factor * 1)

            if not preload:
                self.driver.make_file_executable(str(schedule_entry.call_args_filename))

        elif schedule_entry.reboot:
            # Clear the reboot flag
            schedule_entry.reboot = False
            # Delete the reboot file
            while True:
                ret = self.driver.delete_file(str(schedule_entry.reboot_file))
                if ret is True:
                    break

                if ret is False:
                    self.log.error("Unable to delete reboot file")
                    self.connect_to_driver()

        # Call the call_arguments file to execute the vm_resource
        while True:
            start = time.time()
            self.log.info("CALL ARGS: %s", schedule_entry.call_args_filename)
            pid = self.driver.async_exec(str(schedule_entry.call_args_filename))
            self.log.info("PID returned: %s", pid)
            if not pid:
                self.log.info("No PID, resetting driver")
                self.connect_to_driver()
                continue

            # Wait for the VM resource to finish
            try:
                exitcode = self.driver.get_exitcode(pid)
                while exitcode is None:
                    # Print streaming output while the command is running
                    self.print_output(schedule_entry, pid)
                    time.sleep(self.load_balance_factor * 2)
                    exitcode = self.driver.get_exitcode(pid)
            # Retry on errors and timeouts (`TimeoutError` is a subclass of `OSError`)
            # - NOTE: Python 3.11 aliases `asyncio.TimeoutError` to `TimeoutError` which
            #   will eventually make the second check redundant
            except (OSError, asyncio.TimeoutError):
                self.log.error(
                    "FAILED: Unable to get exitcode of running process; retry command"
                )
                self.connect_to_driver()
                continue

            end = time.time()
            if exitcode != 0:
                self.log.warning(
                    "%s (%s) exited after %05f seconds with code: %s",
                    schedule_entry.executable,
                    pid,
                    end - start,
                    exitcode,
                )
            else:
                self.log.debug(
                    "%s (%s) exited after %05f seconds with code: %s",
                    schedule_entry.executable,
                    pid,
                    end - start,
                    exitcode,
                )

            if "powershell" in schedule_entry.executable.lower() and (end - start) < 2:
                self.log.error(
                    "Powershell took less than two seconds, this is most likely"
                    " an error, retrying"
                )
                time.sleep(self.load_balance_factor * 5)
                continue

            # Handle stdout and stderr
            self.print_output(schedule_entry, pid)
            break

        # Determine if a reboot is required
        need_reboot = None
        if exitcode == 10:
            self.log.info("Rebooting based on exit code")
            need_reboot = True
        else:
            need_reboot = self.check_for_reboot(str(schedule_entry.reboot_file))
        # Execute the reboot if required
        if need_reboot:
            schedule_entry.reboot = True
            if not queue:
                self.log.error(
                    "Can not handle reboots since the Queue"
                    " was not passed to the vm_resource runner"
                )
                return
            queue.put(schedule_entry)

    def check_for_reboot(self, reboot_filepath):
        """
        Check if the reboot file exists and a reboot is needed.

        Args:
            reboot_filepath (str): The path to the reboot file on the VM.

        Returns:
            bool: True if the reboot file exists and a reboot is required,
            otherwise False.
        """
        need_reboot = self.driver.file_exists(reboot_filepath)
        while need_reboot is None:
            self.log.error("Unable to check existence of the reboot file")
            self.connect_to_driver()
            time.sleep(self.load_balance_factor * 1)
            need_reboot = self.driver.file_exists(reboot_filepath)
        return need_reboot

    def transfer_data(self, name, location, interval=None, destination=None):
        """
        Transfer data from the VM to the physical host based on the input
        parameters.

        Args:
            name (str): The name of file to transfer.
            location (str): The full absolute path of where the file is located
                            on the VM.
            interval (int): How often to transfer the data in seconds.
            destination (str): The full, absolute path of where to put the file
                               on the physical host.
        """

        try:
            self._transfer_data(name, location, interval, destination)
        except Exception as exp:  # noqa: BLE001
            self.log.exception(exp)

    def _transfer_data(self, name, location, interval=None, destination=None):
        """
        The helper function which transfers data from the VM to the physical host
        based on the input parameters.

        Args:
            name (str): The name of file to transfer.
            location (str): The full absolute path of where the file is located
                            on the VM.
            interval (int): How often to transfer the data in seconds.
            destination (str): The full, absolute path of where to put the file
                               on the physical host.

        Raises:
            RuntimeError: If the transfer path is not absolute.
            RuntimeError: If it is unable to list files at the location.
        """
        if destination is not None:
            destination = Path(destination)
            local_path = Path(destination) / name
        else:
            destination = Path(global_config["logging"]["root_dir"])
            local_path = Path(destination / "transfers" / name)
        local_time = None

        if "Windows" in self.target_os:
            target_path = PureWindowsPath(location)
            if not target_path.is_absolute() and not Path(location).is_absolute():
                raise RuntimeError(
                    f"Transfer paths must be absolute! Cannot transfer: {location}"
                )
        else:
            target_path = Path(location)
            if not target_path.is_absolute():
                raise RuntimeError(
                    f"Transfer paths must be absolute! Cannot transfer: {location}"
                )

        while True:
            result = self.driver.file_exists(str(target_path))
            if result is None:
                if not interval or not isinstance(interval, int):
                    return
                # An error occurred, reconnect to driver and try again
                self.log.debug(
                    "An error occurred checking if the file=%s exists."
                    "Reconnecting to the driver, sleeping for %s seconds, and retrying.",
                    str(target_path),
                    interval,
                )
                self.connect_to_driver()
                time.sleep(interval)
                continue

            self.log.debug("The file '%s' exists: %s", target_path, result)

            if result is False:
                if not interval or not isinstance(interval, int):
                    return
                self.log.debug(
                    "The file=%s was not found, sleeping for %s seconds and retrying.",
                    str(target_path),
                    interval,
                )
                time.sleep(interval)
                continue

            # Get eligible file names
            filenames = self.driver.get_files(str(target_path), local_time)
            if filenames is None:
                raise RuntimeError(f"Unable to list files at location: {target_path}")

            self.log.debug("Found the following filenames for transfer: %s", filenames)
            if filenames:
                self.log.debug("Getting files: %s", filenames)

            for filename in filenames:
                if "Windows" in self.target_os:
                    # Make a legitimate posix path using the windows path
                    fname = Path(local_path) / PureWindowsPath(filename).as_posix()
                else:
                    fname = Path(local_path) / filename.strip("/")
                # Only pull files if they've changed
                success = self.driver.read_file(filename, fname)
                if not success or not fname.exists():
                    continue
                # Set permissions on all the directories and files that
                # have been pulled from the VM so the user doesn't have
                # to be root to read them
                touched = fname
                while str(touched) != "/":
                    if touched.is_dir():
                        self.log.debug("Changing permissions for '%s' to 777.", touched)
                        touched.chmod(0o777)
                    else:
                        self.log.debug("Changing permissions for '%s' to 666.", touched)
                        touched.chmod(0o666)
                    if touched.parent == destination:
                        self.log.debug("Finished changing permissions")
                        break
                    touched = touched.parent

            if not interval or not isinstance(interval, int):
                return

            # Update the local VM time to only grab
            # updated files next time
            local_time = self.driver.get_time()
            self.log.debug(
                "New local_time is %s -- pausing for %d seconds before next file transfer",
                str(datetime.fromtimestamp(local_time)),
                int(interval),
            )
            time.sleep(interval)

    def log_json(self, content):
        """
        Print any JSON line in vm_resource output to the json log.

        Args:
            content (str or dict): Buffer from agent output.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        # Handle content that is already a dictionary, i.e. from the handler
        if isinstance(content, dict):
            content["timestamp"] = timestamp
            try:
                # Only log a line if it is a JSON object.
                self.json_log.info(json.dumps(content))
            except TypeError:
                self.log.debug("Could not parse '%s' into JSON formatting.", content)
        else:
            try:
                # Buffer can contain multiple lines of output.
                split_lines = [s.strip() for s in content.splitlines()]
            except AttributeError:
                return
            for line in split_lines:
                # Only log a line if it can be decoded
                try:
                    data = json.loads(line.decode())
                except (json.JSONDecodeError, TypeError):
                    try:
                        # Convert decoded line into a dict
                        data = {"msg": line.decode()}
                    except TypeError:
                        return
                data["timestamp"] = timestamp
                self.json_log.info(json.dumps(data))

    def print_output(self, schedule_entry, pid):
        """
        Print any output from an vm_resource to the log.

        Args:
            schedule_entry (ScheduleEntry): ``ScheduleEntry`` object specifying
                the VM resource to run.
            pid (int): The PID of the VM resource process within the VM.
        """
        output = {}
        output["name"] = schedule_entry.executable
        output["pid"] = pid
        # Print stdout output
        try:
            stdout = self.driver.get_stdout(pid)
        except OSError:
            stdout = None
        if stdout:
            self._print_stream(output, stdout, "stdout")
        # Print stderr output
        try:
            stderr = self.driver.get_stderr(pid)
        except OSError:
            stderr = None
        if stderr:
            self._print_stream(output, stderr, "stderr")

    def _print_stream(self, output, stream, stream_name):
        stream_text = stream.encode(sys.getdefaultencoding())
        output["fd"] = stream_name
        output["output"] = rf"{stream_text}"
        self.log.info(output["output"])
        self.log_json(stream_text)

    def preload_files(self):
        """
        This method loads all VM Resources into the VM before the schedule
        is executed. This minimizes the number of after-boot disk alterations.
        This is particularly important for Windows VMs as, in our experience,
        Windows does not appear to appreciate having files modified or created
        on disk immediately after a reboot.
        """

        temp_q = Queue()
        self.condition.acquire()

        if self.prior_q.empty():
            self.condition.wait()

        while not self.prior_q.empty():
            start_time, event = self.prior_q.get()

            if event.get_type() == ScheduleEventType.NEW_ITEM:
                schedule_entry = event.get_data()
                try:
                    self.driver.create_paths(schedule_entry)
                except socket.timeout:
                    self.log.warning(
                        "There was a timeout when loading in a schedule entry. "
                        "Will reset the connection to the driver and try again. "
                        "The `ScheduleEntry` was %s",
                        event.get_data(),
                    )
                    self.connect_to_driver()
                    self.prior_q.put((start_time, event))
                    continue
                except OSError as exp:
                    self.log.error(
                        "There was an error when loading in a schedule entry. "
                        "The `ScheduleEntry` was %s",
                        event.get_data(),
                    )
                    self.log.exception(exp)

                try:
                    self.load_files_in_target(schedule_entry)
                except socket.timeout:
                    self.log.warning(
                        "There was a timeout when loading in a schedule entry. "
                        "Will reset the connection to the driver and try again. "
                        "The `ScheduleEntry` was %s",
                        event.get_data(),
                    )
                    self.connect_to_driver()
                    self.prior_q.put((start_time, event))
                    continue

                if schedule_entry.executable:
                    # Handle preloading the call arguments if this SE
                    # is meant to be executed
                    if not schedule_entry.data:
                        # If there isn't data then the CWD hasn't been
                        # created inside the VM, so create them here
                        self.log.info("creating directory since no file data")
                        ret_value = self.driver.create_directories(
                            str(schedule_entry.working_dir)
                        )
                        while not ret_value:
                            self.log.error(
                                "Unable to create directories to write call arguments"
                            )
                            time.sleep(self.load_balance_factor * 2)
                            ret_value = self.driver.create_directories(
                                str(schedule_entry.working_dir)
                            )
                        self.log.info("done creating directory")

                    ret_value = False
                    while not ret_value:
                        ret_value = self.driver.write(
                            str(schedule_entry.call_args_filename),
                            schedule_entry.call_arguments,
                        )
                        if not ret_value:
                            self.log.error("WRITE FAILED WHEN WRITING CALL ARGS")
                            self.connect_to_driver()

                    ret_value = False
                    while not ret_value:
                        try:
                            ret_value = self.driver.make_file_executable(
                                str(schedule_entry.call_args_filename)
                            )
                        except OSError:
                            ret_value = False
                            self.connect_to_driver()

                schedule_entry.preloaded = True

            temp_q.put((start_time, event))

        # Reload the event queue
        while not temp_q.empty():
            start_time, event = temp_q.get()
            self.prior_q.put((start_time, event))

        self.condition.release()
        self.log.info("Done preloading files")

    def get_events(self):
        """
        Get all eligible events from the priority queue.

        Returns:
            list (ScheduleEvent): List of events that are ready to be processed.
        """
        events = []
        time_updated = False

        # Grab the lock since this function modifies the queue
        self.condition.acquire()

        # If there isn't anything in the schedule, then just wait
        # until something shows up
        if self.prior_q.empty():
            # If the schedule is all negative time vm_resources then when the
            # schedule is empty, the VM is configured
            if self.current_time < 0 and self.current_time > self.initial_time:
                self.current_time = 0
                self.set_current_time(self.current_time)
                self.set_state("configured")

            self.log.debug("Event queue is empty, WAITING")
            self.condition.wait()

        # Work through eligible events
        while not self.prior_q.empty():
            # Get event off the queue
            start_time, event = self.prior_q.get()

            # EXPERIMENT_START_TIME and EMPTY_SCHEDULE events always
            # get processed immediately and shouldn't update current time
            if (
                event.get_type() == ScheduleEventType.EXPERIMENT_START_TIME_SET
                or event.get_type() == ScheduleEventType.EMPTY_SCHEDULE
            ):
                events.append(event)
                continue

            if not time_updated and start_time > self.current_time:
                self.current_time = start_time
                time_updated = True
                self.set_current_time(self.current_time)

            if start_time > self.current_time:
                # Event's start time is past the current time
                # so break and return eligible events
                self.log.debug(
                    "Putting event back: %s, current time: %s",
                    start_time,
                    self.current_time,
                )
                self.prior_q.put((start_time, event))
                break

            # Wait for experiment start time before passing on
            # positive time events
            if start_time > 0 and not self.experiment_start_time:
                self.log.debug("WAITING FOR START TIME")
                # Put the event back since we can't process it yet
                self.prior_q.put((start_time, event))

                # All negative time vm_resources have been handled
                self.set_state("configured")
                self.current_time = 0
                self.set_current_time(self.current_time)

                # This will force a sleep until notified by the ScheduleUpdater
                # that a new event has been enqueued
                self.condition.wait()
                continue

            # If positive time, then return all events in the queue
            if self.current_time > 0:
                events.append(event)
                continue

            # If all checks passed, then time to process this event
            time_updated = True
            events.append(event)

        # Release the lock
        self.condition.release()
        return events

    def load_files_in_target(self, schedule_entry):
        """
        Copy the vm_resource file to the VM's local cache so that it is available
        when the vm_resource gets called.

        Args:
            schedule_entry (ScheduleEntry): The schedule entry to be copied into the VM.

        Returns:
            bool: Success or failure of loading files into the VM.
        """
        if not schedule_entry.data:
            return True

        with contextlib.suppress(AttributeError):
            if schedule_entry.reboot is True:
                return True

        with contextlib.suppress(AttributeError):
            if schedule_entry.preloaded:
                return True

        try:
            while True:
                try:
                    ret_value = self.driver.create_directories(
                        str(schedule_entry.working_dir)
                    )
                    if ret_value:
                        break
                except OSError as exp:
                    self.log.error("There was an issue creating directories: %s", exp)

                self.log.error(
                    "Unable to create directories while loading files into VM"
                )
                self.connect_to_driver()
                ret_value = self.driver.create_directories(
                    str(schedule_entry.working_dir)
                )
        except AttributeError:
            self.log.info("Not creating working directory")

        for data in schedule_entry.data:
            # Check if this file needs to be placed in a relative path
            # or an absolute path in the VM. If we do not have the right
            # key, we shouldn't load anything into the VM.
            try:
                target_path = Path(data["location"])
            except KeyError:
                self.log.warning(
                    "Processed event %s that may not have the right keys", data
                )
                continue

            if not target_path.is_absolute():
                if not schedule_entry.executable:
                    self.log.error(
                        "Files require absolute paths unless they are "
                        "for an vm_resource"
                    )
                    return False

                target_path = schedule_entry.working_dir / target_path

            if data.get("filename"):
                attempts = 1
                local_path = None
                while attempts < 10:
                    try:
                        local_path = Path(
                            self.vm_resource_store.get_path(data["filename"])
                        )
                        if not local_path:
                            self.log.error("Unable to get file: %s", data["filename"])
                            attempts += 1
                            time.sleep(self.load_balance_factor * 2)
                        # If there were no errors then the file was successfully cached
                        else:
                            break
                    except (FileNotFoundError, RuntimeError) as exp:
                        self.log.exception(exp)
                        self.log.error("Unable to get file: %s", data["filename"])
                        attempts += 1
                        time.sleep(self.load_balance_factor * 2)

                if not local_path:
                    self.log.error(
                        "Attempted 10 times to get file: %s", data["filename"]
                    )
                    return False

                attempts = 1
                while attempts < 10:
                    try:
                        if not self.driver.file_exists(str(target_path)):
                            self.log.debug(
                                "Writing file from: %s to %s", local_path, target_path
                            )
                            ret_value = False
                            while not ret_value:
                                ret_value = self.driver.write_from_file(
                                    str(target_path), str(local_path)
                                )
                                if not ret_value:
                                    self.log.error("UNABLE TO WRITE FILE")
                        else:
                            break
                    except OSError:
                        self.log.error(
                            "Unable to connect to the driver, reconnecting and trying again."
                        )
                        attempts += 1
                        time.sleep(self.load_balance_factor * 2)
                        self.connect_to_driver()
                else:
                    return False

                # Make the executable file executable on machines that aren't windows
                if "executable" in data:
                    self.driver.make_file_executable(str(target_path))

            elif "content" in data and isinstance(data["content"], str):
                if not self.driver.file_exists(str(target_path)):
                    # Check that the parent directories exist
                    if not self.driver.file_exists(str(target_path.parent)):
                        success = self.driver.create_directories(
                            str(target_path.parent)
                        )
                        if not success:
                            self.log.error(
                                "Unable to create directory: %s", target_path.parent
                            )
                            return False

                    # File does not exist so write it
                    if "Windows" in self.target_os:
                        # Change newlines to windows newlines
                        data["content"].replace("\n", "\r\n")

                    self.log.debug("Writing content to %s", target_path)
                    ret_value = False
                    while not ret_value:
                        ret_value = self.driver.write(str(target_path), data["content"])
                        if not ret_value:
                            self.log.error("UNABLE TO WRITE CONTENT")

                    if "executable" in data:
                        self.driver.make_file_executable(str(target_path))
            else:
                self.log.error("Data entry for schedule entry is not a file or content")
                self.log.error(schedule_entry)
                return False

        return True

    def reboot(self):
        """
        Reboot the VM. Function doesn't return until the driver can communicate
        with the VM again.
        """

        self.log.debug("Rebooting")
        try:
            self.driver.reboot()
        except Exception as exp:  # noqa: BLE001
            self.log.exception(exp)

            # We now need to sleep a variable amount of time (25 - 45 seconds) after
            sleep_time = self.load_balance_factor * random.SystemRandom().randint(
                25, 45
            )
            # guest agent reconnects to a Windows VM too soon after being asked to
            time.sleep(sleep_time)
        if "Windows" in self.target_os:
            sleep_time = self.load_balance_factor * random.SystemRandom().randint(
                25, 45
            )
            self.log.info("Windows sleep: %s seconds", sleep_time)
            time.sleep(sleep_time)

        self.connect_to_driver()

    def import_driver(self):
        """
        Walk through all the available drivers and find the one that
        matches the type of VM that has been booted.

        Returns:
            object: The driver class that matches the VM's type
        """
        drivers = self._import_drivers()
        if not drivers:
            self.log.error(
                "Unable to find driver to communicate with VM: %s",
                self.config["vm_name"],
            )
            # If there is no driver then we can't talk to the VM.
            # Nothing left to do so exit
            sys.exit(1)

        # Walk the drivers looking for the one that has an engine
        # that matches the config's type (i.e. QemuVM)
        for driver in drivers:
            if driver.get_engine() == self.config["engine"]:
                return driver

        self.log.error(
            "Unable to find driver for type: %s for VM: %s",
            self.config["engine"],
            self.config["vm_name"],
        )
        # No driver found. Can't communicate with the VM so exit.
        sys.exit(1)

    def _import_drivers(self):
        """
        Import available drivers from the driver directory.

        Walk the drivers directory looking for all available drivers that
        can talk to a booted VM. A qualifying driver must be a subclass of
        the abstract driver class, implementing all required methods of
        the driver interface.

        Returns:
            set: A set of available driver classes.
        """
        drivers = set()
        for module_path in self.driver_directory.rglob("*.py"):
            spec = importlib.util.spec_from_file_location(
                module_path.name, str(module_path)
            )
            if spec:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except (FileNotFoundError, SyntaxError):
                    self.log.debug("Could not load module '%s'. Continuing", module)
                for _, driver_cls in inspect.getmembers(module, self._check_driver):
                    drivers.add(driver_cls)
        return drivers

    @staticmethod
    def _check_driver(obj):
        if inspect.isclass(obj):
            return issubclass(obj, AbstractDriver) and not inspect.isabstract(obj)
        return False

    def set_state(self, state):
        """
        Tell the infrastructure the state of the VM.
        If the state is 'configured', then check to see
        if this VM is the last VM to be configured. If it
        is the last VM to be configured, then set the
        experiment start time.

        Args:
            state (str): State of the VM
        """
        if self.state == state:
            return
        try:
            self.log.debug("SETTING STATE: %s", state)
            utils.set_vm_state(
                self.config["vm_uuid"], state, mapping=self.vm_mapping, log=self.log
            )
            self.state = state
        except RuntimeError as exp:
            self.log.error("Error setting VM state. Can not set state to: %s", state)
            self.log.exception(exp)

        # Check to see if the experiment start time can be set
        if state == "configured":
            if self.experiment_start_time:
                return
            not_ready_count = utils.get_vm_count_not_ready(
                mapping=self.vm_mapping, log=self.log
            )
            # All VMs are configured, so set the start time.
            if not_ready_count == 0:
                # Set the experiment start time
                try:
                    self.log.debug("SETTING EXPERIMENT START TIME")
                    api.add_experiment_start_time()
                except Exception as exp:  # noqa: BLE001
                    self.log.error("Unable to set the start time")
                    self.log.exception(exp)

    def set_current_time(self, cur_time):
        """
        Tell the infrastructure the current configuration time of the VM.

        Args:
            cur_time (int): Current VM schedule time
        """
        try:
            utils.set_vm_time(
                self.config["vm_uuid"], cur_time, mapping=self.vm_mapping, log=self.log
            )
        except Exception:  # noqa: BLE001
            self.log.error("Error setting VM state. Can not set state to: %s", cur_time)


# ---------------------------------- __main__ ----------------------------------

if __name__ == "__main__":
    # Get the vm config off the command line
    vm_config = sys.argv[1]
    vm_config = json.loads(vm_config)

    resource_handler = VMResourceHandler(vm_config)
    resource_handler.run()
