from __future__ import annotations

import re
import importlib
from uuid import UUID
from typing import TYPE_CHECKING, Dict, List, Type, Union, Optional
from decimal import Decimal

from firewheel.lib.log import Log
from firewheel.cli.section import Section, MalformedSectionError

if TYPE_CHECKING:
    from firewheel.cli.executors.shell import Shell
    from firewheel.cli.executors.python import Python
    from firewheel.cli.executors.helpers import Helpers
    from firewheel.cli.executors.local_python import LocalPython


class BadExecutorError(Exception):
    """
    Error for when a specified Executor doesn't exist.
    """


class IllegalListError(Exception):
    """
    Error for when a list passed in doesn't meet our assumptions.
    """


class ExecutableSection(Section):
    """
    Represent a RUN section from a Helper.

    RUN sections are like other sections, except they have an execute method.
    """

    def __init__(
        self,
        content: Union[int, List[str]],
        arguments: Optional[Union[List[str], str, List[Union[str, List[str]]]]],
    ) -> None:
        """
        Constructor, invokes Section (superclass) constructor.

        Store our section content and process our arguments to make sure we
        have an Executor name and at least one host group to run on.

        Args:
            content (str): The content of the RUN section we're representing, as one string.
            arguments (list): The arguments from the declaration of this section, as a
                              list. We expect at least 2 items in this list.
                              The first item is taken to be an executor name.
                              The second item is taken to be a list of host groups.

        Raises:
            MalformedSectionError: If the arguments are not a list.
            IllegalListError: If there are not exactly two elements in the
                ``arguments`` list.
        """
        super().__init__(content, arguments)
        self.log = Log(name="CLI").log

        if arguments is None:
            arguments = []

        if not isinstance(arguments, list):
            raise MalformedSectionError("Section arguments are not a list")
        # Handle arguments.
        # Expected list:
        #  - executor name
        #  - host list path
        if len(arguments) != 2:
            raise IllegalListError("Malformed list. Expected exactly 2 elements.")
        self.executor_name = arguments[0]
        self.host_list_path_list = arguments[1]

    def is_executable(self) -> bool:
        """
        Determine if someone's looking at a Section or an ExectuableSection.

        Returns:
            bool: This always returns True we are always executable.
        """
        return True

    def _load_executor(
        self, name: str
    ) -> Union[Type[Helpers], Type[LocalPython], Type[Python], Type[Shell]]:
        """
        Initialize and return the given executor.

        Args:
            name (str): Name of the executor to load, should be in (upper) camel case

        Returns:
            firewheel.cli.executors.abstract_executor.AbstractExecutor: The loaded executor class

        Raises:
            BadExecutorError: If there are non-ascii characters in the executor name.
            BadExecutorError: If the executor is not found.
            Exception: If an unknown error occurs while loading the executor.
        """
        if not name.isascii():
            raise BadExecutorError("Non-ascii characters in executor name")

        # Find the module / class names
        lower_name = (
            re.sub(r"((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))", r"_\1", name)
        ).lower()
        module_name = f"firewheel.cli.executors.{lower_name}"
        class_name = name

        # Now, load the class and save it
        try:
            action_module = importlib.import_module(module_name)
            return getattr(action_module, class_name)
        except ImportError as exp:
            self.log.exception("Unable to find executor: %s", lower_name)
            raise BadExecutorError(
                f"Unable to find executor '{lower_name}': {exp}"
            ) from exp
        except Exception as exp:
            self.log.exception("Unknown error loading executor.")
            raise Exception("Unknown error loading executor!") from exp

    def execute(
        self,
        cache_file: str,
        session: Dict[str, Union[Decimal, int, UUID]],
        arguments: Optional[List[str]],
    ) -> int:
        """
        Try to create the correct Executor and have it run our content.

        Args:
            cache_file (str):  The location of the cached Helper executable.
            session (dict): The current CLI session.
            arguments (list): Arguments from the command-line for our RUN section.

        Returns:
            int: A summation of the return codes from the executed Helpers. Generally this
            will be the number of hosts that failed. However, some Helpers may give specific
            error codes which are then added. This will be 0 on success.
        """
        try:
            executor_class = self._load_executor(self.executor_name)
            return_sum = 0
            for host_list_path in self.host_list_path_list:
                executor = executor_class(host_list_path, self.content)
                ret_code = executor.execute(cache_file, session, arguments)
                if ret_code != 0:
                    return_sum += ret_code
            return return_sum
        # pylint: disable=broad-except
        except Exception as exp:
            print(f"Error: Unable to run executable section: {exp}")
            self.log.exception("Unable to run executable section.")
            return 1

    def get_file_extension(self) -> str:
        """
        Gets the file extension expected by the Executor for this section.

        Returns:
            str: The file extension expected by the Executor for this section.

        Raises:
            BadExecutorError: If there is an error with the executor.
        """
        try:
            executor_class = self._load_executor(self.executor_name)
            executor = executor_class("", "")  # Stub instance
            return executor.get_file_extension()
        except BadExecutorError as exp:
            print(f"Bad Executor '{self.executor_name}': {exp}.")
            self.log.exception('Bad Executor "%s".', self.executor_name)
            raise
