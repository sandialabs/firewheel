import sys
import shlex
import getopt
import subprocess
from abc import ABC, abstractmethod
from time import sleep
from pathlib import Path
from itertools import chain

from rich.syntax import Syntax
from rich.console import Console

from firewheel.cli.utils import cli_output_theme
from firewheel.lib.minimega.api import minimegaAPI


def parse_destination(remote_name):
    """
    Split a machine name destination into its user and host components.

    Given the name of a machine destination, separate the name into its user
    and host components. The components are split by the '@' symbol.

    Args:
        remote_name (str): The name of the machine.

    Returns:
        tuple: A tuple of ``(user, host)``.
        Where ``user`` is a string which is the username component (may be an empty string if the
        username is implied) and ``host`` is a string of the hostname component.
    """
    user, _, host = remote_name.rpartition("@")
    return user, host


def parse_location(location):
    """
    Split a file location into its user/hostname and path components.

    Given the location of a file, separate the string into its user/hostname
    and path components. The components are split by a colon.

    Args:
        location (str): The location of a file (including user/hostname and the
            filename).

    Returns:
        tuple: A tuple of ``(user_host, filename)``.
        Where ``user_host`` is a string of the user/hostname component and
        ``filename`` is a string of the name of the file on the machine described
        by the first component.

    Note:
        This method assumes that all filenames do not contain any colons.
        Colons are permitted in the user/hostname pair, in addition to their
        use as the standard separator between the machine name and the filename.
    """
    # This assumes that filenames will not have colons
    user_host, _, filename = location.rpartition(":")
    return user_host, filename


