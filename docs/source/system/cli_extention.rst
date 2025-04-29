.. _extending_cli:

*****************
Extending the CLI
*****************
The FIREWHEEL CLI is designed to be as extensible as possible.
There are two mechanisms used for this extensibility: Helpers and Executors.

Helpers are located in the code root under the ``src/firewheel/cli/helpers`` directory.

To contribute a new Helper or Executor, please see the :ref:`contributing` to get started.

.. _extending_helpers:

Extending Helpers
=================
Helpers are flat text files that define a new command for the CLI.
The name of the file defining a Helper is used as the name of that Helper.
They consist of a series of sections, each terminated with a line reading ``DONE``.
These sections are:

- ``AUTHOR`` - Give the author of the Helper. Ideally, this would also include contact information.
- ``DESCRIPTION`` - Give a more extensive description of the Helper and its functionality (similar to in-line help in MATLAB or a man page).
- ``RUN`` - A section of executable information. The section header also contains a description of the Executor and host group(s) to be used. For example: ``RUN Shell ON compute``. Indicates the section is defining a shell script intended to be executed on compute nodes.

All sections are assumed to be unique, except for ``RUN`` sections.
That is, there can be multiple ``RUN`` sections but only a single ``DESCRIPTION`` section.
If multiples on a non-RUN section are defined, the last-read is used.
All section names (e.g. ``AUTHOR``, ``RUN``, etc.) are case sensitive.

The CLI will output an error and continue processing other Helpers if it encounters an error in a Helper definition.

Here is an example Helper (:ref:`helper_example_helpers_test`)::

    AUTHOR
    FIREWHEEL Team
    DONE
    DESCRIPTION

    Use this file as a template for new Helpers. If you retain the sections
    (and just update the content) then the Helper should execute properly.

    Arguments
    +++++++++
    All are optional

    Examples
    ++++++++

    ``firewheel example_helpers test``

    DONE
    RUN Shell ON compute
    #! /bin/bash
    touch ~/foo
    DONE
    RUN Shell ON compute
    #! /bin/bash
    touch ~/bar
    DONE
    RUN Shell ON control
    #!/bin/bash
    echo "Hello, World!"
    pwd
    DONE


Helper groups
=============
Developers may need to create a series of related Helpers.
To support this functionality, FIREWHEEL has a concept of Helper groups.
Essentially, this is a new folder in the ``cli/helpers`` directory.
All related Helpers can be added to this folder.
For, example the ``tshoot`` Helper group contains troubleshooting related Helpers.

Here is the ``tshoot`` directory structure::

       cli/helpers/tshoot
       ├── index
       ├── diskspace
       ├── mtu
       └── check_nics

Users can also execute the Helper group directly.
This is done when the developer creates a special Helper called ``index`` in the Helper group.
This file is NOT required to use Helper groups.
This means users can execute ``firewheel tshoot`` or ``firewheel tshoot index`` to run the :ref:`helper_tshoot` index file.
This is most useful when it runs a series of other Helpers.
For example, the :ref:`helper_tshoot` index Helper (located in the ``tshoot`` directory) has a `RUN` section that looks like::

    RUN Helpers ON control
    tshoot diskspace
    tshoot rabbitmq
    tshoot elk
    tshoot network
    DONE

This Helper now runs all the other ``tshoot`` index files ultimately enabling the user to run many Helpers with a simple ``firewheel tshoot``.

Helper groups can also be nested.
Please refer to the series of example Helpers which are provided in ``src/firewheel/cli/helpers/example_helpers``.

.. _cli_executors:

Executors
=========
Executors are designed to allow new types of code to be contained in ``RUN`` sections.
An Executor is given the content of a ``RUN`` section that names it, as well as the host groups the section expects to be executed on.
They are responsible for using the :class:`HostAccessor <firewheel.cli.host_accessor.HostAccessor>` to distribute the executable code and invoke it on remote hosts.

Executors are found by Helpers using a plugin model.
Any Executor defined in the appropriate directory (i.e. ``src/firewheel/cli/executors``) is available to the CLI.
Executors are looked up by name using the name given in a Helper.

Executors are expected to have robust error-handling.
They are expected to handle file creation and copying, as well as remote execution (helpful methods for the remote operations are provided).

All Executors extend the :class:`AbstractExecutor <firewheel.cli.executors.abstract_executor.AbstractExecutor>` class.
This class defines the basic interface used to interact with Executors.

Available Executors include:
    * :class:`Shell <firewheel.cli.executors.shell.Shell>` - Invoke the Helper as a Shell script.
    * :class:`Python <firewheel.cli.executors.python.Python>` - Use the FIREWHEEL virtual environment via `ClusterShell <https://clustershell.readthedocs.io/en/latest/>`_.
    * :class:`LocalPython <firewheel.cli.executors.local_python.LocalPython>` - Use the FIREWHEEL virtual environment without `ClusterShell <https://clustershell.readthedocs.io/en/latest/>`_. That is, the command is only executed on the current node (typically ``control``). Its main advantage is an increased processing speed as it does not have to use SSH.
    * :class:`Helpers <firewheel.cli.executors.helpers.Helpers>` - Run a list of other Helpers.
