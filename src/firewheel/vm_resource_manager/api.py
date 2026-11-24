"""
Public interface for interacting with the *VM Resource Manager*. These
functions should be callable with only information available from experiment
*Control*.
"""

from firewheel.vm_resource_manager.utils import managed_resource
from firewheel.vm_resource_manager.vm_mapping import VMState, VMMapping
from firewheel.vm_resource_manager.schedule_db import ScheduleDb
from firewheel.vm_resource_manager.experiment_start import ExperimentStart
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


def add_vm(
    server_uuid, server_name, control_ip, use_vm_manager=True, mapping=None, log=None
):
    """
    Add a VM to the vm resource database.

    The VM is in the default vm resource state (uninitialized) after insertion.

    Args:
        server_uuid (str): The uuid of the VM, as specified in the *Control* graph.
        server_name (str): The name of the system, as specified in the *Control* graph.
        control_ip (str): The address for this VM on the control network.
        use_vm_manager (bool): This VM uses the *VM Resource Manager*. If False, the
                    vm resource state is set to 'N/A' and the VM is subsequently
                    ignored for *VM Resource Manager* calculations like experiment
                    start time. Default is True.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.
    """
    if use_vm_manager:
        state = VMState.UNINITIALIZED
    else:
        state = VMState.NA

    with managed_resource(mapping, VMMapping) as vm_mapping:
        vm_mapping.put(server_uuid, server_name, state=state, server_address=control_ip)

    if log:
        log.debug("Added VM %s to the VM mapping database.", server_uuid)


def destroy_all(
    mapping=None,
    schedule=None,
    start=None,
    log=None,
    ignore_grpc_connection_errors=False,
):
    """
    Clears the VMMapping, Schedule, and ExperimentStart databases.

    All arguments are only present to enable unit testing and may be safely
    ignored.

    Args:
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        schedule (ScheduleDb):ScheduleDb instance to use as a database. Present
                    for unit testing, safely ignored.
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
                for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.
        ignore_grpc_connection_errors (bool): Whether to ignore gRPC errors or not.

    Raises:
        ConnectionError: If `ignore_grpc_connection_errors=False` and there is an error
            connecting to the gRPC server.
    """
    try:
        mapping_ctx = managed_resource(mapping, VMMapping)
    except ConnectionError:
        if not ignore_grpc_connection_errors:
            raise
    else:
        with mapping_ctx as vm_mapping:
            vm_mapping.destroy_all()

    with managed_resource(schedule, ScheduleDb) as schedule_db:
        schedule_db.destroy_all()

    try:
        start_ctx = managed_resource(start, ExperimentStart)
    except ConnectionError:
        if not ignore_grpc_connection_errors:
            raise
    else:
        with start_ctx as experiment_start:
            experiment_start.clear_start_time()

    if log:
        log.debug("Cleared all databases.")


def get_vm_times(filter_time=None, mapping=None, log=None):
    """
    Get the current negative times of known VMs.

    Args:
        filter_time (int | str | None): Return only VMs with this time value. ``0`` and
            ``"0"`` are equivalent. ``None`` or ``""`` returns all VMs.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Returns:
        dict: Dictionary keyed on server name, values of the current negative time for
        that VM.
    """
    with managed_resource(mapping, VMMapping) as vm_mapping:
        results = vm_mapping.get_all(filter_time=filter_time)

    vm_dict = {}
    for vm in results:
        vm_dict[vm["server_name"]] = vm["current_time"]

    if log:
        log.debug("Got the negative vm resource times.")

    return vm_dict


def get_vm_states(filter_state=None, mapping=None, log=None):
    """
    Get the current vm resources state of all known VMs.

    Args:
        filter_state (str): Only return VMs in this state.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Returns:
        dict: A dictionary keyed on the VM server name, with string values for
        the vm resources state.
    """
    vm_dict = get_vm_statuses(filter_state=filter_state, mapping=mapping, log=log)
    return {vm_name: vm_info["state"] for vm_name, vm_info in vm_dict.items()}


