from typing import TYPE_CHECKING
from decimal import Decimal

from firewheel.cli import utils
from firewheel.cli.executors.abstract_executor import AbstractExecutor

if TYPE_CHECKING:
    from firewheel.cli.helper import Helper


class Helpers(AbstractExecutor):
    """
    An Executor to handle invoking a list of Helpers (newline separated).

    This class tries to avoid throwing any exceptions.
    """

    def __init__(
        self,
        host_list_path: list[str],
        content: list[str],
        helper_dict: dict[str, Helper] | None = None,
    ) -> None:
        """
        Initialize.

        Args:
            host_list_path (list): A list of hostnames (or IP addresses as strings). If
                                   hostnames are used, the system must be able to resolve
                                   them (when `ClusterShell` is ultimately called).
            content (list): The section's content that we want to
                           execute. We're expected to dump it into a file for transfer,
                           compile it, etc.
            helper_dict (dict): Optional dictionary of FIREWHEEL helpers with the
                key=str(helper_name) and the value is the Helper object (corresponding
                to the name).
        """
        super().__init__(host_list_path, content)

        self.helpers = {}

        if helper_dict is None:
            self._prepare_helpers()
        else:
            self.helpers = helper_dict

    def _prepare_helpers(self) -> None:
        """
        Determine the available Helpers and load them into memory.

        Assumed to be called once at start-up (object creation).
        """
        self.helpers = utils.build_helper_dict()

    def execute(
        self,
        _cache_file: str,
        session: dict[str, Decimal],
        arguments: list[str] | None,
    ) -> int:
        """
        Execute Helpers specified in the content list.

        All arguments are passed directly to the Helpers.
        This method tries to avoid throwing any Exceptions, instead printing
        helpful error messages.

        Args:
            _cache_file (str): The file (cached copy of the section content) to try and
                run from.
            session (dict): The overall CLI's view of the current session. This
                includes the current sequence number and session ID.
            arguments (list): Command-line arguments for the remote command. We are
                expected to pass this along to the HostAccessor's command execution
                method as well.

        Returns:
            int: Zero on success, non-zero otherwise. In general, return values are the
            number of Helpers that encountered at least 1 error.
        """
        # Try to run from the cache.
        try:
            error_helpers = 0
            # For each line,
            for helper in self.content:
                try:
                    (helper_obj, args) = utils.parse_to_helper(helper, self.helpers)
                except utils.HelperNotFoundError:
                    self.log.exception(
                        "Error: Helper %s not found. Trying to continue.", helper
                    )
                    error_helpers += 1
                    continue
                # Run the Helper.
                if not arguments:
                    arguments = args
                section_errors = helper_obj.run(session, arguments)
                if section_errors != 0:
                    print(f"Error: Helper `{helper}` encountered errors. Continuing.")
                    self.log.error(
                        "Error: Helper `%s` encountered errors. Continuing.", helper
                    )
                    error_helpers += 1
            return error_helpers
        except IOError as exp:
            print(f"Error: Local I/O error: {exp}")
            self.log.exception("Local I/O error.")

        self.log.error("Something unexpected happened, returning an error.")
        return 1

    def get_file_extension(self) -> str:
        """
        Return the file extension expected for Helpers.

        Returns:
            str: Helpers do not have a file extension.
        """
        return ""
