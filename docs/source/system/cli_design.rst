.. _cli_design:

**********
CLI Design
**********
The FIREWHEEL CLI has two major objectives which make it unique.
First, it has to uniquely work across a FIREWHEEL cluster.
Second, it needs to be flexible enough to use either Shell or Python scripts.
To accomplish these objectives, the CLI has been extended with :ref:`cli_helper_section`.
:ref:`cli_helper_section` do not use the standard `Cmd <https://docs.python.org/3/library/cmd.html>`_ format, but they enable us to use Python and Shell scripting to perform various actions across the cluster (see :ref:`cli_executors`).
Additionally, the CLI automatically distributes Helpers to enable performing actions over the entire cluster.

In order to support its extensible capabilities, the CLI uses the FIREWHEEL configuration file and depends on a few externally configured entities.
Please see :ref:`firewheel_configuration` for more details.

.. _cli_helper_section:

Helpers
=======
Helpers allow the extension of the CLI with new "commands".
A Helper is a flat text file made up of different sections (see :ref:`extending_helpers`).
They are invoked by name or by using the :ref:`command_run` command.
For example, the :ref:`helper_experiment` Helper can be run by using any of the following methods.

.. code-block:: bash

       $ firewheel experiment
       $ firewheel run experiment
       fw-cli> experiment
       fw-cli> run experiment

.. note::
    Recall that the ``fw-cli`` prompt indicates the CLI is running in interactive mode.

Each Helper can define a series of sections which will execute a series of actions (via :ref:`cli_executors`) on either the `compute` or `control` nodes.

The full list of Helpers is found here: :ref:`cli_helpers`.

.. _cli_distributed_section:

Distributed CLI
===============
The CLI uses host groups to logically group hosts in the cluster.
Default host groups include ``control`` and ``compute`` and are defined in the FIREWHEEL configuration file (see :ref:`firewheel_configuration`).

Commands are distributed to local caches on each physical host in the cluster.
By default, these caches are located at ``/tmp/firewheel/fw_cli``.
Each `RUN` section in a Helper (see :ref:`extending_helpers`) becomes a file in the cache, with an appropriate extension supplied by its Executor.
The command cache is created and updated using the :ref:`command_sync` command, which uses `ClusterShell <https://clustershell.readthedocs.io/en/latest/>`_ as a back-end.
If Helpers are modified, the cache must be manually updated (using the :ref:`command_sync` command).
If a host does not have a cached file for a particular Helper, it will result in an execution error on that host.

Once the executable file has been distributed, the Executor then uses
`ClusterShell <https://clustershell.readthedocs.io/en/latest/>`_ to invoke the file and return the output.
If the command is run on multiple hosts, all output (``stdout`` and ``stderr``) will displayed and logged.

The CLI notes on screen (but does not take any action) if a Helper (most of
which are run remotely from the perspective of the CLI) fails.
The failure indication occurs when the remote command gives a non-zero exit code.

Sessions
========
To assist with distinguishing output from commands, each CLI "session" will be assigned a UUID.
A session is either one interactive CLI session or a single non-interactive command.
Each command in a session is also assigned a sequence number which is used to further identify commands within the session.
Session IDs and sequence numbers are useful when viewing the CLI history or CLI logs.

Example
=======

To provide a complete view of the CLI, we can walk through a typical example.
A user may want to quickly view the status an experiment that just launched.
They can use the :ref:`helper_vm_mix` Helper.

.. code-block:: bash

       $ firewheel vm mix
       +----------------------------------------------------+-------------+------------------+-------+
       |                      VM Image                      | Power State |   VM Resource    | Count |
       |                                                    |             |      State       |       |
       +====================================================+=============+==================+=======+
       | ubuntu-16.04.4-server-amd64.qcow2                  | RUNNING     | configuring      | 4     |
       +----------------------------------------------------+-------------+------------------+-------+
       | ubuntu-16.04.4-server-amd64.qcow2                  | RUNNING     | uninitialized    | 2     |
       +----------------------------------------------------+-------------+------------------+-------+
       | vyos-1.1.8.qc2                                     | RUNNING     | uninitialized    | 12    |
       +----------------------------------------------------+-------------+------------------+-------+
       |                                                    |             |                  |       |
       +----------------------------------------------------+-------------+------------------+-------+
       |                                                    |             | Total Scheduled  | 18    |
       +----------------------------------------------------+-------------+------------------+-------+

Then, the :ref:`command_history` command will output something like:

.. code-block:: bash

       $ firewheel history
       <Count>: <ID>:<Sequence Number> -- <command>
       0: ae9ec47e-44e1-4d4d-8caf-d21517395d5d:0 -- vm mix

The resulting messages in ``firewheel.log`` will look like::

    [2020-08-25 06:59:42 INFO FirewheelCLI] Beginning command: vm mix
    [2020-08-25 06:59:44 INFO FirewheelCLI] Command returned: 0

The ``cli.log`` will have logged the command and look similar to::

       [2020-08-25 06:59:42 INFO] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Started session ae9ec47e-44e1-4d4d-8caf-d21517395d5d
       [2020-08-25 06:59:42 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Preparing to run command=`cd /home/user 2>/dev/null; /opt/firewheel/fwpy/bin/python3 /tmp/firewheel/fw_cli/vm/mix0.py` for nodes=['node1'].
       [2020-08-25 06:59:42 INFO] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Starting to run cmd=cd /home/user 2>/dev/null; /opt/firewheel/fwpy/bin/python3 /tmp/firewheel/fw_cli/vm/mix0.py
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: ``
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: ``
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+----------------------------------------------------+-------------+------------------+-------+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `|                      VM Image                      | Power State |   VM Resource    | Count |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `|                                                    |             |      State       |       |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+====================================================+=============+==================+=======+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `| ubuntu-16.04.4-server-amd64.qcow2                  | RUNNING     | configuring      | 4     |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+----------------------------------------------------+-------------+------------------+-------+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `| ubuntu-16.04.4-server-amd64.qcow2                  | RUNNING     | uninitialized    | 2     |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+----------------------------------------------------+-------------+------------------+-------+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `| vyos-1.1.8.qc2                                     | RUNNING     | uninitialized    | 12    |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+----------------------------------------------------+-------------+------------------+-------+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `|                                                    |             |                  |       |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+----------------------------------------------------+-------------+------------------+-------+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `|                                                    |             | Total Scheduled  | 18    |`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: `+----------------------------------------------------+-------------+------------------+-------+`
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: ``
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Output from node1: ``
       [2020-08-25 06:59:44 DEBUG] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Node node1 returned successfully!
       [2020-08-25 06:59:44 INFO] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - Command succeeded!
       [2020-08-25 06:59:44 INFO] ae9ec47e-44e1-4d4d-8caf-d21517395d5d::0 - fatal_error_count = 0
