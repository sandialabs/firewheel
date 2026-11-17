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

    Alternatively, users can leverage the :py:class:`Config <firewheel.config._config.Config>`:

    >>> from firewheel.config import Config
    >>> fw_config = Config()
    >>> print(fw_config.config["logging"]["firewheel_log"])
    firewheel.log
"""

from ._config import Config, FirewheelConfig

config: FirewheelConfig = Config().get_config()
