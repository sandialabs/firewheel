"""
Public interface for interacting with the *VM Resource Manager*. These
functions should be callable with only information available from experiment
*Control*.
"""

from firewheel.config import config
from firewheel.vm_resource_manager.vm_mapping import VMMapping, VMState
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

    close = False
    if mapping is None:
        close = True
        mapping = VMMapping()

    mapping.put(server_uuid, server_name, state=state, server_address=control_ip)

    if log:
        log.debug("Added VM %s to the VM mapping database.", server_uuid)

    if close:
        mapping.close()


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
    skip_mapping = False
    if mapping is None:
        close = True
        try:
            mapping = VMMapping()
        except ConnectionError as exp:
            if ignore_grpc_connection_errors:
                skip_mapping = True
            else:
                raise exp

    if not skip_mapping:
        mapping.destroy_all()

    close = False
    if schedule is None:
        close = True
        schedule = ScheduleDb()

    schedule.destroy_all()
    if close:
        schedule.close()

    skip_start = False
    if start is None:
        try:
            start = ExperimentStart()
        except ConnectionError as exp:
            if ignore_grpc_connection_errors:
                skip_start = True
            else:
                raise exp
    if not skip_start:
        start.clear_start_time()

    if log:
        log.debug("Cleared all databases.")


def get_vm_times(filter_time=None, mapping=None, log=None):
    """
    Get the current negative times of known VMs.

    Args:
        filter_time (int): Return only VMs with this negative time value.
        mapping (firewheel.vm_resource_manager.vm_mapping.VMMapping): VMMapping instance
            to use as a database. Present for unit testing, safely ignored.
        log (logging.Logger): An optional logger that can to output results.

    Returns:
        dict: Dictionary keyed on server name, values of the current negative time for
        that VM.
    """
    close = False
    if mapping is None:
        close = True
        mapping = VMMapping()

    results = mapping.get_all(filter_time=filter_time)

    project_dict = {"_id": 0, "server_name": 1, "current_time": 1}
    results = mapping.get_all(filter_time=filter_time, project_dict=project_dict)

    if close:
        mapping.close()

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
    close = False
    if mapping is None:
        close = True
        mapping = VMMapping()

    project_dict = {"_id": 0, "server_name": 1, "state": 1}
    results = mapping.get_all(filter_state=filter_state, project_dict=project_dict)

    if close:
        mapping.close()

    vm_dict = {}
    for vm in results:
        vm_dict[vm["server_name"]] = vm["state"]

    if log:
        log.debug("Got the vm states.")

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
    if start is None:
        start = ExperimentStart()
    return start.get_launch_time()


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
    if start is None:
        start = ExperimentStart()
    return start.set_launch_time()


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
    if start is None:
        start = ExperimentStart()
    return start.get_start_time()


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
    if start is None:
        start = ExperimentStart()
    return start.add_start_time()


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
    if start is None:
        start = ExperimentStart()
    return start.get_time_to_start()


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
    if start is None:
        start = ExperimentStart()
    return start.get_time_since_start()


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
    close = False
    if store is None:
        close = True
        store = VmResourceStore()

    items = list(store.list_distinct_contents())

    if close:
        store.close()

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
