"""
Interface to the mapping between VMs, their current (vm resource) state, and other
metadata.
"""

from enum import Enum

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.lib.grpc.firewheel_grpc_client import FirewheelGrpcClient


class VMState(str, Enum):
    """
    Valid virtual machine lifecycle states.

    This enum defines the allowed values that may be reported to the
    infrastructure through ``set_state()``. Each enum member uses a
    string value so it can be passed directly to APIs, logging, and
    comparisons without needing additional conversion.

    States:
        UNINITIALIZED:
            The VM has not yet contacted the server or been set to any state.

        NA:
            The VM Resource Manager is not used for this VM.

        CONFIGURING:
            The VM is currently being configured.

        CONFIGURED:
            The VM configuration has completed successfully. When all
            VMs reach this state, the experiment start time may be set.

        FAILED:
            The VM failed during configuration or could not reach the
            configured state.

        TESTING:
            The VM is currently running tests. This is a user-defined state that may be used
            as desired, but it is not used by the VRM system itself.
    """

    UNINITIALIZED = "uninitialized"
    NA = "n/a"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    FAILED = "failed"
    TESTING = "testing"


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

    def _serialize_vm_mapping_state(self, vmm):
        """
        Convert a VMState enum in a VM mapping into its string value for transport.

        Args:
            vmm (dict): Dictionary representation of a VM mapping.

        Returns:
            dict: A copy of the VM mapping with ``state`` converted to its
            string value when needed.
        """
        serialized = dict(vmm)
        if "state" in serialized and isinstance(serialized["state"], VMState):
            serialized["state"] = serialized["state"].value
        return serialized

    def _deserialize_vm_mapping_state(self, vmm):
        """
        Convert a serialized VM mapping state string back into a VMState enum.

        Args:
            vmm (dict): Dictionary representation of a VM mapping.

        Returns:
            dict: The VM mapping with ``state`` converted to ``VMState`` when
            present.
        """
        if not vmm or "state" not in vmm or vmm["state"] is None:
            return vmm

        deserialized = dict(vmm)
        state = deserialized["state"]

        if isinstance(state, VMState):
            return deserialized

        deserialized["state"] = VMState(state)
        return deserialized

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

        return self._deserialize_vm_mapping_state(vmm)

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
            filter_state (str | VMState): Only return VM information when the current
                               vm resource state matches this value. If a string is
                               provided, substring matching is used against the
                               serialized enum value.
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
            vmm = self._deserialize_vm_mapping_state(vmm)

            if filter_time and vmm["current_time"] != filter_time:
                continue

            if filter_state is not None:
                state = vmm["state"]

                if isinstance(filter_state, VMState):
                    if state != filter_state:
                        continue
                else:
                    filter_text = str(filter_state).lower()
                    if (
                        filter_text not in state.value.lower()
                        and filter_text not in state.name.lower()
                    ):
                        continue

            ret.append(vmm)

        if length:
            return len(ret)

        return ret

    def put(
        self,
        server_uuid,
        server_name,
        state=VMState.UNINITIALIZED,
        current_time="",
        server_address="",
    ):
        """
        Add a set of new VM information to the database.

        Args:
            server_uuid (str): UUID of the VM.
            server_name (str): Hostname of the VM.
            state (VMState | str): Vm Resource state the VM starts in.
                Defaults to :py:attr:`VMState.UNINITIALIZED`.
            current_time (str): The current (relative) time for the VM.
                Defaults to '', meaning the VM has not contacted the server yet.
            server_address (str): The `control_ip` of the host where the VM Resource is found.
        """
        state = VMState(state)

        document = {
            "server_uuid": server_uuid,
            "server_name": server_name,
            "state": state,
            "current_time": current_time,
            "control_ip": server_address,
        }
        self.grpc_client.set_vm_mapping(self._serialize_vm_mapping_state(document))

    def set_vm_state_by_uuid(self, uuid, state):
        """
        Set the VMs current state based on the passed in information.

        Args:
            uuid (str): UUID of the VM.
            state (VMState | str): The new state for the VM.

        Returns:
            dict: Dictionary representation of the updated `firewheel_grpc_pb2.VMMapping`.
        """
        state = VMState(state)
        vmm = {"server_uuid": uuid, "state": state}
        ret = self.grpc_client.set_vm_state_by_uuid(
            self._serialize_vm_mapping_state(vmm)
        )
        return self._deserialize_vm_mapping_state(ret)

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
        return self._deserialize_vm_mapping_state(ret)

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
            new_entry["state"] = VMState.UNINITIALIZED
        else:
            new_entry["state"] = VMState(entry["state"])

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
        Add a list of VM information to the database as a batch update. Each
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
