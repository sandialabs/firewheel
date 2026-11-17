import os
import sys
import shutil
import tempfile
from decimal import Decimal
from subprocess import call

from firewheel.cli.executors.abstract_executor import AbstractExecutor


class LocalPython(AbstractExecutor):
    """
    Executor to handle Python scripts on the machine where the CLI is run.

    This class tries to avoid throwing any Exceptions.
    """

    def execute(
        self,
        _cache_file: str,
        _session: dict[str, Decimal],
        arguments: list[str] | None,
    ) -> int:
        """
        Execute Python scripts via the current Python environment.

        Dump our section content into a temporary file and invoke it using
        the Python interpreter.

        This method tries to avoid throwing any Exceptions, instead printing
        helpful error messages.

        Args:
            _cache_file (str): The file (cached copy of the section content) to try and
                run from.
            _session (dict): The overall CLI's view of the current session. This is
                an unused argument.
            arguments (list): Command-line arguments for the local execution. This is
                the file of the Helper and any arguments that should be passed
                to the Helper.

        Returns:
            int: Zero on success, non-zero otherwise.
        """
        # Write content to a temp file
        tdir = tempfile.mkdtemp()
        content_filename = os.path.join(tdir, "content.py")

        with open(content_filename, "w", encoding="utf8") as fhand:
            fhand.write("\n".join(self.content))

        cmd = [sys.executable, content_filename]

        if arguments is not None:
            cmd.extend(arguments)

        # Run the script and wait for it to finish
        # This executes local python scripts on the physical host. This can
        # have security implications. These are documented in the FIREWHEEL
        # documentation.
        try:
            ret = call(cmd)  # nosec
        except KeyboardInterrupt:
            ret = 4  # Returning "Interrupted system call"

        # Clean up
        shutil.rmtree(tdir)

        # Return with the return code from the Helper
        return ret

    def get_file_extension(self) -> str:
        """
        Return the file extension expected for Python files.

        Returns:
            str: Always returns ``.py``.
        """
        return ".py"
