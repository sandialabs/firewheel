"""
Utility functions for common high-level operations performed by the Vm Resource
Manager.

These are high-level functions that may be useful in Modules, but should not be
needed outside the *VM Resource Manager* and its Modules.
"""

from firewheel.vm_resource_manager.vm_mapping import VMMapping


def set_vm_state(vm_uuid, new_state, mapping=None, log=None):
    """
    Set the vm_resources state of a given VM.

    Args:
        vm_uuid (str): The UUID of the VM to set the state of.
        new_state (str): A string representing the new vm_resources state of the VM. There is
                    no validation for strings matching expected states.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Raises:
        RuntimeError: If the VMMapping database could not be created.
    """
    close = False
    if mapping is None:
        close = True
        mapping = VMMapping()

    current_record = mapping.set_vm_state_by_uuid(vm_uuid, new_state)
    if current_record is None:
        raise RuntimeError(
            "Unexpected lack of database entry--I do not have enough parameters!"
        )
    if close:
        mapping.close()

    if log:
        log.debug("Set VM %s to state %s", vm_uuid, new_state)


def set_vm_time(vm_uuid, new_time, mapping=None, log=None):
    """
    Set the current time reported by a VM.

    Args:
        vm_uuid (str): The uuid of the VM to set the state of.
        new_time (str): A string representing the current time.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Raises:
        RuntimeError: If the VMMapping database could not be created.
    """
    close = False
    if mapping is None:
        close = True
        mapping = VMMapping()

    db_time = str(int(new_time))

    current_record = mapping.get(server_uuid=vm_uuid)
    if current_record is None:
        raise RuntimeError(
            "Unexpected lack of database entry while updating "
            "time--I do not have enough parameters!"
        )

    mapping.put(
        current_record["server_uuid"],
        current_record["server_name"],
        current_record["state"],
        db_time,
        current_record["control_ip"],
    )
    if close:
        mapping.close()

    if log:
        log.debug("Set VM %s to time %s", vm_uuid, new_time)


def get_vm_count_not_ready(mapping=None, log=None):
    """
    Returns the number of VMs not in the "configured" or "N/A" states. These
    VMs are not ready in the sense that they are not prepared to begin the
    experiment (set an experiment schedule start time).
    For reference: The configured state means the bootstrap vm_resource has completed
    all negative-start-time vm_resources and checked in as ready and the N/A state
    means there is no vm_resource system present on a VM.

    Args:
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Returns:
        str: Count of the number of VMs not in the "VMState.CONFIGURED" or
             "VMState.NA" vm_resources state.
    """
    close = False
    if mapping is None:
        close = True
        mapping = VMMapping()
    count = mapping.get_count_vm_not_ready()
    if close:
        mapping.close()

    if log:
        log.debug("Number of VMs that are not ready is: %s", count)

    return count
