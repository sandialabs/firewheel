"""
Subsystem to determine and report an experiment start time.
"""

from datetime import datetime, timedelta

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.lib.grpc.firewheel_grpc_client import FirewheelGrpcClient


class ExperimentStart:
    """
    Interface to determine and report an experiment start time. Different start
    times may reported as desired, but a consistent value will always be
    reported as the start time. If no start times have yet been reported, a
    value of None will be reported.

    This is currently implemented using the GRPC database as a synchronization
    mechanism: the current time is reported and recorded into the DB. When
    determining the consistent start time value, the values from the DB are
    sorted and the first-recorded returned.
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
        self.log = Log(name="ExperimentStart").log
        self.grpc_client = None
        # Instantiating the FirewheelGrpcClient may cause an exception.
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
        Safely close the gRPC connection (if it exists at all).
        """
        try:
            if self.grpc_client:
                self.grpc_client.close()
        # pylint: disable=broad-except
        except Exception as exp:
            self.log.error("Error occurred when trying to close the GRPC Client")
            self.log.exception(exp)

    def add_start_time(self):
        """
        Report the current time as a new start time for the database. May be
        called arbitrary many times without affecting the consistency of the
        time returned by `get_start_time()`.

        Returns:
            datetime.datetime: A datetime object representing the time value as
            added to the database: 1-second resolution, UTC.
        """
        # Check to make sure that it isn't already set
        current_time = self.get_start_time()
        if current_time:
            return current_time

        delta = timedelta(
            seconds=int(config["vm_resource_manager"]["experiment_start_buffer_sec"])
        )
        new_time = datetime.utcnow() + delta
        self.grpc_client.set_experiment_start_time(new_time)

        return new_time

    def get_start_time(self):
        """
        Return a consistent value for the experiment start time, as determined
        by the reported times using `add_start_time()`.

        Returns:
            datetime.datetime: datetime object representing the start time
            (in UTC), 1-second resolution or None is no start time has been
            reported yet.
        """
        start_time = self.grpc_client.get_experiment_start_time()
        return start_time

    def set_launch_time(self):
        """
        Set the experiment launch time.

        Returns:
            datetime.datetime: A datetime object representing the time value as
            added to the database: 1-second resolution, UTC.
        """
        # Check to make sure that it isn't already set
        current_time = datetime.utcnow()
        self.grpc_client.set_experiment_launch_time(current_time)

        return current_time

    def get_launch_time(self):
        """
        Return the experiment launch time.

        Returns:
            datetime.datetime: datetime object representing the start time
            (in UTC), 1-second resolution or None is no launch time has been
            reported yet.
        """
        launch_time = self.grpc_client.get_experiment_launch_time()
        return launch_time

    def get_time_to_start(self):
        """
        Get the amount of time it takes from when an experiment is launched to
        when it is configured.

        Returns:
            int: The time in seconds from when the experiment launched to configured.
            or None if experiment hasn't started yet.
        """
        launch_time = self.get_launch_time()
        start_time = self.get_start_time()
        if not launch_time or not start_time:
            return None
        delta = start_time - launch_time
        self.log.debug(
            "Time between experiment launch and experiment start is: %s seconds.",
            delta.total_seconds(),
        )
        return delta.total_seconds()

    def get_time_since_start(self):
        """
        Get the amount of time that has elapsed since the experiment has been configured.

        Returns:
            int: The time in seconds since when the experiment configured or
            None if experiment hasn't started yet.
        """
        current_time = datetime.utcnow()
        start_time = self.get_start_time()
        if not start_time:
            return None
        delta = current_time - start_time
        self.log.debug(
            "Time since experiment start is: %s seconds.", delta.total_seconds()
        )
        return delta.total_seconds()

    def clear_start_time(self):
        """
        Clear the current start time. The system is then uninitialized until
        a new time is reported--after this call, `get_start_time()` returns None
        until `add_start_time()` is called.

        Returns:
            dict: The response dictionary from GRPC initializing the start time.
        """
        self.log.info("Clearing experiment start time.")
        res = self.grpc_client.initialize_experiment_start_time()
        self.log.info("Cleared experiment start time.")
        return res
