import sys
import stat
import subprocess
from pathlib import Path

from rich.prompt import PromptBase
from rich.syntax import Syntax
from rich.console import Console

from firewheel.lib.log import Log


class InstallPrompt(PromptBase[str]):
    """A prompt that has a custom error message."""

    response_type = str
    msg = (
        "[prompt.invalid.choice]Please select one of the available options:\n"
        "y - yes, install execute this script\n"
        "n - no, do not execute this script\n"
        "v - view, see the script text\n"
        "vc - view color, see the script text with color support, must use "
        "a system pager which supports this behavior (e.g. PAGER='less -R')\n"
        "q - quit, exit immediately\n"
    )
    illegal_choice_message = msg
    validate_error_message = msg


class ModelComponentInstall:
    """
    Some Model Components may provide an additional install script called ``INSTALL``
    which can be executed to perform other setup steps (e.g. installing an extra python package
    or downloading an external VM resource).
    This class helps execute that file and install a Model Component.
    ``INSTALL`` scripts can be can be any executable file type as defined by a
    `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ line.

    .. warning::

        The execution of Model Component ``INSTALL`` scripts can be a **DANGEROUS** operation.
        Please ensure that you **fully trust** the repository developer prior to executing
        these scripts.

    .. seealso::

        See :ref:`mc_install` for more information on ``INSTALL`` scripts.

    When installing a Model Component, users will have a variety of choices to select:

        - ``y`` - yes, install execute this script
        - ``n`` - no, do not execute this script
        - ``v`` - view, see the script text
        - ``vc`` - view color, see the script text with color support, must use a system pager
          which supports this behavior (e.g. ``PAGER='less -R'``)
        - ``q`` - quit, exit immediately

    """

    def __init__(self, mc=None):
        """
        Initialize the object.

        Args:
            mc (ModelComponent): The :py:class:`ModelComponent` to install.

        Raises:
            ValueError: Caused if a user didn't specify ``mc``.
        """
        if mc is None:
            raise ValueError("Must specify a Model Component.")

        self.mc = mc
        self.log = Log(name="ModelComponentInstall").log

    def install_mc(self, name, install_path):
        """
        Execute a given Model Component's ``INSTALL`` script.

        Args:
            name (str): The name of the Model Component.
            install_path (pathlib.Path): The path of the ``INSTALL`` file.

        Returns:
            bool: True if the MC was installed successfully (or it was already
            installed), False otherwise
        """
        console = Console()

        # Make the install file executable
        # We assume that it can be run with a "shebang" line
        install_path.chmod(
            install_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
        console.print(f"[b green]Starting to install [cyan]{name}[/cyan]!")
        try:
            # We have already checked with the user to ensure that they want to run
            # this script.
            subprocess.run(  # nosec
                [str(install_path)], cwd=install_path.parent, check=True
            )
            console.print(f"[b green]Installed [cyan]{name}[/cyan]!")
            return True
        except subprocess.CalledProcessError as exp:
            if exp.returncode == 117:  # Structure needs cleaning
                console.print(f"[b yellow][cyan]{name}[/cyan] is already installed!")
                return True

            console.print(f"[b red]Failed to install [cyan]{name}[/cyan]!")
            return False

    def run_install_script(self, insecure=False):
        """
        Ask the user to run the install script for the given Model Component.

        Args:
            insecure (bool): Whether to automatically install the Model Component without asking.
                Default is ``False``.

        Returns:
            bool: ``True`` if all MCs were installed successfully, ``False`` otherwise.
        """
        console = Console()

        install_script = Path(self.mc.path) / "INSTALL"
        install_flag = Path(self.mc.path) / f".{self.mc.name}.installed"

        if not install_script.exists():
            return True

        if install_flag.exists():
            return True

        if insecure is True:
            success = self.install_mc(self.mc.name, install_script)
            if not success:
                console.print(f"[b red]Failed to install [cyan]{self.mc.name}[/cyan].")
                return False
            return True

        choices = ["y", "n", "v", "vc", "q"]
        ask = f"[yellow]Do you want to execute [cyan]{install_script}"
        while True:
            value = InstallPrompt.ask(ask, choices=choices)
            if value == "y":
                success = self.install_mc(self.mc.name, install_script)
                if not success:
                    console.print(
                        f"[b red]Failed to install [cyan]{self.mc.name}[/cyan]"
                        " this may cause downstream issues!"
                    )
                    return False

                # If the install script didn't create the "installed" flag
                # we should do it here.
                if not install_flag.exists():
                    install_flag.touch()
                break
            if value == "n":
                console.print(
                    f"[b red]Continuing WITHOUT running [cyan]{install_script}[/cyan]"
                    " this may cause downstream issues!"
                )
                break
            if value.startswith("v"):
                contents = ""
                with open(install_script, "r", encoding="utf-8") as fhand:
                    contents = fhand.read()
                style = False
                if value == "vc":
                    style = True
                with console.pager(styles=style):
                    console.print(Syntax(contents, lexer="bash"))
            elif value.startswith("q"):
                sys.exit(0)
        return True
