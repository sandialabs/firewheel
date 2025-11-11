import sys
import time
import base64
import random
import asyncio
from contextlib import suppress

from qemu.qmp.legacy import QEMUMonitorProtocol
from qemu.qmp.protocol import StateError

from firewheel.vm_resource_manager.abstract_driver import AbstractDriver


class QemuGuestAgentDriver(AbstractDriver):
    """
    Driver class for the QEMU Guest Agent (QGA). This class
    can communicate to a QGA inside a VM via a serial port.
    """

    def __init__(self, config, log):
        """
        Args:
            config (dict): vm config which is used to find the
                Virtio serial port socket that the guest agent uses
                to communicate to the VM with.
            log (logging.Logger): A logger which can be used by this class.
        """
        self.qga = None
        super().__init__(config, log)

    def connect(self):
        """
        This method sets up the QMP connection with the QGA within the VM so
        that they can communicate. It then calls ``sync()``.

        Returns:
            int: A random synchronization token used in the guest-sync request/response
            exchange.

        Raises:
            OSError: If an error occurs while connecting to the QGA.
            OSError: If an error occurs while syncing.
        """

        self.log.debug("Connecting to QGA on socket: %s", self.config["path"])
        self.qga = QEMUMonitorProtocol(self.config["path"])

        try:
            self.qga.connect(negotiate=False)
            self.log.debug("Successfully connected to QGA socket")
        except OSError as exp:
            self.log.error("Error while connecting")
            self.log.exception(exp)
            raise exp

        try:
            sync_value = self.sync()
        except OSError as exp:
            self.log.error("Error while syncing")
            self.log.exception(exp)
            self.close()
            raise exp

        return sync_value

    def ping(self, timeout=10):
        """
        Use the guest-ping command to check if connection to the guest agent
        was successful.

        Args:
            timeout (int): The time in seconds until the socket times out.

        Returns:
            bool: Indicates if successfully connected to guest agent.
        """

        self.qga.settimeout(timeout)
        try:
            self.qga.cmd("guest-ping")
        except (TimeoutError, asyncio.TimeoutError):
            return False
        except StateError:
            with suppress(
                TimeoutError, asyncio.TimeoutError, OSError, ConnectionResetError
            ):
                self.qga.close()
            return False
        finally:
            self.qga.settimeout(None)

        return True

    def sync(self, timeout=5):
        """
        Use the guest-sync command to synchronize the buffer.

        This works by putting a marker into the buffer and then draining the buffer
        until the marker is returned. Once the marker has been returned, the buffer
        is then synchronized.

        Args:
            timeout (int): Socket timeout in seconds. Defaults to 5.

        Returns:
            int: A random synchronization token used in the guest-sync request/response
            exchange. If the sync fails, returns ``None``.

        Raises:
            EnvironmentError: When the QEMU Guest Agent not alive yet.
        """

        # Avoid being blocked forever
        if not self.ping(timeout):
            raise EnvironmentError("QEMU Guest Agent not alive yet")
        uid = random.SystemRandom().randint(0, (1 << 32) - 1)
        # No lock yet, so don't need to lock around this call
        try:
            return_value = self.qga.cmd("guest-sync", {"id": uid})["return"]

        # pylint: disable=broad-except
        except Exception:
            self.log.exception("An error happened in 'guest-sync'")
            return_value = None

        if return_value == uid:
            return return_value

        self.log.warning(
            "The expected return value of '%s' was not received. Instead got '%s'",
            uid,
            return_value,
        )
        return None

    @staticmethod
    def get_engine():
        """
        Get the virtualization engine that this driver supports.

        Returns:
            str: The name of the virtualization engine that this driver supports.
            Currently this is only 'QemuVM'.
        """

        return "QemuVM"

    def get_time(self):
        """
        Get the time inside the VM.

        Returns:
            int: Time in nanoseconds since the epoch.
        """

        # No need to wrap this call since qmp's command function
        # already does the error checking and throws an exception
        with self.lock:
            time_nano = self.qga.cmd("guest-get-time")["return"]
            self.log.debug("guest-get-time=%s", time_nano)
        time_sec = time_nano / 1e9
        return time_sec

    def set_time(self):
        """
        Set the time in the VM to the current host time.
        """

        # guest-set-time does not return anything
        # Error checking is done by qmp's command function
        # Time is supposed to be in nanosecond resolution
        # time.time() returns a float of seconds (to microsecond
        # precision) since epoch so move the decimal point over by 9 places
        with self.lock:
            cur_time_nano = int(time.time() * 1e9)
            self.qga.cmd("guest-set-time", {"time": cur_time_nano})

    def reboot(self):
        """
        Reboot the VM.
        """
        super().reboot()

        try:
            with self.lock:
                self.qga.settimeout(2)
                self.qga.cmd("guest-shutdown", {"mode": "reboot"})
                self.qga.settimeout(None)
        except (TimeoutError, asyncio.TimeoutError):
            # Shutdown does not return, therefore it's going to timeout
            with self.lock:
                self.qga.settimeout(None)

    def file_write_from_file(self, handle, filename):
        """
        Given a local filename, read the contents from that file and write
        them to the provided file handle. The file handle is a handle to an
        open file within the guest VM.

        Args:
            handle (File): file handle returned from guest-file-open.
            filename (str): Name of file to read content from and then send
                to the VM.

        Returns:
            bool: True on success, False on failure.

        Raises:
            RuntimeError: An error occurred.
            RuntimeError: The file write didn't have a byte count.
            RuntimeError: The returned size does not match the read size.
        """

        # Use a chunk size of 1 MB. While this value is not strictly necessary
        # performance testing has demonstrated that a value between 102400 and
        # 1024000 (100KB - 1MB) has significant performance advantages over values
        # outside of that range (including no value).
        chunk_size = 1024000  # 1Mb
        with open(filename, "rb") as fname:
            eof = False
            while not eof:
                # Read a chunk of data from the file
                content = fname.read(chunk_size)

                # Content is already a byte array, so pass straight into encoding
                b64_content = base64.b64encode(content).decode(encoding="UTF-8")
                attempt = 1
                max_attempts = 30
                while True:
                    try:
                        with self.lock:
                            self.qga.settimeout(10)
                            result = self.qga.cmd(
                                "guest-file-write",
                                {
                                    "handle": handle,
                                    "buf-b64": b64_content,
                                    "count": len(content),
                                },
                            )["return"]
                            self.qga.settimeout(None)
                        break
                    # pylint: disable=broad-except
                    except Exception as exp:
                        self.log.exception(exp)
                        with self.lock:
                            self.qga.settimeout(None)
                        if attempt >= max_attempts:
                            self.log.error("FILE WRITE WITH CHUNK FAILED: %s", filename)
                            return False
                        attempt += 1
                        return False

                # If error is in the dictionary returned then an error happened
                if "error" in result:
                    raise RuntimeError(f"File write: {result['error']['desc']}")

                # Make sure there is a byte count in the returned status
                if "count" not in result:
                    raise RuntimeError("File write: Return didn't have byte count.")

                # Make sure the returned written byte counts agrees with the amount
                # of data that was intended to be written
                if result["count"] != len(content):
                    self.qga.settimeout(None)
                    raise RuntimeError(
                        f"File write: Returned size of {result['count']} does not "
                        f"match read size of {len(content)}"
                    )

                # Check if the entire file has been written
                if len(content) < chunk_size:
                    eof = True

        return True

    def file_write_content(self, handle, content):
        """
        Given content (i.e. ASCII data), write the content to a file inside
        the VM. The given handle is a handle to an open file inside the
        guest VM.

        Args:
            handle (File): File handle returned from guest-file-open.
            content (str): Content to write to file handle.

        Returns:
            bool: True on success, False on failure.
        """

        b64_content = str(
            base64.b64encode(bytes(content, "utf-8")), sys.getdefaultencoding()
        )
        with self.lock:
            self.qga.settimeout(30)
            result = self.qga.cmd(
                "guest-file-write",
                {"handle": handle, "buf-b64": b64_content},
            )["return"]
            self.qga.settimeout(None)

        # If error is in the dictionary returned then an error happened
        if "error" in result:
            self.log.error(result["error"]["desc"])
            return False

        if "count" in result and result["count"] == len(content):
            return True

        self.log.error("Actual length and written length do not match!")
        return False

    def file_flush(self, handle):
        """
        Flush a file to disk inside the guest VM

        Args:
            handle (File): file handle returned from `guest-file-open`.
        """

        with self.lock:
            self.qga.cmd("guest-file-flush", {"handle": handle})

    def network_get_interfaces(self):
        """
        Gets a list of network interface info.

        Returns:
            list: List of GuestNetworkInfo JSON objects.
        """

        with self.lock:
            interfaces = self.qga.cmd("guest-network-get-interfaces")["return"]
            self.log.debug("guest-network-get-interfaces=%s", interfaces)
        return interfaces

    def set_user_password(self, username, password):
        """
        Sets a user's password.

        Args:
            username (str): The user account that will have its password changed.
            password (str): A new password for the user account.
        """

        b64_password = str(
            base64.b64encode(bytes(password, "utf-8")), sys.getdefaultencoding()
        )
        with self.lock:
            self.qga.cmd(
                "guest-set-user-password",
                {"username": username, "password": b64_password},
            )

    def execute(self, path, arg=None, env=None, input_data=None, capture_output=True):
        """
        Run a program inside the guest VM.

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

        Returns:
            int: The process's PID is returned on success or ``None`` on failure.
        """
        return self.async_exec(
            path, arg=arg, env=env, input_data=input_data, capture_output=capture_output
        )

    def _prep_async_exec(
        self, path, arg=None, env=None, input_data=None, capture_output=True
    ):
        """
        Run a program inside the guest VM.

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

        Returns:
            int: The process's PID is returned on success or ``None`` on failure.
        """

        options = {"path": path, "capture-output": capture_output}
        self.log.debug("Starting `async_exec` for: %s", options)

        # If the arg that was passed in is a list, then just put them in options
        if arg:
            # arg was a string, so split into a list
            if isinstance(arg, str):
                arg = [arg]
            elif not isinstance(arg, list):
                self.log.error("arg must be a string or a list")
                return None
            options["arg"] = arg

        if env:
            if not isinstance(env, list):
                self.log.error(
                    "env must be a list of key value pairs. "
                    'i.e. ["PATH=/bin","PYTHONPATH=/opt"]'
                )
                return False
            for e_key in env:
                if len(e_key.split("=")) != 2:
                    self.log.error(
                        'env key value pairs must be of the form "X=Y". '
                        'i.e. ["PATH=/bin","PYTHONPATH=/opt"]'
                    )
                    return None
            options["env"] = env

        if input_data:
            b64_input_data = str(
                base64.b64encode(bytes(input_data, "utf-8")), sys.getdefaultencoding()
            )
            options["input-data"] = b64_input_data
        return options

    def async_exec(
        self, path, arg=None, env=None, input_data=None, capture_output=True
    ):
        """
        Run a program inside the guest VM as an async process.

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

        Returns:
            int: The process's PID is returned on success or ``None`` on failure.
        """

        options = self._prep_async_exec(path, arg, env, input_data, capture_output)

        # Call the exec command
        try:
            with self.lock:
                result = self.qga.cmd("guest-exec", options)["return"]
        except OSError as exp:
            self.log.error("Unable to call guest-exec with options: %s", options)
            self.log.exception(exp)
            return None

        # If error is in the dictionary returned then an error happened
        if "error" in result:
            self.log.error(result["error"]["desc"])
            return None

        if "pid" in result:
            self.log.debug(
                'The PID for QGA command "guest-exec" with arguments %s is %s',
                options,
                result["pid"],
            )
            return result["pid"]

        self.log.warning(
            "Unknown result from QGA command 'guest-exec' with arguments '%s'."
            "No key 'pid': %s",
            options,
            result,
        )
        return None

    def exec_status(self, pid):
        """
        Get the status of a program that was run using guest-exec-status.

        Args:
            pid (int): The PID that for the process that was returned from `guest-exec-status`.

        Returns:
            dict: The dictionary with the exit code and other information
                returned from the `guest-exec-status` command.

        Raises:
            TimeoutError: If the QGA status check times out.
            OSError: If the QGA fails to execute the `guest-exec-status` command.
        """

        # Get the status of a process that was kicked off by `async_exec`
        self.log.debug("Checking status of PID: %s", pid)

        if pid in self.output_cache:
            # Check to see if the process output has already been handled.
            if "exited" in self.output_cache[pid] and self.output_cache[pid]["exited"]:
                return self.output_cache[pid]

        # Get the output (process has either not yet been queried or not yet exited)
        with self.lock:
            self.qga.settimeout(10)
            try:
                result = self.qga.cmd("guest-exec-status", {"pid": pid})["return"]
            except (TimeoutError, asyncio.TimeoutError) as exc:
                self.log.error(
                    "A timeout occurred when calling exec-status for PID: %s", pid
                )
                raise TimeoutError from exc
            except OSError as exc:
                self.log.error("Unable to call exec-status for PID: %s", pid)
                self.log.exception(exc)
                raise OSError from exc
            finally:
                self.qga.settimeout(None)

        # Hold on to the output for later retrieval
        self.store_captured_output(pid, result)
        return self.output_cache[pid]

    def store_captured_output(self, pid, output):
        """
        Store output from a VM program.

        Hold on to output that has been returned from a program
        that was run inside the VM via the ``async_exec`` method.

        Args:
            pid (int): The PID for the process that produced the output.
            output (str): The processed returned output to be cached.
        """

        # Add the PID to the cache if it isn't already there
        if pid not in self.output_cache:
            self.output_cache[pid] = {}

        cache = self.output_cache[pid]

        if "exited" in output:
            cache["exited"] = output["exited"]

        if "exitcode" in output:
            cache["exitcode"] = output["exitcode"]

        if "signal" in output:
            cache["signal"] = output["signal"]

        if "out-data" in output:
            if "stdout" not in cache:
                cache["stdout"] = ""
            cache["stdout"] += str(
                base64.b64decode(output["out-data"]), sys.getdefaultencoding()
            )

        if "out-truncated" in output:
            cache["stdout_trunc"] = True

        if "err-data" in output:
            if "stderr" not in cache:
                cache["stderr"] = ""
            cache["stderr"] += str(
                base64.b64decode(output["err-data"]), sys.getdefaultencoding()
            )

        if "err-truncated" in output:
            cache["stderr_trunc"] = True

    def _write(self, filename, data, mode="w"):
        """
        Write the provided data at the provided filename within the guest VM.

        Args:
            filename (str): name of the file to open for writing.
            data (str): String of content to write to the file.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        Returns:
            bool: True or False indicating success.
        """

        while True:
            try:
                with self.lock:
                    # it's annoying to recover from a timeout that occurs after the file is open,
                    # but before we receive the handle, so we leave the timeout here to `None`.
                    handle = self.qga.cmd(
                        "guest-file-open", {"path": filename, "mode": mode}
                    )["return"]
                break
            # pylint: disable=broad-except
            except Exception as exp:
                self.log.exception(exp)
                with self.lock:
                    self.qga.settimeout(None)
                return False

        success = None
        with self.lock:
            try:
                success = self.file_write_content(handle, data)
            # pylint: disable=broad-except
            except Exception as exp:
                self.log.error("Error writing file")
                self.log.exception(exp)
            finally:
                self.qga.cmd("guest-file-close", {"handle": handle})
        return success

    def read_file(self, filename, local_destination, mode="rb"):
        """
        Read a file from a VM and put it onto the physical host.

        QGA has issues detecting EOF on Windows VMs. Therefore, if two reads from the file
        have the exact same data (e.g. 4K bytes per read) this method makes an assumption
        that all the data has been read. This approach can possibly cause issues.
        For example, if the file has two chunks of 4K bytes that are the same but then
        additional data, this will truncate the reading of the file.
        For that reason, we only apply this method for Windows VMs.
        If this becomes an issue with a particular experiment, it is possible to change the
        default number of bytes from 4K to a higher number (up to 48MB). You can see
        https://qemu-project.gitlab.io/qemu/interop/qemu-ga-ref.html#qapidoc-47
        for more details.

        Args:
            filename (str): The file to read from inside the VM. This should be
                the full path.
            local_destination (pathlib.PurePosixPath): The path on the physical host
                where the file should be read to.
            mode (str): The mode of reading the file. Defaults to ``'rb'``.

        Returns:
            bool: True if the read was successful, False otherwise.

        Raises:
            RuntimeError: There is a read error.
            RuntimeError: The return didn't have a byte count.
            RuntimeError: The returned size does not match the read size.
        """

        handle = None
        try:
            with self.lock:
                # it's annoying to recover from a timeout that occurs after the file is open,
                # but before we receive the handle, so we leave the timeout here to None.
                handle = self.qga.cmd(
                    "guest-file-open", {"path": filename, "mode": mode}
                )["return"]
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.exception(exp)
            return False

        lockfile = local_destination.parent / f"{local_destination.name}-lock"
        try:
            last = None
            if not local_destination.parent.exists():
                local_destination.parent.mkdir(parents=True)
            if local_destination.exists():
                # If the file already exists, then delete it
                # otherwise this will append to it
                local_destination.unlink()

            # Create a lock-file to prevent any issues with reading partially-written files
            lockfile.touch(exist_ok=True)

            self.log.debug("Starting to read file %s", filename)
            while True:
                with self.lock:
                    result = self.qga.cmd("guest-file-read", {"handle": handle})[
                        "return"
                    ]

                # If error is in the dictionary returned then an error happened
                if "error" in result:
                    self._delete_parent_directories(local_destination.parent)
                    raise RuntimeError(f"File read: {result['error']['desc']}")

                # Make sure there is a byte count in the returned status
                if "count" not in result:
                    self._delete_parent_directories(local_destination.parent)
                    raise RuntimeError("File read: Return didn't have byte count.")

                if "buf-b64" not in result and result["count"] != 0:
                    self._delete_parent_directories(local_destination.parent)
                    raise RuntimeError(f"Unable to get read data: {filename}")

                if "buf-b64" not in result and result["count"] == 0:
                    # Empty file, no need for the parent directory structure
                    self._delete_parent_directories(local_destination.parent)
                    return True

                content = base64.b64decode(result["buf-b64"])

                # Make sure the returned written byte count agrees with the amount
                # of data that was intended to be written
                if result["count"] != len(content):
                    self._delete_parent_directories(local_destination.parent)
                    raise RuntimeError(
                        f"File read: Returned size of {result['count']} does not match "
                        f"read size of {len(content)}"
                    )

                # Write out the content to the local file on the compute
                with local_destination.open(mode="ab") as fname:
                    fname.write(content)

                if result.get("eof"):
                    self.log.debug("Returning due to EOF")
                    return True

                # QGA does not pick up EOF on windows files
                # therefore, we check for the OS version and if Windows is the OS
                # and two previous loops have the exact same data (e.g. 4K bytes)
                # than we assume that the file has read all the data.
                # This approach can possibly cause issues. For example, if the file
                # has two chunks of 4K Bytes that are the same but then additional data,
                # this will truncate the reading of the file. For that reason, we only apply
                # this method for Windows VMs.
                if content == last:
                    os_version = self.get_os()
                    self.log.debug(
                        "Found two consecutive chunks of data that is the same. "
                        "It's likely that an EOF was missed by QGA."
                        "Returning if the VM is windows, otherwise continuing to write data."
                    )
                    if "windows" in os_version.lower():
                        # This is needed since the QGA doesn't pick up EOF on
                        # windows files
                        return True

                last = content

            # If a return hasn't been triggered yet then something went wrong,
            # so cleanup the created directories
            self._delete_parent_directories(local_destination.parent)
            return False

        except RuntimeError:
            with self.lock:
                self.log.error("Error reading from file")
        finally:
            if handle:
                with self.lock:
                    self.log.debug("Closing file")
                    self.qga.cmd("guest-file-close", {"handle": handle})
            lockfile.unlink()

        return False

    def write_from_file(self, filename, local_filename, mode="w"):
        """
        Given a local filename, open that file to read its data and write
        that data to a location (provided in filename) in the guest VM.

        Args:
            filename (str): The name of the file to open for writing.
            local_filename (str): Filename of the file containing data to
                send to the VM.
            mode (str): Mode for writing to the file. ``'w'`` or ``'a'``.

        Returns:
            bool: True or False indicating success.

        Raises:
            OSError: If an issue occurs writing the file.
        """

        try:
            with self.lock:
                # it's annoying to recover from a timeout that occurs after the file is open,
                # but before we receive the handle, so we leave the timeout here to `None`.
                handle = self.qga.cmd(
                    "guest-file-open", {"path": filename, "mode": mode}
                )["return"]
        except (OSError, KeyError) as exp:
            self.log.exception(exp)
            raise OSError from exp

        success = False
        try:
            success = self.file_write_from_file(handle, local_filename)
        except OSError as exp:
            self.log.error("Error writing from file")
            self.log.exception(exp)
            raise OSError from exp

        with self.lock:
            self.qga.cmd("guest-file-close", {"handle": handle})

        return success

    def get_os(self):
        """
        Get the Operating System details for the VM.

        Returns:
            str: The "pretty" name for the OS.

        Raises:
            OSError: Unable to get OS info.
        """

        if self.target_os:
            return self.target_os
        attempts = 1
        while True:
            retry = False
            self.log.debug("Getting OS info attempt=%s", attempts)
            with self.lock:
                ret = self.qga.cmd("guest-get-osinfo")["return"]
                self.log.debug("guest-get-osinfo=%s", ret)
            if "name" in ret:
                self.target_os = ret["name"]
            elif "kernel-release" in ret:
                self.target_os = ret["kernel-release"]
            elif "version" in ret:
                self.target_os = ret["version"]
            else:
                # Must've failed, try again
                retry = True

            if not retry:
                break

            if attempts > 120:
                raise OSError("Unable to get OS info")
            attempts += 1

        return self.target_os

    def close(self):
        """
        Close the connection to the socket used for guest agent.
        """

        self.qga.close()
