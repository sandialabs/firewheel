
.. _cli_helpers:

Available CLI Helpers
=====================

Helpers allow the extension of the CLI with new
"commands". They are invoked by name (the most common option) or using the :ref:`command_run` command. The name of the
file defining a Helper is used as the name of that Helper. Helpers available in
the current CLI session can be enumerated using the :ref:`command_list` command.

Below are all the available Helpers within FIREWHEEL. To learn more about Helpers
see :ref:`cli_helper_section`.

.. _helper_example_helpers_pytest:

example_helpers pytest
----------------------

.. program:: example_helpers pytest


Use this file as a template for new Python Helpers. If you retain the sections
(and just update the content) then the Helper should execute properly.

Arguments
+++++++++
When executed, this Helper will print out any passed in arguments.

Examples
++++++++

``firewheel example_helpers pytest``


.. _helper_example_helpers_subgroup:

example_helpers subgroup
------------------------

.. program:: example_helpers subgroup


This is an example of an index file. If no sub-Helper is called, the
Helper group's index file is automatically called.
Use this file as a template for new index Helpers. If you retain the sections
(and just update the content) then the index Helper should execute properly.

Arguments
+++++++++
N/A

Examples
++++++++

``firewheel example_helpers subgroup``


.. _helper_example_helpers_subgroup_test:

example_helpers subgroup test
-----------------------------

.. program:: example_helpers subgroup test


Use this file as a template for new Helpers. If you retain the sections
(and just update the content) then the Helper should execute properly.

Arguments
+++++++++
N/A

Examples
++++++++

``firewheel example_helpers subgroup test``


.. _helper_example_helpers_test:

example_helpers test
--------------------

.. program:: example_helpers test


Use this file as a template for new Helpers. If you retain the sections
(and just update the content) then the Helper should execute properly.

Arguments
+++++++++
N/A

Examples
++++++++

``firewheel example_helpers test``


.. _helper_experiment:

experiment
----------

.. program:: experiment


Create a FIREWHEEL experiment using a set of model components.

**Usage:**  ``firewheel experiment [-h] [--profile] [--dry-run] [-f] <model_component>[:<name1>=<value1>[:<name2>=<value2>]...] [<model_component2>[:<name1>=<value1>[:<name2>=<value2>]...]]``

All of the experiment Helper's command line arguments, along with any named
MC parameter value settings, must be included on a single line.

Named parameter value settings are passed into the model component's plugin.
If no name is provided, these arguments are treated as positional. Plugin
arguments are separated from both the model component and additional arguments
by a colon (:). (i.e. ``<mc>:<name1>=<value1>:<name2>=<value2>`` or a combination
of positional and named arguments ``<mc>:<value1>:<value2>:<named1>=<value3>``).
**No spaces are allowed.**

The ordering of model components on the command line provides an explicit
"depends" relationship among them. For example, ``firewheel experiment mc1 mc2``
implies that *mc2* will run after *mc1*.

For *most* experiments, users will want at least two model components: their
topology and some method of "doing something" with the topology. This could
include anything from exporting the topology (with the ``print_graph`` Model
Component) or realizing the topology into an emulation. The current method to
launch an experiment is to use the ``minimega.launch`` model component which uses
`minimega <https://www.sandia.gov/minimega>`_ to instantiate the emulation. **NOTE: This is not required**.
FIREWHEEL is extensible and enables users to create other experiment instantiation methods.

Arguments
+++++++++

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <model_component[:<value1>[:<param2>=<value2>]]>

    The model component to use in the experiment. More than one of these may be
    specified. (required)

    If the given Model Component's Plugin requires a parameter, the value can be passed to the MC by using a colon separated list (e.g. ``<model_component>:[value1]:[value2]``).
    Keyword parameters can be specified as well, using the traditional keyword format of ``name=value``.
    If no name is provided, these arguments are treated as positional.
    No spaces are allowed when providing MC parameters.

    Command-line examples:

    .. code-block:: bash

        $ # Single MC positional argument
        $ firewheel experiment tests.router_tree:3 minimega.launch
        $ # Muliple MC named arguments
        $ firewheel experiment tests.router_tree:3 tests.large_resource:size=1024:location_dir=/tmp:preload=True minimega.launch


Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Print this experiment Helper description then exit. (optional)

