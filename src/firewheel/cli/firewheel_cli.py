#!/usr/bin/env python

import os
import cmd
import sys
import shlex
import logging
import textwrap
from math import floor
from uuid import uuid4
from importlib.metadata import version

from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown

from firewheel.cli import utils
from firewheel.config import Config
from firewheel.lib.log import Log
from firewheel.cli.utils import HelperNotFoundError, InvalidHelperTypeError
from firewheel.cli.helper import Helper
from firewheel.cli.host_accessor import sync
from firewheel.cli.init_firewheel import InitFirewheel
from firewheel.cli.configure_firewheel import ConfigureFirewheel


class FirewheelCLI(cmd.Cmd):
    """
    Entry class for the CLI.

    Uses the cmd module to handle commands. Most functionality is based on
    "Helpers", the names of which are determined at run-time.
    Commands are designed to support Helpers. If you want to add functionality,
    it should probably be a Helper.
    """

    prompt = "fw-cli> "
    doc_header = """
# FIREWHEEL Infrastructure Command Line Interpreter (CLI)

CLI commands and Helpers can be run in-line (e.g., `firewheel help`) or
within the interpreter by invoking FIREWHEEL without additional arguments.
CLI commands (i.e., internal to the CLI) and Helpers (i.e., defined in cli/helpers)

For complete help on any command or Helper, use: `firewheel help <command | Helper>`.
For a list of Helpers of type `<filter>`, use: `firewheel list <filter>`
Some Python-based Helpers also may use `argparse`. In that case, the `-h` or
`--help` flags will also provide some help output (though this should be captured
via `firewheel help <Helper>` as well).
"""
    ruler = ""

    def __init__(self, interactive=False):
        """Constructor.
        Initialize our Helper system and our session history.

        Attributes:
            prompt (str): The prompt issued to solicit input.
            doc_header (str): The header to issue if the help output has a section for
                documented commands.
            ruler (str): The character used to draw separator lines under the help-message
                headers. If empty, no ruler line is drawn.

        Args:
            interactive (bool): Should this be in interactive mode or not.
        """
        super().__init__()

        config = Config().get_config()

        # We are careful about setting self.log to None so we don't cause more
        # errors in the destructor if we have an error while setting the umask.
        # The same logic applies to self.session.
        self.log = None
        self.session = None

        # Set up our umask.
        try:
            os.umask(int(config["system"]["umask"], base=0))
        except ValueError as exp:
            print(f"Error: Invalid integer configured for umask: {exp}")
            sys.exit(1)
        except OSError as exp:
            print(f"Error: Unexpected error trying to set umask value: {exp}")
            sys.exit(1)

        # session is a dictionary containing the basic information about this CLI session
        # This is expected to contain:
        #  - sequence_number : The current command sequence number.
        #  - id : The session's unique ID. Implemented as a UUID.
        self.session = {}
        self.session["sequence_number"] = 0
        self.session["id"] = uuid4()

        self.interactive = interactive

        # Set up logging for the CLI
        self._setup_logging()

        self.log.info("Started session %s", self.session["id"])

        # Initialize a few standard strings
        self.cmd_not_found = str(
            "Error: Use `firewheel list` to "
            "view all available Helpers. FIREWHEEL Helper not found:"
        )

        self.helpers = {}
        self._prepare_helpers()

        # Create our history file
        try:
            # pylint: disable=consider-using-with
            self.history_file = open(
                os.path.join(config["logging"]["root_dir"], "cli_history.log"),
                "a",
                encoding="utf8",
            )
        except (OSError, TypeError):
            print("Warning: Continuing without session history.")
            self.log.warning("Warning: Continuing without session history.")
            # pylint: disable=consider-using-with
            self.history_file = open("/dev/null", "w", encoding="utf8")

        # Create our experiment history file
        try:
            # pylint: disable=consider-using-with
            self.history_exp_file = open(
                os.path.join(config["logging"]["root_dir"], "experiment.history"),
                "a",
                encoding="utf8",
            )
        except (OSError, TypeError):
            print("Warning: Continuing without experiment history.")
            self.log.warning("Warning: Continuing without experiment history.")
            # pylint: disable=consider-using-with
            self.history_exp_file = open("/dev/null", "w", encoding="utf8")

    def __del__(self):
        """Destructor which closes the history file, if possible."""
        try:
            self.history_file.close()
        except (AttributeError, OSError) as exp:
            print("Warning: Unable to close history file.")
            if self.log is not None:
                self.log.error("Unable to close history file.")
                self.log.exception(exp)

    def _setup_logging(self):
        """
        Create custom CLI logger.

        The CLI logger should have the output include the time, level, session ID and
        sequence number. All CLI logging should use the same logger. If the existing
        log file is inaccessible this method tries to create a new file by appending
        the current users username. In the event which the original log file was
        created by a different user (and therefore has different permissions) this
        will enable logging to continue. If a log file is still unable to be created
        (likely due to a directory which cannot be accessed) the CLI will continue
        without a log file.
        """
        config = Config().get_config()
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.session_id = self.session["id"]
            record.seq_number = self.session["sequence_number"]
            return record

        logging.setLogRecordFactory(record_factory)

        self.log = Log(
            name="CLI",
            log_file=config["logging"]["cli_log"],
            log_format="[%(asctime)s %(levelname)s] %(session_id)s::%(seq_number)s - %(message)s",
        ).log
        self.main_log = Log(name="FirewheelCLI").log

    def _prepare_helpers(self):
        """
        Determine the available Helpers and load them into memory.

        Assumed to be called once at start-up (object creation).
        """
        self.helpers = utils.build_helper_dict()

    def postcmd(self, stop, line):
        """
        Defined by cmd as the action taken after each command is completed.

        We use this method to track our history.

        Args:
            stop (func): Used internally by `cmd`, needs to be returned.
            line (str): The line that has been executed.

        Returns:
            stop: The previously passed in parameter
        """
        # Write to the history file.
        self.write_history(line)

        # Update the current sequence number.
        self.session["sequence_number"] = floor(self.session["sequence_number"])
        self.session["sequence_number"] += 1

        return stop

    def emptyline(self):
        """
        Defined by cmd as the action taken when a blank line is entered.

        We want this to be a no-op.
        """
        # Ignore and re-prompt on empty lines.
        # Override the superclass because the default behavior is to repeat
        # the last command.
        return

    def default(self, line):
        """
        Defined by cmd for the action taken when an unrecognized command is given.

        In our system this could be the name of Helper, so we'll search for it.

        Args:
            line (str): The command-line as entered by the user.

        Returns:
            int: The return value of handle_run.
        """
        # When we don't recognize the command, try to run a Helper.
        try:
            result = self.handle_run(line)
            if not self.interactive:
                # Write to the history file.
                self.write_history(line)
                return result
        except HelperNotFoundError:
            if not self.interactive:
                print(
                    f'Invalid command and invalid Helper: "{line}".\n'
                    f'For a list of valid commands and helpers, use the "firewheel help" command.'
                )

                return 1

            print(
                f'Invalid command and invalid Helper: "{line}".\n'
                f'For a list of valid commands and helpers, type "help".'
            )
        except InvalidHelperTypeError:
            print("Cannot run a Helper group.")
            self.do_list(line)
        return 0

    def _list_helpers(self, dict_to_list, group_filter=None):
        """
        Recursively produce a flat list of available Helpers.

        Args:
            dict_to_list (dict): The dictionary of Helpers to list.
                        During recursion, this may be a sub-dictionary of the
                        main Helpers dictionary.
            group_filter (list): A list of strings specifying a Helper group to limit the
                        list to. If specified and not None, all non-matching
                        Helpers are ignored.

        Returns:
            list: The list of available Helpers.
        """
        out_list = []
        if group_filter:
            current_filter = group_filter[0]
            if len(group_filter) > 1:
                next_filter = group_filter[1:]
            else:
                next_filter = None
            if current_filter in dict_to_list:
                # If they've asked us to list a specific Helper, just list that
                # Helper.
                if isinstance(dict_to_list[current_filter], Helper):
                    return [current_filter]
                # Move down a level in the group hierarchy.
                return self._list_helpers(dict_to_list[current_filter], next_filter)
            matches = [i for i in dict_to_list if current_filter in i]
            for helper in matches:
                if isinstance(dict_to_list[helper], Helper):
                    out_list.append(helper)
                else:
                    helper_groups = self._list_helpers(
                        dict_to_list[helper], next_filter
                    )
                    helper_groups = [f"{helper} {i}" for i in helper_groups]
                    out_list += helper_groups

        else:
            for k in dict_to_list:
                if isinstance(dict_to_list[k], Helper):
                    out_list.append(k)
                else:
                    group_list = self._list_helpers(dict_to_list[k])
                    for helper in group_list:
                        out_list.append(f"{k} {helper}")
        return out_list

    def do_init(self, args):  # pragma: no cover
        """
        Initializes FIREWHEEL on this node.

        Args:
            args (str): This argument is passed to
                :py:class:`firewheel.cli.init_firewheel.InitFirewheel`
                for command interpretation.

        Examples:
            .. code-block:: bash

                $ firewheel init
                Checking /usr/bin/firewheel: OK
                Checking write access to default_output_dir: /tmp/firewheel
                Successfully able to write to default_output_dir.
                ...

        """
        cli_path = os.path.abspath(__file__)
        InitFirewheel(cli_path).onecmd(args)

    def do_list(self, args):
        """
        List the available Helpers by name.

        This enables users to identify all the available FIREWHEEL Helpers. Users
        can optionally filter the list by partially completing a Helper name.

        Args:
            args (str): Optionally specify a group to list.

        Examples:
            .. code-block:: bash

                $ firewheel list
                FIREWHEEL Helper commands:
                           example_helpers pytest
                           example_helpers subgroup index
                           ...

            .. code-block:: bash

                $ firewheel list
                FIREWHEEL Helper commands containing 'vm:'
                         vm list
                         vm mix
        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"list {args}")

        args = args.split()
        if args:
            group_filter = args
            cmd_preamble = " ".join(args)
        else:
            group_filter = None
            cmd_preamble = " "

        helper_list = self._list_helpers(self.helpers, group_filter)
        helper_list.sort()

        if group_filter is None:
            print("FIREWHEEL Helper commands:")
        else:
            print(f"FIREWHEEL Helper commands containing '{cmd_preamble}':")
        for helper in helper_list:
            print("\t", helper)

    def do_author(self, args):
        """
        Print the `AUTHOR` section of the specified Helper.

        Args:
            args (str): The Helper name for which to print the author.

        Examples:
            .. code-block:: bash

                $ firewheel author experiment
                FIREWHEEL Team

        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"author {args}")

        if len(args) < 1:
            print(utils.strip_markup_chrs(self.help_author()))
            return

        try:
            (helper, args) = utils.parse_to_helper(args, self.helpers)
        except HelperNotFoundError:
            print(f"{self.cmd_not_found} {args}")
            return

        if "AUTHOR" not in helper:
            print(f"Error: Helper '{args[0]}' does not have an AUTHOR section.")
            return

        helper["AUTHOR"].print_content()

    def handle_run(self, args):
        """
        Brains of running a Helper that are common to both ways of invoking a Helper.

        Error handling may want different messages, so we don't handle
        much here, just (rudely) throw things.

        Args:
            args (str): The Helper invocation string (arguments to the "run" command
                        or the whole command-line if "run" wasn't used).

        Returns:
            int: The number of executable sections in the Helper that encountered
            errors. 0 on success. Negative (e.g. -1) on other errors.

        Raises:
            HelperNotFoundError: If the named Helper cannot be located.
            Exception: If and thing there is a terrible error.
        """
        self.main_log.info("Beginning command: %s", args)
        if len(args) < 1:
            error_msg = utils.strip_markup_chrs(self.help_run())
            print(error_msg)
            self.main_log.info(error_msg)
            return -1

        try:
            (helper, args) = utils.parse_to_helper(args, self.helpers)
        except HelperNotFoundError:
            self.main_log.error("Helper not found.")
            raise
        except Exception:
            self.main_log.exception("Had unknown issue with running command!")
            raise

        ret = helper.run(self.session, args)
        self.main_log.info("Command returned: %s", ret)
        return ret

    def do_run(self, args):
        """Runs the scripts found in the specified Helper file.

        This command is functionally equivalent to running the same
        Helper without the keyword `run` in front of it. It is largely
        useful when using interactive mode.

        Args:
            args (str): Name of the Helper to execute.

        Returns:
            int: The result of :py:meth:`firewheel.cli.firewheel_cli.FirewheelCLI.handle_run`
            which is the number of executable sections in the Helper that encountered
            errors. 0 on success. Negative (e.g. -1) on other errors.

        Examples:
            .. code-block:: bash

                $ firewheel run start_time
                Experiment start time: 03-25-2020 16:19:38 UTC

        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"run {args}")
        try:
            result = self.handle_run(args)
            if not self.interactive:
                return result
        except HelperNotFoundError:
            print(f"{self.cmd_not_found} {args}")
            self.log.exception("Helper not found in session %s", self.session["id"])
            if not self.interactive:
                return 1
        except InvalidHelperTypeError:
            # Try to run the index Helper.
            print("Error: Cannot run a Helper group.")
            self.do_list(args)
        return 0

    def do_docs(self, args):
        """
        Generate documentation file for all available Helpers and commands.

        This command generates an RST file (`helper_docs.rst`) which contains
        the `DESCRIPTION` section for all available Helpers. Additionally,
        the docstring for all available commands is compiled into a single RST
        file (`commands.rst`). These files are then written to the input location
        or, if no argument is passed in, to ``../../../../docs/source/cli`` which
        is where FIREWHEEL's CLI documentation is located if the repository has been
        cloned.

        Args:
            args (str): Optional directory to write docs to. If not provided,
                this path will be ``../../../../docs/source/cli``.

        Examples:
            .. code-block:: bash

                $ firewheel docs
                FIREWHEEL Helper documentation placed in:
                /opt/firewheel/docs/source/cli/helper_docs.rst
                FIREWHEEL Command documentation placed in:
                /opt/firewheel/docs/source/cli/commands.rst

        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"docs {args}")
        if args:
            config_dir = args
        else:
            config_dir = os.path.abspath(
                os.path.join(__file__, "../../../../docs/source/cli")
            )

        # Remove any existing file
        # Add new file with some default text
        helper_description = """Helpers allow the extension of the CLI with new
"commands". They are invoked by name (the most common option) or using the :ref:`command_run` command. The name of the
file defining a Helper is used as the name of that Helper. Helpers available in
the current CLI session can be enumerated using the :ref:`command_list` command.

Below are all the available Helpers within FIREWHEEL. To learn more about Helpers
see :ref:`cli_helper_section`."""
        # Get a list of all the Helpers
        helper_list = self._list_helpers(self.helpers, None)
        helper_list.sort()
        with open(f"{config_dir}/helper_docs.rst", "w", encoding="utf8") as doc_file:
            title = "Available CLI Helpers"
            reference = ".. _cli_helpers:"
            doc_file.write(f"\n{reference}\n")
            doc_file.write(f"\n{title}\n")
            doc_file.write("=" * len(title))
            doc_file.write("\n\n")
            doc_file.write(f"{helper_description}\n\n")

            # Iterate over all the Helpers
            for name in helper_list:
                helper_name = name
                # We can obscure the weird "index" stuff from a user as it might
                # be confusing
                if "index" in name:
                    helper_name = " ".join(name.split()[:-1])
                # Add a link to the Helper so that it can be referenced
                doc_file.write(f".. _helper_{helper_name.replace(' ', '_')}:\n\n")
                # Put the Helper name in the file
                doc_file.write(f"{helper_name}\n")
                doc_file.write("-" * len(helper_name))
                doc_file.write("\n\n")
                doc_file.write(f".. program:: {helper_name}")
                doc_file.write("\n\n")
                # Get the documentation for all the Helpers
                try:
                    (helper, args) = utils.parse_to_helper(helper_name, self.helpers)
                except HelperNotFoundError:
                    doc_file.write(
                        f"Error: Helper '{helper_name}' does not have a "
                        "DESCRIPTION section."
                    )
                    continue

                if "DESCRIPTION" not in helper:
                    doc_file.write(
                        f"Error: Helper '{helper_name}' does not have a "
                        "DESCRIPTION section."
                    )
                    continue
                doc_file.write(helper["DESCRIPTION"].format_content())
                doc_file.write("\n")

        print(f"FIREWHEEL Helper documentation placed in: {config_dir}/helper_docs.rst")

        # Get the commands docs
        with open(f"{config_dir}/commands.rst", "w", encoding="utf8") as doc_file:
            # Write beginning of file
            title = "Available CLI Commands"
            doc_file.write("=" * len(title))
            doc_file.write(f"\n{title}\n")
            doc_file.write("=" * len(title))
            doc_file.write("\n\nThese are the built-in commands\n\n")

            # Get all the commands
            for method in sorted(FirewheelCLI.__dict__, key=str.lower):
                if method.startswith("do_"):
                    command = method[3:]
                    cmd_help = f"help_{command}"

                    # Add a link to the Helper so that it can be referenced
                    doc_file.write(f".. _command_{command.replace(' ', '_')}:\n\n")
                    # Put the command name in the file
                    doc_file.write(f"{command}\n")
                    doc_file.write("-" * len(command))
                    doc_file.write("\n\n")
                    doc_file.write(getattr(self, cmd_help)())
                    doc_file.write("\n\n")

        print(f"FIREWHEEL Command documentation placed in: {config_dir}/commands.rst")

    def write_exp_history(self, arg):
        """
        Write to the experiment history file.

        This method writes the experiment the history file to help identify current/past
        experiments.

        Args:
            arg (str): The command/Helper which was typed by the user and should
                be recorded in the history file.
        """

        try:
            # Write to the history file.
            self.history_exp_file.write(f"firewheel {arg.strip()}\n")
        except OSError:
            self.log.error("Unable to write to log file for argument=%s.", arg.strip())

    def write_history(self, arg):
        """
        Write to history file.

        This method writes to the history file and will include the session ID,
        session sequence number, and the passed in argument.

        Args:
            arg (str): The command/Helper which was typed by the user and should
                be recorded in the history file.
        """

        try:
            # Write out experiments to a separate file
            if arg and arg.startswith("experiment"):
                self.write_exp_history(arg)

            # Write to the history file.
            self.history_file.write(
                f"{self.session['id']}:"
                f"{self.session['sequence_number']} -- "
                f"{arg.strip()}\n"
            )
        except OSError:
            self.log.error("Unable to write to log file for argument=%s.", arg.strip())

    def do_history(self, args):
        """
        Print the history of commands/Helpers.

        Shows full command line as entered and includes the associated sequence number
        and session ID. History is preserved between sessions and until the logs are
        cleared (typically during a ``firewheel restart hard``.
        The output is shown in the form of ``<Count>: <ID>:<Sequence Number> -- <command>``.

        Args:
            args (str): This argument is ignored.

        Example:
            .. code-block:: bash

                $ firewheel history
                <Count>: <ID>:<Sequence Number> -- <command>
                0: 1ff79073-5e4a-4279-9d4c-8d81168736b1:0 -- vm mix
                1: 1fcb30cb-00fb-4179-b99c-b2f4ae6f7577:0 -- list
                2: a7af6f9c-6eb3-46b4-b6d8-9c0f9604808d:0 -- version
                ...

        """
        config = Config().get_config()
        if args.startswith("experiment"):
            self.history_exp_file.close()

            exp_path = os.path.join(config["logging"]["root_dir"], "experiment.history")
            try:
                with open(exp_path, "r", encoding="utf8") as f_hand:
                    lines = f_hand.read().splitlines()
                    if not lines:
                        print(
                            "No experiments have been run or the history has been deleted!"
                        )

                    else:
                        for line in lines:
                            print(f"{line.strip()}")
            except OSError:
                print("No experiments have been run or the history has been deleted!")

            # pylint: disable=consider-using-with
            self.history_exp_file = open(
                os.path.join(config["logging"]["root_dir"], "experiment.history"),
                "a",
                encoding="utf8",
            )
            self.write_history(f"history {args}")
            return

        counter = 0
        # We can't write after we iterate, so give us our own file descriptor.
        self.history_file.close()
        # pylint: disable=consider-using-with
        self.history_file = open(
            os.path.join(config["logging"]["root_dir"], "cli_history.log"),
            "r",
            encoding="utf8",
        )
        print("<Count>: <ID>:<Sequence Number> -- <command>")
        for line in self.history_file:
            print("%d: %s" % (counter, line.strip("\n")))  # noqa: FS001
            counter += 1
        # We're done, reset our file descriptor.
        self.history_file.close()
        # pylint: disable=consider-using-with
        self.history_file = open(
            os.path.join(config["logging"]["root_dir"], "cli_history.log"),
            "a",
            encoding="utf8",
        )
        # Write to the history file.
        if not self.interactive:
            self.write_history("history")

    def do_sync(self, _args):  # pragma: no cover
        """
        Update the Helper cache on all hosts controlled by the CLI.

        This command essentially calls :py:func:`firewheel.cli.host_accessor.sync`.
        All Helpers are executed from this cache. Therefore, this command should be run
        on the creation of a new FIREWHEEL cluster and after updating a Helper.

        Args:
            _args (str): This argument is ignored.

        Example:
            .. code-block:: bash

                $ firewheel sync
                $

        """
        # Write to the history file.
        if not self.interactive:
            self.write_history("sync")
        sync(self.session, self.helpers)

    def do_config(self, args):  # pragma: no cover
        """
        Enables command-line access to get and set the FIREWHEEL configuration.

        This command essentially calls
        :py:class:`firewheel.cli.configure_firewheel.ConfigureFirewheel`.

        Args:
            args (str): This argument is passed to
                :py:class:`firewheel.cli.configure_firewheel.ConfigureFirewheel`
                to handle.

        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"config {args}")
        ConfigureFirewheel().onecmd(args)

    def base_do_help(self, arg):
        """
        List available commands with "help" or detailed help with "help cmd".

        This is a slightly modified version of do_help from the base class.
        Here, if the help method isn't found, it raises the AttributeError
        to the calling method.

        Args:
            arg (str): the command/Helper from which we need to get the help docs.

        Raises:
            AttributeError: Caused if the help method isn't found.
        """
        # This copied from the base class
        if arg:
            try:
                name = "help_" + arg
                func = getattr(self, name)
            except AttributeError:
                try:
                    doc = getattr(self, "do_" + arg).__doc__
                    if doc:
                        self.stdout.write(f"\n{doc!s}\n")
                        return
                except AttributeError as exp:
                    raise AttributeError(exp) from exp
            print(utils.strip_markup_chrs(func()))
        else:
            names = self.get_names()
            cmds_doc = []
            cmds_undoc = []
            help_dict = {}
            for name in names:
                if name[:5] == "help_":
                    help_dict[name[5:]] = 1
            names.sort()
            # There can be duplicates if routines overridden
            prevname = ""
            for name in names:
                if name[:3] == "do_":
                    if name == prevname:
                        continue
                    prevname = name
                    command = name[3:]
                    if command in help_dict:
                        cmds_doc.append(command)
                        del help_dict[command]
                    elif getattr(self, name).__doc__:
                        cmds_doc.append(command)
                    else:
                        cmds_undoc.append(cmd)

            helper_list = self._list_helpers(self.helpers)
            helper_list.sort()

            # We now will build the help output
            self._print_help_doc(
                cmds=cmds_doc,
                helper_list=helper_list,
                misc_list=list(help_dict),
                undoc_list=cmds_undoc,
            )

    def _print_help_doc(
        self, cmds=None, helper_list=None, misc_list=None, undoc_list=None
    ):
        """
        Print the "help" documentation using `rich`.

        Args:
            cmds (list): A list of available commands.
            helper_list (list): A list of available Helpers.
            misc_list (list): A list of any miscellaneous documentation.
            undoc_list (list): A list of any undocumented commands.
        """
        console = Console()
        console.print(Markdown(self.doc_header))

        # Print all commands
        formatted_cmds = [f"[yellow]{com}" for com in cmds]
        console.print(
            Markdown("## Available CLI Commands"),
            Columns(formatted_cmds, column_first=True, padding=(0, 4)),
        )

        # Print all Helpers
        helper_list_fmt = [f"[yellow]{helper}" for helper in helper_list]
        console.print(
            Markdown("## Available CLI Helpers"),
            Columns(helper_list_fmt, column_first=True, padding=(0, 4)),
        )

        # Print all Misc Topics and Undocumented commands
        if misc_list:
            console.print(
                Markdown(f"## {self.misc_header}"),
                Columns(misc_list, column_first=True, padding=(0, 4)),
            )
        if undoc_list:
            console.print(
                Markdown(f"## {self.undoc_header}"),
                Columns(undoc_list, column_first=True, padding=(0, 4)),
            )

    def invalid_helper(self, arg):
        """
        Identify what the user was asking help on and give them a starting point.

        Args:
            arg (str): Specify a group to list.
        """
        self.do_list(arg)
        print("For additional help, use firewheel help <full command>")

    def do_help(self, arg):
        """
        Print the help text for Helpers and commands.

        For Helpers, the `DESCRIPTION` section is printed. For Commands, the
        docstring is printed. In `interactive` mode all commands/Helpers can be
        tab completed.

        Args:
            arg (str): the command/Helper from which we need to get the help docs.

        Example:
            .. code-block:: bash

                $ firewheel help history
                Print the history of commands/Helpers.

                Shows full command line as entered and includes the associated sequence number
                ...

            .. code-block:: bash

                $ firewheel help vm mix
                Generates a table showing the VM Images for a running experiment. The
                table also includes the power state of the VMs and the vm_resource
                state. Images that are the same and have the same power/vm_resource
                state are grouped. The count of the various VMs are provided.
                Additionally, the total number of scheduled VMs is shown at the bottom
                of the table.

                ...

        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"help {arg}")
        try:
            self.base_do_help(arg)
        except AttributeError:
            try:
                # pylint: disable=unused-variable
                (helper, _args) = utils.parse_to_helper(arg, self.helpers)
            except HelperNotFoundError:
                print(f"{self.cmd_not_found} {arg}")
                return
            except InvalidHelperTypeError:
                self.invalid_helper(arg)
                return
            if "DESCRIPTION" in helper and helper["DESCRIPTION"].has_content():
                print(
                    utils.strip_markup_chrs(
                        helper["DESCRIPTION"].format_content(pre="")
                    )
                )

    def do_version(self, arg):
        """
        Print FIREWHEEL's version.

        Args:
            arg (str): This argument is ignored.

        Example:
            .. code-block:: bash

                $ firewheel version
                2.6.0
        """
        # Write to the history file.
        if not self.interactive:
            self.write_history(f"version {arg}")
        print(version("firewheel"))

    def help_list(self):
        """Help message for the list command.

        Returns:
            str: The docstring for :py:meth:`do_list`.
        """

        return textwrap.dedent(self.do_list.__doc__)

    def help_author(self):
        """
        Help message for the author command.

        Returns:
            str: The docstring for :py:meth:`do_author`.
        """
        return textwrap.dedent(self.do_author.__doc__)

    def help_run(self):
        """
        Help message for the run command.

        Returns:
            str: The docstring for :py:meth:`do_run`.
        """
        return textwrap.dedent(self.do_run.__doc__)

    def help_docs(self):
        """
        Help message for the docs command.

        Returns:
            str: The docstring for :py:meth:`do_docs`.
        """
        return textwrap.dedent(self.do_docs.__doc__)

    def help_history(self):
        """
        Help message for the history command.

        Returns:
            str: The docstring for :py:meth:`do_history`.
        """
        return textwrap.dedent(self.do_history.__doc__)

    def help_version(self):
        """
        Help message for the version command.

        Returns:
            str: The docstring for :py:meth:`do_version`.
        """
        return textwrap.dedent(self.do_version.__doc__)

    def help_sync(self):
        """
        Help message for the sync command.

        Returns:
            str: The docstring for :py:meth:`do_sync`.
        """
        return textwrap.dedent(self.do_sync.__doc__)

    def help_config(self):
        """
        Help message for the config command.

        Returns:
            str: The help message for
            :py:class:`firewheel.cli.configure_firewheel.ConfigureFirewheel`.
        """
        doc = ConfigureFirewheel().get_docs()
        return doc

    def help_init(self):
        """
        Help message for the init command.

        Returns:
            str: The help message for :py:class:`firewheel.cli.init_firewheel.InitFirewheel`.
        """
        doc = textwrap.dedent(InitFirewheel().get_docs())
        return doc

    def help_help(self):
        """
        Help message for the help command.

        Returns:
            str: The help message for :py:meth:`do_help`.
        """
        return textwrap.dedent(self.do_help.__doc__)

    # CLI Quitting Commands

    def do_exit(self, _args):
        """
        Process the exit command, and perform the expected termination of the CLI.

        Both :py:meth:`do_exit` and :py:meth:`do_quit` are aliases.

        Args:
            _args (str): This argument is ignored.

        Returns:
            bool: This always returns True:
        """
        return True

    def do_EOF(self, _args):  # noqa: N802
        """
        Process the EOF command, and perform the expected termination of the CLI.

        Args:
            _args (str): This argument is ignored.

        Returns:
            bool: This always returns True:
        """
        # Print out a new line to prevent an unnecessarily long prompt
        print("")
        return True

    def do_quit(self, _args):
        """Process the quit command, and perform the expected termination of the CLI.

        Both :py:meth:`do_exit` and :py:meth:`do_quit` are aliases.

        Args:
            _args (str): This argument is ignored.

        Returns:
            bool: This always returns True:
        """
        return True

    def help_exit(self):
        """
        Help message for the exit command.

        Returns:
            str: The help message
        """
        doc = "\nExits the command line\n"
        return doc

    # pylint: disable=invalid-name
    def help_EOF(self):  # noqa: N802
        """
        Help message for the EOF command.

        Returns:
            str: The help message
        """
        doc = "\nProcess the exit command, and perform the expected termination of the CLI\n"
        return doc

    def help_quit(self):
        """
        Help message for the quit command.

        Returns:
            str: The help message
        """
        doc = "\nExits the command line\n"
        return doc

    # Auto-complete section to allow for tab completion of files

    def complete_author(self, text, line, _begidx, _endidx):
        """
        Tab completion for the author command.

        We expect a Helper name, so we need to give the list
        of Helper names as potential completions.

        Args:
            text (str): The partial text to search.
            line (str): The full line on the command.
            _begidx (int): This argument is ignored.
            _endidx (int): This argument is ignored.

        Returns:
            list: A list of potential Helper names.
        """
        mline = line.partition(" ")[2]
        offs = len(mline) - len(text)
        return [
            s[offs:] for s in self._list_helpers(self.helpers) if s.startswith(mline)
        ]

    def complete_run(self, text, line, _begidx, _endidx):
        """
        Tab completion for the run command.

        We expect a Helper name, so we need to give the list
        of Helper names as potential completions.

        Args:
            text (str): The partial text to search.
            line (str): The full line on the command.
            _begidx (int): This argument is ignored.
            _endidx (int): This argument is ignored.

        Returns:
            list: A list of potential Helper names.
        """
        mline = line.partition(" ")[2]
        offs = len(mline) - len(text)
        return [
            s[offs:] for s in self._list_helpers(self.helpers) if s.startswith(mline)
        ]

    def complete_help(self, text, line, _begidx, _endidx):
        """
        Tab completion for the help command.

        We expect a Helper or command name, so we need to give the list
        of Helper names as potential completions.

        Args:
            text (str): The partial text to search.
            line (str): The full line on the command.
            _begidx (int): This argument is ignored.
            _endidx (int): This argument is ignored.

        Returns:
            list: A list of potential Helper names.
        """
        mline = line.partition(" ")[2]
        offs = len(mline) - len(text)
        complete_list = self._list_helpers(self.helpers)

        for method in sorted(FirewheelCLI.__dict__, key=str.lower):
            if method.startswith("do_"):
                command = method[3:]
                complete_list.append(command)

        return [s[offs:] for s in complete_list if s.startswith(mline)]


def main():  # pragma: no cover
    """Provide an entry point to the FIREWHEEL CLI."""
    if len(sys.argv) > 1:
        argstr = shlex.join(sys.argv[1:])
        try:
            sys.exit(FirewheelCLI().onecmd(argstr))
        except KeyboardInterrupt:
            sys.exit(1)
    else:
        FirewheelCLI(interactive=True).cmdloop("FIREWHEEL Infrastructure CLI")


if __name__ == "__main__":
    main()
