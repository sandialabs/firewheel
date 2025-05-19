======================
Available CLI Commands
======================

These are the built-in commands

.. _command_author:

author
------


Print the `AUTHOR` section of the specified Helper.

Args:
    args (str): The Helper name for which to print the author.

Examples:
    .. code-block:: bash

        $ firewheel author experiment
        FIREWHEEL Team



.. _command_config:

config
------


Enables command-line access to get and set the FIREWHEEL configuration.

Users can interact with the :ref:`command_config` command (i.e. ``firewheel config``)
series of sub-commands which enable easily getting/setting various configuration options.


.. _command_config_edit:

config edit
^^^^^^^^^^^

usage: firewheel config edit [-e EDITOR]

Edit the FIREWHEEL configuration with a text editor. The user must set either the VISUAL or EDITOR
environment variable or use the provided flag to override these environment variables.

options:
  -e EDITOR, --editor EDITOR
                        Use the specified text editor.



.. _command_config_get:

config get
^^^^^^^^^^

usage: firewheel config get [-a] [SETTING]

Get a FIREWHEEL configuration.

positional arguments:
  SETTING    Get a particular configuration value. Nested settings can be grabbed
             with a period separating them. For example, to get the value for the
             config key ``{'logging':{'level':'INFO'}}``, you can use the
             command: ``firewheel config get logging.level``.

options:
  -a, --all  Get the entire FIREWHEEL configuration.



.. _command_config_reset:

config reset
^^^^^^^^^^^^

usage: firewheel config reset [config_path]

Reset the FIREWHEEL configuration to the default values.

positional arguments:
  config_path  Path of the configuration file to be reset.



.. _command_config_set:

config set
^^^^^^^^^^

usage: firewheel config set (-f FILE | -s SETTING [VALUE ...])

Set a FIREWHEEL configuration.

options:
  -f FILE, --file FILE  Add config from a file.

  -s SETTING [VALUE ...], --single SETTING [VALUE ...]
                        Set (or create) a particular configuration value. Nested settings
                        can be used with a period separating them. For example, to change
                        the value for the config key ``{'logging':{'level':'DEBUG'}}``, you
                        can use the command: ``firewheel config set -s logging.level INFO``.
                        If no VALUE is passed, the setting's value will become ``None``.





.. _command_docs:

docs
----


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



.. _command_EOF:

EOF
---


Process the exit command, and perform the expected termination of the CLI


.. _command_exit:

exit
----


Exits the command line


.. _command_help:

help
----


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



.. _command_history:

history
-------


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



.. _command_init:

init
----


Enables easy ability for a user to "initialize" a FIREWHEEL node.

Initialization includes checking various FIREWHEEL config path and verifying
that non-standard dependencies (minimega and discovery) are installed and working.


.. _command_init_static:

init static
^^^^^^^^^^^

Do not check if any services are running any only check if they exist.

        Args:
            _args (str): This is unused in this method.





.. _command_list:

list
----


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


.. _command_quit:

quit
----


Exits the command line


.. _command_run:

run
---

Runs the scripts found in the specified Helper file.

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



.. _command_sync:

sync
----


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



.. _command_version:

version
-------


Print FIREWHEEL's version.

Args:
    arg (str): This argument is ignored.

Example:
    .. code-block:: bash

        $ firewheel version
        2.6.0