.. option:: -f, --force

    Force the experiment to launch even if there is an existing experiment. This essentially clears the testbed by running ``firewheel restart``. (optional)

.. option:: -r, --restart

    Similar to :option:`-f`, but only restarts if an active experiment is detected. If an experiment is detected, runs ``firewheel restart`` before starting the experiment. (optional)

.. option:: --profile

    Output profiling info for experiment graph construction. It creates a ``firewheel_profile.prof`` file in the current working directory. (optional)

.. option:: --dry-run

    Output the ModelComponent sequence that would be evaluated, but don't actually evaluate the components. (optional)

.. option:: -ni, --no-install

    Continue regardless of if Model Components within the experiment have been "installed" (i.e., the ``INSTALL`` file executed). Defaults to None. (optional)


Examples
++++++++
``firewheel experiment acme.run minimega.launch``

``firewheel experiment tests.vm_gen:3 minimega.launch``

``firewheel experiment tests.vm_gen:size=3 minimega.launch``

``firewheel experiment -r tests.vm_gen:size=3 tests.connect_all tests.ping_all minimega.launch``


.. _helper_mc_dep_graph:

mc dep_graph
------------

.. program:: mc dep_graph


Print out a Graphviz dependency graph between all model components in currently installed repositories.

Arguments
+++++++++

All arguments are optional.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show a help message and exit

.. option:: -o

    Output file name to print to. Print to ``stdout`` if not provided.


Example
+++++++

``firewheel mc dep_graph``

``firewheel mc dep_graph -o /tmp/test.txt``



.. _helper_mc_generate:

mc generate
-----------

.. program:: mc generate

This Helper is used to generate a new model component.
It can be used in "interactive" mode or via CLI arguments.
Ultimately, it calls :mod:`firewheel.control.utils.new_model_component`.

**Usage:** ``firewheel mc generate [-h] --name NAME --location LOCATION [--attribute_depends ATTRIBUTE_DEPENDS [ATTRIBUTE_DEPENDS ...]] [--attribute_provides ATTRIBUTE_PROVIDES [ATTRIBUTE_PROVIDES ...]] [--attribute_precedes ATTRIBUTE_PRECEDES [ATTRIBUTE_PRECEDES ...]] [--model_component_depends MODEL_COMPONENT_DEPENDS [MODEL_COMPONENT_DEPENDS ...]] [--model_component_precedes MODEL_COMPONENT_PRECEDES [MODEL_COMPONENT_PRECEDES ...]] [--plugin PLUGIN] [--model_component_objects MODEL_COMPONENT_OBJECTS] [--plugin_class PLUGIN_CLASS] [--vm_resource VM_RESOURCES [VM_RESOURCES ...]] [--image IMAGE] [--arch ARCH] [--non-interactive] [--template_dir TEMPLATE_DIR] [--no_templates]``


Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

**MANIFEST-related Arguments:**

.. option:: --name <NAME>

    The Model Component name.

.. option:: --attribute_depends <ATTRIBUTE_DEPENDS [ATTRIBUTE_DEPENDS ...]>

    Graph Attribute(s) depended on by the new Model Component as space-separated-strings.

.. option:: --attribute_provides <ATTRIBUTE_PROVIDES [ATTRIBUTE_PROVIDES ...]>

    Graph Attribute(s) provided by the new Model Component as space-separated-strings.

.. option:: --attribute_precedes <ATTRIBUTE_PRECEDES [ATTRIBUTE_PRECEDES ...]>

    Graph Attribute(s) preceded by the new Model Component as space-separated-strings.

.. option:: --model_component_depends <MC_DEPENDS [MC_DEPENDS ...]>

    Model Component names required by the new MC. These should be space-separated-strings.

.. option:: --model_component_precedes <MC_PRECEDES [MC_PRECEDES ...]>

    Model Component names that will be preceded by the new MC. These should be space-separated-strings.

.. option:: --plugin <PLUGIN>

    File name for a Plugin. If this is needed, we recommend using ``plugin.py``.

.. option:: --model_component_objects <MODEL_COMPONENT_OBJECTS>

    File name for Model Component Objects file. If this is needed, we recommend using ``model_component_objects.py``.

.. option:: --location <LOCATION>

    Location for the new Model Component (i.e Where should the newly generated MC files go?).
    Include the directory of the MC itself. That is, if you would like the new MC to be placed in ``/opt/firewheel/model_components/`` your location should be ``/opt/firewheel/model_components/<MC dir name>``.

