
from firewheel.vm_resource_manager.abstract_driver import AbstractDriver
import adbutils

class ADBDriver(AbstractDriver):
    def __init__(self, config, log):
        self.console_port = config["qemu_append"]["port"]
        self.adb_name = f"emulator-{self.console_port}"
        self.adb_client = adbutils.AdbClient()
        self.adb_device = self.adb_client.device(self.adb_name)

    def connect(self):
        self.adb_device.root()
        return

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
            result = adb_device.get_state()
            return result.stdout.strip() == "device"
        except Exception:
            # Any exception (including timeout) indicates the device is not reachable
            return False

    def sync(self):
        # TODO this function is not needed I think
        return

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
        output = self.adb_device.shell('date +%s')
        # The output may contain newline characters; strip them.
        secs_str = output.strip()
        secs = int(secs_str)
        # Return as float seconds for consistency with other drivers.
        return float(secs)


    def set_time(self):
        cur_time_nano = int(time.time() * 1e9)
        self.adb_device.shell(f"date -s {cur_time_nano}")
    
    def reboot(self):
        self.adb_device.reboot()
    
    def file_flush(self):
        raise NotImplementedError

    def network_get_interfaces(self):
        return json.loads(self.adb_device.shell("ip -j address"))

    def set_user_password(self, username, password):
        raise NotImplementedError

    def execute(self, path, arg=None, env=None, input_data=None, capture_output=True):
        full_cmd = ""

        if input_data is not None:
            full_cmd += f"printf '{input_data}' | "

        if env is not None:
            for env_var in env:
                full_cmd += env_var
                full_cmd += " "
        
        full_cmd += path
        full_cmd += " "
        full_cmd += arg
        full_cmd += " &" # Run the command asynchronously
        self.adb_device.shell(full_cmd)

    def exec_status(self, pid):
        raise NotImplementedError

    def store_captured_output(self, pid, output):
        raise NotImplementedError

    def _write(self, filename, data, mode="w"):
        if mode == "w":
            redirect = ">"
        elif mode == "a":
            redirect = ">>"
        else:
            raise ValueError("Unsupported file mode")

        self.adb_device.shell(f"printf '{data}' {redirect} {filename}")

    def read_file(self, filename, local_destination, mode="rb"):
        self.adb_device.sync.pull_file(filename, local_destination)

    def write_from_file(self, filename, local_filename, mode="w"):
        with open(local_filename) as fhand:
            data = fhand.read()
        self._write(filename, data, mode)

    def get_os(self):
        cmd = 'echo "'
        cmd += '$(getprop ro.product.brand) '
        cmd += 'Android '
        cmd += '$(getprop ro.build.version.release) '
        cmd += '($(getprop ro.product.model))'
        cmd += '"'
        return self.adb_device.shell(cmd)