"""This module enables access to get and set FIREWHEEL's configuration.

Attributes:
    config (dict): This is a convenient way to access FIREWHEEL's configuration
        dictionary.

Examples:
    This module could be leveraged either by using :py:attr:`config` to
    directly access the configuration:

    >>> from firewheel.config import config
    >>> print(config["logging"]["firewheel_log"])
    firewheel.log

    Alternatively, users can leverage the :py:class:`Config`:

    >>> from firewheel.config import Config
    >>> fw_config = Config()
    >>> print(fw_config.config["logging"]["firewheel_log"])
    firewheel.log
"""

import shlex
import shutil
from typing import Any, Set, Dict, List, Final, Tuple, Union
from pathlib import Path

import yaml
from dotenv import dotenv_values
from rich.console import Console

from firewheel.lib.utilities import strtobool

CONFIG_MODULE_PATH = Path(__file__).parent


class Config:
    """Provide an interface to ``firewheel.yaml``.

    This `class` enables programmatic interaction with FIREWHEEL's configuration.
    through various getters and setters. Aside from manually editing
    :ref:`firewheel_yaml`, this Class should be the single programmatic interface
    to those settings.

    This `class` (or :py:attr:`config`) can be accessed asynchronously by any
    FIREWHEEL module. This can cause issues if there are multiple simultaneous writers.
    However, almost all FIREWHEEL code relies on *reading* values from the
    configuration. Additionally, we try to prevent this by restricting write access
    to functions which specifically request it. This prevents accidental writes
    to the config.

    Note:
        We recommend limiting the setting of configuration variables and saving
        the configuration to only the CLI :ref:`command_config` command.

    """

    _config_template_path = CONFIG_MODULE_PATH / "config-template.yaml"
    _default_config_path = CONFIG_MODULE_PATH.parent / "firewheel.yaml"

    def __init__(self, config_path: str = "", writable: bool = False) -> None:
        """Initialize the FIREWHEEL configuration.

        This should read the configuration for :ref:`firewheel_yaml` to enable access
        for various FIREWHEEL modules.

        Args:
            config_path (str): A specific path to locate the configuration file.
                If this is not provided, it is assumed that the default file
                location (``./firewheel.yaml``) is used.
            writable (bool): Enable users to overwrite the configuration file
                if this is ``True``. Defaults to ``False``.

        Raises:
            RuntimeError: If the configuration file is malformed.

        Attributes:
            config (dict): A dictionary representation of FIREWHEEL's configuration.
            config_path (str, pathlib.Path): The path of the configuration file.
            __writable (bool): Indicates whether the current Class instantiation can
                write the existing config to :ref:`firewheel_yaml`. This should be used
                with caution to ensure that in-memory copies of the config are up-to-date.
        """
        # Handle arguments
        self.config_path = (
            Path(config_path) if config_path else self._default_config_path
        )
        self.__writable: Final = writable
        # Copy the template in cases where the file does not already exist
        if not self.config_path.exists():
            self.generate_config_from_defaults()
        # Load the configuration parameters from the file
        self.config: Dict[
            str,
            Union[
                int,
                str,
                bool,
                Dict[str, Union[int, str, bool]],
                List[Union[int, str, bool]],
            ],
        ] = {}
        self._load_config_file()

    def generate_config_from_defaults(self) -> None:
        """Generate a configuration file from the default file template."""
        shutil.copy(self._config_template_path, self.config_path)
        Console().print(
            "A configuration file was produced based on the FIREWHEEL "
            "defaults. You may either edit this configuration file "
            f"([magenta]{self.config_path}[/ magenta]) or register a new config file "
            "using [cyan]firewheel config set -f <path-to-config>[/ cyan]."
        )

    def _load_config_file(self) -> None:
        with self.config_path.open("r", encoding="utf8") as fhand:
            try:
                self.config = yaml.safe_load(fhand)
            except yaml.YAMLError as exp:
                raise RuntimeError("Malformed configuration file!") from exp

    def convert_logging(self) -> None:
        """Convert logging arguments to uppercase if they are a :obj:`str`.

        This method checks the type of ``self.config["logging"]["level"]``
        and verifies that it is an integer. If it is not, it then converts to
        uppercase and checks that it is the string representation of the common
        Python `Logging Levels`_.
        If no logging level is found, this config value is created and set to
        `INFO`.

        Raises:
            TypeError: If the value is not a integer nor one of
                {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}.

        .. _Logging Levels: https://docs.python.org/3/library/logging.html#logging-levels.
        """
        predefined_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        default_value = "INFO"
        try:
            if not isinstance(self.config["logging"]["level"], int):
                # Convert to upper case
                self.config["logging"]["level"] = str(
                    self.config["logging"]["level"]
                ).upper()

                if self.config["logging"]["level"] not in predefined_levels:
                    # Unknown log level
                    raise TypeError(
                        f"Unknown log level {self.config['logging']['level']}. "
                        f"Must be an integer one of {predefined_levels}."
                    )
        except KeyError:
            # No logging level found defaulting to `info`
            if "logging" not in self.config:
                self.config["logging"] = {}
            self.config["logging"]["level"] = default_value

    def check_cluster(self) -> None:
        """Synchronize the number of nodes in the cluster with the minimega mesh degree.

        This method verifies that the ``self.config["minimega"]["degree"]``
        matches the total number of nodes in the cluster. If there is a mismatch
        it is assumed that the cluster config is correct and the minimega
        degree will be updated accordingly.

        Additionally, this method verifies that there is only ONE control node.
        If there are more (or less), it prints a warning.
        """
        if len(self.config["cluster"]["control"]) != 1:
            Console().print(
                f"[b yellow]WARNING: There must be only ONE control node. Currently have: "
                f"[cyan]{len(self.config['cluster']['control'])}[/ cyan]"
            )

        nodes: Set[str] = set()
        nodes.update(self.config["cluster"]["control"])
        nodes.update(self.config["cluster"]["compute"])

        if self.config["minimega"]["degree"] != len(nodes):
            Console().print(
                f"[b yellow]There is a mismatch between minimega degree and the number of "
                f"nodes in the cluster. Updating minimega degree to be [cyan]{len(nodes)}[/cyan]."
            )
            Console().print(nodes)
            self.config["minimega"]["degree"] = len(nodes)

    def check_minimega_config(self) -> None:
        """Synchronize the minimega configuration with the values in the FIREWHEEL config.

        This method verifies that the ``self.config["minimega"]["base_dir"]`` and
        ``self.config["minimega"]["files_dir"]`` matches the values in
        ``/opt/minimega/misc/daemon/minimega.conf``. If there is a mismatch
        it is assumed that the FIREWHEEL config is correct and the minimega
        configuration will be updated accordingly.
        """
        default_minimega_config_path = Path(
            f"{self.config['minimega']['install_dir']}/misc/daemon/minimega.conf"
        )
        default_minimega_docker_config_path = Path("/etc/default/minimega")
        if not default_minimega_config_path.exists():
            if not default_minimega_docker_config_path.exists():
                print(
                    f"The minimega config at {default_minimega_config_path} nor "
                    f"{default_minimega_docker_config_path} does not exist!"
                )
            default_minimega_config_path = default_minimega_docker_config_path
        try:
            minimega_config = dotenv_values(default_minimega_config_path)

            if self.config["minimega"]["base_dir"] != minimega_config["MM_RUN_PATH"]:
                self._update_minimega_config_value(
                    minimega_config,
                    default_minimega_config_path,
                    "MM_RUN_PATH",
                    "base_dir",
                    description="the minimega base directory",
                )

            if self.config["minimega"]["files_dir"] != minimega_config["MM_FILEPATH"]:
                self._update_minimega_config_value(
                    minimega_config,
                    default_minimega_config_path,
                    "MM_FILEPATH",
                    "files_dir",
                    description="the minimega files directory",
                )
        except KeyError:
            print(
                f"The minimega config at {default_minimega_config_path} nor "
                f"{default_minimega_docker_config_path} does not exist!"
            )

    def _update_minimega_config_value(
        self,
        minimega_config,
        default_minimega_config_path,
        minimega_config_parameter,
        firewheel_config_parameter,
        description=None,
    ):
        description = description or f"minimega parameter {minimega_config_parameter}"
        Console().print(
            f"[b yellow]WARNING: Updating {description}. Currently have:"
            f"[cyan]{minimega_config[minimega_config_parameter]}[/ cyan]"
        )
        mm_env_vals = default_minimega_config_path.read_text(encoding="UTF-8")
        # Add extra double quotes to prevent updating similar paths that are not exact
        mm_env_vals = mm_env_vals.replace(
            '"' + minimega_config[minimega_config_parameter] + '"',
            '"' + self.config["minimega"][firewheel_config_parameter] + '"',
        )
        default_minimega_config_path.write_text(mm_env_vals)

    def check_config(self) -> None:
        """Check various configuration values to ensure correct formatting.

        This method call a series of other methods in an effort to correct
        potential formatting errors. It current calls:

            * :py:meth:`convert_logging`
            * :py:meth:`check_cluster`
        """
        self.convert_logging()
        self.check_cluster()
        self.check_minimega_config()

    def get_config(self) -> Dict[str, Any]:
        """Get the currently instantiated configuration.

        Returns:
            dict: The current FIREWHEEL configuration.
        """
        return self.config

    def set_config(
        self,
        new_config: Dict[
            str,
            Union[
                int,
                str,
                bool,
                Dict[str, Union[int, str, bool]],
                List[Union[int, str, bool]],
            ],
        ],
    ) -> None:
        """Set configuration to the value of the passed-in configuration.

        Note:
            This only changes the in-memory copy of the configuration and does
            **NOT** actually write the configuration to a file. This is to prevent
            possible issues with multiple writers.

        Args:
            new_config (dict): A new FIREWHEEL configuration dictionary.

        Todo:
            * In the future, it might be better to validate the incoming
              configuration with a schema. We could use a tool like `Yamale`_
              to help with this.

        .. _Yamale: https://github.com/23andMe/Yamale
        """
        self.config = new_config
        self.check_config()

    def resolve_get(
        self, key: str, space_sep: bool = True
    ) -> Union[
        int, str, bool, Dict[str, Union[int, str, bool]], List[Union[int, str, bool]]
    ]:
        """Get the value of a specific key.

        This helper method enables getting the value for a specific configuration
        key. If a nested key is requested it should be represented using periods
        to indicate the nesting. This function will return the Python object
        of the key. Alternatively, if the value is a list, the user can return
        a space separated string.

        Args:
            key (str): The input key to get in *dot* notation. This means that
                nested keys should separated using a period. For example, to get
                ``self.config["logging"]["level"]`` the key would be
                ``'logging.level'``.
            space_sep (bool): Indicate whether to return list values as a space
                separated string or as a Python ``list`` object. Defaults to ``True``.

        Returns:
            Union[str, int, list, dict]: The value of the specified key.

        Examples:
            To get the value of ``self.config["cluster"]["compute"]`` as
            a space separated string users can run:

            >>> # Initialize the config
            >>> from firewheel.config import Config
            >>> fw_config = Config()
            >>> # Initialize the config option
            >>> fw_config.config["cluster"]["compute"] = ["host1", "host2", "host3"]
            >>> fw_config.resolve_get("cluster.compute")
            "host1 host 2 host3"

            To get the same key as a Python object users can run:

            >>> fw_config.resolve_get("cluster.compute", space_sep=False)
            ["host1", "host2", "host3"]

        """
        value = self.resolve_key(key)[0]
        if isinstance(value, list) and space_sep:
            return " ".join(str(x) for x in value)
        return value

    def resolve_set(
        self, key: str, value: str
    ) -> Union[
        int, str, bool, Dict[str, Union[int, str, bool]], List[Union[int, str, bool]]
    ]:
        """Set the value of a specific key to the given value.

        This helper method enables setting the value for a specific configuration
        key. If a nested key is requested, it should be represented using periods
        to indicate the nesting. This function will return the newly set value
        using :py:meth:`resolve_get`.

        Note:
            This only changes the in-memory copy of the configuration and does
            **NOT** actually write the configuration to a file. This is to prevent
            possible issues with multiple writers.

        Args:
            key (str): The input key to set in *dot* notation. This means that
                nested keys should separated using a period. For example, to set
                ``self.config["logging"]["level"]`` the key would be
                ``'logging.level'``.
            value (str): The new value of the key. This method will automatically
                attempt to convert that value into the correct Python type.

        Returns:
            Union[str, int, list, dict]: The new value of the specified key.

        Raises:
            ValueError: If the passed in value type cannot be converted into
                the type of the previous value.
        """
        cur_value, resolved_key, parent_dict = self.resolve_key(key)

        # Set the correct type of the input data
        try:
            if isinstance(cur_value, list):
                value = shlex.split(value)
            elif isinstance(cur_value, bool):
                value = bool(strtobool(value))
            elif cur_value is not None:
                value = type(cur_value)(value)
        except ValueError as exp:
            # We can accept a logging level as a string as it will be
            # converted later in the function.
            if key != "logging.level":
                raise ValueError(
                    f"The key={key} should take a value of type={type(cur_value)}. "
                    f"The passed in value={value} is not of that type."
                ) from exp

        parent_dict[resolved_key] = value
        self.check_config()
        return self.resolve_get(key)

    def resolve_key(
        self, key: str
    ) -> Tuple[
        Union[
            int,
            str,
            Dict[str, Union[int, str, bool]],
            List[Union[int, str, bool]],
            None,
        ],
        str,
        Dict[
            str,
            Union[
                int,
                str,
                bool,
                Dict[str, Union[int, str, bool]],
                List[Union[int, str, bool]],
            ],
        ],
    ]:
        """Identify the configuration key based on a period-separated string.

        This method is used by :py:meth:`resolve_get` and :py:meth:`resolve_set` to
        identify and return a configuration option based on a key which uses periods
        to separate dictionary levels. We assume that there is only a single level
        in the :py:attr:`Config.config` dictionary. This example would be expected::

            {
                "logging": {
                    "firewheel_log": "firewheel.log",
                    ...
                }
            }

        Whereas this example is **INVALID**::

            {
                "logging": {
                    "files": {
                        "firewheel": "firewheel.log",
                        ...
                    }
                }
            }

        Args:
            key (str): The input key to get in *dot* notation. This means that
                nested keys should separated using a period. For example, to get
                ``self.config["logging"]["level"]`` the key would be
                ``'logging.level'``.

        Returns:
            tuple: Containing the current value of the found key, the key, and
            a parent dictionary.

        Raises:
            RuntimeError: If there is not a valid ``leaf_key``.
            AttributeError: Users can not add *top-level* attributes to the
                configuration to prevent accidental configuration modification.
        """
        split_key = key.split(".")
        leaf_key = split_key[-1]
        key_path = split_key[:-1]
        if not leaf_key:
            raise RuntimeError(f"No leaf key found for {key}")
        current_d = self.config
        try:
            for key_p in key_path:
                current_d = current_d.get(key_p)
            resolved_value = current_d.get(leaf_key)
        except AttributeError as exp:
            # Quickly converting the config keys to a list:
            # https://stackoverflow.com/a/45253740
            raise AttributeError(
                f"Provided key={key} is not valid. To prevent potential issues, "
                f"top-level configuration keys cannot be added. Existing keys "
                f"include: {[*self.config]}."
            ) from exp
        parent_d = current_d
        return (resolved_value, leaf_key, parent_d)

    def write(self) -> None:
        """Write the current config to :ref:`firewheel_yaml`.

        If the user has set enabled write-access, then the current configuration
        i.e. :py:attr:`Config.config` will be saved to disk by overwriting :ref:`firewheel_yaml`.

        Raises:
            PermissionError: If the user has not initialized the instance with
                write access.
        """
        if not self.__writable:
            raise PermissionError(
                "ERROR: Cannot write to FIREWHEEL config. Only users accessing "
                "the config through the ``firewheel config`` command should change "
                "settings to reduce possibilities of errors."
            )

        with open(self.config_path, "w", encoding="utf8") as fhand:
            yaml.safe_dump(self.config, fhand, sort_keys=True, indent=4)