.. option:: --plugin_class <PLUGIN_CLASS>

    Name for the new Plugin class.

.. option:: --vm_resource <VM_RESOURCES [VM_RESOURCES ...]>

    File(s) to be used as VM Resources as space-separated-strings.

.. option:: --image <IMAGE>

    Specify a file to be used as a VM disk.

.. option:: --arch <ARCH>

    Specify the architecture of the supplied image (x86_64, x86, etc). Defaults to ``x86_64`` if an image is provided but the ``--arch`` option is not.

**Configuration-related Arguments:**

.. option:: --non-interactive

    Require minimum parameters as arguments and do not prompt for any values

.. option:: --no_templates

    Do not generate files from templates. Only generate a MANIFEST file.

.. option:: --template_dir <TEMPLATE_DIR>

    Override the configured templates directory.


.. _helper_mc_list:

mc list
-------

.. program:: mc list


List information about the currently installed model components.
Model components can be grouped by repository (default), or any of the ``provides``, ``depends``, ``precedes``, ``model_component_depends``, ``model_component_precedes``.
fields in the model component's manifest.
Filters can be used to reduce the MCs that are shown. Filters are independent and
are greedily matching. If multiple filters are used then anything that matches **all**
filters will be displayed. Filters will attempt substring matching so ensure that
you provide enough of a substring to the filter to narrow down the displayed results.

Arguments
+++++++++

All arguments are optional.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show a help message and exit.

.. option:: --paths, -p

    Print additional paths information.

.. option:: -g <group>, --group <group>

    :default: ``repository``

    Group model components by one of: ``repository``, ``provides``, ``depends``, ``model_component_depends``.

.. option:: -m

    Print without color, i.e. monochromatic.

