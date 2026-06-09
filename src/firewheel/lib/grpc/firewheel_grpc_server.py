import os
import copy
import time
import threading
import contextlib
from typing import Iterable
from datetime import datetime, timezone
from concurrent import futures
from importlib.metadata import version

import grpc

from firewheel.config import Config
from firewheel.lib.log import Log
from firewheel.lib.grpc import firewheel_grpc_pb2, firewheel_grpc_pb2_grpc
from firewheel.vm_resource_manager.vm_mapping import VMState


class FirewheelServicer(firewheel_grpc_pb2_grpc.FirewheelServicer):
    """
    The Servicer for the Firewheel GRPC Service.
    """

    def get_vm_mapping(self, db, uuid):
        """
        Returns the vm_mapping object associated with the given db and uuid.

        Args:
            db (dict): The database to search.
            uuid (str): The key to search on.

        Returns:
            firewheel_grpc_pb2.VMMapping: The found vm_mapping, or None on KeyError.
        """
        try:
            vm_mapping = db[uuid]
        except KeyError as exp:
            self.log.exception(exp)
            return None
        return vm_mapping

    def __init__(self):
        """
        Initialize the Servicer.
        """
        self.log = Log(
            name="FirewheelServicer",
            log_format="%(asctime)s %(levelname)s: [%(funcName)s]: %(message)s",
        ).log

        config = Config().get_config()

        self.log.info("Initialized FirewheelServicer log.")
        self.server_start_time = datetime.now(timezone.utc)
        self.version = version("firewheel")
        self.cache_dir = os.path.join(
            config["grpc"]["root_dir"], config["grpc"]["cache_dir"]
        )
        os.makedirs(self.cache_dir, exist_ok=True)

        # Protect all shared in-memory DB structures.
        # This server runs RPC handlers in a ThreadPoolExecutor, so concurrent
        # access/mutation is possible.
        self._db_lock = threading.RLock()

        self.dbs = {}
        for db in ["test", "prod"]:
            os.makedirs(os.path.join(self.cache_dir, db), exist_ok=True)
            self._init_db(db)

    def _init_db(self, db_name):
        """
        Initializes the database with name db_name.

        Args:
            db_name (str): The name of the database to initialize.
        """
        with self._db_lock:
            self.dbs[db_name] = {
                "vm_mappings": {},
                "not_ready_vmms": set(),
                "ready_states": {VMState.NA.value, VMState.CONFIGURED.value},
                "experiment_start_time": None,
                "experiment_launch_time": None,
            }

    def GetInfo(self, request, context):  # noqa: N802,ARG002
        """
        Returns general server info on version, uptime, and whether
        there is a currently running experiment.

        Args:
            request (firewheel_grpc_pb2.GetInfoRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.GetInfoResponse: The server info.
        """
        uptime = datetime.now(timezone.utc) - self.server_start_time
        uptime = uptime.total_seconds()

        with self._db_lock:
            experiment_running = bool(
                self.dbs["prod"]["experiment_launch_time"] is not None
            )

        response = firewheel_grpc_pb2.GetInfoResponse(
            version=self.version, uptime=uptime, experiment_running=experiment_running
        )
        return response

    def SetExperimentLaunchTime(self, request, context):  # noqa: N802,ARG002
        """
        Sets the experiment launch time.

        Args:
            request (firewheel_grpc_pb2.ExperimentLaunchTime): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.ExperimentLaunchTime: The set experiment launch time.
        """
        db = request.db
        with self._db_lock:
            self.dbs[db]["experiment_launch_time"] = request
            return self.dbs[db]["experiment_launch_time"]

    def GetExperimentLaunchTime(self, request, context):  # noqa: N802,ARG002
        """
        Gets the experiment launch time.

        Args:
            request (firewheel_grpc_pb2.GetExperimentLaunchTimeRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.ExperimentLaunchTime: The set experiment launch time
            or None on failure.
        """
        db = request.db
        with self._db_lock:
            if self.dbs[db]["experiment_launch_time"] is not None:
                return self.dbs[db]["experiment_launch_time"]

        error_details = "IndexError. No launch time available yet."
        error_code = grpc.StatusCode.OUT_OF_RANGE
        context.abort(code=error_code, details=error_details)
        return None

    def SetExperimentStartTime(self, request, context):  # noqa: N802,ARG002
        """
        Atomically initializes the experiment start time if it has not already
        been set. If a start time already exists, returns the existing value.

        Args:
            request (firewheel_grpc_pb2.ExperimentStartTime): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.ExperimentStartTime: The existing or newly set
            experiment start time.
        """
        db = request.db
        with self._db_lock:
            if self.dbs[db]["experiment_start_time"]:
                return self.dbs[db]["experiment_start_time"]

            self.dbs[db]["experiment_start_time"] = request
            return self.dbs[db]["experiment_start_time"]

    def GetExperimentStartTime(self, request, context):  # noqa: N802,ARG002
        """
        Gets the experiment start time.

        Args:
            request (firewheel_grpc_pb2.GetExperimentStartTimeRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.ExperimentStartTime: The set experiment start time.
        """
        db = request.db
        with self._db_lock:
            with contextlib.suppress(IndexError):
                return self.dbs[db]["experiment_start_time"]

        error_details = "IndexError. No start time available yet."
        error_code = grpc.StatusCode.OUT_OF_RANGE
        context.abort(code=error_code, details=error_details)

        return None

    def InitializeExperimentStartTime(self, request, context):  # noqa: N802,ARG002
        """
        Initializes the experiment timing state.

        Args:
            request (firewheel_grpc_pb2.InitializeExperimentStartTimeRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.InitializeExperimentStartTimeResponse: Empty message on success.
        """
        db = request.db
        with self._db_lock:
            with contextlib.suppress(KeyError):
                self.dbs[db]["experiment_launch_time"] = None
            with contextlib.suppress(KeyError):
                self.dbs[db]["experiment_start_time"] = None
        return firewheel_grpc_pb2.InitializeExperimentStartTimeResponse()

    def CountVMMappingsNotReady(self, request, context):  # noqa: N802,ARG002
        """
        Returns the count of VMs that are not ready.

        Args:
            request (firewheel_grpc_pb2.CountVMMappingsNotReadyRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.CountVMMappingsNotReadyResponse: Message containing the
            count of the not ready VMs.
        """
        db = request.db
        with self._db_lock:
            count = len(self.dbs[db]["not_ready_vmms"])

        resp = firewheel_grpc_pb2.CountVMMappingsNotReadyResponse(count=count)
        return resp

    def GetVMMappingByUUID(self, request, context):  # noqa: N802,ARG002
        """
        Gets the vm_mapping associated with the given uuid.

        Args:
            request (firewheel_grpc_pb2.VMMappingUUID): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.VMMapping: The found vm_mapping or None on failure.
        """
        db = request.db
        with self._db_lock:
            vm_mapping = self.get_vm_mapping(
                self.dbs[db]["vm_mappings"], request.server_uuid
            )
            if vm_mapping:
                return copy.deepcopy(vm_mapping)

        error_details = f"IndexError. No vm_mapping found for {request.server_uuid}"
        error_code = grpc.StatusCode.OUT_OF_RANGE
        context.abort(code=error_code, details=error_details)
        return None

    def SetVMTimeByUUID(self, request, context):  # noqa: N802,ARG002
        """
        Sets the time for the vm_mapping associated with the given uuid.

        Args:
            request (firewheel_grpc_pb2.SetVMTimeByUUIDRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.VMMapping: The updated vm_mapping.
        """
        db = request.db
        with self._db_lock:
            try:
                self.dbs[db]["vm_mappings"][
                    request.server_uuid
                ].current_time = request.current_time
                return copy.deepcopy(self.dbs[db]["vm_mappings"][request.server_uuid])
            except KeyError:
                error_details = (
                    f"IndexError. No vm_mapping found for {request.server_uuid}"
                )
                error_code = grpc.StatusCode.OUT_OF_RANGE
                context.abort(code=error_code, details=error_details)

        return None

    def _update_not_ready_vmms(self, vmm, db):
        """
        Updates the number of VMs that are ready and not ready.

        Args:
            vmm (firewheel_grpc_pb2.SetVMStateByUUIDRequest): The VMM request object.
            db (str): The database that this client will be using. (e.g. "prod" or "test")
        """
        if vmm.state not in self.dbs[db]["ready_states"]:
            self.dbs[db]["not_ready_vmms"].add(vmm.server_uuid)
        else:
            with contextlib.suppress(KeyError):
                self.dbs[db]["not_ready_vmms"].remove(vmm.server_uuid)

    def SetVMStateByUUID(self, request, context):  # noqa: N802,ARG002
        """
        Sets the state for the vm_mapping associated with the given uuid.

        Args:
            request (firewheel_grpc_pb2.SetVMStateByUUIDRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.VMMapping: The updated vm_mapping.
        """
        with self._db_lock:
            try:
                db = request.db
                self._update_not_ready_vmms(request, db)
                vmm = self.dbs[db]["vm_mappings"][request.server_uuid]
                vmm.state = request.state
                return copy.deepcopy(vmm)
            except KeyError:
                error_details = (
                    f"IndexError. No vm_mapping found for {request.server_uuid}"
                )
                error_code = grpc.StatusCode.OUT_OF_RANGE
                context.abort(code=error_code, details=error_details)

        return None

    def DestroyVMMappingByUUID(self, request, context):  # noqa: N802,ARG002
        """
        Destroys the vm_mapping associated with the given uuid.

        Args:
            request (firewheel_grpc_pb2.VMMappingUUID): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.DestroyVMMappingResponse: Empty message on success.
        """
        db = request.db
        with self._db_lock:
            with contextlib.suppress(KeyError):
                self.dbs[db]["not_ready_vmms"].remove(request.server_uuid)

            try:
                del self.dbs[db]["vm_mappings"][request.server_uuid]
            except KeyError as exp:
                self.log.debug(
                    "in DestroyVMMappingByUUID, no key for %s, exp=%s",
                    request.server_uuid,
                    exp,
                )

        return firewheel_grpc_pb2.DestroyVMMappingResponse()

    def SetVMMapping(self, request, context):  # noqa: N802,ARG002
        """
        Sets the given vm_mapping.

        Args:
            request (firewheel_grpc_pb2.VMMapping): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.VMMapping: The set vm_mapping.
        """
        db = request.db
        with self._db_lock:
            self._update_not_ready_vmms(request, db)
            self.dbs[db]["vm_mappings"][request.server_uuid] = copy.deepcopy(request)
            return copy.deepcopy(self.dbs[db]["vm_mappings"][request.server_uuid])

    def ListVMMappings(  # noqa: N802
        self,
        request,
        context,  # noqa: ARG002
    ) -> Iterable[firewheel_grpc_pb2.VMMapping]:
        """
        Iterates through all requested vm_mappings.

        Args:
            request (firewheel_grpc_pb2.ListVMMappingsRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Yields:
            firewheel_grpc_pb2.VMMapping: The iterated vm_mappings.
        """
        db = request.db
        with self._db_lock:
            current_vm_mappings = copy.deepcopy(self.dbs[db]["vm_mappings"])

        yield from current_vm_mappings.values()

    def DestroyAllVMMappings(self, request, context):  # noqa: N802,ARG002
        """
        Destroys all vm_mappings.

        Args:
            request (firewheel_grpc_pb2.DestroyAllVMMappingsRequest): The gRPC request.
            context (grpc._server._Context): The gRPC context.

        Returns:
            firewheel_grpc_pb2.DestroyAllVMMappingsReponse: Empty message on success.
        """
        db = request.db
        with self._db_lock:
            with contextlib.suppress(KeyError):
                self.dbs[db]["vm_mappings"] = {}
            with contextlib.suppress(KeyError):
                self.dbs[db]["not_ready_vmms"] = set()
        return firewheel_grpc_pb2.DestroyAllVMMappingsResponse()