def get_vm_statuses(filter_state=None, mapping=None, log=None):
    """
    Get the current vm resources lifecycle state and execution issue metadata of all
    known VMs.

    Args:
        filter_state (str): Only return VMs in this state.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Returns:
        dict: Dictionary keyed on VM server name, where each value contains the
        vm_resource lifecycle state and execution issue metadata.
    """
    with managed_resource(mapping, VMMapping) as vm_mapping:
        results = vm_mapping.get_all(filter_state=filter_state)

    vm_dict = {}
    for vm in results:
        vm_dict[vm["server_name"]] = {
            "state": vm["state"],
            "has_execution_issues": vm.get("has_execution_issues", False),
            "execution_issue_count": vm.get("execution_issue_count", 0),
            "last_execution_issue": vm.get("last_execution_issue", ""),
        }

    if log:
        log.debug("Got the vm statuses.")

    return vm_dict


def get_experiment_launch_time(start=None):
    """
    Get the launch time of the currently running experiment.
    All parameters to this function are only present to enable unit testing and
    may be safely ignored.

    Args:
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
                for unit testing, safely ignored.

    Returns:
        datetime.datetime: A datetime object containing the launch time for the
        currently running experiment. The time is defined to be in the UTC time zone.
        None if no launch time has been determined yet.
    """
    with managed_resource(start, ExperimentStart) as experiment_start:
        return experiment_start.get_launch_time()


def set_experiment_launch_time(start=None):
    """
    Set the launch time of the currently running experiment.
    All parameters to this function are only present to enable unit testing and
    may be safely ignored.

    Args:
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
             for unit testing, safely ignored.

    Returns:
        datetime.datetime: A datetime object containing the launch time for the
        currently running experiment. The time is defined to be in the UTC time zone.
    """
    with managed_resource(start, ExperimentStart) as experiment_start:
        return experiment_start.set_launch_time()


def get_experiment_start_time(start=None):
    """
    Get the start time of the currently running experiment.
    All parameters to this function are only present to enable unit testing and
    may be safely ignored.

    Args:
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
                for unit testing, safely ignored.

    Returns:
        datetime.datetime: A datetime object containing the start time for the
        currently running experiment. The time is defined to be in the UTC time zone.
        None if no start time has been determined yet.
    """
    with managed_resource(start, ExperimentStart) as experiment_start:
        return experiment_start.get_start_time()


def add_experiment_start_time(start=None):
    """
    Set the start time of the currently running experiment.
    All parameters to this function are only present to enable unit testing and
    may be safely ignored.

    Args:
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
                for unit testing, safely ignored.

    Returns:
        datetime.datetime: A datetime object containing the start time for the
        currently running experiment. The time is defined to be in the UTC time zone.
    """
    with managed_resource(start, ExperimentStart) as experiment_start:
        return experiment_start.add_start_time()


def get_experiment_time_to_start(start=None):
    """
    Get the time it took for the experiment to configure.
    All parameters to this function are only present to enable unit testing and
    may be safely ignored.

    Args:
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
                for unit testing, safely ignored.

    Returns:
        int: The time in seconds from when the experiment launched to configured.
        None if experiment hasn't started yet.
    """
    with managed_resource(start, ExperimentStart) as experiment_start:
        return experiment_start.get_time_to_start()


def get_experiment_time_since_start(start=None):
    """
    Get the time since the experiment configured.
    All parameters to this function are only present to enable unit testing and
    may be safely ignored.

    Args:
        start (ExperimentStart): ExperimentStart instance to use as a database. Present
            for unit testing, safely ignored.

    Returns:
        int: The time in seconds since when the experiment configured.
        None if experiment hasn't started yet.
    """
    with managed_resource(start, ExperimentStart) as experiment_start:
        return experiment_start.get_time_since_start()


def vm_resource_list(store=None, log=None):
    """
    List the available vm resources in the VmResourceStore.
    All parameters to this function all only present to enable unit testing and
    may be safely ignored.

    Args:
        store (VmResourceStore): VmResourceStore instance to use as a database.
            Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Returns:
        list: A list of (unique) file names in the VmResourceStore.
    """
    if store is None:
        store = VmResourceStore()

    items = list(store.list_distinct_contents())

    if log:
        log.debug("Got the vm resource list: %s", items)

    return items


def add_vm_resource_file(filename, store=None, log=None):
    """
    Add a file to the VmResourceStore.

    Args:
        filename (str): The path to the (locally stored) file to add to the VmResourceStore.
        store (VmResourceStore): VmResourceStore instance to use as a database.
            Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.
    """
    if store is None:
        store = VmResourceStore()

    store.add_file(filename)

    if log:
        log.debug("Added %s to the VmResourceStore", filename)
