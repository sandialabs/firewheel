"""
Subsystem for the storage and retrieval of vm_resource schedules.
"""

import json
import base64

from firewheel.lib.log import Log
from firewheel.lib.utilities import retry
from firewheel.lib.minimega.file_store import FileStore


class ScheduleDbTimeoutError(Exception):
    """An exception for general time outs."""


retry_exception = retry(30, (ScheduleDbTimeoutError,))


def _build_schedule_document(server_name, text, vm_resources_ip):
    """
    Build the stored schedule document for a VM.

    Args:
        server_name (str): The name of the VM to assign this schedule to.
        text (bytes): The schedule payload.
        vm_resources_ip (str): The IP of the VM.

    Returns:
        dict: JSON-serializable schedule document.
    """
    return {
        "server_name": server_name,
        "text": base64.b64encode(text).decode(),
        "ip": vm_resources_ip,
    }


def _decode_schedule_document(document):
    """
    Decode a stored schedule document.

    Args:
        document (dict): Stored schedule document loaded from JSON.

    Returns:
        dict: A copy of the document with the schedule payload decoded to bytes.
    """
    decoded_document = dict(document)
    decoded_document["text"] = base64.b64decode(decoded_document["text"])
    return decoded_document


class ScheduleDb:
    """
    Class to represent the experiment schedule database. This is currently
    backed by a minimega store, but the interface should remain general
    enough that this could change without modifying users of this class.
    """

    @retry_exception
    def __init__(self, cache_name="schedules", log=None):
        """
        Initialize the ScheduleDb.

        All arguments are present only for unit testing and may be safely
        ignored.

        Args:
            cache_name (str): Override the default minimega cache dir.
            log (firewheel.lib.log.Log): Override the default FIREWHEEL log.

        Raises:
            RuntimeError: If there is an invalid value for FileStore connections.
        """
        if log is None:
            self.log = Log(name="ScheduleDb").log
        else:
            self.log = log

        try:
            self.cache = FileStore(cache_name, log=self.log)
        except Exception as exp:
            self.log.exception("FileStore connection failed.")
            raise RuntimeError(
                f"Invalid value for FileStore connection. Details: {exp}"
            ) from exp

    @retry_exception
    def close(self):
        """
        Close the ScheduleDb. Currently, this is unused.
        """

    @retry_exception
    def list_all(self, pattern=None):
        """
        Retrieve the schedule for a particular VM.

        Args:
            pattern (str): The pattern to match filenames against.

        Returns:
            list: List of matching schedule dictionaries on success.

        Raises:
            Exception: If minimega has an error.
        """
        matches = self.cache.list_distinct_contents(pattern)
        schedules = []
        for match in matches:
            schedule_path = self.cache.get_path(match)
            try:
                with open(schedule_path, "r", encoding="utf8") as f_name:
                    schedules.append(_decode_schedule_document(json.load(f_name)))
            except Exception as exp:
                self.log.exception(exp)
                raise exp
        return schedules

    @retry_exception
    def get(self, server_name):
        """
        Retrieve the schedule for a particular VM.

        Args:
            server_name (str): The name of the VM to retrieve the schedule for.

        Returns:
            str: The decoded schedule as a string on success, None if there is no
            entry for the specified VM.

        Raises:
            Exception: If minimega has an error.
        """
        try:
            schedule_path = self.cache.get_path(server_name)
        except FileNotFoundError:
            return None
        try:
            with open(schedule_path, "r", encoding="utf8") as f_name:
                schedule = _decode_schedule_document(json.load(f_name))
                return schedule["text"]
        except Exception as exp:
            self.log.exception(exp)
            raise exp
        return None

    @retry_exception
    def put(self, server_name, text, vm_resources_ip, broadcast=True):
        """
        Add a schedule entry for a particular VM.

        Args:
            server_name (str): The name of the VM to assign this schedule to.
            text (str): The schedule to assign to the VM.
            vm_resources_ip (str): The IP of the VM.
            broadcast (bool): Whether to have all nodes update their cache to include the new files.

        Raises:
            Exception: If minimega has an error.
        """
        try:
            document = _build_schedule_document(server_name, text, vm_resources_ip)
            self.cache.add_file_from_content(
                json.dumps(document), server_name, broadcast=broadcast
            )
        except Exception as exp:
            raise exp

    @retry_exception
    def batch_put(self, sched_list, broadcast=False):
        """
        Add a schedule entry for a particular VM.

        Args:
            sched_list (list): List of `{'server_name': <value>, 'text': <value>}`
            broadcast (bool): Whether to have all nodes update their cache to include the new files.
        """
        for sched in sched_list:
            self.put(
                sched["server_name"], sched["text"], sched["ip"], broadcast=broadcast
            )

    @retry_exception
    def destroy_one(self, server_name):
        """
        Remove the schedule for a particular VM.

        Args:
            server_name (str): The name of the VM whose schedule will be removed.
        """
        self.log.debug("Entering schedule_db to remove: %s", server_name)
        self.cache.remove_file(server_name)
        self.log.debug("Successfully deleted schedule for VM %s", server_name)

    @retry_exception
    def destroy_all(self):
        """
        Remove the schedule for a particular VM.
        """
        self.log.debug("Entering schedule_db to remove all schedules")
        self.cache.remove_file("*")
        self.log.debug("Successfully deleted schedules")