class _SSHProtocolManager(ABC):
    """
    Class managing SSH-based protocol calls made from a helper.;
    """

    # Create a `rich.Console` object for displaying console outputs
    _console = Console(theme=cli_output_theme)

    def __init__(
        self, max_call_attempts=10, capture_output=False, test_connections=True
    ):
        # Use minimega API to identify local host
        self._mm_api = minimegaAPI()
        self.local_hostname = self._mm_api.cluster_head_node
        # Save information about connection preferences
        self.max_call_attempts = max_call_attempts
        self._capture_output = capture_output
        self._test_connections = test_connections

    @property
    @abstractmethod
    def protocol_name(self):
        raise NotImplementedError("Define the protocol name in a subclass.")

    @property
    @abstractmethod
    def flag_options(self):
        raise NotImplementedError("Define available flags in a subclass.")

    @property
    @abstractmethod
    def argument_options(self):
        raise NotImplementedError(
            "Define available options taking arguments in a subclass."
        )

    @property
    def default_options(self):
        """
        Default options for the protocol (set by FIREWHEEL).

        Returns:
            list: The list of default options to include in the protocol instruction.
        """
        options = [
            ("-o", "LogLevel=error"),
            ("-o", "UserKnownHostsFile=/dev/null"),
            ("-o", "StrictHostKeyChecking=no"),
            ("-o", "HostKeyAlgorithms=+ssh-rsa"),
            ("-o", f"ProxyCommand ssh -o BatchMode=yes {self.local_hostname} -W %h:%p"),
        ]
        return options

    @property
    def _control_network_err_msg(self):
        err_msg = (
            "A control network is required to use [inline_code]`firewheel ssh`[/inline_code] or "
            "[inline_code]`firewheel scp`[/inline_code] with minimega emulation.\n"
            "If you would like to add a control network to your experiment you can do so by adding "
            "[inline_code]`control_network`[/inline_code] to your experiment command. For example:"
        )
        err_msg_example = Syntax(
            "firewheel experiment tests.router_tree:5 control_network minimega.launch",
            lexer="bash",
        )
        return (err_msg, err_msg_example)

    @property
    def _connection_test_command(self):
        raise NotImplementedError(
            "Define a command to test the connection in a subclass."
        )

    @property
    def _connection_test_interval(self):
        raise NotImplementedError(
            "Define an interval (in seconds) for testing the connection in a subclass."
        )

    @classmethod
    def _generate_error_prefix(cls):
        return f"[error]ERROR ({cls.protocol_name}):[/error]"

    @classmethod
    def _exit(cls, *messages, display_usage=False):
        """
        Exit the method, printing any messages to the console.

        Args:
            *messages: A sequence of objects that can be passed to the console object
                for this manager.
            display_usage (bool): A flag indicating whether the protocol usage
                should be displayed after exiting.
        """
        if messages:
            cls._console.print(cls._generate_error_prefix(), *messages)
        if display_usage:
            # Output the ssh command's usage by calling it without arguments
            subprocess.run(cls.protocol_name.lower(), check=True)  # nosec
        sys.exit(1)

    def _call(self, *args, options):
        """
        Generalized call method.

        This is a call method that is generalized for SSH-based commands.
        All of those commands require positional arguments and options.

        Args:
            *args: Additional positional arguments that are specific to
                the command being executed.
            options (list): A list of options to pass to the SSH/SCP instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            CompletedProcess: The result of the SSH-based subprocess call.
        """
        instruction = self._form_instruction(*args, options=options)
        try:
            result = subprocess.run(
                shlex.split(instruction),
                check=True,
                capture_output=self._capture_output,
            )  # nosec
        except KeyboardInterrupt:
            print("Connection attempt terminated.")
            result = None
        except subprocess.CalledProcessError as exception:
            # Since FIREWHEEL adds extra options, provide a bit more information
            # to help users determine why the command failed
            err_msg = (
                f"\nThe {self.protocol_name} attempt failed with non-zero exit code "
                f"{exception.returncode}.\n"
                f"See the output of {self.protocol_name} (above) for reasons why this failure "
                "occurred. For reference, the exact command issued by FIREWHEEL was:"
            )
            self._exit(err_msg, Syntax(instruction, lexer="bash"))
        return result

    def _resolve_address(self, destination):
        # Convert the hostname to a VM IP
        user, host = parse_destination(destination)
        vm_ip = self._get_remote_vm_ip(host)
        return "@".join(filter(None, [user, vm_ip]))

    def _get_remote_vm_ip(self, remote_hostname):
        """
        Look up the specified VM from among the available minimega VMs.

        Given the hostname for a remote VM, look up the IP address for
        that VM and test that a connection can be made. If not, or the
        IP address does not exist, fail gracefully.

        Args:
            remote_hostname (str): The hostname of the remote VM.

        Returns:
            str: The IP address of the remote VM matching the given hostname.
        """
        vm_dict = self._mm_api.mm_vms()
        try:
            vm_ip = vm_dict[remote_hostname]["control_ip"]
            if not vm_ip:
                self._console.print(*self._control_network_err_msg)
                sys.exit(1)
        except KeyError as exp:
            err_msg = (
                f"No VM with name [bold]{exp}[/bold] is found. "
                "Ensure a VM with that name exists."
            )
            self._exit(err_msg)
        if self._test_connections:
            self._test_vm_connection(vm_ip)
        return vm_ip

    def _test_vm_connection(self, vm_ip):
        """
        Test the connection to the VM.

        Args:
            vm_ip (str): The IP address of the VM whose connection is
                         being tested.
        """
        test_command = (
            "ssh -o LogLevel=error -o UserKnownHostsFile=/dev/null "
            f"-o StrictHostKeyChecking=no -o BatchMode=yes {self.local_hostname} "
            f'"{self._connection_test_command} {vm_ip}"'
        )
        attempt = 1
        with self._console.status("", spinner="line"):
            while True:
                try:
                    subprocess.check_output(shlex.split(test_command))  # nosec
                    break
                except subprocess.CalledProcessError:
                    self._handle_failed_connection(attempt, vm_ip)
                    attempt += 1

    def _handle_failed_connection(self, attempt, vm_ip):
        if attempt > self.max_call_attempts:
            self._exit(
                f"Unable to connect to VM. Access IP [bold]{vm_ip}[/bold] never came up."
            )
        sleep(self._connection_test_interval)

    def _form_instruction(self, *args, options):
        raise NotImplementedError("Specify the instruction to be formed in a subclass.")

    def _prepare_options(self, options):
        """
        Prepare options for inclusion in the protocol instruction.

        Join options specified on the command line with the required default
        options. Joins options lists (tuples of options and arguments) as a
        string ready to be included in the protocol instruction.

        Args:
            options (list): A list of options given as tuples of
                ``(option, value)`` pairs. Options that take no arguments are
                given as length-1 tuples.

        Returns:
            str: A string containing all the options to use in the instruction
            (including defaults).
        """
        # Flatten options and ignore empty strings for flag-like options
        all_options = filter(
            None, chain.from_iterable(self.default_options + list(options))
        )
        return shlex.join(all_options)  # pylint: disable=no-member

    @classmethod
    def _assemble_shortopts_string(cls):
        # `getopts` requires options with arguments to be followed by a colon
        arg_options_string = "".join([f"{_}:" for _ in cls.argument_options])
        return cls.flag_options + arg_options_string

    @classmethod
    def parse_cli_input(cls, argv):
        """
        Given FIREWHEEL input from the command line, separate the options.

        Takes inputs from the command line and separates it into a list of
        options and a list of positional arguments.

        Args:
            argv (list): Command line input components (e.g., in the format of
                ``sys.argv``).

        Returns:
            tuple: A tuple of ``(args, optlist)``.
            Where ``args``is a list of arguments left over after options have been
            stripped and ``optlist`` is a list of tuples giving ``(option, value)`` pairs.
        """
        # First CLI argument is `ssh`/`scp` command
        args = argv[1:]
        # Exit and print usage if no arguments are given
        if not args:
            cls._exit(display_usage=True)
        # Get options (flag and argument options) from the command line input
        shortopts = cls._assemble_shortopts_string()
        try:
            optlist, args = getopt.getopt(args, shortopts)
        except getopt.GetoptError as exception:
            cls._exit(f"{exception!s}", display_usage=True)
        return args, optlist