.. option:: -k <FIELDS [FIELDS ...]>

    Space separated list of additional MANIFEST fields to display for each found MC, in the form field[=filter] where filter is an optional substring of the results being filtered on.
    Example fields are in the following table, but any manifest fields should be valid.

    .. tabularcolumns:: |\Y{.32}|\Y{.68}|

    ============================   ==================================================================================================================================
    Filter fields                  Description
    ============================   ==================================================================================================================================
    ``name``                       The name of the MC.
    ``provides``                   The attributes provided by the MC.
    ``depends``                    The attributes depended on by the MC.
    ``precedes``                   The attributes preceded by the MC.
    ``attributes``                 The dictionary of both provides and depends. Filters provided return true if found in either provides or depends.
    ``model_component_depends``    The model components depended on by the MC.
    ``model_component_precedes``   The model components preceded by the MC.
    ``model_component_objects``    The model_component_objects provided by the MC.
    ``vm_resources``               The VM Resources proved by the MC. This will not auto-expand any wildcards (e.g. ``vm_resources/**``).
    ============================   ==================================================================================================================================


Examples
++++++++

``firewheel mc list -p``

``firewheel mc list -p -m -k provides=topology``

``firewheel mc list -p -g provides -k name=ubuntu``

``firewheel mc list -k vm_resources``




.. _helper_mm_clean_bridge:

mm clean_bridge
---------------

.. program:: mm clean_bridge


In the rare case that when minimega is shut down it does not clean up all of its Open vSwitch interfaces, these interfaces should then be removed.
This Helper will enable a user to manually remove **all** interfaces created by minimega and restore the ``control_bridge`` to the original state (prior the experiment running).
When run, this Helper identifies the ``control_bridge``, finds all ports which start with the phrase ``mega_tap``, and then removes them via both the ``ovs-vsctl`` and ``ip link`` commands.

.. seealso::

    For more information on the ``control_bridge`` see :ref:`config-minimega`.

.. warning::

    Do not run this Helper while your experiment is running!
    It will have unintended consequences!

Arguments
+++++++++

This Helper takes no arguments.

Example
+++++++

``firewheel mm clean_bridge``


.. _helper_mm_clear_cache:

mm clear_cache
--------------

.. program:: mm clear_cache

This will delete all files in the requested :class:`FileStore <firewheel.lib.minimega.file_store.FileStore>`.

**Usage:**  ``firewheel mm clear_caches <caches>``

Arguments
+++++++++

A user must either provide a list of caches (one of ``images``, ``schedules``, ``vm_resources``) or the :option:`mm clear_cache --all` parameter.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: --all

    Clear all caches, including ``images``, ``schedules``, and ``vm_resources``

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <caches>

    The name(s) of the caches to clear (i.e. ``images``, ``schedules``, and/or ``vm_resources``).

Example
+++++++

``firewheel mm clear_cache images``

``firewheel mm clear_cache images schedules``

``firewheel mm clear_cache --all``



.. _helper_mm_flush_locks:

mm flush_locks
--------------

.. program:: mm flush_locks

This will delete all lock directories and optionally the associated cache_files in the requested :class:`FileStore <firewheel.lib.minimega.file_store.FileStore>`.

**Usage:**  ``firewheel mm flush_locks <caches>``

Arguments
+++++++++

A user must either provide a list of caches (one of ``images``, ``schedules``, ``vm_resources``) or the :option:`mm flush_locks --all` parameter.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: --all

    Clear lock files for all caches, including ``images``, ``schedules``, and ``vm_resources``.

.. option:: --clear

    Clear cache files associated with found lock files.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <caches>

    The name(s) of the caches to check (i.e. ``images``, ``schedules``, and/or ``vm_resources``).

Example
+++++++

``firewheel mm flush_locks images``

``firewheel mm flush_locks --clear images schedules``

``firewheel mm flush_locks --all``


.. _helper_mm_make_bridge:

mm make_bridge
--------------

.. program:: mm make_bridge


If the experiment interface is the loopback interface (single node installation),
the cluster is configured to use GRE tunnels, or the `mega_bridge` interface
already exists, this Helper does nothing.

Otherwise, the following steps occur:

1. An Open vSwitch bridge is created for the `mega_bridge`
2. A port is added between the `mega_bridge` and the experiment interface
3. The experiment interface has its IP flushed.
4. The previous experiment interface IP address is added to the `mega_bridge`.


.. _helper_mm_mesh:

mm mesh
-------

.. program:: mm mesh

Attempts to run mesh dial from the head node to all compute nodes.
This command blocks until the expected degree of the cluster matches
what is reported by minimega on the head node.
Takes one optional argument, when equal to `quiet`, limits debug output.

**Usage:**  ``firewheel mm mesh [quiet]``

Arguments
+++++++++

All arguments are optional.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: quiet

    Do not print debug information.

Example
+++++++

``firewheel mm mesh``

``firewheel mm mesh quiet``


.. _helper_mm_show_caches:

mm show_caches
--------------

.. program:: mm show_caches


List the image and vm_resource cache directories which are found in the
:class:`FileStore <firewheel.lib.minimega.file_store.FileStore>`. This enables
users to identify if a file was correctly cached.

Examples
++++++++

``firewheel mm show_caches``


.. _helper_pull_file:

pull file
---------

.. program:: pull file


Pull a file or directory from a VM using the VM resource handler. This does not require that
the VM is running a SSH server. Also, unlike :ref:`helper_scp`, there is no need
to use the :ref:`control_network_mc` model component since the VM resource handler has access to
the VM through a serial port.

All files get placed at the location specified on the command line.

**Usage:**  ``firewheel pull file [-h] <filename> <vm hostname> <destination>``

Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: --attempts

    :default: 24

    Number of 5 second attempts to try before giving up

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <filename>

    The name of the file or directory on the VM to extract

.. option:: <vm hostname>

    The hostname of the VM within the experiment from which to pull the files

.. option:: <destination>

    Local destination path for the files that were extracted from the VM

Example
+++++++

``firewheel pull file /tmp/test.txt host.root.net /tmp/myfile.txt``

``firewheel pull file /tmp/test host.root.net /tmp/mydir``


.. _helper_push_file:

push file
---------

.. program:: push file


Push a file to a VM using the VM resource handler. This does not require that
the VM is running a SSH server. Also, unlike :ref:`helper_scp`, there is no need
to use the :ref:`control_network_mc` model component since the VM resource handler has access to
the VM through a serial port.

All files get placed at the location specified on the command line.

.. note::

    The destination **MUST** be the full path (including the filename), not simply a destination directory.

.. warning::

    Any shell expansions (e.g. ``~``) used in the ``destination`` path are resolved **BEFORE** the file is pushed to the VM.


**Usage:**  ``firewheel push file [-h] <filename> <vm hostname> <destination>``

Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show this help message and exit

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <filename>

    The name of the file to push to the VM

.. option:: <vm hostname>

    The hostname of the VM to push the file to.

.. option:: <destination>

    The full path (including the filename) of the destination location on the VM for the file.

Example
+++++++

``firewheel push file /tmp/test.txt host.root.net /tmp/myfile.txt``

``firewheel push file /tmp/test.txt whost.root.net '/Users/User/Downloads/myfile.txt'``


.. _helper_repository_install:

repository install
------------------

.. program:: repository install

Install a new repository of Model Components.
The repository should be an existing directory on the filesystem.
The path may be specified absolute or relative.
If the path does not exist, an error message is printed.

Some Model Components may provide an additional install script called ``INSTALL`` which can be executed to perform other setup steps (e.g. installing an extra python package or downloading an external VM resource).
INSTALL scripts can be can be any executable file type as defined by a `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ line.

.. warning::

    The execution of Model Component ``INSTALL`` scripts can be a **DANGEROUS** operation. Please ensure that you **fully trust** the repository developer prior to executing these scripts.

.. seealso::

    See :ref:`mc_install` for more information on INSTALL scripts.

When installing a Model Component, users will have a variety of choices to select:

- ``y`` - yes, install execute this script
- ``n`` - no, do not execute this script
- ``v`` - view, see the script text
- ``vc`` - view color, see the script text with color support, must use a system pager which supports this behavior (e.g. ``PAGER='less -R'``)
- ``q`` - quit, exit immediately


Arguments
+++++++++

.. option:: path

    The path to the repository to install. If not provided, will assume that the user desires to run the installation scripts for all existing repositories (assuming the ``-s`` flag is also used).

.. option::  -s, --script

    Run any Model Component-specific installation scripts. The install script should be in the Model Components top-level directory in a file called ``INSTALL``.

.. option::  -i, --insecure

    Automatically run all Model Component INSTALL scripts. Must be run with the :option:`repository install -s` option to take effect.

.. option:: -h, --help

    Show a help message and exit.


Examples
++++++++

``firewheel repository install <directory>``

``firewheel repository install --script <directory>``


.. _helper_repository_list:

repository list
---------------

.. program:: repository list

Show all installed repositories.

Example
+++++++

``firewheel repository list``


.. _helper_repository_uninstall:

repository uninstall
--------------------

.. program:: repository uninstall

Uninstall a repository of model components. The repository should be an
existing directory on the filesystem. The path may be specified absolute or
relative.

.. warning::

    This does **NOT** uninstall any actions performed by Model Component ``INSTALL`` scripts.

Example
+++++++
``firewheel repository uninstall <directory>``

.. _helper_restart_experiment:

restart experiment
------------------

.. program:: restart experiment

Cleans up all of the virtual machines and virtual networks started by
FIREWHEEL and ensures it is ready for another run.

.. _helper_restart_hard:

restart hard
------------

.. program:: restart hard

Executes the `stop hard` and `start` Helpers in order to restart the FIREWHEEL system.
This will tear down all services, virtual machines, and networking independent
of whether FIREWHEEL restart them or not. Use this if a bug in FIREWHEEL is
preventing a regular restart from working.

Example
+++++++

``firewheel restart hard``


.. _helper_restart:

restart
-------

.. program:: restart

Cleans up all of the virtual machines and virtual networks started by
FIREWHEEL and ensures it is ready for another run. This is the same
as running ``firewheel restart experiment``

Example
+++++++

``firewheel restart``


.. _helper_scp:

scp
---

.. program:: scp


SCP files to or from a VM that is currently running in the FIREWHEEL
environment. All SCP options can be used.

.. warning::
    To use this, the following requirements MUST be met:
        * The VM must be running an SSH server.
        * The experiment must be run with the :ref:`control_network_mc` model component. For example: ``firewheel experiment tests.vm_gen:2 control_network minimega.launch``.
        * This Helper *MUST* be run from the cluster head node.

    If any of these conditions are not or cannot be met, use the
    :ref:`helper_pull_file` Helper (i.e. ``firewheel file pull``) instead.

Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <SCP command>

    The remaining standard SCP options, which includes the the hostname of the VM to SCP to or from. An optional username can be specified before the hostname as well. (i.e. ubuntu@vm.net)

Example
+++++++

``firewheel scp ubuntu@host.root.net:/tmp/test.txt /tmp/myfile.txt``

``firewheel scp -r ubuntu@host.root.net:/tmp/test /tmp/mydir``

``firewheel scp /tmp/test.txt ubuntu@host.root.net:/tmp/test.txt``


.. _helper_ssh:

ssh
---

.. program:: ssh


SSH to VM that is currently running in the FIREWHEEL environment.
This command supports running commands directly from a call to SSH.

.. warning::

    To use this, the following requirements MUST be met:
        * The VM must be running an SSH server.
        * The experiment must be run with the :ref:`control_network_mc` model component. For example: ``firewheel experiment tests.vm_gen:2 control_network minimega.launch``.
        * This Helper *MUST* be run from the cluster head node.

Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <SSH options>

    The remaining standard SSH options, which includes the the hostname of the VM to SSH to. An optional username can be specified before the hostname as well. (i.e. ubuntu@vm.net).

Example
+++++++

``firewheel ssh ubuntu@host.root.net``

``firewheel ssh vyos@bgp.root.net``

``firewheel ssh ubuntu@vm.net touch /tmp/test``


.. _helper_start:

start
-----

.. program:: start

Start the FIREWHEEL services (grpc and discovery) and set up the minimega environment.

.. _helper_status:

status
------

.. program:: status

This informs a user if the testbed is available for use or occupied by
an existing experiment.

Example
+++++++

``firewheel status``


.. _helper_stop_hard:

stop hard
---------

.. program:: stop hard

Aggressively clean up FIREWHEEL after an experiment. This will:
 * Destroy all running VMs (regardless of whether FIREWHEEL/minimega created them).
 * Restart all FIREWHEEL/minimega services
 * Recreate minimega's mesh
 * Kill all ``vm_resource_handler`` processes
 * Set permissions on the ``mm_base`` directory (typically ``/tmp/minimega``)
 * Remove all logs

It is important to note that this will destroy all virtual machines
found on the system and likely any networking that is not "standard".
Only use this if you want to clear the system independent of what
FIREWHEEL's state thinks it is.

It is almost always better to use :ref:`helper_stop` instead.

Example
+++++++

``firewheel stop hard``

.. _helper_stop:

stop
----

.. program:: stop

This will request all FIREWHEEL services to stop and kill all
``vm_resource_handler`` processes.

This will not aggressively tear down everything. Use ``firewheel stop hard``
for that.

Example
+++++++

``firewheel stop``

.. _helper_test_all:

test all
--------

.. program:: test all

Executes all of the Helpers in the test folder including:
 * ``test unit``
 * ``test functional all``

Example
+++++++

``firewheel test all``


.. _helper_test_functional:

test functional
---------------

.. program:: test functional

Run functional (i.e. end-to-end) test cases based on the input suite (`minimal`, `basic`, `windows`, or `all`). It is
important to note that ``suite=all`` does *NOT* include windows test cases. In order
to run ``suite=windows`` users must have the `windows` model component repository installed and all
images downloaded.

**Usage:** ``firewheel test functional [-h] [suite]``

Arguments
+++++++++

All arguments are optional.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^
.. option:: <suite>

    :default: basic

    Which test suite should be run. This is one of (``all``, ``minimal``, ``windows``, ``basic``).

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

Example
+++++++

``firewheel test functional``

``firewheel test functional all``


.. _helper_test:

test
----

.. program:: test

Executes all of the Helpers in the test folder including:
 * ``test unit``
 * ``test functional minimal``

This Helper is extremely valuable to test if a FIREWHEEL install is successful.

Example
+++++++

``firewheel test``


.. _helper_test_unit:

test unit
---------

.. program:: test unit

Run all available unit test cases using :py:mod:`pytest`. Any extra arguments
given to the helper will be passed to the :py:mod:`pytest` runner.

Example
+++++++

``firewheel test unit``


.. _helper_time:

time
----

.. program:: time

Get the time (in UTC) of when the experiment will start
(i.e. when experiment positive time will start). To get the
time in UTC on your control/compute nodes (to compare) you can
use the command ``date --utc``.

If the experiment has started, the number of seconds since the experiment
started is also printed.

Arguments
+++++++++
All arguments are optional.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: --json

    Dump output as JSON-formatted dictionary in the form of ``{start_time: <datetime>, seconds_since_start: <int>}``

Example
+++++++

``firewheel time``

``firewheel time --json``


.. _helper_tmux_cluster:

tmux cluster
------------

.. program:: tmux cluster

Uses the compute lists to build tmux for the cluster. To join this tmux session
use the command: ``tmux -S /tmp/cluster attach``.

Example
+++++++

``firewheel tmux cluster``

``tmux -S /tmp/cluster attach``


.. _helper_tshoot_check_nics:

tshoot check_nics
-----------------

.. program:: tshoot check_nics


Check to see if the physical host control bridge is in a sane state. This includes
ensuring that the control bridge is up (but doesn't necessarily have an IP address).

Example
+++++++

``firewheel tshoot network check_nics``


.. _helper_tshoot_diskspace:

tshoot diskspace
----------------

.. program:: tshoot diskspace

Troubleshoot possible issues with disk space. This Helper will inform
a user if the disks are too full to run an experiment.

.. _helper_tshoot:

tshoot
------

.. program:: tshoot

This Helper troubleshoots various issues that can arise with FIREWHEEL
deployments. This will execute ALL troubleshooting Helpers to assist in
identifying potential problems. This Helper is also useful to run after an
installation is complete.

Example
+++++++

``firewheel tshoot``

.. _helper_tshoot_mtu:

tshoot mtu
----------

.. program:: tshoot mtu

This Helper finds possible problems with MTU sizes. FIREWHEEL and minimega
strongly recommend that Jumbo Frames are turned on. This feature enables packets
with large MTUs (such as those needing to use GRE tunnels) to traverse the network.
Therefore, we use this Helper to verify that Jumbo Frames (9000 MTU) are turned on.

Example
+++++++

``firewheel tshoot network mtu``

.. _helper_vm_builder:

vm builder
----------

.. program:: vm builder

This Helper enables users to launch/modify a single VM based on a passed in image file using minimega.
It is largely useful for preparing images for use with FIREWHEEL and as a testing ground for developing VM resources using the exact OS.

This helper relies on `libvirt <https://libvirt.org/>`__ to provide automated networking to VMs, therefore, this is installed if it is not already.

.. warning::

    Currently, the automated installation of `libvirt <https://libvirt.org/>`__ only works on Debian-based systems (e.g. Ubuntu).

If users would like to use `libvirt <https://libvirt.org/>`__ networking, via the ``-n`` flag, than that interface is automatically bridged to the host system.
Within the VM, users will likely have to run ``sudo dhclient`` to ensure that their interfaces receive an IP address.
However, after this point, the VM should have network access.

.. note::

    Users with corporate security features (e.g. proxies, firewalls, etc.) may need to manually configure the VM services to access the network.


Ultimately, it calls :mod:`firewheel.control.utils.vm_builder` and if desired, users can call that script manually.

**Usage:** ``firewheel vm builder [-h] (--modify | --launch) [-n] [-m MEMORY] [-c VCPUS] [-d CDROM] image``

Arguments
+++++++++

Users must provide a KVM-compatible image file and either ``--modify`` or ``--launch``.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: image

    VM image file to work with. Must be KVM-compatible.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show a help message and exit.

.. option:: --modify

    Launch a VM image and save the changes.

.. option:: --launch

    Launch a VM image, discarding the changes on shutdown.

.. option:: -n, --network

    Include a network interface when launching the VM.

.. option:: -m, --memory

    :default: 2048

    Memory allotted to the VM [MB].

.. option:: -c, --vcpus

    :default: 1

    Number of VCPUs allotted to the VM.

.. option:: -d, --cdrom

    Include a CD-ROM ISO image when launching a VM. May be specified multiple times.

Example
+++++++

.. code-block:: bash

    # Modify an image and provide 4096MB of memory
    firewheel vm builder --modify -n -m 4096 /path/to/image.qcow2``

.. code-block:: bash

    # Launch (i.e. don't persist changes) an image with more VCPUs
    firewheel vm builder --launch -n -c 4 /path/to/image.qcow2``

.. code-block:: bash

    # Modify an image and pass in a CD
    firewheel vm builder --modify -n --cdrom /path/to/cd.iso /path/to/image.qcow2``


.. _helper_vm_list:

vm list
-------

.. program:: vm list


List running state information about the currently deployed virtual machines.
Filters can be used to reduce the VMs that are shown. Filters result in the union
of all filters. If multiple filters are used then anything that matches **all**
of filters will be displayed. Filters will attempt substring matching so ensure that
you provide enough of a substring to the filter to narrow down the displayed results.

Arguments
+++++++++

All arguments are optional.

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: --csv

    Output in CSV format.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <field[=filter]>

    A field to display for each found VM, in the form field[=filter] where filter is a substring of the results being filtered on. Available fields are in the following table.

    .. tabularcolumns:: |\Y{.15}|\Y{.85}|

    =============  ==================================================================================================================================
    Filter fields  Description
    =============  ==================================================================================================================================
    ``uuid``       Unique number for each VM instance
    ``name``       The name of the VM
    ``state``      State of VM QEMU process and vm_resource run status
    ``image``      Full name of the base image of the VM
    ``hostname``   The hostname as it was assigned in the experiment
    ``vnc``        The shortened port number used to connect to the VM through VNC. Note, the real port number is 5900 + that shown
    ``time``       If VM is configuring, this displays the time of the vm_resource currently running within a VM. If VM has not started configuring, this displays N/A. If VM is configured, this displays 0, unless an experiment start time has been determined, in which case all VMs return :)
    ``ip``         The VMs :ref:`control_network_mc` IP address, if the experiment included the :ref:`control_network_mc` MC
    =============  ==================================================================================================================================

Example
+++++++

``firewheel vm list vnc hostname image``

``firewheel vm list name=host.root.net vnc hostname``

``firewheel vm list name=root image=vyos vnc hostname``

``firewheel vm list name=root --csv``

``firewheel vm list image=vyos state``


.. _helper_vm_log:

vm log
------

.. program:: vm log


Retrieve a log for the given VM. This enables users to easily access log files for VMs
without intimate knowledge of where the VM resource logs are stored. Additionally, it enables
easy parsing and data analysis of logs.

All log output is directly piped to standard out and can be further examined using common
command line tools such as ``less``, ``tail``, or ``grep``, just to name a few.

Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: -j, --json

    Retrieve the JSON log rather than the standard log.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <vm>

    The name of the VM for which the log should be retrieved.


Example
+++++++

``firewheel vm log host.root.net``

``firewheel vm log --json host.root.net``

``firewheel vm log host.root.net | less``


.. _helper_vm_mix:

vm mix
------

.. program:: vm mix


Generates a table showing the VM Images for a running experiment. The table also
includes the power state of the VMs and the vm_resource state. Images that are the same
and have the same power/vm_resource state are grouped. The count of the various VMs are
provided. Additionally, the total number of scheduled VMs is shown at the bottom
of the table.

Example
+++++++

``firewheel vm mix``

The output will look similar to the below table.::

    +------------------------------------------------+-------------+----------------------+-------+
    |                    VM Image                    | Power State |  VM Resource State   | Count |
    +================================================+=============+======================+=======+
    | ubuntu-16.04.4-server-amd64.qcow2              | RUNNING     | configured           | 4     |
    +------------------------------------------------+-------------+----------------------+-------+
    +------------------------------------------------+-------------+----------------------+-------+
    |                                                |             | Total Scheduled      | 4     |
    +------------------------------------------------+-------------+----------------------+-------+


.. _helper_vm_resume:

vm resume
---------

.. program:: vm resume


Submit a :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>` event to a set of VMs within an experiment. This can be applied to a set of
VMs or to all VMs within the experiment. This is primarily used for resuming VMs which have
created a *break* within the VM resource schedule. For more information see :ref:`vm-resource-schedule`.

**Usage:**  ``firewheel vm resume [-h] (-a | vm_name [vm_name ...])``

Arguments
+++++++++

Named Arguments
^^^^^^^^^^^^^^^

.. option:: -h, --help

    Show help message and exit.

.. option:: -a, --all

    Send a :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>` event for all VMs in the experiment.

Positional Arguments
^^^^^^^^^^^^^^^^^^^^

.. option:: <vm_name>

    The hostname of the VM within the experiment whose schedule should resume.


Example
+++++++

``firewheel vm resume host.root.net``

``firewheel vm resume host.root.net bgp.root.net``

``firewheel vm resume --all``

