import time
import threading
from abc import ABC, abstractmethod
from pathlib import Path, PureWindowsPath
from datetime import datetime


class AbstractDriver(ABC):
    """
    An abstract driver class for communicating with all in-VM agents that work
    with FIREWHEEL. All driver-specific implementation is left to subclasses.
    """

    _EXEC_ERROR_MSG = "`execute` returned `None` indicating an error has occurred."

    def __init__(self, config, log):
        """
        An abstract driver class for communicating with all in-VM agents that work
        with FIREWHEEL. All driver-specific implementation is left to subclasses.

        Attributes:
            log (Logger): Logger for output
            driver (object): Object for speaking QMP
                over the serial port to the QGA process in the VM
            lock (threading.Condition): Only one connection to the serial port
                is allowed, therefore access to the port needs to be
                thread safe.
            target_os (str): The operating system of the VM.
            used_agent_paths (str): Agents need a unique directory
                to hold their relevant files. This keeps track of
                paths that have already been used.
            output_cache (dict): The output cache is a cache of
                all output resulting from calling programs within
                a VM. This data lives as long as the process runs.
                It allows streaming output from an agent to be collected
                and agent output to be requested multiple times if needed.
                The output cache has the following format:

                .. code-block:: text

                    {
                        <pid>: {
                            'exited': True or False,
                            'exitcode': <integer status code>,
                            'signal': <Optional: signal or unhandled exception code>,
                            'stdout': <Optional: output from stdout>,
                            'stdout_trunc': <Optional: True if stdout was truncated>,
                            'stderr': <Optional: output from stderr>,
                            'stderr_trunc': <Optional: True if stder was truncated>
                        }
                    }

                The output cache is cleared on system reboot.

        Args:
            config (dict): vm config which is used to find the
                Virtio serial port socket that the guest agent uses
                to communicate to the VM with.
            log (logging.Logger): A logger which can be used by this class.

        Raises:
            FileNotFoundError: If no path was given to the QGA serial device.
        """
        self.log = log
        self.config = config
        if not config.get("path"):
            raise FileNotFoundError("Was not given path to QGA serial device")

        self.lock = threading.Condition()

        sync = self.connect()
        while sync is None:
            time.sleep(2)
            sync = self.connect()

        self.log.info("SYNCED: %s", sync)

        # Determine the target OS of the VM
        self.target_os = None
        self.used_agent_paths = set()
        self.output_cache = None
        self._reset_cache()

    def _reset_cache(self):
        self.output_cache = {}

    @abstractmethod
    def connect(self):
        """
        This method sets up the driver connection with the agent within the VM so
        that they can communicate. It then should call :py:meth:`sync`. The return
        value of this method is typically a random synchronization token used in
        the sync request/response exchange.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def close(self):
        """
        Close the connection to the socket used for agent.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def ping(self, timeout=10):
        """
        Check if connection to the in-VM agent was successful.

        Args:
            timeout (int): The time in seconds until the socket times out.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def sync(self, timeout=5):
        """
        Synchronize the buffer for the agent. This method should return a random
        synchronization token used in the sync request/response

        Args:
            timeout (int): Socket timeout in seconds. Defaults to 5.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_engine():
        """
        Get the virtualization engine that this driver supports.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def get_time(self):
        """
        Get the time inside the VM in nanoseconds since the epoch.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def set_time(self):
        """
        Set the time in the VM to the current host time.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def reboot(self):
        """
        Reboot the VM.
        """
        self._reset_cache()

    @abstractmethod
    def file_flush(self, handle):
        """
        Flush a file to disk inside the guest VM

        Args:
            handle (File): file handle returned from `guest-file-open`.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def network_get_interfaces(self):
        """
        Gets a list of network interface info. This is typically returned as a list
        of JSON objects.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def set_user_password(self, username, password):
        """
        Sets a user's password.

        Args:
            username (str): The user account that will have its password changed.
            password (str): A new password for the user account.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    @abstractmethod
    def execute(self, path, arg=None, env=None, input_data=None, capture_output=True):
        """
        Run a program inside the guest VM. This should return process's PID on
        success or :py:data:`None` on failure.

        Args:
            path (str): Path or executable name to execute.
            arg (str): Argument list to pass to executable. Must
                be a list or string. Defaults to None.
            env (list): Environment variables to pass to executable.
                List of "<key>=<value>" strings. Defaults to None.
            input_data (str): Data to be passed to process stdin. Defaults to
                ``None``.
            capture_output (bool): Flag to enable capture of stdout/stderr.
                Defaults to True.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def exec_status(self, pid):
        """
        Get the status of a program that was run. It should return a dictionary with
        the exit code and other information about the status (STDOUT, STDERR, etc.)

        Args:
            pid (int): The PID that for the process that was returned from `guest-exec-status`.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def store_captured_output(self, pid, output):
        """
        Store output from a VM program.

        Hold on to output that has been returned from a program
        that was run inside the VM via the ``exec`` method.

        Args:
            pid (int): The PID for the process that produced the output.
            output (str): The processed returned output to be cached.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    def get_stdout(self, pid):
        """
        Query for the standard output of a process run via ``exec_status``.

        Args:
            pid (int): The process PID for the desired output.

        Returns:
            str: The `stdout` buffer if available, otherwise ``None``.
        """
        return self._get_stream("stdout", pid)

    def get_stderr(self, pid):
        """
        Query for the standard error of a process run via ``exec_status``.

        Args:
            pid (int): The process PID for the desired output.

        Returns:
            str: The `stderr` buffer if available, otherwise ``None``.
        """
        return self._get_stream("stderr", pid)

    def _get_stream(self, stream_name, pid):
        """
        Set a set of information from a given stream (stdout, stderr, etc.).

        Arguments:
            stream_name (str): The name of the stream.
            pid (int): The process ID for the stream.

        Returns:
            str: Get the information from the given stream (stdout, stderr, etc.)
        """
        # Query for a process output stream via `exec_status`
        cache = self.exec_status(pid)
        # Get the stream (e.g., stdout, stderr) from the cache
        stream = cache.get(stream_name)
        if stream:
            cache[stream_name] = ""
            return stream
        return None

    def get_exitcode(self, pid):
        """
        Query for the exit code of a process run via ``exec_status``.

        Args:
            pid (int): The process PID to query for an exit code.

        Returns:
            int: The exit code if the process has exited and it is known,
            otherwise ``None``.
        """
        cache = self.exec_status(pid)
        return cache.get("exitcode") if cache.get("exited") else None

    def wait_for_exitcode(self, pid, interval=1):
        """
        Repeatedly query for the exit code of a process run via `exec_status`.

        Args:
            pid (int): The process PID to query for an exit code.
            interval (int): The time (in seconds) to wait between queries.
                The default is to wait for one second.

        Returns:
            int: The exit code if the process has exited.
        """
        exitcode = self.get_exitcode(pid)
        while exitcode is None:
            time.sleep(interval)
            exitcode = self.get_exitcode(pid)
        return exitcode

    def evaluate_process_success(self, pid, interval=1):
        """
        Wait for a process to complete, and return a success indicator.

        Args:
            pid (int): The process PID to query for an exit code.
            interval (int): The time (in seconds) to wait between queries.
                The default is to wait for one second.

        Returns:
            bool: `True` if the process was successful (exit code 0), otherwise
                `False`.
        """
        try:
            exitcode = self.wait_for_exitcode(pid, interval)
        except OSError:
            # An error means that the process was not successful
            return False
        else:
            return exitcode == 0

    def append(self, filename, content):
        """
        Append to a file within the guest VM.

        Args:
            filename (str): name of the file to open for writing on the VM.
            content (str): String of content to write to the file.

        Returns:
            bool: True or False indicating success.
        """

        return self.write(filename, content, "a")

    def write(self, filename, data, mode="w"):
        """
        Write the provided data at the provided filename within the guest VM.

        This will also create required directories in the filename's path.

        Args:
            filename (str): name of the file to open for writing.
            data (str): String of content to write to the file.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        Returns:
            bool: True or False indicating success.
        """

        return self._write(filename, data, mode)

    @abstractmethod
    def _write(self, filename, data, mode="w"):
        """
        Write the provided data at the provided filename within the guest VM.

        Args:
            filename (str): name of the file to open for writing.
            data (str): String of content to write to the file.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    def _delete_parent_directories(self, directory):
        """
        Delete the directory and any (empty) parent directories.

        Recursively delete the given directory and all parent directories
        until encountering a directory that is not empty.

        Args:
            directory (PurePosixPath): The directory to remove. Parent
                directories of this directory will also be deleted if
                otherwise empty.
        """
        try:
            directory.rmdir()
            self._delete_parent_directories(directory.parent)
        except OSError:
            # OSError means that the directory isn't empty
            # so stop walking up the dir structure
            return

    @abstractmethod
    def read_file(self, filename, local_destination, mode="rb"):
        """
        Read a file from a VM and put it onto the physical host.

        Args:
            filename (str): The file to read from inside the VM. This should be
                the full path.
            local_destination (pathlib.PurePosixPath): The path on the physical host
                where the file should be read to.
            mode (str): The mode of reading the file. Defaults to ``'rb'``.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def write_from_file(self, filename, local_filename, mode="w"):
        """
        Given a local filename, open that file to read its data and write
        that data to a location (provided in filename) in the guest VM.

        Args:
            filename (str): The name of the file to open for writing.
            local_filename (str): Filename of the file containing data to
                send to the VM.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    def create_directories(self, directory):
        """
        The guest agent does not allow interacting with a new file if the
        file's path does not exist. Therefore, this function creates the
        path for a file if it does not exist.

        Args:
            directory (str): The absolute path for a directory.

        Returns:
            bool: True or False indicating success.
            A value of ``None`` means that the execution
            attempt (performed on the VM) failed.
        """

        self.log.info("Creating directory: %s", directory)
        try:
            if "Windows" in self.target_os:
                win_path = directory.replace("/", "\\")
                pid = self.execute(
                    path="cmd", arg=f"/c if not exist {win_path} md {win_path}"
                )
            else:
                pid = self.execute(
                    path="/bin/bash",
                    arg=["-c", f"[ -d {directory} ] || mkdir -p {directory}"],
                )
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.exception(exp)
            return False

        if pid is None:
            self.log.error(self._EXEC_ERROR_MSG)
            return None

        success = self.evaluate_process_success(pid, interval=2)
        return success

    @abstractmethod
    def get_os(self):
        """
        Get the Operating System details for the VM. It should return the "pretty"
        name for the OS.

        Raises:
            NotImplementedError: This should be implemented by a subclass.
        """

        raise NotImplementedError

    def connected(self, timeout=10):  # noqa: DOC502
        """
        Check that the driver is currently connected to the guest agent inside the VM.

        Args:
            timeout (int): Timeout in seconds to wait for a response from the VM.

        Returns:
            dict: Empty dictionary on success, throws an exception on timeout.

        Raises:
            Exception: Happens on timeout.
        """

        # Must lock here since ping is used in startup syncing which
        # does not allow it to lock since the lock isn't created at that point
        with self.lock:
            result = self.ping(timeout)
        return result

    def delete_file(self, path):
        """
        Delete a file inside the VM.

        Args:
            path (str): Absolute path of the file to be deleted.

        Returns:
            bool: True or False indicating success.
            A value of ``None`` means that the execution
            attempt (performed on the VM) failed.
        """

        pid = None
        if "Windows" in self.get_os():
            argument = (
                f"/c if exist {PureWindowsPath(path)} del /q {PureWindowsPath(path)}"
            )
            pid = self.execute(path="cmd", arg=argument)
        else:
            pid = self.execute(path="/bin/bash", arg=["-c", f"rm -rf {path}"])

        if pid is None:
            self.log.error(self._EXEC_ERROR_MSG)
            return None

        success = self.evaluate_process_success(pid, interval=2)
        if success:
            return True

        try:
            stderr = self.get_stderr(pid)
        except OSError:
            pass
        else:
            self.log.error(stderr.encode("UTF-8"))
        return False

    def file_exists(self, path):
        """
        Check if a file exists inside the VM.
        If a user used a shell-globbing wildcard (e.g. ``*``) in the path
        (and shell-globbing is supported by the VM) then this function only checks to
        see if **at least one** file matching the wildcard exists.

        Args:
            path (str): Absolute path for the file to be checked.

        Returns:
            bool: Indicates existence of the file inside the VM.
            A value of ``None`` means that the execution
            attempt (performed on the VM) failed.
        """

        self.log.debug("Checking if %s exists", path)
        if "Windows" in self.get_os():
            argument = f"/c if exist {PureWindowsPath(path)} echo True"
            pid = self.execute(path="cmd", arg=argument)
        else:
            # If a user added a wildcard to the path, we should check to see if
            # at least one file exists: https://stackoverflow.com/a/14765676
            argument = str(
                f"for i in {path}; "
                'do test -e "$i" && echo True && break || echo False && break; '
                "done"
            )
            pid = self.execute(path="/bin/bash", arg=["-c", argument])

        if pid is None:
            self.log.error(self._EXEC_ERROR_MSG)
            return None

        success = self.evaluate_process_success(pid)
        if success:
            try:
                stdout = self.get_stdout(pid)
            except OSError:
                stdout = None
            return bool(stdout and "True" in stdout)

        return False

    def get_files(self, path, timestamp=None):
        """
        Get all filenames at a specified path.

        Args:
            path (str): Absolute path for the file/directory to be walked.
            timestamp (str): A date that can be used to compare against the file.
                This function will find files with a modification time newer than
                the one passed in.

        Returns:
            list: A list of filenames at the specified location or ``None``
            if an error occurs.
        """

        if timestamp:
            dtime = datetime.utcfromtimestamp(timestamp)
            tstamp = f"'{dtime:%m/%d/%Y %H:%M:%S UTC}'"

        if "Windows" in self.get_os():
            argument = f"dir /s /b {PureWindowsPath(path)}"

            pid = self.execute(path="cmd", arg=["/c", argument])
        else:
            argument = f"find {path} -type f"
            if timestamp:
                argument += f" -newermt {tstamp}"
            pid = self.execute(path="/bin/bash", arg=["-c", argument])

        if pid is None:
            self.log.error(self._EXEC_ERROR_MSG)
            return None

        success = self.evaluate_process_success(pid)
        if success:
            try:
                stdout = self.get_stdout(pid)
            except OSError:
                stdout = None
            # Collect filenames (one per non-empty line if stdout exists)
            filenames = filter(None, stdout.split("\n")) if stdout else ()
            # Exclude swap files from returned filenames
            return [name.strip() for name in filenames if not name.endswith("swp")]

        try:
            stderr = self.get_stderr(pid)
        except OSError:
            pass
        else:
            self.log.error(stderr.encode("UTF-8"))
        return None

    def make_file_executable(self, path):
        """
        If the guest VM is not a Windows VM then set the executable flag
        for the file at the provided path.

        Args:
            path (str): Path in guest VM to file to be set executable.

        Returns:
            bool: :py:data:`True` or :py:data:`False` indicating success.
            A value of :py:data:`None` means that the execution
            attempt (performed on the VM) failed.
        """

        # Can't make files executable in Windows
        if "Windows" in self.get_os():
            return True

        pid = self.execute(
            path="/bin/bash",
            arg=["-c", f"chmod +x {path} && echo True || echo False"],
        )

        if pid is None:
            self.log.error(self._EXEC_ERROR_MSG)
            return None

        success = self.evaluate_process_success(pid)
        if success:
            try:
                stdout = self.get_stdout(pid)
            except OSError:
                stdout = None
            return bool(stdout and "True" in stdout)

        return False

    def create_paths(self, schedule_entry):
        """
        Since the paths that need to be created are dependent
        on what the driver accepts (i.e. QGA doesn't want C:
        to be prepended on Windows paths, but the agent needs the
        path to the reboot file, which will need the drive letter
        prepended to the path) it is the driver's job to determine
        the paths for the agent.

        Args:
            schedule_entry (ScheduleEntry): The schedule_entry object.
        """

        if not schedule_entry.executable:
            # If there isn't an executable then this entry
            # is just dropping data and doesn't support
            # relative paths for data
            return

        try:
            schedule_entry.working_dir  # noqa: B018
            # If this already exists then it doesn't need to be calculated again
            return
        except AttributeError:
            pass

        call_arguments = ""
        if "Windows" in self.get_os():
            base = Path("/launch")
        elif "Android" in self.get_os():
            base = Path("/data/var/launch")
        else:
            base = Path("/var/launch")

        executable = Path(schedule_entry.executable)

        schedule_entry.working_dir = self.deconflict_agent_path(
            base / str(schedule_entry.start_time) / executable.name
        )

        if executable.is_absolute():
            schedule_entry.exec_path = executable
        else:
            # Check if the executable was loaded by the schedule entry
            local = False
            if schedule_entry.data:
                for entry in schedule_entry.data:
                    if (
                        "filename" in entry
                        and entry["filename"] == schedule_entry.executable
                    ):
                        local = True
                        break
            if local:
                # If the executable is being loaded in, then the abs path
                # can be created
                schedule_entry.exec_path = schedule_entry.working_dir / executable
            else:
                # The executable is not being loaded in and it was not provided
                # as an absolute path so the executable must be on the machine's path
                schedule_entry.exec_path = executable

        schedule_entry.reboot_file = schedule_entry.working_dir / "reboot"

        if "Windows" in self.get_os():
            schedule_entry.call_args_filename = (
                schedule_entry.working_dir / "call_arguments.bat"
            )
        else:
            schedule_entry.call_args_filename = (
                schedule_entry.working_dir / "call_arguments.sh"
            )

        if "Windows" in self.get_os():
            call_arguments = str(
                f"@echo off\r\npushd {PureWindowsPath(schedule_entry.working_dir)}\r\n"
            )
            call_arguments += str(PureWindowsPath(schedule_entry.exec_path))
        else:
            call_arguments = str(
                "#!/bin/bash\n"
                'CURRENT_DIR="$(dirname "$0")"\n'
                f"cd {schedule_entry.working_dir}\n"
            )
            call_arguments += f"{schedule_entry.exec_path!s}"

        # If there are arguments, then append them to the path to the executable
        if schedule_entry.arguments:
            call_arguments += f" {schedule_entry.arguments}"

        if "Windows" in self.get_os():
            call_arguments += "\r\nexit /B %ERRORLEVEL%\r\n"
        else:
            call_arguments += "\n"

        schedule_entry.call_arguments = call_arguments

    def deconflict_agent_path(self, path):
        """
        Create unique path names for agents.

        Args:
            path (str): Desired path name.

        Returns:
            Path: A :py:class:`pathlib.Path` object which is unique.
        """

        while path in self.used_agent_paths:
            path_str = str(path)
            num = None
            try:
                num = path_str[path_str.rindex("_") + 1 :]
            except ValueError:
                num = None

            if num:
                try:
                    num = int(num)
                except ValueError:
                    num = None

            if not num:
                num = 0
            else:
                # Get the base of the path name
                path_str = path_str[: path_str.rindex("_")]

            path = Path(f"{path_str}_{num + 1}")

        self.used_agent_paths.add(path)
        return path