def serve():
    """
    Initializes the gRPC server and servicer.
    Starts the server.
    """
    servicer = FirewheelServicer()
    servicer.log.info("Initialized servicer")
    config = Config().get_config()

    # 100 MB max message size and ensure only one server is running
    # See: https://github.com/grpc/grpc/issues/16920#issuecomment-432837463
    options = [("grpc.max_message_length", 100 * 1024 * 1024), ("grpc.so_reuseport", 0)]
    threads = 2
    # Override threads if a value is specified in the config.
    try:
        threads = int(config["grpc"]["threads"])
        servicer.log.debug(
            "Loaded threads from grpc.threads. Setting max_workers=%s", threads
        )
    except (KeyError, ValueError, TypeError) as exp:
        servicer.log.exception(exp)
        servicer.log.debug(
            "Unable to use the config setting for grpc.threads. Defaulting to %s.",
            threads,
        )

    # pylint: disable=consider-using-with
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=threads), options=options
    )

    firewheel_grpc_pb2_grpc.add_FirewheelServicer_to_server(servicer, server)
    hostname = config["grpc"]["hostname"]
    port = config["grpc"]["port"]
    bind_addr = f"{hostname}:{port}"
    try:
        server.add_insecure_port(bind_addr)
    except RuntimeError:
        servicer.log.warning(
            "Failed to start server on %s. Another server may be bound to that address.",
            bind_addr,
        )
        return

    server.start()
    servicer.log.info("Started server. Listening on %s.", bind_addr)

    try:
        while True:
            time.sleep(60 * 60)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
