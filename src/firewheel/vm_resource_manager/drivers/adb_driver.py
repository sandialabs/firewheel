"""
ADB driver for FIREWHEEL VM Resource Manager.

This driver communicates with Android Virtual Devices / Android guests via ADB.
It implements the AbstractDriver interface used by VMResourceHandler while avoiding
QGA/Linux-specific assumptions such as /bin/bash, /var/launch, and writable /system.
"""

import re
import json
import time
import uuid
import shlex
import base64
import posixpath
from pathlib import Path

import adbutils

from firewheel.vm_resource_manager.abstract_driver import AbstractDriver


class ADBDriver(AbstractDriver):
    """
    Driver class for Android Debug Bridge (ADB).

    This driver is intended to be selected for minimega/FIREWHEEL VMs whose engine
    is ``ADB``. It uses Android-native paths and /system/bin/sh.
    """

    ANDROID_SHELL = "/system/bin/sh"
    FIREWHEEL_ROOT = "/data/local/tmp/firewheel"
    LAUNCH_ROOT = f"{FIREWHEEL_ROOT}/launch"
    PROC_ROOT = f"{FIREWHEEL_ROOT}/proc"

    _ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, config, log):
        """
        Initialize the ADB driver.

        Args:
            config (dict): Handler config. Expected keys:
                - ``adb_serial``: ADB serial, e.g. ``emulator-5554``.
                - ``android_console_port``: Optional emulator console port, e.g. 5554.
                - ``android_adb_port``: Optional ADB daemon port, e.g. 5555.
                - ``require_root``: Optional bool. Defaults to True.
            log (logging.Logger): Logger instance.
        """
        log.info("ADBDriver config = %s", config)

        self.adb_name = config.get("adb_serial")
        self.android_console_port = config.get("android_console_port")
        self.android_adb_port = config.get("android_adb_port")
        self.require_root = config.get("require_root", True)

        if not self.adb_name:
            if self.android_console_port is None:
                raise ValueError(
                    "ADBDriver requires either adb_serial or android_console_port."
                )
            self.adb_name = f"emulator-{self.android_console_port}"

        self.adb_client = adbutils.AdbClient()
        self.adb_device = self.adb_client.device(self.adb_name)
        self._is_rooted = False

        super().__init__(config, log)

    # -------------------------------------------------------------------------
    # Basic ADB helpers
    # -------------------------------------------------------------------------

    def _refresh_device(self):
        """Refresh the adbutils device handle."""
        self.adb_device = self.adb_client.device(self.adb_name)

    def _shell(self, command):
        """
        Run an Android shell command and return stdout.

        Args:
            command (str): Command string.

        Returns:
            str: stdout text.
        """
        with self.lock:
            return self.adb_device.shell(command)

    def _shell2(self, command):
        """
        Run an Android shell command and return an adbutils shell2 result.

        Args:
            command (str): Command string.

        Returns:
            object: Result object with ``returncode`` and ``output``.
        """
        with self.lock:
            return self.adb_device.shell2(command)

    @staticmethod
    def _contains_glob(path):
        """Return True if ``path`` contains simple shell glob metacharacters."""
        return any(char in str(path) for char in ("*", "?", "["))

    def _quote_path(self, path, allow_glob=False):
        """
        Quote a path for shell use.

        Args:
            path (str): Path to quote.
            allow_glob (bool): If True, preserve glob patterns unquoted.

        Returns:
            str: Shell-safe path string.
        """
        path = str(path)
        if allow_glob and self._contains_glob(path):
            return path
        return shlex.quote(path)

    def _ensure_firewheel_dirs(self):
        """Create FIREWHEEL runtime directories on the Android guest."""
        result = self._shell2(
            f"mkdir -p {shlex.quote(self.LAUNCH_ROOT)} {shlex.quote(self.PROC_ROOT)}"
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Unable to create FIREWHEEL Android directories: {result.output}"
            )

    # -------------------------------------------------------------------------
    # Connection / lifecycle
    # -------------------------------------------------------------------------

    def _wait_for_device_online(self):
        """Wait until the ADB device is online and shell commands work."""
        while not self.ping():
            self.log.debug(
                "Waiting for Android device %s to come online", self.adb_name
            )
            time.sleep(1)

    def _root(self):
        """
        Obtain root access.

        Raises:
            RuntimeError: If root is required but could not be obtained.
        """
        self.log.debug("Requesting adb root for %s", self.adb_name)

        with self.lock:
            self.adb_device.root()

        # adb root commonly restarts adbd.
        time.sleep(1)
        self._refresh_device()
        self._wait_for_device_online()

        result = self._shell2("id -u")
        uid = result.output.strip()

        if result.returncode != 0 or uid != "0":
            raise RuntimeError(
                f"ADB root requested for {self.adb_name}, but device UID is "
                f"{uid!r}; output={result.output!r}"
            )

        self._is_rooted = True
        self.log.debug("ADB root confirmed for %s", self.adb_name)

    def connect(self):
        """
        Establish or re-establish connection to the Android device.

        Returns:
            int: ``1`` on success.
        """
        self._refresh_device()
        self._wait_for_device_online()

        if self.require_root and not self._is_rooted:
            self._root()
            self._wait_for_device_online()

        self._ensure_firewheel_dirs()

        return self.sync()

    def close(self):
        """
        Close the driver connection.

        adbutils does not require explicit cleanup for this usage.
        """
        return

    def ping(self, timeout=10):
        """
        Check whether the Android device is reachable.

        Args:
            timeout (int): Present for API compatibility.

        Returns:
            bool: True if the device is online and shell responds.
        """
        _timeout = timeout

        try:
            with self.lock:
                state = self.adb_device.get_state()

            if state.strip() != "device":
                return False

            with self.lock:
                result = self.adb_device.shell2("true")

            return result.returncode == 0

        except (adbutils.errors.AdbError, OSError):
            return False

    def sync(self, timeout=5):
        """
        Synchronize the driver state.

        Args:
            timeout (int): Present for API compatibility.

        Returns:
            int: ``1``.
        """
        _timeout = timeout
        return 1

    @staticmethod
    def get_engine():
        """
        Return the VM Resource Handler communication driver name.

        Returns:
            str: ``"ADB"``.
        """
        return "ADB"

    def reboot(self):
        """
        Reboot the Android guest.
        """
        super().reboot()

        with self.lock:
            self._is_rooted = False
            self.adb_device.reboot()

    # -------------------------------------------------------------------------
    # Time / OS / platform information
    # -------------------------------------------------------------------------

    def get_time(self):
        """
        Get current Android guest time.

        Returns:
            float: Seconds since epoch.
        """
        if not (output := self._shell("date +%s")):
            raise RuntimeError("Failed to acquire date")
        final_line = output.strip().splitlines()[-1]
        return float(int(final_line))
         

    def set_time(self):
        """
        Set Android guest time to the host's current UTC time.

        This usually requires root. Android date syntax varies, so try several
        common forms.
        """
        epoch_seconds = int(time.time())
        android_stamp = time.strftime("%m%d%H%M%Y.%S", time.gmtime(epoch_seconds))

        commands = [
            f"date -u {shlex.quote(android_stamp)}",
            f"toybox date -u {shlex.quote(android_stamp)}",
            f"date -u @{epoch_seconds}",
            f"toybox date -u @{epoch_seconds}",
        ]

        last_result = None

        for command in commands:
            last_result = self._shell2(command)
            if last_result.returncode == 0:
                self.log.debug("Set Android time using command: %s", command)
                return

        self.log.warning(
            "Unable to set Android time on %s. Last command output: %s",
            self.adb_name,
            last_result.output if last_result else "",
        )

    def get_os(self):
        """
        Get Android OS details.

        Returns:
            str: Human-readable OS string containing ``Android``.
        """
        if self.target_os:
            return self.target_os

        cmd = (
            'echo "$(getprop ro.product.brand) Android '
            "$(getprop ro.build.version.release) "
            '($(getprop ro.product.model))"'
        )

        for _attempt in range(10):
            try:
                output = self._shell(cmd).strip()
                if output:
                    self.target_os = output
                    return self.target_os
            except Exception as exc:
                self.log.exception(exc)
                time.sleep(1)

        self.target_os = "Android"
        return self.target_os

    def network_get_interfaces(self):
        """
        Retrieve network interface information.

        Returns:
            object: Parsed JSON from ``ip -j address``.
        """
        output = self._shell("ip -j address")
        return json.loads(output)

    def set_user_password(self, username, password):
        """
        Set a user's password.

        Android does not use this mechanism for normal FIREWHEEL experiment control.
        """
        _username = username
        _password = password
        raise NotImplementedError("set_user_password is not implemented for Android")

    # -------------------------------------------------------------------------
    # Filesystem helpers required by VMResourceHandler
    # -------------------------------------------------------------------------

    def file_flush(self, handle=None):
        """
        Flush filesystem buffers on Android.

        Args:
            handle (File): Unused; present for AbstractDriver compatibility.

        Returns:
            bool: True on success.
        """
        _handle = handle
        result = self._shell2("sync")
        return result.returncode == 0

    def create_directories(self, directory):
        """
        Create directories on the Android guest.

        Args:
            directory (str): Absolute directory path.

        Returns:
            bool: True on success.
        """
        self.log.info("Creating directory: %s", directory)
        result = self._shell2(f"mkdir -p {self._quote_path(directory)}")

        if result.returncode != 0:
            self.log.error("mkdir failed for %s: %s", directory, result.output)
            return False

        return True

    def delete_file(self, path):
        """
        Delete a file or directory inside the Android guest.

        Args:
            path (str): Absolute path. Globs are allowed.

        Returns:
            bool: True on success.
        """
        quoted = self._quote_path(path, allow_glob=True)
        result = self._shell2(f"rm -rf {quoted}")

        if result.returncode != 0:
            self.log.error("rm failed for %s: %s", path, result.output)
            return False

        return True

    def file_exists(self, path):
        """
        Check whether a path exists inside the Android guest.

        Args:
            path (str): Absolute path, optionally containing shell globs.

        Returns:
            bool | None: True if at least one match exists, False if not, None on error.
        """
        pattern = self._quote_path(path, allow_glob=True)
        command = (
            "found=False; "
            f"for i in {pattern}; do "
            'if [ -e "$i" ]; then found=True; break; fi; '
            "done; "
            'echo "$found"'
        )

        result = self._shell2(command)

        if result.returncode != 0:
            self.log.error("file_exists failed for %s: %s", path, result.output)
            return None

        return "True" in result.output

    def get_files(self, path, timestamp=None):
        """
        Get file names under a path on the Android guest.

        Args:
            path (str): Absolute file/directory path. Globs are allowed.
            timestamp (float | None): If provided, only return files with modification
                times newer than this value. The timestamp is seconds since epoch.

        Returns:
            list | None: List of file paths, or None on error.
        """
        pattern = self._quote_path(path, allow_glob=True)
        result = self._shell2(f"find {pattern} -type f")

        if result.returncode != 0:
            self.log.error("Unable to list files at %s: %s", path, result.output)
            return None

        files = [
            line.strip()
            for line in result.output.splitlines()
            if line.strip() and not line.strip().endswith("swp")
        ]

        if timestamp is None:
            return files

        filtered_files = []

        for filename in files:
            mtime = self._get_file_mtime(filename)

            # If mtime cannot be determined, include the file rather than risk
            # missing data that should be transferred.
            if mtime is None or mtime > timestamp:
                filtered_files.append(filename)

        return filtered_files

    def make_file_executable(self, path):
        """
        Mark a file executable inside the Android guest.

        Args:
            path (str): File path.

        Returns:
            bool: True on success.
        """
        result = self._shell2(f"chmod +x {self._quote_path(path)}")

        if result.returncode != 0:
            self.log.error("chmod failed for %s: %s", path, result.output)
            return False

        return True

    def _write(self, filename, data, mode="w"):
        """
        Write content to a file inside the Android guest.

        Args:
            filename (str): Remote file path.
            data (str | bytes): Content to write.
            mode (str): ``"w"`` or ``"a"``.

        Returns:
            bool: True on success.

        Raises:
            ValueError: If mode is unsupported.
        """
        if mode == "w":
            redirect = ">"
        elif mode == "a":
            redirect = ">>"
        else:
            raise ValueError("Unsupported file mode")

        if isinstance(data, str):
            raw = data.encode("utf-8")
        else:
            raw = bytes(data)

        parent = posixpath.dirname(str(filename))
        if parent and not self.create_directories(parent):
            return False

        encoded = base64.b64encode(raw).decode("ascii")
        command = (
            f"printf %s {shlex.quote(encoded)} | "
            f"base64 -d {redirect} {self._quote_path(filename)}"
        )

        result = self._shell2(command)

        if result.returncode != 0:
            self.log.error("write failed for %s: %s", filename, result.output)
            return False

        return True

    def read_file(self, filename, local_destination, mode="rb"):
        """
        Pull a file from Android to the physical host.

        Args:
            filename (str): Remote Android path.
            local_destination (pathlib.Path): Local destination path.
            mode (str): Present for API compatibility.

        Returns:
            bool: True on success.
        """
        _mode = mode

        try:
            local_destination = Path(local_destination)
            local_destination.parent.mkdir(parents=True, exist_ok=True)

            with self.lock:
                self.adb_device.sync.pull_file(str(filename), str(local_destination))

            return local_destination.exists()

        except Exception as exc:
            self.log.exception(exc)
            return False

    def write_from_file(self, filename, local_filename, mode="w"):
        """
        Push a local file into the Android guest.

        Args:
            filename (str): Remote Android destination path.
            local_filename (str): Local source filename.
            mode (str): Present for API compatibility. ADB push overwrites.

        Returns:
            bool: True on success.
        """
        _mode = mode

        try:
            parent = posixpath.dirname(str(filename))
            if parent and not self.create_directories(parent):
                return False

            with self.lock:
                self.adb_device.sync.push(str(local_filename), str(filename))

            return True

        except Exception as exc:
            self.log.exception(exc)
            return False

    # -------------------------------------------------------------------------
    # ScheduleEntry path generation
    # -------------------------------------------------------------------------

    def create_paths(self, schedule_entry):
        """
        Create Android-specific paths and call script content for a ScheduleEntry.

        This intentionally avoids the inherited Linux defaults:
        - no /var/launch
        - no /bin/bash
        - no /bin/sh
        """
        if not schedule_entry.executable:
            return

        try:
            schedule_entry.working_dir  # noqa: B018
            return
        except AttributeError:
            pass

        executable = Path(schedule_entry.executable)

        schedule_entry.working_dir = self.deconflict_agent_path(
            Path(self.LAUNCH_ROOT) / str(schedule_entry.start_time) / executable.name
        )

        if executable.is_absolute():
            schedule_entry.exec_path = executable
        else:
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
                schedule_entry.exec_path = schedule_entry.working_dir / executable
            else:
                # Executable is expected to be available on Android PATH.
                schedule_entry.exec_path = executable

        schedule_entry.reboot_file = schedule_entry.working_dir / "reboot"
        schedule_entry.call_args_filename = (
            schedule_entry.working_dir / "call_arguments.sh"
        )

        call_arguments = (
            f"#!{self.ANDROID_SHELL}\n"
            'CURRENT_DIR="$(dirname "$0")"\n'
            f"cd {self._quote_path(schedule_entry.working_dir)}\n"
            f"{self._quote_path(schedule_entry.exec_path)!s}"
        )

        if schedule_entry.arguments:
            call_arguments += f" {schedule_entry.arguments}"

        call_arguments += "\n"

        schedule_entry.call_arguments = call_arguments

    # -------------------------------------------------------------------------
    # Process execution/status API
    # -------------------------------------------------------------------------

    def _format_env(self, env):
        """
        Format environment variable assignments.

        Args:
            env (list[str] | None): List of KEY=VALUE strings.

        Returns:
            str: Shell-safe assignment prefix.
        """
        if not env:
            return ""

        assignments = []

        for item in env:
            if not isinstance(item, str) or "=" not in item:
                self.log.error("env entries must be strings of the form KEY=VALUE")
                return ""

            key, value = item.split("=", 1)

            if not self._ENV_NAME_RE.match(key):
                self.log.error("Invalid environment variable name: %s", key)
                return ""

            assignments.append(f"{key}={shlex.quote(value)}")

        return " ".join(assignments) + " "

    def _format_args(self, arg):
        """
        Format command arguments.

        List/tuple arguments are shell-quoted element-by-element. String arguments
        are preserved for compatibility with existing FIREWHEEL usage.
        """
        if arg is None:
            return ""

        if isinstance(arg, (list, tuple)):
            return " ".join(shlex.quote(str(item)) for item in arg)

        if isinstance(arg, str):
            return arg

        self.log.error("arg must be a string, list, tuple, or None")
        return ""

    def _build_command(self, path, arg=None, env=None, input_data=None):
        """
        Build the Android shell command.

        Args:
            path (str): Executable path/name.
            arg (str | list | tuple | None): Arguments.
            env (list[str] | None): Environment assignments.
            input_data (str | bytes | None): Data for stdin.

        Returns:
            str: Shell command.
        """
        env_prefix = self._format_env(env)
        args = self._format_args(arg)

        command = f"{env_prefix}{shlex.quote(str(path))}"

        if args:
            command += f" {args}"

        if input_data is not None:
            if isinstance(input_data, str):
                raw_input = input_data.encode("utf-8")
            else:
                raw_input = bytes(input_data)

            encoded_input = base64.b64encode(raw_input).decode("ascii")
            command = f"printf %s {shlex.quote(encoded_input)} | base64 -d | {command}"

        return command

    def execute(self, path, arg=None, env=None, input_data=None, capture_output=True):
        """
        Run a program asynchronously inside the Android guest.

        Instead of keeping a long-lived ADB stream open, the remote process writes
        stdout, stderr, and return code into files under ``PROC_ROOT``. ``exec_status``
        polls those files.

        Args:
            path (str): Executable path/name.
            arg (str | list | tuple | None): Arguments.
            env (list[str] | None): Environment assignments.
            input_data (str | bytes | None): stdin content.
            capture_output (bool): Whether to capture stdout/stderr.

        Returns:
            int | None: PID on success, None on failure.
        """
        token = uuid.uuid4().hex
        out_file = f"{self.PROC_ROOT}/{token}.stdout"
        err_file = f"{self.PROC_ROOT}/{token}.stderr"
        rc_file = f"{self.PROC_ROOT}/{token}.rc"
        started_file = f"{self.PROC_ROOT}/{token}.started"
        runner_file = f"{self.PROC_ROOT}/{token}.runner.sh"

        command = self._build_command(path, arg=arg, env=env, input_data=input_data)

        if capture_output:
            stdout_target = self._quote_path(out_file)
            stderr_target = self._quote_path(err_file)
        else:
            stdout_target = "/dev/null"
            stderr_target = "/dev/null"

        runner_content = (
            f"#!{self.ANDROID_SHELL}\n"
            f"echo started > {self._quote_path(started_file)}\n"
            f"{command} > {stdout_target} 2> {stderr_target}\n"
            "rc=$?\n"
            f"echo $rc > {self._quote_path(rc_file)}\n"
            "exit $rc\n"
        )

        cleanup_command = (
            f"mkdir -p {shlex.quote(self.PROC_ROOT)}; "
            f"rm -f {self._quote_path(out_file)} "
            f"{self._quote_path(err_file)} "
            f"{self._quote_path(rc_file)} "
            f"{self._quote_path(started_file)} "
            f"{self._quote_path(runner_file)}"
        )

        cleanup_result = self._shell2(cleanup_command)
        if cleanup_result.returncode != 0:
            self.log.error(
                "Unable to prepare Android proc directory for command %s: %s",
                command,
                cleanup_result.output,
            )
            return None

        if not self._write(runner_file, runner_content):
            self.log.error(
                "Unable to write Android runner script for command: %s", command
            )
            return None

        if not self.make_file_executable(runner_file):
            self.log.error(
                "Unable to make Android runner script executable: %s", runner_file
            )
            return None

        runner_invocation = (
            f"{self.ANDROID_SHELL} {self._quote_path(runner_file)} "
            f">> {self._quote_path(out_file)} "
            f"2>> {self._quote_path(err_file)} "
            "< /dev/null"
        )

        launch_command = (
            "if command -v setsid >/dev/null 2>&1; then "
            f"setsid {runner_invocation} & pid=$!; "
            "else "
            f"{runner_invocation} & pid=$!; "
            "fi; "
            "sleep 0.25; "
            "echo $pid"
        )

        self.log.debug("ADB execute command: %s", launch_command)

        try:
            output = self._shell(launch_command)
        except Exception as exc:
            self.log.error("Unable to launch Android command: %s", command)
            self.log.exception(exc)
            return None

        first_line = output.strip().splitlines()[0] if output.strip() else ""

        try:
            pid = int(first_line)
        except ValueError:
            self.log.error("Unable to parse PID from ADB output: %r", output)
            return None

        self.output_cache[pid] = {
            "stdout_file": out_file,
            "stderr_file": err_file,
            "rc_file": rc_file,
            "started_file": started_file,
            "runner_file": runner_file,
            "stdout_offset": 0,
            "stderr_offset": 0,
            "stdout": "",
            "stderr": "",
            "exited": False,
            "start_monotonic": time.monotonic(),
            "rc_missing_reported": False,
        }

        self.log.debug("Started Android process PID=%s command=%s", pid, command)
        return pid

    def async_exec(
        self, path, arg=None, env=None, input_data=None, capture_output=True
    ):
        """
        Execute an ADB command.

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
            int | None: PID on success.
        """
        return self.execute(
            path,
            arg=arg,
            env=env,
            input_data=input_data,
            capture_output=capture_output,
        )

    def _is_pid_alive(self, pid):
        """
        Check whether a PID is alive inside Android.

        Args:
            pid (int): Process ID.

        Returns:
            bool: True if alive.
        """
        result = self._shell2(f"kill -0 {int(pid)}")
        return result.returncode == 0

    def _read_remote_text_file(self, filename):
        """
        Read a remote text file.

        Args:
            filename (str): Remote path.

        Returns:
            str: File contents, or empty string if not available.
        """
        result = self._shell2(f"cat {self._quote_path(filename)} 2>/dev/null")

        if result.returncode != 0:
            return ""

        return result.output

    def exec_status(self, pid):
        """
        Retrieve execution status and captured output for a PID.

        Args:
            pid (int): Process ID returned by execute/async_exec.

        Returns:
            dict: Status dictionary compatible with AbstractDriver helpers.
        """
        if pid not in self.output_cache:
            raise OSError(f"Unknown Android process PID: {pid}")

        cache = self.output_cache[pid]

        # If the process has already been finalized, do not keep appending error
        # messages or re-reading state.
        if cache.get("exited") and "exitcode" in cache:
            return cache

        stdout_full = self._read_remote_text_file(cache["stdout_file"])
        stdout_offset = cache.get("stdout_offset", 0)

        if len(stdout_full) > stdout_offset:
            cache["stdout"] = cache.get("stdout", "") + stdout_full[stdout_offset:]
            cache["stdout_offset"] = len(stdout_full)

        stderr_full = self._read_remote_text_file(cache["stderr_file"])
        stderr_offset = cache.get("stderr_offset", 0)

        if len(stderr_full) > stderr_offset:
            cache["stderr"] = cache.get("stderr", "") + stderr_full[stderr_offset:]
            cache["stderr_offset"] = len(stderr_full)

        rc_text = self._read_remote_text_file(cache["rc_file"]).strip()

        if rc_text:
            try:
                cache["exitcode"] = int(rc_text.splitlines()[-1])
                cache["exited"] = True
            except ValueError:
                self.log.warning(
                    "Unable to parse Android exit code for PID %s from %r",
                    pid,
                    rc_text,
                )
                alive = self._is_pid_alive(pid)
                cache["exited"] = not alive

                if not alive:
                    cache.setdefault("stderr", "")
                    cache["stderr"] += (
                        f"\nUnable to parse Android return-code file "
                        f"{cache['rc_file']}: {rc_text!r}\n"
                    )
                    cache["exitcode"] = 1

            self.log.debug("exec_status of %s: %s", pid, cache)
            return cache

        alive = self._is_pid_alive(pid)

        if alive:
            cache["exited"] = False
            self.log.debug(
                "PID %s is still running and has not written rc file yet.", pid
            )
            return cache

        # The process appears to have exited, but Android/ADB file visibility can
        # lag briefly for very short-lived commands. Do not mark this as failed
        # immediately.
        age = time.monotonic() - cache.get("start_monotonic", time.monotonic())
        rc_grace_sec = 2.0

        if age < rc_grace_sec:
            cache["exited"] = False
            self.log.debug(
                "PID %s is no longer alive, but return-code file %s is not visible yet. "
                "Waiting for grace period %.1fs; age=%.3fs.",
                pid,
                cache["rc_file"],
                rc_grace_sec,
                age,
            )
            return cache

        started_text = ""
        started_file = cache.get("started_file")
        if started_file:
            started_text = self._read_remote_text_file(started_file)

        cache["exited"] = True
        cache["exitcode"] = 1

        if not cache.get("rc_missing_reported"):
            cache.setdefault("stderr", "")

            if not started_text.strip():
                cache["stderr"] += (
                    f"\nADB process wrapper for PID {pid} did not create started file "
                    f"{started_file}. The wrapper may have failed before executing "
                    "the command.\n"
                )

            cache["stderr"] += (
                f"\nADB process wrapper for PID {pid} exited without writing "
                f"return-code file {cache['rc_file']} after {age:.3f}s.\n"
            )
            cache["rc_missing_reported"] = True

        self.log.debug("exec_status of %s: %s", pid, cache)
        return cache

    def store_captured_output(self, pid, output):
        """
        Store captured output/status.

        This is normally unused by the ADB implementation but is implemented for
        interface completeness.
        """
        self.output_cache.setdefault(pid, {}).update(output)

    def _get_file_mtime(self, filename):
        """
        Get a file's modification time on Android.

        Args:
            filename (str): Remote Android file path.

        Returns:
            float | None: Modification time in seconds since epoch, or None if unavailable.
        """
        quoted = self._quote_path(filename)

        commands = [
            f"stat -c %Y {quoted}",
            f"toybox stat -c %Y {quoted}",
        ]

        for command in commands:
            result = self._shell2(command)
            if result.returncode != 0:
                continue

            output = result.output.strip().splitlines()
            if not output:
                continue

            try:
                return float(output[-1])
            except ValueError:
                continue

        self.log.warning(
            "Unable to determine modification time for Android file: %s", filename
        )
        return None
