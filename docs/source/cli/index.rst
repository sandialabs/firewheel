.. _cli:

######################
Command Line Interface
######################

Once the Python virtual environment is active, the CLI can be accessed by using the command ``firewheel`` in your terminal or directly using :exc:`firewheel_cli.py <firewheel.cli.firewheel_cli>`.
This will open up the CLI in "interactive" mode which looks like:

.. code-block:: bash

    $ firewheel
    FIREWHEEL Infrastructure CLI
    fw-cli>

The CLI also supports single-command execution (or non-interactive mode).
This is the most common use of the CLI.
Running the CLI with arguments results in those arguments being treated as a single entered command (and associated arguments).
For example, the following examples are equivalent:

.. code-block:: bash

    $ firewheel vm mix

.. code-block:: bash

    fw-cli> vm mix

Helpers can be invoked by name as a command or using the :ref:`command_run` command.

.. code-block:: bash

    fw-cli> run vm mix

While it is most common that users will invoke a Helper via its name, using the :ref:`command_run` command also disambiguates a Helper's name from built-in command names.
Additionally in interactive mode, the :ref:`command_run` command provides the ability to tab-complete Helpers.

Available Helpers can be enumerated using the :ref:`command_list` or :ref:`command_help` commands or they can found here: :ref:`cli_helpers`.

For complete help on any command, use: ``firewheel help <command | Helper>``.

Some commands may take arguments.
Everything on the command line after the name of the command is treated as an argument to that command.
Some commands use `Argparse <https://docs.python.org/3/library/argparse.html>`_ to handle arguments.
In this case, using ``-h`` or ``--help`` flag may also work.
However, this information *should* also be available by using: ``firewheel help <command | Helper>``.

All CLI commands *should* report success/failure via the exit code.
Many commands also output useful information directly to the screen.
For example:

.. code-block:: bash

    $ firewheel repository list
    Installed Model Component Repositories:
    /opt/firewheel/model_components

As with other FIREWHEEL components, the CLI logs to ``firewheel.log``.
However, because the CLI is verbose, it has an additional log file (``cli.log``) which contains more in-depth logging information, including the output.
Additionally, the history of CLI commands is located in ``cli_history.log`` (or it can be accessed via the :ref:`command_history` command).

The location of the CLI-specific log files can be set using FIREWHEEL's configuration.

.. toctree::

    commands.rst
    helper_docs.rst
