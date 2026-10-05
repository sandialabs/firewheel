import os
import grp
import time
import getpass
import logging

from firewheel.config import config


class Log:
    """
    Contains a set of helper methods which create logs/loggers for FIREWHEEL.
    """

    def __init__(self, name, log_file=None, log_format=None, log_level=None):
        """
        Create logger for the given name.

        This constructor develops a consistent way of logging for FIREWHEEL. If a
        logging handler cannot be created, a warning will be printed to the screen
        and a :py:class:`logging.NullHandler` will be used.

        Additionally, each log file will attempt to update the log files to use the
        FIREWHEEL default group (if any).

        Attributes:
            log (logging.Logger): The logger created by the class.
            log_file (str): The log file name.
            log_file_path (str): The full path to the log file.
            log_level (str): The specified log level.

        Args:
            name (str): What logging name should be used. Typically this is either a
                class name or a FIREWHEEL sub-system name (e.g. CLI).
            log_file (str): Which file should the logger log to.
            log_format (str): A specific logging format.
            log_level (str): The specified log level.
        """
        self.log = logging.getLogger(name)
        self.log.propagate = False
        self.log_file = log_file
        self.log_level = log_level

        # Default to the Control log
        if self.log_file is None:
            self.log_file = config["logging"]["firewheel_log"]

        if self.log_level is None:
            self.log_level = config["logging"]["level"]
        self.log.setLevel(self.log_level)

        # If a Handler for the given logger already exists, no need
        # to create a new one.
        if self.log.hasHandlers():
            return

        try:
            self.log_file_path = os.path.join(
                config["logging"]["root_dir"], self.log_file
            )
            handler: logging.FileHandler | logging.NullHandler = logging.FileHandler(
                filename=self.log_file_path
            )

            # Check and fix the group on the log file.
            if config["system"]["default_group"]:
                try:
                    group = grp.getgrnam(config["system"]["default_group"])
                    # Only attempt to change the group when different from both the
                    # default group and the current user
                    stat_info = os.stat(self.log_file_path)
                    if (
                        stat_info.st_gid != group.gr_gid
                        and stat_info.st_gid != os.getgid()
                    ):
                        os.chown(self.log_file_path, -1, group.gr_gid)
                except KeyError as exp:
                    self.log.warning(
                        "Group %s does not exist. Not setting group on "
                        "default log file and continuing.",
                        exp,
                    )
                except OSError as exp:
                    # We will ignore this warning with CLI logs as this
                    # is common when sharing a node amongst users
                    if "cli.log" not in self.log_file:
                        self.log.warning(
                            "Unable to change group on default log file: %s", exp
                        )
        except TypeError:
            print(
                f"Warning: Unable to open log file at {config['logging']['root_dir']}"
                f"/{self.log_file}"
            )
            print("Warning: Continuing without log.")
            handler = logging.NullHandler()
        except IOError:
            print(f"Warning: Unable to open log file at {self.log_file_path}")
            try:
                # If the existing log file is inaccessible
                # this tries to create a new file by appending the current users
                # username. In the event which the original log file was created
                # by a different user (and therefore has different permissions)
                # this will enable logging to continue. If this still fails,
                # the CLI will continue without a log file.
                username = getpass.getuser()
                filename = (
                    f"{os.path.join(config['logging']['root_dir'], self.log_file)}"
                    f"-{username}"
                )
                handler = logging.FileHandler(filename)
            except IOError:
                print(f"Warning: Unable to open second-try log file at {filename}")
                print("Warning: Continuing without log.")
                handler = logging.NullHandler()

        if log_format is None:
            log_format = "[%(asctime)s %(levelname)s %(name)s] %(message)s"
        formatter = self._define_formatter(log_format)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)

    def _define_formatter(self, log_format):
        # Define and set the log formatter
        return logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S %Z")


class UTCLog(Log):
    """A subclass of ``Log`` that logs messages in UTC."""

    def _define_formatter(self, log_format):
        formatter = super()._define_formatter(log_format)
        formatter.converter = time.gmtime
        return formatter
