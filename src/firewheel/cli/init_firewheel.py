import os
import os.path
import tempfile
import textwrap
from cmd import Cmd
from inspect import cleandoc

import colorama
from dotenv import dotenv_values

from firewheel.config import Config
from firewheel.lib.log import Log
from firewheel.lib.minimega.api import minimegaAPI
from firewheel.lib.discovery.api import discoveryAPI


class InitFirewheel(Cmd):
    """
    Enables easy ability for a user to "initialize" a FIREWHEEL node.

    Initialization includes checking various FIREWHEEL config path and verifying
    that non-standard dependencies (minimega and discovery) are installed and working.
    """

    doc_header = "Initialize the FIREWHEEL cluster."

    def __init__(self, cli_path: None = None) -> None:
        """
        This is the constructor which initializes several class variables.

        Args:
            cli_path (str): The path to the CLI binary.
        """
        super().__init__()
        self.load_config = Config()
        self.config = self.load_config.get_config()
        self.log = Log(name="CLI").log
        self.cli_path = cli_path

    def default(self, _line):
        """
        Defined by cmd for the action taken when an unrecognized command is given.

        In the case of :class:`InitFirewheel` there are no sub-commands, so any
        incorrect commands will run this method.

        Args:
            _line (str): The command-line as entered by the user.
        """
        self._check_paths()
        self._check_grpc_config()
        self._check_minimega_socket()
        self._check_discovery_wrapper()

    def emptyline(self):
        """Print help when a blank line is entered.

        Required by :py:mod:`cmd` as the action taken when a blank line is entered.
        We want this to print help.
        """
        self.default([])

    def do_static(self, _args):
        """Do not check if any services are running any only check if they exist.

        Args:
            _args (str): This is unused in this method.
        """
        self._check_paths()
        self._check_grpc_config()
        self._check_discovery_wrapper(check_service=False)

    def help_static(self):
        """
        Help message for the static command.

        Returns:
            str: The docstring for :py:meth:`do_static`.
        """
        return print(self._help_static())

    def _help_static(self) -> str:
        """Help message for the :py:meth:`do_static` sub-command.

        Returns:
            str: The help message.
        """
        return textwrap.dedent(self.do_static.__doc__)

    def _get_success_str(self, success):
        reset_all = colorama.Style.RESET_ALL
        bright = colorama.Style.BRIGHT
        if success:
            return bright + colorama.Fore.GREEN + "OK" + reset_all
        return bright + colorama.Fore.RED + "FAIL" + reset_all

    def _check_grpc_config(self) -> bool:
        """
        Check that the GRPC server has a proper hostname and port.

        Returns:
            bool: :py:data:`True` if there is a proper hostname/port :py:data:`False` otherwise.
        """
        success = False
        grpc_hostname = self.config["grpc"]["hostname"]
        grpc_port = self.config["grpc"]["port"]
        print("Checking whether GRPC has a hostname and port: ", end="")
        # If either port or hostname is Falsey, than we should fail this test
        success = all([grpc_hostname, grpc_port])
        success_str = self._get_success_str(success)
        print(success_str)
        return success

    def _check_minimega_socket(self):
        """
        Check the status of minimega's socket.

        Returns:
            bool: False if minimega is not running, True otherwise.
        """
        try:
            minimegaAPI()
        except (RuntimeError, TimeoutError):
            status = False
        else:
            status = True
        finally:
            success_str = self._get_success_str(status)
            print(f"Checking minimega service status: {success_str}")
        return status

    def _get_minimega_install_dir(self):
        # We should check that the minimega bin is in the expected location.
        success = False
        minimega_install_dir = self.config["minimega"]["install_dir"]
        print(
            f"Checking whether {minimega_install_dir} contains bin/minimega: ", end=""
        )
        expected_minimega_bin = os.path.join(minimega_install_dir, "bin", "minimega")
        success = os.access(expected_minimega_bin, os.X_OK)
        success_str = self._get_success_str(success)
        print(success_str)
        return success

    def _check_cache_dirs(self):
        fw_config = Config(writable=True)
        default_output_dir = fw_config.resolve_get("system.default_output_dir")
        dir_keys = ["logging.root_dir", "cli.root_dir", "grpc.root_dir"]
        print(f"Checking write access to default_output_dir: {default_output_dir}")
        if self._check_access_to_dir(default_output_dir):
            print("Successfully able to write to default_output_dir.")
            for dir_key in dir_keys:
                dir_value = fw_config.resolve_get(dir_key)
                if not dir_value:
                    print(f"{dir_key} is not set. Defaulting to {default_output_dir}.")
                    fw_config.resolve_set(dir_key, default_output_dir)
                else:
                    print(f"{dir_key} has value {dir_value}. Checking write access.")
                    self._check_access_to_dir(dir_value)
                    print(f"Successfully able to write to {dir_value}.")

        # Write out any changes
        fw_config.write()
        # update self.config
        self.config = fw_config.get_config()

    def _check_access_to_dir(self, directory):
        try:
            os.makedirs(directory, exist_ok=True)
            # pylint: disable=unused-variable
            with tempfile.TemporaryFile(dir=directory):
                return True
        except Exception as exp:
            print(f"Unable to write to directory {directory}")
            print("Please ensure that it exists and is writable.")
            raise exp

    def _check_paths(self):
        self._check_cache_dirs()
        self._get_minimega_install_dir()

    def _get_discovery_install_dir(self):
        def _check_discovery_bin(install_dir):
            print(f"Checking whether {install_dir} contains bin/discovery: ", end="")
            expected_discovery_bin = os.path.join(install_dir, "bin", "discovery")
            success = os.access(expected_discovery_bin, os.X_OK)
            success_str = self._get_success_str(success)
            print(success_str)
            return success

        success = False

        # First we check to see if a user set the discovery install_dir
        # was set in the firewheel config.
        try:
            print("Checking whether discovery.install_dir is set in firewheel config.")
            discovery_install_dir = self.config["discovery"]["install_dir"]
            if discovery_install_dir and _check_discovery_bin(discovery_install_dir):
                success = True
                # Because it's already set, we don't need to set it ourselves.
                return discovery_install_dir
        except OSError as exp:
            self.log.exception(exp)

        # If it was not set, then we check the default path for a discovery
        # config file.
        if not success:
            try:
                install_dir_key = "DISCOVERY_DIR"
                default_discovery_config_path = "/etc/discovery/discovery.conf"
                print(
                    f"Checking whether {install_dir_key} is set in {default_discovery_config_path}."
                )
                discovery_config = dotenv_values(default_discovery_config_path)
                discovery_install_dir = discovery_config[install_dir_key]
                if discovery_install_dir and _check_discovery_bin(
                    discovery_install_dir
                ):
                    success = True
            except OSError as exp:
                self.log.exception(exp)
                print(f"Unable to load config from {default_discovery_config_path}")
            except KeyError as exp:
                self.log.exception(exp)
                print(f"Unable to load config from {default_discovery_config_path}")
                return False

        # If we still haven't found it, we check the default discovery install_dir.
        if not success:
            try:
                default_discovery_install_dir = "/opt/discovery"
                discovery_install_dir = default_discovery_install_dir
                print(
                    "Checking whether discovery is installed in its default "
                    f"location ({discovery_install_dir})"
                )
                if discovery_install_dir and _check_discovery_bin(
                    discovery_install_dir
                ):
                    success = True
            except OSError as exp:
                self.log.exception(exp)

        if success:
            print(f"Setting discovery.install_dir={discovery_install_dir}")
            fw_config = Config(writable=True)
            fw_config.resolve_set("discovery.install_dir", discovery_install_dir)
            fw_config.write()
            # update self.config
            self.config = fw_config.get_config()
            return discovery_install_dir

        # If we could not find it. We raise an exception
        error_msg = (
            "Unable to find the discovery install directory. Please set "
            "it using `firewheel config set`."
        )
        raise FileNotFoundError(error_msg)

    def _check_discovery_wrapper(self, check_service: bool = True) -> None:
        if not minimegaAPI.get_am_head_node():
            print("Not checking discovery because we are not the head node.")
            return

        print("Checking discovery because we are the head node.")
        success = self._get_discovery_install_dir()
        success_str = self._get_success_str(success)
        print(f"Checking discovery install_dir: {success_str}")
        if check_service:
            success = self._check_discovery()
            print("Checking discovery service: ", end="")
            print(self._get_success_str(success))

    def _check_discovery(self):
        discovery = discoveryAPI()

        # Try to start discovery service
        if discovery.start_discovery():
            return True
        print(
            "ERROR: The Discovery service cannot be started. "
            f"Check {discovery.log_file} for more information."
        )
        return False

    def _help_help(self):
        """Help message for the help sub-command.

        Returns:
            str: The help message.
        """
        doc = str(
            "    Prints help for the different sub-commands.\n\n    **Usage**: "
            "``firewheel init help <sub-command>``"
        )
        return doc

    def help_help(self):
        """Print help for the help sub-command."""
        print(self._help_help())

    def get_docs(self) -> str:
        """Get the documentation for the set of commands that relate to :ref:`command_init`.

        Returns:
            str: The full documentation for `init` command.
        """
        # Get all the commands
        command_string = "\n" + cleandoc(InitFirewheel.__doc__)
        command_string += "\n\n\n"
        classdict = InitFirewheel.__dict__
        for method in sorted(classdict.keys()):
            if method.startswith("do_"):
                command = method.split("_", maxsplit=1)[-1]
                cmd_help = f"_help_{command}"

                reference = f".. _command_init_{command}:"
                full_cmd = f"init {command}"

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
                command_string += (
                    f"{reference}\n\n"
                    f"{full_cmd}\n"
                    f"{'^' * len(full_cmd)}"
                    f"\n\n{clean_text}\n\n"
                )

        return command_string