class SSHManager(_SSHProtocolManager):
    """
    Class managing SSH calls made from a helper.
    """

    protocol_name = "SSH"
    # Available SSH flag/keyword options (OpenSSH 7.2p2)
    flag_options = "1246AaCfGgKkMNnqsTtVvXxYy"
    argument_options = "bcDEeFIiJLlmOopQRSWw"
    # Parameters for testing an SSH connection
    _connection_test_command = "ping -w 1 -c 1"
    _connection_test_interval = 2

    def __init__(
        self, max_call_attempts=10, capture_output=False, test_connections=True
    ):
        """
        Initialize the call manager, setting general parameters.

        Establishes an object that executes SSH commands for use by the
        FIREWHEEL SSH helper. It uses the minimega API to determine the
        current host, then uses that information to make subsequent SSH
        calls to remote VMs.

        Args:
            max_call_attempts (int): The number of times to attempt making calls
                before throwing an error back to the user. By default the "
                caller attempts 10 times.
            capture_output (bool): A flag indicating whether subprocess calls
                will capture output. The default is ``False``.
            test_connections (bool): A flag indicating whether to test
                connections before attempting to execute an SSH-based
                command. The default is ``True``.
        """
        super().__init__(
            max_call_attempts=max_call_attempts,
            capture_output=capture_output,
            test_connections=test_connections,
        )

    def __call__(self, destination, command="", options=()):
        """
        Execute an SSH call.

        Args:
            destination (str): The machine to be accessed, provided as a
                string consisting of a username and hostname (separated by an
                '@' symbol, per convention). If the username is not provided
                it is inferred to be the current user's username.
            command (str): A command to execute after making the SSH
                connection.
            options (list): A list of options to pass to the SSH instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            CompletedProcess: The result of the SSH-based subprocess call.
        """
        # Resolve the address to include its IP address
        destination = self._resolve_address(destination)
        # Execute the SSH call using the new destination address (with IP)
        return self._call(destination, command, options=options)

    def _form_instruction(self, *args, options):
        destination, command = args
        # Pass the arguments to the designated instruction builder
        return self._form_ssh_instruction(destination, command, options)

    def _form_ssh_instruction(self, destination, command, options):
        """
        Add necessary arguments to the user-provided SSH command.

        Create an SSH-specific instruction. Combine any options
        specified by the user with their username and the remote VM IP
        address, along with options that are required by the
        experimental setup.

        Args:
            destination (str): The machine to be accessed, provided as a
                string consisting of a username and VM IP address.
            command (str): A command to execute after making the SSH
                connection.
            options (list): A list of options to pass to the SSH instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            str: The complete SSH instruction.
        """
        instruction_options = self._prepare_options(options)
        return f"ssh {instruction_options} {destination} {command}"

    @classmethod
    def parse_cli_input(cls, argv):
        """
        Given FIREWHEEL SSH input from the command line, separate the options.

        Takes inputs from the command line for executing SSH to a
        FIREWHEEL VM and separates it into a list of options and a
        list of positional arguments.

        Args:
            argv (list): Command line input components (e.g., in the format
                of ``sys.argv``).

        Returns:
            tuple: A tuple of ``(args, optlist)``.
            Where ``args`` is a list of arguments left over after options have been
            stripped. The first is a string giving the target address, the second is a
            string giving the command to be executed after establishing the SSH connection.
            ``optlist`` is a list of tuples giving ``(option, value)`` pairs.
        """
        args, optlist = super(SSHManager, cls).parse_cli_input(argv)
        # All but the first positional argument are elements of the command
        destination, command = args[0], shlex.join(args[1:])
        return [destination, command], optlist


