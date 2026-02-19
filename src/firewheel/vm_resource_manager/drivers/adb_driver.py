import json
import time
import base64

import adbutils

from firewheel.vm_resource_manager.abstract_driver import AbstractDriver

EXIT_MAGIC = "ExitCode="


class ADBDriver(AbstractDriver):
    """
    Driver class for the Android Debug Bridge (ADB). This class can communicate
    with an emulated Android device via ADB.
    """
    def __init__(self, config, log):
        """Initialize the ADB driver.

        Args:
            config (dict): Configuration containing adb_port and other information.
            log (logging.Logger): Logger instance for emitting debug/info messages.
        """
        log.info("Config = %s", config)
        self.console_port = config["adb_port"]
        self.adb_name = f"emulator-{self.console_port}"
        self.adb_client = adbutils.AdbClient()
        self.adb_device = self.adb_client.device(self.adb_name)
        self._is_rooted = False
        super().__init__(config, log)

    def _wait_for_device_online(self):
        """Wait until the device responds to ping.

        Continuously calls :py:meth:`ping` until it returns ``True`` indicating the
        Android device is online. Sleeps briefly between attempts.
        """
        sleep_time = 1
        while not self.ping():
            self.log.debug("Waiting for device to come online")
            time.sleep(sleep_time)

    def _remount_system(self):
        """Remount the /system partition as writable.

        Ensures the device is online, then checks if the /system partition is already
        writable. If not, attempts to remount it, reboot the device, and repeat the
        process to guarantee the partition is writable.
        """
        self._wait_for_device_online()

        returncode = self.adb_device.shell2("test -w /system").returncode
        if returncode == 0:
            # it was already writable
            return

        def _remount():
            num_attempts = 10
            for _ in range(num_attempts):
                try:
                    self.adb_device.adb_output("remount")
                    break
                except Exception as exc:
                    self.log.exception(exc)
            else:
                raise RuntimeError("Error remounting /system as writable")

        _remount()
        self.reboot()
        self._wait_for_device_online()
        self._root()
        self._wait_for_device_online()
        _remount()
        self._wait_for_device_online()

    def _root(self):
        """Obtain root access on the Android device.

        Acquires a thread-safe lock before invoking ``adb root`` on the device.
        Sets the internal ``_is_rooted`` flag to ``True`` on success.
        """
        with self.lock:
            self.adb_device.root()
        self._is_rooted = True

    def _symlink_bash(self):
        """Create a symbolic link ``/bin/bash`` → ``/bin/sh`` on the device.

        The link is created under a thread-safe lock so that concurrent callers
        do not race the underlying ``adb shell`` command.
        """
        with self.lock:
            self.adb_device.shell("ln -s /bin/sh /bin/bash")

    def connect(self):
        """Establish a connection to the Android device.

        Ensures the device is online, obtains root access if necessary, remounts the
        system partition, and creates a ``bash`` symlink. The method acquires a lock
        for thread-safety and returns ``1`` on success.
        """
        with self.lock:
            self._wait_for_device_online()

            self.log.debug("Getting root access on device")
            if not self._is_rooted:
                self._root()

                self._wait_for_device_online()

                # Also, we need to remount /system as writable
                self._remount_system()

                # And, for now, let's symlink bash to sh
                # It may get overwritten by the model component if the user
                # wants to use bash features
                self._symlink_bash()

        return 1

    def close(self):
        """Close the driver connection.

        This method fulfills the abstract ``close`` contract but currently does
        not perform any cleanup because the underlying resources are managed
        elsewhere.
        """
        return

    def ping(self, timeout=10):
        """
        Ping the Android device via ADB to ensure it is reachable.

        Args:
            timeout (int): Number of seconds to wait for the ADB command.

        Returns:
            bool: True if the device responds, False otherwise.
        """
        _timeout = timeout # unused variable

        try:
            # "adb get-state" returns "device" when the emulator/device is online
            with self.lock:
                result = self.adb_device.get_state()
            online = result.strip() == "device"

            if not online:
                return False

            # as an extra check, try to run a very simple shell command
            with self.lock:
                self.adb_device.shell("true")

            return True
        except adbutils.errors.AdbError:
            # Any ADB exception indicates the device is not reachable
            return False

    def sync(self):
        """Synchronize the driver state.

        Currently a placeholder that returns ``1``. In future this could ensure the
        driver is in a consistent state after connection changes.
        """
        return 1

    @staticmethod
    def get_engine():
        """
        Get the virtualization engine that this driver supports.

        Returns:
            str: The name of the virtualization engine that this driver supports.
            Currently this is only 'AVD'.
        """

        return "AVD"

    def get_time(self):
        """
        Get the current time from the Android device via ADB.
        Returns the time in seconds (float) since the epoch.
        """
        # Use the shell command to get epoch seconds on the device.
        # Android's date supports +%s which returns seconds since epoch.
        with self.lock:
            output = self.adb_device.shell("date +%s")
        # The output may contain newline characters; strip them.
        secs_str = output.strip()
        secs = int(secs_str)
        # Return as float seconds for consistency with other drivers.
        return float(secs)

    def set_time(self):
        """Set the VM time to the host's current time.

        Computes the current host time in nanoseconds and sends a ``date -s``
        command to the device. This helps keep the VM clock synchronized.
        """
        cur_time_nano = int(time.time() * 1e9)
        with self.lock:
            self.adb_device.shell(f"date -s {cur_time_nano}")

    def reboot(self):
        """Reboot the Android device.

        Clears the internal ``_is_rooted`` flag and invokes ``adb reboot`` via the
        ADB client. The operation is performed inside a thread-safe lock.
        """
        with self.lock:
            self._is_rooted = False
            self.adb_device.reboot()

    def file_flush(self):
        """Flush a file to disk inside the guest VM.

        This is a placeholder implementation that raises ``NotImplementedError``.
        Subclasses should provide the actual logic to ensure data is flushed to
        persistent storage on the VM.
        """
        raise NotImplementedError

    def network_get_interfaces(self):
        """Retrieve network interface information from the Android device.

        Executes ``ip -j address`` via ADB and parses the JSON output to return a
        Python data structure describing each network interface.
        """
        with self.lock:
            return json.loads(self.adb_device.shell("ip -j address"))

    def set_user_password(self, username, password):
        """
        Sets a user's password. This is not yet implemented for Android and is
        not needed at this time.

        Args:
            username (str): The user account that will have its password changed.
            password (str): A new password for the user account.

        Raises:
            NotImplementedError: This functionality is not yet needed
        """
        raise NotImplementedError

    def _get_pid_from_stream(self, stream):
        """Read the PID from an ADB output stream.

        The ADB ``shell`` command used in :py:meth:`execute` returns a stream where
        the first line contains the PID followed by a newline. This method reads
        bytes from the stream until a newline character is encountered, restores
        the original blocking mode of the underlying socket, converts the
        collected characters to an integer PID, and returns it. If conversion fails
        ``None`` is returned.
        """
        # We want this phase to be a blocking read
        old_blocking_status = stream.conn.getblocking()
        stream.conn.setblocking(True)

        pid_str = ""
        while True:
            char = stream.read(1).decode("utf-8")
            if char == "\n":
                break
            pid_str += char
        stream.conn.setblocking(old_blocking_status)

        try:
            pid = int(pid_str)
            return pid
        except ValueError:
            return None

    def execute(self, path, arg=None, env=None, input_data=None, capture_output=True):
        """Run a program inside the Android VM.

        Constructs a command line, optionally prefixes it with input data, and
        executes the command via ``adb shell`` in the background. The method
        returns the PID of the spawned process and stores the output stream for
        later retrieval via :py:meth:`exec_status`.
        """
        _capture_output = capture_output # unused variable

        full_cmd = ""

        if input_data is not None:
            full_cmd += f"printf '{input_data}' | "

        if env is not None:
            for env_var in env:
                full_cmd += env_var
                full_cmd += " "

        if isinstance(arg, (list, tuple)):
            arg = adbutils._utils.list2cmdline(arg)
        if arg is None:
            arg = ""

        full_cmd += path
        full_cmd += " "
        full_cmd += arg

        # make it run in the background and echo the PID so we can save it
        full_cmd += f' & pid=$!; echo $pid; wait $pid; echo "{EXIT_MAGIC}$?"'

        with self.lock:
            output_stream = self.adb_device.shell(full_cmd, stream=True)

        # Get and return the PID
        pid = self._get_pid_from_stream(output_stream)

        self.output_cache[pid] = {"stream": output_stream}

        return pid

    def async_exec(
        self, path, arg=None, env=None, input_data=None, capture_output=True
    ):
        """Convenience wrapper for asynchronous execution.

        Delegates to :py:meth:`execute` to run the command asynchronously and
        returns the same PID value.
        """
        return self.execute(path, arg, env, input_data, capture_output)

    def _is_pid_alive(self, pid):
        """Check whether a given PID is still running inside the VM.

        Executes ``kill -0 <pid>`` via ADB; a zero return code indicates the
        process exists, otherwise it is considered terminated.
        """
        returncode = self.adb_device.shell2(f"kill -0 {pid}").returncode
        if returncode == 0:
            return True
        return False

    def exec_status(self, pid):
        """Retrieve execution status and output for a PID.

        Reads any pending stdout from the stored output stream, determines whether
        the process has exited using :py:meth:`_is_pid_alive`, and, if the process
        is finished, extracts the exit code from the ``ExitCode=`` marker that the
        ``execute`` method appends to the command output. The method updates the
        ``self.output_cache[pid]`` dictionary with keys ``exited`` (bool),
        ``exitcode`` (int, when known), and ``stdout`` (captured output). The
        populated dictionary is returned.
        """
        stream = self.output_cache[pid]["stream"]

        exited = not self._is_pid_alive(pid)

        # We want this read to be non-blocking
        old_blocking_status = stream.conn.getblocking()
        stream.conn.setblocking(False)
        stdout = ""
        try:
            while True:
                byte = stream.read(1)
                if byte == b"":
                    break
                char = byte.decode("utf-8")
                stdout += char
        except BlockingIOError:
            # no more data to read
            pass

        stream.conn.setblocking(old_blocking_status)

        self.log.debug("process stdout: ****%s****", stdout)
        self.log.debug(self.output_cache[pid])

        # check if process has finished
        self.output_cache[pid]["exited"] = exited

        self.output_cache[pid].setdefault("stdout", "")
        stdout = self.output_cache[pid]["stdout"] + stdout
        if "exitcode" in self.output_cache[pid]:
            pass

        elif exited:
            # look for the "ExitCode=..." string in the output for exit code reporting
            idx = stdout.rfind(EXIT_MAGIC)
            exit_code_str = stdout[idx + len(EXIT_MAGIC) :]
            exit_code = int(exit_code_str)
            self.output_cache[pid]["exitcode"] = exit_code
            self.output_cache[pid]["stdout"] = stdout[:idx]

        else:
            self.output_cache[pid]["stdout"] = stdout

        self.log.info("exec_status of %s: %s", pid, self.output_cache[pid])
        return self.output_cache[pid]

    def store_captured_output(self, pid, output):
        """
        Store output from a VM program.

        Hold on to output that has been returned from a program
        that was run inside the VM via the ``exec`` method.

        Args:
            pid (int): The PID for the process that produced the output.
            output (str): The processed returned output to be cached.

        Raises:
            NotImplementedError: This does not seem to be needed yet and should
            be implemented if/when it is needed
        """

        raise NotImplementedError

    def _write(self, filename, data, mode="w"):
        """
        Write the provided data at the provided filename within the guest VM.

        Args:
            filename (str): name of the file to open for writing.
            data (str): String of content to write to the file.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        Raises:
            ValueError: if a file mode other than "w" or "a" are provided
        """
        if mode == "w":
            redirect = ">"
        elif mode == "a":
            redirect = ">>"
        else:
            raise ValueError("Unsupported file mode")

        maybe_b64 = ""
        if isinstance(data, bytes):
            data = base64.b64encode(data).decode("utf-8")
            maybe_b64 = " | base64 -d "

        with self.lock:
            self.adb_device.shell2(
                f"echo -n '{data}' {maybe_b64} {redirect} {filename}"
            )

        return True

    def read_file(self, filename, local_destination, mode="rb"):
        """
        Read a file from a VM and put it onto the physical host.

        Args:
            filename (str): The file to read from inside the VM. This should be
                the full path.
            local_destination (pathlib.PurePosixPath): The path on the physical host
                where the file should be read to.
            mode (str): The mode of reading the file. Defaults to ``'rb'``.
        """
        _mode = mode # unused variable

        with self.lock:
            self.adb_device.sync.pull_file(filename, local_destination)

    def write_from_file(self, filename, local_filename, mode="w"):
        """
        Given a local filename, use ``adb push`` to push that file into the
        guest VM at the location specified by ``filename``.

        Args:
            filename (str): The name of the file to open for writing.
            local_filename (str): Filename of the file containing data to
                send to the VM.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        """
        _mode = mode # unused variable
        self.adb_device.sync.push(local_filename, filename)
        return True

    def get_os(self):
        """
        Get the Operating System details for the VM. Return the "pretty" name
        """
        if self.target_os:
            return self.target_os

        cmd = 'echo "'
        cmd += "$(getprop ro.product.brand) "
        cmd += "Android "
        cmd += "$(getprop ro.build.version.release) "
        cmd += "($(getprop ro.product.model))"
        cmd += '"'

        num_attempts = 10
        for _attempt in range(num_attempts):
            with self.lock:
                try:
                    self.target_os = self.adb_device.shell(cmd)
                    break
                except Exception as exc:
                    self.log.exception(exc)
                    time.sleep(1)
        return self.target_os
