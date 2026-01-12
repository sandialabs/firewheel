import grpc
from google.protobuf.timestamp_pb2 import Timestamp  # pylint: disable=no-name-in-module

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.lib.grpc import firewheel_grpc_pb2, firewheel_grpc_pb2_grpc
from firewheel.lib.grpc.firewheel_grpc_resources import msg_to_dict


class FirewheelGrpcClient:
    """
    A client to interact with the FirewheelGrpcServicer.
    """

    def __init__(
        self,
        hostname=config["grpc"]["hostname"],
        port=config["grpc"]["port"],
        db=config["grpc"]["db"],
        log=None,
        require_connection=True,
    ):
        """
        Initializes the client.

        Args:
            hostname (str): The gRPC server's hostname.
            port (str): The gRPC server's port.
            db (str): The database that this client will be using. (e.g. "prod" or "test").
            log (logging.Logger): A log the client can use.
            require_connection (bool): Check whether or not to raise an error on a
                missing connection.

        Raises:
            RuntimeError: If the gRPC port is out of range.
        """
        if int(port) < 1 or int(port) > 65535:
            raise RuntimeError(f"The gRPC port={port} is out of range.")
        self.db = db
        self.server_addr = f"{hostname}:{port}"
        self.chan = grpc.insecure_channel(self.server_addr)
        self.stub = firewheel_grpc_pb2_grpc.FirewheelStub(self.chan)
        if log:
            self.log = log
        else:
            self.log = Log(name="FirewheelGrpcClient").log

        self.connected = self.check_connection(error=require_connection)

    def check_connection(self, error=True):
        """
        Check on whether a connection exists to the gRPC server.

        Args:
            error (bool): Whether to raise an exception on a missing connection.

        Returns:
            bool: True if a connection exists, False otherwise.

        Raises:
            ConnectionError: If the connection cannot be started
                (and `error=True`).  # noqa: DAR401,DAR402
        """
        info = self.get_info()
        if info:
            return True
        exp_str = (
            f"Unable to get info from gRPC server at {self.server_addr}. "
            "It may need to be started with `firewheel start`."
        )
        exp = ConnectionError(exp_str)
        self.log.error(exp)
        if error:
            raise exp
        return False

    def get_info(self):
        """
        Requests general gRPC server info.

        Returns:
            dict: Dictionary representation of `firewheel_grpc_pb2.GetInfoResponse`.
        """
        try:
            req = firewheel_grpc_pb2.GetInfoRequest()
            response = self.stub.GetInfo(req)
            response_dict = msg_to_dict(response)
        except grpc.RpcError as exp:
            if exp.exception().code() != grpc.StatusCode.UNAVAILABLE:
                self.log.exception(exp)
            return None
        return response_dict

    def get_experiment_launch_time(self):
        """
        Requests the `experiment_launch_time`.

        Returns:
            datetime.datetime: The datetime that the experiment was launched.
        """
        req = firewheel_grpc_pb2.GetExperimentLaunchTimeRequest(db=self.db)
        try:
            experiment_launch_time = self.stub.GetExperimentLaunchTime(req)
            experiment_launch_time_dt = experiment_launch_time.launch_time.ToDatetime()
        except grpc.RpcError as exp:
            if exp.exception().code() != grpc.StatusCode.OUT_OF_RANGE:
                self.log.exception(exp)
            return None
        return experiment_launch_time_dt

    def get_experiment_start_time(self):
        """
        Requests the `experiment_start_time`.

        Returns:
            datetime.datetime: The datetime that the experiment was started.
        """
        req = firewheel_grpc_pb2.GetExperimentStartTimeRequest(db=self.db)
        try:
            experiment_start_time = self.stub.GetExperimentStartTime(req)
            experiment_start_time_dt = experiment_start_time.start_time.ToDatetime()
        except grpc.RpcError as exp:
            if exp.exception().code() != grpc.StatusCode.OUT_OF_RANGE:
                self.log.exception(exp)
            return None
        return experiment_start_time_dt

    def set_experiment_launch_time(self, launch_time_dt):
        """
        Requests to set the `experiment_launch_time`.

        Args:
            launch_time_dt (datetime.datetime): The datetime that the experiment was launched.

        Returns:
            datetime.datetime: The datetime that the experiment was launched.
        """
        launch_time_msg = Timestamp()
        launch_time_msg.FromDatetime(launch_time_dt)
        req = firewheel_grpc_pb2.ExperimentLaunchTime(
            launch_time=launch_time_msg, db=self.db
        )
        experiment_launch_time = self.stub.SetExperimentLaunchTime(req)
        experiment_launch_time_dt = experiment_launch_time.launch_time.ToDatetime()
        return experiment_launch_time_dt

    def set_experiment_start_time(self, start_time_dt):
        """
        Requests to set the `experiment_start_time`.

        Args:
            start_time_dt (datetime.datetime): The datetime that the experiment was started.

        Returns:
            datetime.datetime: The datetime that the experiment was started.
        """
        start_time_msg = Timestamp()
        start_time_msg.FromDatetime(start_time_dt)
        req = firewheel_grpc_pb2.ExperimentStartTime(
            start_time=start_time_msg, db=self.db
        )
        experiment_start_time = self.stub.SetExperimentStartTime(req)
        experiment_start_time_dt = experiment_start_time.start_time.ToDatetime()
        return experiment_start_time_dt

    def clear_db(self):
        """
        Clear the gRPC database.

        This method essentially calls :meth:`initialize_experiment_start_time` and
        :meth:`destroy_all_vm_mappings`.

        Returns:
            Tuple: Contains the response codes
            (:meth:`initialize_experiment_start_time`, :meth:`destroy_all_vm_mappings`)
        """
        res_1 = self.initialize_experiment_start_time()
        res_3 = self.destroy_all_vm_mappings()
        return (res_1, res_3)

    def initialize_experiment_start_time(self):
        """
        Requests to initialize the `experiment_start_time`.

        Returns:
            dict: Dictionary representation of
            `firewheel_grpc_pb2.InitializeExperimentStartTimeResponse`. Empty on success.
        """
        req = firewheel_grpc_pb2.InitializeExperimentStartTimeRequest(db=self.db)
        response = self.stub.InitializeExperimentStartTime(req)
        response = msg_to_dict(response)
        return response

    def destroy_all_vm_mappings(self):
        """
        Requests to destroy all `vm_mappings`.

        Returns:
            dict: Dictionary representation of
            `firewheel_grpc_pb2.DestroyAllVMMappingsReponse`. Empty on success.
        """
        req = firewheel_grpc_pb2.DestroyAllVMMappingsRequest(db=self.db)

        response = self.stub.DestroyAllVMMappings(req)
        return msg_to_dict(response)

    def list_vm_mappings(self):
        """
        Requests to list all `vm_mappings`.

        Returns:
            (list) Dictionary representations of `firewheel_grpc_pb2.VMMapping`.
        """
        req = firewheel_grpc_pb2.ListVMMappingsRequest(db=self.db)

        vm_mappings = self.stub.ListVMMappings(req)
        vm_mappings = [msg_to_dict(vmm) for vmm in vm_mappings]
        return vm_mappings

    def set_vm_mapping(self, vmm):
        """
        Requests to set a given vm_mapping.

        Args:
            vmm (dict): Dictionary representation of vm_mapping.

        Returns:
            (dict) Dictionary representation `firewheel_grpc_pb2.VMMapping`.
        """
        mapping = firewheel_grpc_pb2.VMMapping(
            server_uuid=vmm["server_uuid"],
            server_name=vmm["server_name"],
            control_ip=vmm["control_ip"],
            state=vmm["state"],
            current_time=vmm["current_time"],
            db=self.db,
        )
        resp = self.stub.SetVMMapping(mapping)
        return msg_to_dict(resp)

    def get_vm_mapping_by_uuid(self, vm_uuid):
        """
        Requests to get the vm_mapping corresponding to a given uuid.

        Args:
            vm_uuid (str): vm uuid to search on.

        Returns:
            (dict) Dictionary representation `firewheel_grpc_pb2.VMMapping`.
        """
        try:
            mapping = firewheel_grpc_pb2.VMMappingUUID(server_uuid=vm_uuid, db=self.db)
            resp = self.stub.GetVMMappingByUUID(mapping)
            ret = msg_to_dict(resp)
        except grpc.RpcError as exp:
            if exp.exception().code() != grpc.StatusCode.OUT_OF_RANGE:
                self.log.exception(exp)
            return None
        return ret

    def destroy_vm_mapping_by_uuid(self, vm_uuid):
        """
        Requests to destroy the vm_mapping corresponding to a given uuid.

        Args:
            vm_uuid (str): vm uuid to search on.

        Returns:
            dict: Dictionary representation of
            `firewheel_grpc_pb2.DestroyVMMappingResponse`. Empty on success.
        """
        mapping = firewheel_grpc_pb2.VMMappingUUID(server_uuid=vm_uuid, db=self.db)
        resp = self.stub.DestroyVMMappingByUUID(mapping)
        ret = msg_to_dict(resp)
        return ret

    def count_vm_mappings_not_ready(self):
        """
        Requests the count of VMs that are not ready.

        Returns:
            dict: Dictionary representation of
            `firewheel_grpc_pb2.CountVMMappingsNotReadyResponse`.
        """
        req = firewheel_grpc_pb2.CountVMMappingsNotReadyRequest(db=self.db)
        resp = self.stub.CountVMMappingsNotReady(req)
        ret = msg_to_dict(resp)
        return ret

    def set_vm_time_by_uuid(self, vmm):
        """
        Requests to set the time of the `vm_mapping` corresponding
        to a given uuid.

        Args:
            vmm (dict): Dictionary containing `server_uuid` and `current_time`.

        Returns:
            (dict) Dictionary representation of the updated `firewheel_grpc_pb2.VMMapping`.
        """
        try:
            mapping = firewheel_grpc_pb2.SetVMTimeByUUIDRequest(
                server_uuid=str(vmm["server_uuid"]),
                current_time=str(vmm["current_time"]),
                db=self.db,
            )
            resp = self.stub.SetVMTimeByUUID(mapping)
            ret = msg_to_dict(resp)
        except grpc.RpcError as exp:
            if exp.exception().code() != grpc.StatusCode.OUT_OF_RANGE:
                self.log.exception(exp)
            return None
        return ret

    def set_vm_state_by_uuid(self, vmm):
        """
        Requests to set the state of the `vm_mapping` corresponding
        to a given uuid.

        Args:
            vmm (dict): Dictionary containing server_uuid and state.

        Returns:
            (dict) Dictionary representation of the updated `firewheel_grpc_pb2.VMMapping`.
        """
        try:
            mapping = firewheel_grpc_pb2.SetVMStateByUUIDRequest(
                server_uuid=str(vmm["server_uuid"]), state=str(vmm["state"]), db=self.db
            )
            resp = self.stub.SetVMStateByUUID(mapping)
            ret = msg_to_dict(resp)
        except grpc.RpcError as exp:
            if exp.exception().code() != grpc.StatusCode.OUT_OF_RANGE:
                self.log.exception(exp)
            return None
        return ret

    def close(self):
        """
        Closes the gRPC channel.
        """
        self.chan.close()