class ParallelSSHManager(_SSHProtocolManager):
    """
    Class managing Parallel SSH calls made from a helper.
    """

    protocol_name = "PSSH"
    # Available SSH flag/keyword options (OpenSSH 7.2p2)
    flag_options = "vAiIP"
    argument_options = "hHlpoetOxX"
    # Parameters for testing an SSH connection
    _connection_test_command = "ping -w 1 -c 1"
    _connection_test_interval = 2

    def __init__(
        self,
        max_call_attempts=10,
        capture_output=False,
        test_connections=False,
    ):
        """
        Initialize the call manager, setting general parameters.

        Establishes an object that executes parallel-ssh commands for
        use by the FIREWHEEL parallel-ssh helper. It uses the minimega
        API to determine the current host, then uses that information to
        make subsequent parallel-ssh calls to remote VMs.

        Args:
            max_call_attempts (int): The number of times to attempt making calls
                before throwing an error back to the user. By default the "
                caller attempts 10 times.
            capture_output (bool): A flag indicating whether subprocess calls
                will capture output. The default is ``False``.
            test_connections (bool): A flag indicating whether to test
                connections before attempting to execute an SSH-based
                command. The default is ``False``. Note that when set,
                connections will be checked individually and performance
                may degrade.
        """
        super().__init__(
            max_call_attempts=max_call_attempts,
            capture_output=capture_output,
            test_connections=test_connections,
        )
        self._tmp_files = []

    @property
    def default_options(self):
        """
        Default options for the parallel-ssh protocol (set by FIREWHEEL).

        Returns:
            list: The list of default options to include in the protocol instruction.
        """
        # SSH options passed by parallel-ssh use a "-O" instead of "-o"
        return [("-O", value) for option, value in super().default_options]

    def __call__(self, command, options=()):
        """
        Execute a parallel SSH call.

        Args:
            command (str): A command to execute after making the SSH
                connection.
            options (list): A list of options to pass to the SSH instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            CompletedProcess: The result of the SSH-based subprocess call.

        Raises:
            ValueError: Raised when neither the ``'h'`` nor ``'-H'`` option
                is provided to define the destination hosts.
        """
        if not any(option in {"-h", "-H"} for option, value in options):
            raise ValueError("For parallel-ssh either `-h` or `-H` must be used")

        processed_options = [
            self._process_option(option, value) for option, value in options
        ]
        result = self._call(command, options=processed_options)

        # Remove temporary files
        while self._tmp_files:
            self._tmp_files.pop().unlink()

        return result

    def _process_option(self, option, value):
        # Process options and their values (e.g., identifying VM IPs from hostnames)
        if option == "-h":
            processed_value = self._process_host_file(value)
        elif option == "-H":
            processed_value = self._process_host_string(value)
        else:
            processed_value = value
        return option, processed_value

    def _process_host_file(self, host_file):
        # Read the host file
        host_file = Path(host_file)
        with host_file.open(encoding="utf-8") as infile:
            host_file_contents = infile.read()
        # Replace VM hostnames with control network IPs
        # (to avoid parsing file line-by-line and then reassembling)
        vm_dict = self._mm_api.mm_vms()
        for hostname, vm_info in vm_dict.items():
            vm_ip = vm_info["control_ip"]
            host_file_contents = host_file_contents.replace(hostname, vm_ip)
        # Write the output to a temporary file
        tmp_host_file = host_file.with_suffix(".tmp")
        with tmp_host_file.open("w", encoding="utf-8") as outfile:
            outfile.write(host_file_contents)
        self._tmp_files.append(tmp_host_file)
        return str(tmp_host_file)

    def _process_host_string(self, host_string):
        # Resolve each host in the (space-separated) string.
        hosts = [self._resolve_address(host) for host in host_string.split(" ")]
        return " ".join(hosts)

    def _form_instruction(self, *args, options):
        command = args[0]
        # Pass the arguments to the designated instruction builder
        return self._form_parallel_ssh_instruction(command, options)

    def _form_parallel_ssh_instruction(self, command, options):
        """
        Add necessary arguments to the user-provided parallel-ssh command.

        Create an parallel-ssh-specific instruction. Combine any options
        specified by the user with options that are required by the
        experimental setup.

        Args:
            command (str): A command to execute after making each SSH
                connection.
            options (list): A list of options to pass to the SSH instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            str: The complete parallel-ssh instruction.
        """
        instruction_options = self._prepare_options(options)
        return f"parallel-ssh {instruction_options} '{command}'"

    def _prepare_options(self, options):
        """
        Prepare options for inclusion in the protocol instruction.

        Join options specified on the command line with the required default
        options. Joins options lists (tuples of options and arguments) as a
        string ready to be included in the protocol instruction.

        Args:
            options (list): A list of options given as tuples of
                ``(option, value)`` pairs. Options that take no arguments are
                given as length-1 tuples.

        Returns:
            str: A string containing all the options to use in the instruction
            (including defaults).
        """  # pylint: disable=useless-super-delegation
        return super()._prepare_options(options)

    @classmethod
    def parse_cli_input(cls, argv):
        """
        Given FIREWHEEL SSH input from the command line, separate the options.

        Takes inputs from the command line for executing SSH to a
        FIREWHEEL VM and separates it into a list of options and a
        list of positional arguments.

        Args:
            argv (list): Command line input components (e.g., in the format
                of ``sys.argv``).

        Returns:
            tuple: A tuple of ``(args, optlist)``.
            Where ``args`` is a list of arguments left over after options have been
            stripped. The first is a string giving the target address, the second is a
            string giving the command to be executed after establishing the SSH connection.
            ``optlist`` is a list of tuples giving ``(option, value)`` pairs.
        """
        args, optlist = super(ParallelSSHManager, cls).parse_cli_input(argv)
        # All but the first positional argument are elements of the command
        destination, command = args[0], shlex.join(args[1:])
        return [destination, command], optlist


