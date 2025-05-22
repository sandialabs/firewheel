import os
import cmd
import pprint
import argparse
import operator
import subprocess
from inspect import cleandoc
from pathlib import Path

import yaml
from rich.console import Console

from firewheel.config import Config
from firewheel.lib.log import Log


class ConfigureFirewheel(cmd.Cmd):
    """Enables command-line access to get and set the FIREWHEEL configuration.

    Users can interact with the :ref:`command_config` command (i.e. ``firewheel config``)
    series of sub-commands which enable easily getting/setting various configuration options.
    """

    doc_header = "Get or set the FIREWHEEL configuration using sub-commands:"

    def __init__(self) -> None:
        """Initialize the :py:class:`cmd.Cmd` and the class logger.

        Attributes:
            doc_header (str): The documentation header for the :ref:`command_config` command.
            log (logging.Logger): The log to use for class.
        """
        super().__init__()
        self.log = Log(name="CLI").log

    @staticmethod
    def _handle_parsing(
        parser: argparse.ArgumentParser, args: str
    ) -> argparse.Namespace:
        # Print the full help message on an error
        # (see: https://stackoverflow.com/a/29293080)
        try:
            cmd_args = parser.parse_args(args.split())
        except SystemExit as err:
            if err.code == 2:
                parser.print_help()
            raise err
        return cmd_args

    def define_reset_parser(self) -> argparse.ArgumentParser:
        """Create an :py:class:`argparse.ArgumentParser` for :ref:`command_config_reset`.

        Returns:
            argparse.ArgumentParser: The parser needed for :ref:`command_config_reset`.
        """
        parser = argparse.ArgumentParser(
            description="Reset the FIREWHEEL configuration to the default values.",
            prog="firewheel config reset",
            add_help=False,
        )
        parser.add_argument(
            "config_path",
            nargs="?",
            default=None,
            type=Path,
            help="Path of the configuration file to be reset.",
        )
        return parser

    def define_edit_parser(self) -> argparse.ArgumentParser:
        """Create an :py:class:`argparse.ArgumentParser` for :ref:`command_config_edit`.

        Returns:
            argparse.ArgumentParser: The parser needed for :ref:`command_config_edit`.
        """
        parser = argparse.ArgumentParser(
            description=str(
                "Edit the FIREWHEEL configuration with a text editor. "
                "The user must set either the VISUAL or EDITOR environment variable "
                "or use the provided flag to override these environment variables."
            ),
            prog="firewheel config edit",
            add_help=False,
        )
        parser.add_argument(
            "-e",
            "--editor",
            required=False,
            default="",
            help="Use the specified text editor.",
        )
        return parser

    def do_edit(self, args: str = "") -> None:
        """
        Edit the FIREWHEEL config with the default text editor as determined by
        the ``VISUAL`` or ``EDITOR`` environment variables.
        If no editor is found an error message is output.

        Args:
            args (str): A string of arguments passed in by the user.
        """
        # Create a Console object for colored output
        console = Console()

        # Get the parser for the reset command
        parser = self.define_edit_parser()
        cmd_args = self._handle_parsing(parser, args)

        # Check for VISUAL, then EDITOR
        editor = cmd_args.editor or os.environ.get("VISUAL") or os.environ.get("EDITOR")

        if not editor:
            self.help_edit()
            return

        # Attempt to open the file with the chosen editor
        try:
            subprocess.run([editor, Config(writable=True).config_path], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            console.print(
                f"Error: Failed to open FIREWHEEL configuration with '{editor}'.\n",
                style="bold red",
            )
            self.help_edit()
            return

    def do_reset(self, args: str = "") -> None:
        """
        Reset the FIREWHEEL configuration to the defaults.

        Users can reset the current FIREWHEEL configuration to the
        defaults provided in the template.

        Args:
            args (str): A string of arguments passed in by the user.
        """
        # Get the parser for the reset command
        parser = self.define_reset_parser()
        cmd_args = self._handle_parsing(parser, args)
        # Reset the config file by regenerating the file from the template
        fw_config = Config(config_path=cmd_args.config_path)
        fw_config.generate_config_from_defaults()

    def define_set_parser(self) -> argparse.ArgumentParser:
        """Create an :py:class:`argparse.ArgumentParser` for :ref:`command_config_set`.

        Returns:
            argparse.ArgumentParser: The parser needed for :ref:`command_config_set`.
        """
        parser = argparse.ArgumentParser(
            description="Set a FIREWHEEL configuration.",
            prog="firewheel config set",
            add_help=False,
            formatter_class=argparse.RawTextHelpFormatter,
        )
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "-f",
            "--file",
            required=False,
            type=argparse.FileType("r"),
            help="Add config from a file.",
        )
        group.add_argument(
            "-s",
            "--single",
            nargs="+",
            metavar=("SETTING", "VALUE"),
            help=(
                "Set (or create) a particular configuration value. Nested settings\n"
                "can be used with a period separating them. For example, to change\n"
                "the value for the config key ``{'logging':{'level':'DEBUG'}}``, you\n"
                "can use the command: ``firewheel config set -s logging.level INFO``.\n"
                "If no VALUE is passed, the setting's value will become ``None``."
            ),
        )
        return parser

    def do_set(self, args: str) -> None:  # noqa: DOC502
        """Enable a user to set a particular FIREWHEEL configuration option.

        Users can either set a single configuration value or pass in
        a file to replace the entire configuration.

        Args:
            args (str): A string of arguments which are passed in by the user.

        Raises:
            SystemExit: If an incorrect arguments are given.
        """
        # Parse the arguments provided to the `set` command
        parser = self.define_set_parser()
        cmd_args = self._handle_parsing(parser, args)

        if cmd_args.file is not None:
            self.log.debug("Setting the FIREWHEEL config to file: %s", cmd_args.file)
            new_config = yaml.safe_load(cmd_args.file)
            fw_config = Config(writable=True)
            fw_config.set_config(new_config)
            fw_config.write()

        if cmd_args.single is not None:
            key = cmd_args.single[0]
            value = " ".join(cmd_args.single[1:])
            self.log.debug(
                "Setting the FIREWHEEL config value for `%s` to `%s`.", key, value
            )
            fw_config = Config(writable=True)
            fw_config.resolve_set(key, value)
            fw_config.write()

    def define_get_parser(self) -> argparse.ArgumentParser:
        """Create an :py:class:`argparse.ArgumentParser` for :ref:`command_config_get`.

        Returns:
            argparse.ArgumentParser: The parser needed for :ref:`command_config_get`.
        """
        parser = argparse.ArgumentParser(
            description="Get a FIREWHEEL configuration.",
            prog="firewheel config get",
            add_help=False,
            formatter_class=argparse.RawTextHelpFormatter,
        )
        parser.add_argument(
            "-a",
            "--all",
            required=False,
            action="store_true",
            help="Get the entire FIREWHEEL configuration.",
        )
        parser.add_argument(
            "setting",
            nargs="?",
            metavar=("SETTING"),
            help=(
                "Get a particular configuration value. Nested settings can be grabbed\n"
                "with a period separating them. For example, to get the value for the\n"
                "config key ``{'logging':{'level':'INFO'}}``, you can use the\n"
                "command: ``firewheel config get logging.level``."
            ),
        )
        return parser

    def do_get(self, args: str) -> None:  # noqa: DOC502
        """Enable a user to get a particular FIREWHEEL configuration option.

        Users can either get a single configuration value or get the
        entire configuration.

        Args:
            args (str): A string of arguments which are passed in by the user.

        Raises:
            SystemExit: If incorrect arguments are given.
        """
        # Parse the arguments provided to the `get` command
        parser = self.define_get_parser()
        cmd_args = self._handle_parsing(parser, args)

        if cmd_args.all is True:
            self.log.debug("Getting the entire FIREWHEEL configuration.")
            fw_config = Config()
            output = yaml.safe_dump(fw_config.get_config(), sort_keys=True, indent=4)
            print(output)
        elif cmd_args.setting is not None:
            self.log.debug(
                "Getting the FIREWHEEL config value for `%s`.", cmd_args.setting
            )
            fw_config = Config()
            output = fw_config.resolve_get(cmd_args.setting)
            if isinstance(output, dict):
                output = pprint.pformat(output)
            print(output)
        else:
            parser.print_help()

    def emptyline(self) -> None:
        """Print help when a blank line is entered.

        Required by :py:mod:`cmd` as the action taken when a blank line is entered.
        We want this to print help.
        """
        print("Error: A sub-command is required.")
        self.do_help("")

    def get_docs(self) -> str:
        """Get the documentation for the set of commands that relate to :ref:`command_config`.

        Returns:
            str: The full documentation for all hostgroup commands.
        """
        # Get all the commands
        command_string = "\n" + cleandoc(ConfigureFirewheel.__doc__)
        command_string += "\n\n\n"
        classdict = ConfigureFirewheel.__dict__
        sortddict = sorted(classdict.items(), key=operator.itemgetter(0))
        for method in sortddict:
            if method[0].startswith("do_"):
                command = method[0][3:]
                cmd_help = f"_help_{command}"

                reference = f".. _command_config_{command}:"
                full_cmd = f"config {command}"

                # Fix odd Sphinx warnings
                help_text = getattr(self, cmd_help)()
                help_list = help_text.split("\n")
                clean_text = ""
                for num, line in enumerate(help_list):
                    if line.startswith("  -") and help_list[num + 1].startswith("  -"):
                        clean_text += line + "\n"
                    else:
                        clean_text += line
                    clean_text += "\n"

                # Put the command name in the file
                command_string += f"{reference}\n\n"
                command_string += f"{full_cmd}\n"
                command_string += "^" * len(full_cmd)
                command_string += "\n\n"
                command_string += clean_text
                command_string += "\n\n"
        return command_string

    def _help_edit(self) -> str:
        """Help message for the :py:meth:`do_edit` sub-command.

        Returns:
            str: The help message.
        """
        return self.define_edit_parser().format_help()

    def help_edit(self) -> None:
        """Print help for the :py:meth:`do_edit` sub-command."""
        print(self._help_edit())

    def _help_reset(self) -> str:
        """Help message for the :py:meth:`do_reset` sub-command.

        Returns:
            str: The help message.
        """
        return self.define_reset_parser().format_help()

    def help_reset(self) -> None:
        """Print help for the :py:meth:`do_reset` sub-command."""
        print(self._help_reset())

    def _help_set(self) -> str:
        """Help message for the :py:meth:`do_set` sub-command.

        Returns:
            str: The help message.
        """
        return self.define_set_parser().format_help()

    def help_set(self) -> None:
        """Print help for the :py:meth:`do_set` sub-command."""
        print(self._help_set())

    def _help_get(self) -> str:
        """Help message for the :py:meth:`do_get` sub-command.

        Returns:
            str: The help message.
        """
        return self.define_get_parser().format_help()

    def help_get(self) -> None:
        """Print help for the :py:meth:`do_get` sub-command."""
        print(self._help_get())

    def _help_help(self) -> str:
        """Help message for the help sub-command.

        Returns:
            str: The help message.
        """
        doc = str(
            "    Prints help for the different sub-commands.\n\n    **Usage**: "
            "``firewheel config help <sub-command>``"
        )
        return doc

    def help_help(self) -> None:
        """Print help for the help sub-command."""
        print(self._help_help())
