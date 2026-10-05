import sys
from decimal import Decimal

from firewheel.cli.host_accessor import HostAccessor
from firewheel.cli.executors.abstract_executor import AbstractExecutor


class Python(AbstractExecutor):
    """
    Executor to handle Python scripts.

    This class tries to avoid throwing any Exceptions.
    """

    def execute(
        self,
        cache_file: str,
        session: dict[str, Decimal],
        arguments: list[str] | None,
    ) -> int:
        """
        Execute Python scripts via the :class:`firewheel.cli.host_accessor.HostAccessor`.

        Dump our section content into a temporary file, copy it to the remote
        hosts, and invoke it using the Python interpreter.

        This method tries to avoid throwing any Exceptions, instead printing
        helpful error messages.

        Args:
            cache_file (str): The file (cached copy of the section content) to try and
                              run from.
            session (dict): The overall CLI's view of the current session. This
                     includes the current sequence number and session ID.
            arguments (list): Command-line arguments for the remote command. We are
                       expected to pass this along to the HostAccessor's command
                       execution method as well.

        Returns:
            int: Zero on success, non-zero otherwise. Expects HostAccessor to handle
            the details of specific return code meanings.

        Note:
            FIREWHEEL assumes that the path to `python` is the same across the entire
            cluster. This means that if FIREWHEEL was installed in a virtual environment
            then the virtual environment should have the same path for each node in the
            cluster.
        """
        # Try to run from the cache.
        try:
            hosts = HostAccessor(self.host_list_path)
            # Get the correct path for python
            cache_file = f"{sys.executable} {cache_file}"
            return hosts.run_command(cache_file, session, arguments)
        except IOError as exp:
            print(f"Error: Local I/O error: {exp}")
            self.log.exception("Local I/O error.")

        self.log.error("Unexpected error trying to execute Helper.")
        return 1

    def get_file_extension(self) -> str:
        """
        Return the file extension expected for Python files.

        Returns:
            str: Always returns ``.py``.
        """
        return ".py"