class SCPManager(_SSHProtocolManager):
    """
    Class managing SCP calls made from a helper.
    """

    protocol_name = "SCP"
    # Available SCP flag/keyword options (OpenSSH 7.2p2)
    flag_options = "12346BCpqrv"
    argument_options = "cFiloPS"
    # Parameters for testing an SCP connection
    _connection_test_command = "ping -c 1"
    _connection_test_interval = 4

    @property
    def default_options(self):
        """
        Default options for the SCP protocol (set by FIREWHEEL).

        Returns:
            list: The list of default options to include in the protocol instruction.
        """
        scp_options = [("-r", "")]
        return super().default_options + scp_options

    @property
    def _control_network_err_msg(self):
        scp_err_msg_addendum = (
            "\nIf you would like to grab a file off of a VM without adding a "
            "control network, use `firewheel pull`."
        )
        return (*super()._control_network_err_msg, scp_err_msg_addendum)

    def __call__(self, target, *sources, options=()):
        """
        Execute an SCP call.

        Args:
            target (str): The target file to be produced, provided as a string
                consisting of a username, hostname, and file path. (See the
                SCP manual entry for formatting guidance.)
            *sources: The source files to be copied, each provided as a string
                consisting of a username, hostname, and file path. (See the
                SCP manual entry for formatting guidance.)
            options (list): A list of options to pass to the SCP instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            CompletedProcess: The result of the SSH-based subprocess call.

        Raises:
            ValueError: Raised when no source files are provided.
        """
        # Perform quick checks that the input is acceptable
        if not sources:
            raise ValueError("No source files were specified.")
        if not any(":" in location for location in (target, *sources)):
            self._exit(
                "FIREWHEEL SCP instructions require that either the target or "
                "a source contain a ':' to denote a remote location."
            )
        # Resolve locations to include their IP addresses
        target = self._resolve_location(target)
        sources = [self._resolve_location(source) for source in sources]
        # Execute the SCP call using the new locations (with IPs)
        return super()._call(target, *sources, options=options)

    def _resolve_location(self, location):
        # Handle the location info as address and filename components
        user_host, filename = parse_location(location)
        if not user_host:
            # An unstated address is implied to be on the local machine
            return filename
        address = self._resolve_address(user_host)
        # Rejoin the address and files into a single location
        return ":".join([address, filename])

    def _form_instruction(self, *args, options):
        target, sources = args[0], args[1:]
        # Pass the arguments to the designated instruction builder
        return self._form_scp_instruction(target, *sources, options=options)

    def _form_scp_instruction(self, target, *sources, options):
        """
        Add necessary arguments to the user-provided SCP command.

        Create an SCP-specific instruction. Combine any arguments
        specified by the user with their username and the remote VM IP
        address, along with options that are required by the
        experimental setup.

        Args:
            target (str): The target file to be produced, provided as a string
                          consisting of a username, VM IP address, and file path.
            *sources: The source files to be copied, each provided as a string
                      consisting of a username, hostname, and file path.
            options (list): A list of options to pass to the SCP instruction
                given as tuples of ``(option, value)`` pairs. The second element
                (the ``value``) is the empty string for options that take no
                arguments.

        Returns:
            str: The complete SSH instruction.
        """
        instruction_options = self._prepare_options(options)
        return f"scp {instruction_options} {shlex.join(sources)} {target}"

    @classmethod
    def parse_cli_input(cls, argv):
        """
        Given FIREWHEEL SCP input from the command line, separate the options.

        Takes inputs from the command line for executing SCP with FIREWHEEL
        VMs and separates the inputs into a list of positional arguments and
        a list of options.

        Args:
            argv (list): Command line input components (e.g., in the
                         format of `sys.argv`).

        Returns:
            tuple: A tuple of ``(args, optlist)``.
            Where ``args`` is a list of arguments left over after options have been
            stripped. The first is the target destination, while all other arguments
            are the source files to copy to that target.
            ``optlist`` is a list of tuples giving ``(option, value)`` pairs.
        """
        args, optlist = super(SCPManager, cls).parse_cli_input(argv)
        # Python prefers required positional arguments before optional ones
        # and there will only ever be one target; therefore, swap the order
        # of sources/target (now with target first)
        target, sources = args[-1], args[:-1]
        return [target, *sources], optlist
