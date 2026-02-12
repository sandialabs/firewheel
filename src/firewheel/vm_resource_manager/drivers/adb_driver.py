
from firewheel.vm_resource_manager.abstract_driver import AbstractDriver
import json
import adbutils
import time
import signal
import base64

EXIT_MAGIC = "ExitCode="

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException()

class ADBDriver(AbstractDriver):
    def __init__(self, config, log):
        log.info("Config = %s", config)
        self.console_port = config["adb_port"]
        self.adb_name = f"emulator-{self.console_port}"
        self.adb_client = adbutils.AdbClient()
        self.adb_device = self.adb_client.device(self.adb_name)
        self._is_rooted = False
        super().__init__(config, log)

    def _wait_for_device_online(self):
        sleep_time = 1
        while not self.ping():
            self.log.debug("Waiting for device to come online")
            time.sleep(sleep_time)
        
    def _remount_system(self):
        self._wait_for_device_online()

        #time.sleep(60) #FIXME debugging
        while True:
            import os
            if os.path.exists("/tmp/flag"):
                break
            time.sleep(2)

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
        with self.lock:
            self.adb_device.root()
        self._is_rooted = True

    def _symlink_bash(self):
        with self.lock:
            self.adb_device.shell("ln -s /bin/sh /bin/bash")

    def connect(self):
        with self.lock:
            self._wait_for_device_online()

            self.log.debug("Getting root access on device")
            if not self._is_rooted:
                self._root()

                self._wait_for_device_online()

                # Also, we need to remount /system as writable
                self._remount_system()

                # And, for now, let's symlink bash to sh
                self._symlink_bash()

        return 1

    def close(self):
        # TODO this function is not needed I think
        return

    def ping(self, timeout=10):
        """
        Ping the Android device via ADB to ensure it is reachable.

        Args:
            timeout (int): Number of seconds to wait for the ADB command.

        Returns:
            bool: True if the device responds, False otherwise.
        """
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
        except Exception as exc:
            # Any exception (including timeout) indicates the device is not reachable
            return False

    def sync(self):
        # TODO this function is not needed I think
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
            output = self.adb_device.shell('date +%s')
        # The output may contain newline characters; strip them.
        secs_str = output.strip()
        secs = int(secs_str)
        # Return as float seconds for consistency with other drivers.
        return float(secs)


    def set_time(self):
        cur_time_nano = int(time.time() * 1e9)
        with self.lock:
            self.adb_device.shell(f"date -s {cur_time_nano}")
    
    def reboot(self):
        with self.lock:
            self._is_rooted = False
            self.adb_device.reboot()
    
    def file_flush(self):
        raise NotImplementedError

    def network_get_interfaces(self):
        with self.lock:
            return json.loads(self.adb_device.shell("ip -j address"))

    def set_user_password(self, username, password):
        raise NotImplementedError

    def _get_pid_from_stream(self, stream):
        pid_str = ""
        while True:
            char = stream.read(1).decode("utf-8")
            if char == "\n":
                break
            pid_str += char
        
        try:
            pid = int(pid_str)
            return pid
        except ValueError:
            return None
        
    def execute(self, path, arg=None, env=None, input_data=None, capture_output=True):
        # TODO we probably need a way to just use bash, but until it's installed, try and replace it with sh
        if path == "/bin/bash":
            path = "/bin/sh"
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
        full_cmd += f" & pid=$!; echo $pid; wait $pid; echo \"{EXIT_MAGIC}$?\"" # make it run in the background and echo the PID so we can save it
        with self.lock:
            output_stream = self.adb_device.shell(full_cmd, stream=True)

        # Get and return the PID
        pid = self._get_pid_from_stream(output_stream)

        self.output_cache[pid] = {"stream": output_stream}
        self.output_cache[pid]['cmd'] = full_cmd # TODO debugging

        return pid

    def async_exec( self, path, arg=None, env=None, input_data=None, capture_output=True):
        return self.execute(path, arg, env, input_data, capture_output)

    def exec_status(self, pid):
        stream = self.output_cache[pid]["stream"]

        read_timeout = 1
        timed_out = False
        signal.alarm(read_timeout)
        try:
            stdout = stream.read_until_close()
        except TimeoutException as exc:
            timed_out = True
        finally:
            # end the timeout alarm
            signal.alarm(0)


        self.log.debug("process stdout: ****%s****", stdout)
        self.log.debug(self.output_cache[pid])

        # check if process has finished
        exited = not timed_out
        self.output_cache[pid]["exited"] = exited

        # look for the "ExitCode=..." string in the output for exit code reporting
        self.output_cache[pid].setdefault("stdout", "")
        if "exitcode" in self.output_cache[pid]:
            pass # TODO surely there's a cleaner way to do this logic
        elif exited:
            idx = stdout.rfind(EXIT_MAGIC)
            self.log.debug("idx=%s", idx)
            exit_code_str = stdout[idx+len(EXIT_MAGIC):]
            exit_code = int(exit_code_str)
            self.output_cache[pid]['exitcode'] = exit_code
            
            self.output_cache[pid]["stdout"] += stdout[:idx]
        else:
            self.output_cache[pid]["stdout"] += stdout

        return self.output_cache[pid]


    def store_captured_output(self, pid, output):
        raise NotImplementedError

    def _write(self, filename, data, mode="w"):
        if mode == "w":
            redirect = ">"
        elif mode == "a":
            redirect = ">>"
        else:
            raise ValueError("Unsupported file mode")

        maybe_b64 = ""
        if isinstance(data, bytes):
            data = base64.b64encode(data)
            maybe_b64 = " | base64 -d "

        with self.lock:
            self.adb_device.shell(f"printf '{data}' {maybe_b64} {redirect} {filename}")

        return True

    def read_file(self, filename, local_destination, mode="rb"):
        with self.lock:
            self.adb_device.sync.pull_file(filename, local_destination)

    def write_from_file(self, filename, local_filename, mode="w"):
        with open(local_filename, "rb") as fhand:
            data = fhand.read()
        self._write(filename, data, mode)
        return True

    def get_os(self):
        if self.target_os:
            return self.target_os

        cmd = 'echo "'
        cmd += '$(getprop ro.product.brand) '
        cmd += 'Android '
        cmd += '$(getprop ro.build.version.release) '
        cmd += '($(getprop ro.product.model))'
        cmd += '"'

        num_attempts = 10
        for attempt in range(num_attempts):
            with self.lock:
                try:
                    self.target_os = self.adb_device.shell(cmd)
                    break
                except Exception as exc:
                    self.log.exception(exc)
                    time.sleep(1)
        return self.target_os
