
from firewheel.vm_resource_manager.abstract_driver import AbstractDriver
import json
import adbutils
import time
import signal

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


    def connect(self):
        sleep_time = 1
        while not self.ping():
            self.log.debug("Waiting for device to come online")
            time.sleep(sleep_time)
        self.log.debug("Getting root access on device")
        if not self._is_rooted:
            with self.lock:
                self.adb_device.root()
            self.is_rooted = True

            while not self.ping():
                self.log.debug("Waiting for device to come online")
                time.sleep(sleep_time)
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
            return result.strip() == "device"
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
        if exited:
            idx = stdout.rfind(EXIT_MAGIC)
            self.log.debug("idx=%s", idx)
            exit_code_str = stdout[idx+len(EXIT_MAGIC):]
            exit_code = int(exit_code_str)
            
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

        with self.lock:
            self.adb_device.shell(f"printf '{data}' {redirect} {filename}")

    def read_file(self, filename, local_destination, mode="rb"):
        with self.lock:
            self.adb_device.sync.pull_file(filename, local_destination)

    def write_from_file(self, filename, local_filename, mode="w"):
        with open(local_filename) as fhand:
            data = fhand.read()
        self._write(filename, data, mode)

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
