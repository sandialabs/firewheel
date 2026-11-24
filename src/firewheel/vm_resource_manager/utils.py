"""
Utility functions for common high-level operations performed by the Vm Resource
Manager.

These are high-level functions that may be useful in Modules, but should not be
needed outside the *VM Resource Manager* and its Modules.
"""

from contextlib import closing, nullcontext

from firewheel.vm_resource_manager.vm_mapping import VMMapping


def managed_resource(resource, factory):
    """
    Return a context manager for a resource that may have been caller-supplied.

    If ``resource`` is provided it is used as-is and is **never** closed, since the
    caller owns it. Otherwise ``factory()`` is called to create a new resource,
    which is closed when the ``with`` block exits, including when it exits with
    an exception.

    Args:
        resource (object): A caller-supplied resource, or None.
        factory (Callable[[], object]): Creates a new resource with a ``close()``
            method. Any exception it raises (e.g. ``ConnectionError``)
            propagates immediately, before the ``with`` block is entered.

    Returns:
        contextlib.AbstractContextManager: Yields the resource to use.
    """
    if resource is not None:
        return nullcontext(resource)
    return closing(factory())


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
    with managed_resource(mapping, VMMapping) as vm_mapping:
        current_record = vm_mapping.set_vm_state_by_uuid(vm_uuid, new_state)
    if current_record is None:
        raise RuntimeError(
            "Unexpected lack of database entry--I do not have enough parameters!"
        )

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
        ValueError: If ``new_time`` cannot be converted to an integer.
    """
    # Validate before opening a connection so bad input never creates one.
    db_time = str(int(new_time))

    with managed_resource(mapping, VMMapping) as vm_mapping:
        current_record = vm_mapping.set_vm_time_by_uuid(vm_uuid, db_time)
    if current_record is None:
        raise RuntimeError(
            "Unexpected lack of database entry while updating "
            "time--I do not have enough parameters!"
        )

    if log:
        log.debug("Set VM %s to time %s", vm_uuid, new_time)


def add_execution_issue(vm_uuid, issue_message, mapping=None, log=None):
    """
    Record a non-fatal vm_resource execution issue for a VM.

    Args:
        vm_uuid (str): The UUID of the VM to update.
        issue_message (str): A short execution issue description.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Raises:
        RuntimeError: If the VMMapping database could not be created.
    """
    with managed_resource(mapping, VMMapping) as vm_mapping:
        current_record = vm_mapping.add_execution_issue_by_uuid(vm_uuid, issue_message)
    if current_record is None:
        raise RuntimeError(
            "Unexpected lack of database entry while updating execution issue metadata!"
        )

    if log:
        log.debug(
            "Recorded vm_resource execution issue on VM %s: %s", vm_uuid, issue_message
        )


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
    with managed_resource(mapping, VMMapping) as vm_mapping:
        count = vm_mapping.get_count_vm_not_ready()

    if log:
        log.debug("Number of VMs that are not ready is: %s", count)

    return count
