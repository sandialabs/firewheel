import os
import sys
import json
import platform
import subprocess
import multiprocessing
from pathlib import Path

import minimega

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.lib.utilities import retry


# The proper way to spell minimega is ALWAYS lowercase.
# pylint: disable=invalid-name
class minimegaAPI:  # noqa: N801
    """
    This class implements an API to minimega to run common commands and
    parse outputs into python objects.
    """

    def __init__(self, mm_base=None, timeout=120, skip_retry=False):
        """
        Initializes the object with a minimega connection.

        Args:
            mm_base (str): The root directory for minimega. The default is
                ``None``, in which case the directory is pulled from the
                current configuration.
            timeout (int): Number of seconds to wait for minimega socket when
                initializing before raising a TimeoutError.
            skip_retry (bool): Do not attempt to retry connecting to minimega if there
                is an error.

        Raises:
            RuntimeError: If the minimega socket does not exist.
            TimeoutError: If the connection to minimega timed out.
        """
        if mm_base is None:
            mm_base = config["minimega"]["base_dir"]

        self.log = Log(name="minimegaAPI").log

        self.cluster_head_node = self.get_head_node()
        self.am_head_node = self.get_am_head_node()

        self.mm_base = mm_base
        self.mm_socket = os.path.join(self.mm_base, "minimega")

        if (namespace := config["minimega"].get("namespace")) is None:
            self.log.warning("minimega namespace not set, using default")
        if not os.path.exists(self.mm_socket):
            self.log.error("minimega socket does not exist at: %s", self.mm_socket)
            raise RuntimeError(f"minimega socket does not exist at: {self.mm_socket}")
        try:
            self.mm = minimega.minimega(self.mm_socket, True, False, namespace)
        except Exception as exp:
            self.log.error("minimega connection failed.")
            self.log.exception(exp)
            raise RuntimeError("minimega connection failed") from exp

        try:
            self._check_version(timeout, skip_retry=skip_retry)
        except TimeoutError as exp:
            self.log.error("minimega connection timed out.")
            raise exp

        self.mesh_size = self.get_mesh_size()

    @staticmethod
    def get_am_head_node():
        """
        Provide method for determining if the current node is the head node.

        Returns:
            bool: True if the current node is the head node. False otherwise.
        """
        cluster_head_node = minimegaAPI.get_head_node()
        am_head_node = platform.node() == cluster_head_node
        return am_head_node

    @staticmethod
    def get_head_node():
        """
        Get the head node from the FIREWHEEL configuration.

        Returns:
            str: The head node from the cluster. This is assumed to be the first node of
            the control node list.

        Raises:
            RuntimeError: If no cluster control node exists.
        """
        try:
            cluster_head_node = config["cluster"]["control"][0]
        except IndexError as exp:
            raise RuntimeError("A cluster control node must be set!") from exp

        return cluster_head_node

    @retry(5, (TimeoutError,), base_delay=10, exp_factor=2)
    def _check_version(self, timeout, skip_retry=False):
        """
        Checks if the version of the minimega python bindings matches the
        versions of all running instances of minimega in the namespace.

        To enable timeouts, a process is spawned to call the necessary
        minimega functions.

        Args:
            timeout (int): Number of seconds to wait for minimega socket before
                raising a TimeoutError.
            skip_retry (bool): Do not attempt to retry connecting to minimega if there
                is an error.

        Returns:
            bool: True if versions match, False otherwise.

        Raises:
            TimeoutError: If a timeout occurs when connecting to minimega.
            RuntimeError: If a timeout occurs when connecting to minimega but
                ``skip_retry is true``.
        """

        def _proc_check_version(queue):
            for resp in self.mm.version():
                if minimega.__version__ not in resp["Response"]:
                    queue.put(False)
                    return
            queue.put(True)
            return

        queue = multiprocessing.Queue()
        proc = multiprocessing.Process(target=_proc_check_version, args=(queue,))
        proc.start()
        proc.join(timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join()
            if skip_retry:
                raise RuntimeError(
                    f"Timed out after {timeout} seconds when trying to receive "
                    f"from minimega socket at: {self.mm_socket}"
                )

            raise TimeoutError(
                f"Timed out after {timeout} seconds when trying to receive "
                f"from minimega socket at: {self.mm_socket}"
            )

        ret = queue.get()
        return ret

    def set_group_perms(self, path):
        """
        Recursively sets the group permissions on a path to be equal
        to the user permissions.

        Args:
            path (str): The path to set group permissions.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            relative_path = Path(path).relative_to(self.mm_base)
        except ValueError:
            relative_path = path

        full_path = os.path.join(self.mm_base, relative_path)
        self.log.debug("Trying to set group permissions on %s.", full_path)
        cmd = f"chmod g=u -R {full_path}"
        ret = self.mm.shell(cmd)
        if any(res["Error"] for res in ret):
            self.log.error("Setting group permissions on %s failed.", full_path)
            return False
        self.log.debug("Successfully set group permissions on %s.", full_path)
        return True

    def ns_kill_processes(self, path):
        """
        Kill a specified process using ``pkill -f``

        Args:
            path (str): The path to kill. (This path will be prefixed with
                ``sys.executable``.)

        Returns:
            bool: True on success, False otherwise.

        Raises:
            minimega.Error: If minimega has an issue running the command.
        """
        kill_path = f"{sys.executable}.{path}"
        cmd = f'shell "/usr/bin/pkill" -f {kill_path}'
        self.log.debug("Trying to run %s on namespace.", cmd)
        processes_killed = False
        try:
            self.mm.ns_run(cmd)
            processes_killed = True
        except minimega.Error as exp:
            if "status 1" in str(exp).lower():
                self.log.debug(
                    "Received %s. Assuming this means no processes to kill and continuing.",
                    str(exp),
                )
            else:
                self.log.exception(exp)
                raise
        return processes_killed

    def get_mesh_size(self):
        """
        Gets the size of the minimega mesh.

        Returns:
            int: The size of the minimega mesh.
        """
        mesh_status = self.mm.mesh_status()
        mapped_mesh_status = self.mmr_map(mesh_status, first_value_only=True)
        size = int(mapped_mesh_status["size"])
        return size

    @staticmethod
    def mmr_map(raw_response, first_value_only=False):
        """
        Attempts to map a raw minimega output into a python dictionary

        Args:
            raw_response (str): raw output from a minimega command.
            first_value_only (bool): If True, return only the first value in the response.
                Defaults to False.

        Returns:
            dict: Dictionary representation of minimega output.
        """

        new_response = {}
        for host_response in raw_response:
            new_host_response = []
            header = host_response["Header"]
            table = host_response["Tabular"]
            hostname = host_response["Host"]
            if table:
                for row in table:
                    new_row = {header[i]: row[i] for i in range(len(header))}
                    if first_value_only:
                        return new_row
                    new_host_response.append(new_row)
                new_response[hostname] = new_host_response
        return new_response

    @staticmethod
    def check_host_filter(filter_dict, elem):
        """
        Checks an element against a provided dictionary of filter keys
        and expected values.

        The provided dictionary is expected to be of the form ``{filter_key : filter_obj}``,
        where the ``filter_obj`` is a tuple of ``(filter_relation, filter_value)``.

        Filtering an element proceeds as follows:

        (1) For each ``filter_key``, ensure that the provided element's value
            for that key satisfies the ``filter_relation`` for the given ``filter_value``.
        (2) Return True only if each filter check is satisfied.

        Currently, the following ``filter_relation`` values are supported:
        ``{"=", "!=", "~", "!~"}``.

        Args:
            filter_dict (dict): A dictionary of filters of the form:
                    ``{filter_key : filter_obj}``, where `filter_obj` is of the form:
                    ``(filter_relation, filter_value)``.
            elem (dict): The element to check against the filter.

        Returns:
            bool: Whether the element passes all of the filters checks.

        Raises:
            RuntimeError: If the ``filter_relation`` is unsupported.
        """
        # we want to support the following filters:
        # =, !=, ~, and !~
        if filter_dict:
            for filter_key, filter_obj in filter_dict.items():
                filter_relation, filter_value = filter_obj
                if filter_relation == "=":
                    check = elem[filter_key] == filter_value
                elif filter_relation == "!=":
                    check = elem[filter_key] != filter_value
                elif filter_relation == "~":
                    check = filter_value in elem[filter_key]
                elif filter_relation == "!~":
                    check = filter_value not in elem[filter_key]
                else:
                    raise RuntimeError(f"Unsupported filter for {filter_dict.items()}")
                if not check:
                    return False
        return True

    def mm_vms(self, filter_dict=None):
        """
        List the VMs in current experiment. Optionally filtered by supplied filter_dict.

        Args:
            filter_dict (dict): A dictionary of filters of the form:
                    `{filter_key : filter_obj}`, where `filter_obj` is of the form:
                    `(filter_relation, filter_value)`

        Returns:
            dict: A dictionary representation of the filtered VMs.
        """
        mm_vm_info = self.mm.vm_info()
        formatted_vm_info = self.mmr_map(mm_vm_info)
        mm_common_keys = {"uuid", "name", "state", "id"}
        vms = {}
        for hostname, host_vms in formatted_vm_info.items():
            for host_vm in host_vms:
                if not self.check_host_filter(filter_dict, host_vm):
                    continue
                new_host_vm = {k: v for k, v in host_vm.items() if k in mm_common_keys}
                new_host_vm["vnc"] = host_vm["vnc_port"]
                tags = json.loads(host_vm["tags"])
                new_host_vm["image"] = tags.get("image", "")
                new_host_vm["control_ip"] = tags.get("control_ip", "")
                new_host_vm["hostname"] = hostname
                new_host_vm["pid"] = host_vm.get("pid", "")
                vms[new_host_vm["name"]] = new_host_vm
        return vms

    @staticmethod
    def _parse_output(output):
        """
        Debug function. Used to parse the output of a minimega shell command.

        Args:
            output (str): The minimega command output.

        Returns:
            list: A list representation of the minimega shell command output.
        """
        new_output = []
        for line in output.decode("utf-8").split("\n"):
            new_output.append([k.strip() for k in line.split("|")])
        return new_output

    @staticmethod
    def _parse_table(table_output):
        """
        Debug function. Used to parse the tabular output of a minimega shell command.

        Args:
            table_output (list): The minimega command output.

        Returns:
            list: A parsed table representation of the minimega output.
        """
        header = table_output[0]
        rows = table_output[1:-1]
        new_table = []
        for row in rows:
            new_row = {header[i]: row[i] for i in range(len(header))}
            new_table.append(new_row)
        return new_table

    def _cmd_to_dict(self, cmd):
        """
        Debug function. Used to return a dictionary representation of the output
        of a minimega shell command.

        Args:
            cmd (list): The minimega command to run.

        Returns:
            list: A parsed table representation of the minimega output.
        """
        cmd_output = self._run_cmd(cmd)
        parsed_output = self._parse_output(cmd_output)
        parsed_table = self._parse_table(parsed_output)
        return parsed_table

    @staticmethod
    def _run_cmd(args):
        """
        Debug function. Used to return the output of a minimega shell command.

        Note:
            In general, this provides direct access to minimega and can have some
            serious security implications. Please review :ref:`firewheel_security`
            for more details.

        Args:
            args (list): The minimega command to run.

        Returns:
            str: The output of the minimega shell command.
        """
        minimega_bin_path = os.path.join(
            config["minimega"]["install_dir"], "bin", "minimega"
        )
        new_args = [minimega_bin_path, "-e", *args]
        ret = subprocess.check_output(new_args)
        return ret

    def _parse_host(self, host_item):
        """
        Parses a host response item from minimega.

        Args:
            host_item (tuple): Tuple of hostname, host_values from minimega
                `host` output.

        Returns:
            dict: The parsed host.
        """
        if not host_item:
            return None
        hostname, host_values = host_item
        host_value = host_values[0]
        control_hostname = hostname
        new_host = {
            "control_hostname": control_hostname,
            "hostname": hostname,
            "cpus": int(host_value["cpus"]),
            "cpucommit": int(host_value["cpucommit"]),
            "memtotal": int(host_value["memtotal"]),
            "memcommit": int(host_value["memcommit"]),
        }
        return new_host

    def get_hosts(self, host_key=None):
        """
        Get the  hosts in the minimega namespace, and return the parsed hosts
        as a dict keyed on hostname.

        Args:
            host_key (str): Optional, when provided return only the parsed host
                with hostname equal to host_key. Otherwise, return all parsed
                hosts as a dict.

        Returns:
            dict: A dict of parsed hosts.
        """
        hosts = self.mm.host()
        mapped_hosts = self.mmr_map(hosts)
        if host_key:
            host_values = mapped_hosts.get(host_key, None)
            if not host_values:
                return None
            host_item = (host_key, host_values)
            return self._parse_host(host_item)
        parsed_hosts = {}
        for host_item in mapped_hosts.items():
            hostname = host_item[0]
            parsed_host = self._parse_host(host_item)
            parsed_hosts[hostname] = parsed_host
        return parsed_hosts

    def get_cpu_commit_ratio(self):
        """
        Returns the ratio of committed CPUs to logical CPUs on the current
        physical host. This is used to intelligently throttle based on load.

        Returns:
            float: (CPU commit / logical CPUs).
        """
        host = self.get_hosts(host_key=platform.node())
        return host["cpucommit"] / host["cpus"]
