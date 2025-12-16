"""
Interface to the mapping between VMs, their current (vm resource) state, and other
metadata.
"""

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.lib.grpc.firewheel_grpc_client import FirewheelGrpcClient


class VMMapping:
    """
    Database interface for the mapping between VM name, VM control IP, and
    vm_resources state or other metadata.

    Access may use name or IP as a key.
    """

    def __init__(
        self,
        hostname=config["grpc"]["hostname"],
        port=config["grpc"]["port"],
        db=config["grpc"]["db"],
    ):
        """
        All arguments are present only for unit testing and may be safely
        ignored.

        Args:
            hostname (str): The GRPC server IP/hostname.
            port (int): The GRPC server port.
            db (str): The GRPC database.
        """
        self.grpc_client = None
        self.log = Log(name="VMMapping").log
        self.grpc_client = FirewheelGrpcClient(hostname, port, db)

    def __del__(self):
        """
        Attempt to gracefully close our database connection as we are destroyed.
        """
        try:
            if self.grpc_client:
                self.grpc_client.close()
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.error("Error occurred when trying to close the GRPC Client")
            self.log.exception(exp)

    def close(self):
        """
        Close the connection to the GRPC client.
        """
        self.grpc_client.close()

    def get(self, server_uuid=None):
        """
        Retrieve a single entry from the database. This can only retrieve
        by using the `server_uuid`.

        Args:
            server_uuid (str): UUID of the VM to be retrieved.

        Returns:
            dict: Dictionary with the information about the VM as stored. Includes current
            `vm_resource` state for the VM.

        Raises:
            ValueError: If the `server_uuid` is not provided.
        """
        if server_uuid:
            vmm = self.grpc_client.get_vm_mapping_by_uuid(server_uuid)
        else:
            raise ValueError("Must provide server_uuid")
        return vmm

    def get_all(
        self, filter_time=None, filter_state=None, project_dict=None, length=False
    ):
        """
        Retrieve multiple entries from the database. May filter on current
        (relative) time or vm resource state.

        **NOTE**: This will not allow filtering for VMs where the time has been not been
        initialized yet, since both that condition and no filter is represented
        with `None`.

        Args:
            filter_time (int): Only return VM information when the current
                               relative time matches this value.
            filter_state (str): Only return VM information when the current
                                vm resource state matches this value.
            project_dict (dict): Only return VM information from these keys.
            length (bool): Should the function return how many VMs are in the list
                           or should it return the list itself.

        Returns:
            list: If length is False, return a list of dictionaries, where each
            dictionary is the same as would be returned for the VM if retrieved
            using `get()`. If length is `True`, returns the length of the list.
        """

        if not project_dict:
            project_dict = {"_id": 0}

        vmms = self.grpc_client.list_vm_mappings()
        ret = []

        for vmm in vmms:
            if filter_time and vmm["current_time"] != filter_time:
                continue
            if filter_state and filter_state not in vmm["state"]:
                continue
            ret.append(vmm)
        if length:
            return len(ret)

        return ret

    def put(
        self,
        server_uuid,
        server_name,
        state=config["vm_resource_manager"]["default_state"],
        current_time="",
        server_address="",
    ):
        """
        Add a set of new VM information to the database.

        Args:
            server_uuid (str): UUID of the VM.
            server_name (str): Hostname of the VM.
            state (str): Vm Resource state the VM starts in. Defaults to the
                         configured default state (located in the FIREWHEEL configuration).
            current_time (str): The current (relative) time for the VM.
                                Defaults to '', meaning the VM has not contacted the
                                server yet.
            server_address (str): The `control_ip` of the host where the VM Resource
                                  is found.
        """
        document = {
            "server_uuid": server_uuid,
            "server_name": server_name,
            "state": state,
            "current_time": current_time,
            "control_ip": server_address,
        }
        self.grpc_client.set_vm_mapping(document)

    def set_vm_state_by_uuid(self, uuid, state):
        """
        Set the VMs current state based on the passed in information.

        Args:
            uuid (str): UUID of the VM.
            state (str): The new state for the VM.

        Returns:
            dict: Dictionary representation of the updated `firewheel_grpc_pb2.VMMapping`.
        """
        vmm = {"server_uuid": uuid, "state": state}
        ret = self.grpc_client.set_vm_state_by_uuid(vmm)
        return ret

    def set_vm_time_by_uuid(self, uuid, time):
        """
        Set the VMs current time based on the passed in information.

        Args:
            uuid (str): UUID of the VM.
            time (str): The new (relative) time for the VM.

        Returns:
            dict: Dictionary representation of the updated `firewheel_grpc_pb2.VMMapping`.
        """
        vmm = {"server_uuid": uuid, "current_time": time}
        ret = self.grpc_client.set_vm_time_by_uuid(vmm)
        return ret

    def get_count_vm_not_ready(self):
        """
        Get the number of VMs that are not yet in the "Configured" state.

        Returns:
            int: The count of VMs which are not in the "Configured" state.
        """
        res = self.grpc_client.count_vm_mappings_not_ready()
        count = res["count"]
        return count

    def prepare_put(self, entry):
        """
        Validate that the provided entry has the necessary fields and if it does
        not, provide details or raise an error in the case of a required field.
        The two required fields are `server_uuid` and `server_name`.

        Args:
            entry (dict): A dictionary which contains a subset of the following fields::

                                    {
                                        'server_uuid': '',
                                        'server_name': '',
                                        'state': '',
                                        'current_time': '',
                                        'control_ip': ''
                                    }

                                Default values apply to `state`, `current_time`, and
                                `control_ip` fields. These values match those in `put()`.
                                Only `server_uuid` and `server_name` fields are
                                required for each entry in the list.

        Returns:
            dict: An entry dictionary which can be put into the database.

        Raises:
            ValueError: If the entry does not contain the `server_uuid` field.
            ValueError: If the entry does not contain the `server_name` field.
        """
        if "server_uuid" not in entry:
            raise ValueError('Each entry must contain a "server_uuid".')
        if "server_name" not in entry:
            raise ValueError('Each entry must contain a "server_name".')

        new_entry = {
            "server_uuid": entry["server_uuid"],
            "server_name": entry["server_name"],
        }

        if "state" not in entry:
            new_entry["state"] = config["vm_resource_manager"]["default_state"]
        else:
            new_entry["state"] = entry["state"]

        if "current_time" not in entry:
            new_entry["current_time"] = ""
        else:
            new_entry["current_time"] = entry["current_time"]

        if "control_ip" not in entry:
            new_entry["control_ip"] = ""
        else:
            new_entry["control_ip"] = entry["control_ip"]
        return new_entry

    def batch_put(self, server_list):
        """
        Add a list of VM information  to the database as a batch update. Each
        entry in the list is a dictionary specifying the relevant information.

        Args:
            server_list (list): List of dictionaries where each entry looks like::

                                    {
                                        'server_uuid': '',
                                        'server_name': '',
                                        'state': '',
                                        'current_time': '',
                                        'control_ip': ''
                                    }

                                Default values apply to the state and `current_time`
                                fields. These values match those in `put()`.
                                Only `server_uuid` and `server_name` fields are
                                required for each entry in the list.
        """
        # Avoid polluting the up-stream data structures.
        for entry in server_list:
            new_entry = self.prepare_put(entry)
            self.put(
                new_entry["server_uuid"],
                new_entry["server_name"],
                state=new_entry["state"],
                current_time=new_entry["current_time"],
                server_address=new_entry["control_ip"],
            )

    def destroy_one(self, server_uuid):
        """
        Remove a single entry from the database.

        Args:
            server_uuid (str): UUID for the entry to remove.
        """
        self.log.debug("Entering vm_mapping_db to remove: %s", server_uuid)
        self.grpc_client.destroy_vm_mapping_by_uuid(server_uuid)
        self.log.debug("Successfully deleted vm_mapping for VM %s", server_uuid)

    def destroy_all(self):
        """
        Remove all content from the database.
        """
        self.log.debug("Entering vm_mapping_db to remove all vm_mappings")
        self.grpc_client.destroy_all_vm_mappings()
        self.log.debug("Successfully deleted vm_mappings")
