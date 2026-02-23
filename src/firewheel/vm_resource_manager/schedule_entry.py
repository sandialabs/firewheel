import sys


class ScheduleEntry:
    """
    This class is the base class for all types of schedule entries.
    It is in this class that all necessary instance variables are declared.
    It is important that all variables within the :py:class:`base_objects.ScheduleEntry`
    be instance variables, as opposed to class variables. This is because a VM's schedule
    (i.e. :py:class:`base_objects.VmResourceSchedule`, which contains a list of
    :py:class:`base_objects.ScheduleEntry` objects) is serialized via :py:mod:`pickle` and
    passed to the :ref:`vm-resource-handler`.
    Only instance variables get preserved through the :py:mod:`pickle` process.

    Schedule entries have a set of general instance variables.
    The type of schedule entry determines which variables are required.
    The only variable that all ScheduleEntries require is ``start_time``.
    This class is not intended to be used directly, but through its
    subclasses.
    """

    def __init__(self, start_time, ignore_failure=False):
        """
        Create a new ScheduleEntry

        Attributes:
            start_time (int): Relative time to handle the VM resource. (See :ref:`start-time`
                for more details).
            ignore_failure (bool): Whether or not to let the VM resource handler
                exit if this entry fails.
            executable (str): Name of the executable to run.
            arguments (str):  Arguments to pass to the executable.
            pause(bool): Whether or not this entry is a pause entry.
            on_host(bool): Whether or not this entry is to be run on the host.
            data (list(dict)): List of dictionaries specifying required files: ::

                Paths can be either absolute or relative to the VMR.

                Dictionary to drop specified content on VM
                {
                    "location": <string>, # Path on VM to place content
                    "content":  <string>, # Content to be placed at location
                    "executable": <bool>  # Optionally set file's executable flag
                }

                Dictionary to load a file into the VM
                {
                    "location": <string>, # Path on VM to place file
                    "filename": <string>, # Name of file to be loaded on the VM
                    "executable": <bool>  # Optionally set file's executable flag
                }

        Args:
            start_time (int): VM resource scheduled start time
            ignore_failure (bool): Whether or not to let the VM resource
                handler exit if this entry fails.

        Raises:
            ValueError: If a start time of 0 is provided.
        """

        if start_time == 0:
            raise ValueError("VM resources cannot start at time zero.")
        self.start_time = start_time
        self.ignore_failure = ignore_failure
        self.data = []
        self.pause = None
        self.executable = None
        self.arguments = ""
        self.on_host = False

    def set_executable(self, path, arguments=None, on_host=False):
        """
        Specify the name of a program to run within the VM.

        Args:
            path (str): Path inside the VM to the program to be run.
            arguments (str or list, optional): Arguments to pass on the command line
                to the program. Defaults to None.
            on_host (bool, optional): Whether or not the executable is to be run
                on the host. Defaults to :py:data:`False`.

        Raises:
            RuntimeError: If the executable name is not a string.
        """

        if not isinstance(path, str):
            raise RuntimeError("Executable name must be a string")

        self.executable = path
        self.on_host = on_host

        if arguments:
            self.append_arguments(arguments)

    def append_arguments(self, arguments):
        """
        Append an argument to be passed on the command line to the executable

        Args:
            arguments (str or list): A space-separated string or list of strings
                of arguments to be passed on the command line to the executable.

        Raises:
            TypeError: If the arguments an not in a valid format.
        """

        if isinstance(arguments, list):
            for arg in arguments:
                if not isinstance(arg, str):
                    raise TypeError(
                        "Arguments to an executable must be a string"
                        "or a list of strings"
                    )
            if self.arguments:
                self.arguments += " "
            self.arguments += " ".join(arguments)
        elif isinstance(arguments, str):
            if self.arguments:
                self.arguments += " "
            self.arguments += arguments
        else:
            raise TypeError(
                "Arguments to an executable must be a string or a list of strings"
            )

    def add_content(self, location, content, executable=False):
        """
        Add a block of content to be loaded into the VM at the specified location.

        Args:
            location (str): Path inside the VM to write the provided content,
                including filename. This path can be absolute or relative to the VM resource.
            content (str): Content to be written or a callback function that will
                return a string.
            executable (bool, optional): Set the new file's executable
                flag. Defaults to False.
        """

        self.data = getattr(self, "data", [])

        entry = {"location": location, "content": content, "executable": executable}

        self.data.append(entry)

    def add_file(self, location, filename, executable=False):
        """
        Drop a file on the VM at the specified location. This file
        needs to be available to FIREWHEEL. This only happens when the files
        are included in the list of "vm_resources" that are specified in a model
        component's ``MANIFEST`` file.

        Args:
            location (str): Path inside the VM to write the file, including filename
                This path can be absolute or relative to the VM resource.
            filename (str): Name of file in the vm_resource's database to be written.
            executable (bool, optional): Boolean for setting the new file's executable flag.
                Defaults to False.
        """

        self.data = getattr(self, "data", [])

        entry = {"location": location, "filename": filename, "executable": executable}

        self.data.append(entry)

    def add_file_transfer(self, location, interval=30, destination=None):
        """
        Specifies that a file or directory needs to be monitored and pulled
        off the VM.

        Note:
            If specifying a destination, the FIREWHEEL group (if any) must have
            permissions to modify and write to that directory. See the
            :ref:`config-system` configuration options to add FIREWHEEL group permissions.

        Args:
            location (str): Path inside the VM to the file or directory
                to be monitored and pulled off the VM.
            interval (int, optional): Interval specifying how often to check for
                file or directory updates.
            destination (str, optional): Absolute path on compute node of the
                directory where transferred files are to be placed:
                ``<destination>/<vm_name>/<location>``. If no destination is provided,
                files will be written to ``<logging.root_dir>/transfers/``. See
                :py:meth:`_transfer_data <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler._transfer_data>`
                for more details.
        """  # noqa: E501, W505
        self.data = getattr(self, "data", [])

        entry = {"location": location, "interval": interval, "destination": destination}

        self.data.append(entry)

    def add_pause(self, duration):
        """
        Add data to the schedule entry that indicates that it should pause all
        following events. The duration (seconds) can be any positive number where a duration
        of :py:attr:`math.inf` indicates a *break* event which requires a resume to
        occur prior to advancing the schedule.

        Note:
            To ensure the exact ordering of events within a time-window (e.g.
            multiple events scheduled at the same time) the pause/break is
            technically added at the ``start_time + sys.float_info.min``.

        Args:
            duration (float): The duration (seconds) of the pause where :py:attr:`math.inf` is an
                *break* event.

        Raises:
            ValueError: If the ``duration`` is not positive.
        """

        self.data = getattr(self, "data", [])

        if duration < 0:
            raise ValueError("The `duration` must be positive!")

        self.start_time += sys.float_info.min

        entry = {"pause_duration": duration}
        self.pause = True

        self.data.append(entry)

    def __str__(self):
        """
        A custom string method for ScheduleEntry Objects.

        Returns:
            str: A string representation of a ScheduleEntry.
        """
        string = (
            f"{type(self)}(\n"
            f"\tstart_time={self.start_time},\n"
            f"\tignore_failure={self.ignore_failure},\n"
            f"\tpause={self.pause},\n"
            f"\ton_host={self.on_host},\n"
            f"\texecutable={self.executable},\n"
            f"\targuments={self.arguments},\n"
            f"\tdata={self.data}\n)"
        )
        return string
