.. _using-vm-resources:

Using VMRs in an Experiment
===========================

Making VMRs Available to an Experiment
--------------------------------------

When there is a VMR file which must be loaded onto the VM, rather than a standard program already available to the VM, it must first be "available".
That is, it must be included as part of a model component.
This includes the actual VMR itself as well as any other supporting files needed by that VMR.
VMR files should not need to be changed from experiment to experiment, as they can take arguments if desired.

For example, the ``tests.ping_all`` model component (``model_components/base/tests/ping_all``) uses a VMR which helps test network connectivity.
To make this VMR available to be loaded/executed within the experiment environment, it is declared as part of the MC's ``MANIFEST`` file.
More information about specifying VMRs within the ``MANIFEST`` can be found in the section discussing :ref:`the VM Resources field <vm_resources_field>`.

.. _adding-vmr-schedule:

Adding VMRs to the Schedule
---------------------------

VMRs are added to vertices at topology creation time.
Resources can be defined in any MC and in some cases it is actually advantageous to separate VMRs into their own model components.
Generally speaking, it is a good idea to separate a model into components where each component accomplishes a specific goal.
For example, creating a domain controller requires that several PowerShell scripts get loaded on to a Windows VM and executed.
Instead of bundling those scripts into a specific topology, it's better to make a separate model component that will walk around the experiment graph and load those scripts on to VMs that have been designated as domain controllers.
This way, any topology that needs to build a domain controller can consume the domain controller model component without needing to duplicate the code.

As mentioned in the :ref:`vm-resource-schedule` section, adding a VMR to a VM requires a new :py:class:`ScheduleEntry <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>`.
There are additional objects which make scheduling VMRs easier.
While the full details are outlined in :py:mod:`base_objects`, we will outline some of them here.

Each of these functions are available via the :py:class:`base_objects.VMEndpoint`, which is the base class which defines a VM, and therefore are available to every VM within the topology.

:py:meth:`drop_content <base_objects.VMEndpoint.drop_content>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :py:meth:`drop_content <base_objects.VMEndpoint.drop_content>` method is intended to take any string and write it to a specified location on a VM.
The method takes a :ref:`start-time` to know when to perform the content write.
It then needs to know the location (absolute path, including filename) on the VM to write the content.
It needs the actual content to write. This can also be a callable function which returns a string when the :py:mod:`vm_resource.schedule` model component is executed.
Finally, it needs to know if the new file should be made executable.
This is useful if you are creating a simple script and therefore need it to be executable so that it can be subsequently called.

Examples
""""""""

.. code-block:: python

   # Place the string "Useful data" into a file /tmp/data.txt on the VM.
   vm.drop_content(-10, "/tmp/data.txt", "Useful data")

.. code-block:: python

   # We want to know the scheduled physical host of the VM
   # but the host scheduling has not yet occurred.
   def gethost():
      return vm.scheduled_physical_host
   vm.drop_content(-10, "/tmp/data.txt", gethost)


:py:meth:`drop_file <base_objects.VMEndpoint.drop_file>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :py:meth:`drop_file <base_objects.VMEndpoint.drop_file>` method is intended to take a file and load it on to a VM at a specified location.
The method needs a takes a :ref:`start-time` to know when to execute the dropping of the file.
It then needs to know the location (absolute path, including filename) on the VM to write the file.
That is followed by the local name of the file (i.e. the name of the file within the model component).
The local name needs to be specified in the ``vm_resources`` list that is in the model component's ``MANIFEST`` file (see :ref:`vm_resources_field` for more information).
Additionally, it needs to know if the new file should be made executable.
Finally, the method needs to know if the file should be preloaded (i.e. loaded onto the VM before the :ref:`start-time`.
Preloading is set to ``True`` by default.

.. note::
   By default, all VMR files are loaded onto the VMs before starting negative time. However, if the :py:meth:`drop_file <base_objects.VMEndpoint.drop_file>` method is used, the file will be moved into the correct destination at the designated :ref:`start-time`.

Examples
""""""""

.. code-block:: python

   # Place the file "data.tgz" into the location /tmp/data.tgz on the VM.
   vm.drop_file(-10, "/tmp/data.tgz", "data.tgz")

.. code-block:: python

   # Place the file "run.exe" into the location /tmp/run.exe on the VM.
   vm.drop_file(-10, "/tmp/run.exe", "run.exe", executable=True, preloaded=False)


:py:meth:`run_executable <base_objects.VMEndpoint.run_executable>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :py:meth:`run_executable <base_objects.VMEndpoint.run_executable>` method allows a user to run commands both with or without providing a script as the command.
The method needs a takes a :ref:`start-time` to know when to execute the specified program.
It next needs the name of the program or script to run.
In general, it's safer to provide absolute paths for program names instead of relying on the environment of the VM to resolve the name.
After the program, an optional arguments field allows a user to provide arguments for the program as either a single string or a list of strings.
These get passed to the program on the command line.
Finally, the ``vm_resource`` parameter is an optional Boolean that indicates if ``program`` is the name of a script that needs to be loaded on to the VM before execution.
If ``vm_resource`` is ``True`` then the specified program name is assumed to be the local filename of the file (i.e. not the full path, just the filename) to load on to the VM.
In this case, like :py:meth:`drop_file <base_objects.VMEndpoint.drop_file>`, the file that corresponds to ``program`` must be part of the ``vm_resources`` list in a model component's ``MANIFEST`` file (see :ref:`vm_resources_field`).
The user does not need to specify where the file will be dropped on the VM since it will be placed in the appropriate ``/var/launch`` or ``C:\launch`` location (see :ref:`vmr-location`).

Examples
""""""""

.. code-block:: python

   # Run the ``/usr/bin/touch`` program.
   vm.run_executable(-10, "/usr/bin/touch", arguments="/tmp/testing")

.. code-block:: python

   # Run the "run.exe" file.
   vm.run_executable(-10, "run.exe", arguments=["first_arg", "second_arg"], vm_resource=True)

.. _vmr-rebooting:

Rebooting a VM
--------------

Sometimes, VM Resources (VMRs) require a VM to be rebooted in order to complete an operation.
For example, many Windows operations require a reboot [#]_.
FIREWHEEL provides the ability for VM resources to request that the OS reboot during the execution of the VMR scheduled at a negative time.
This reboot functionality will **ONLY** work when used in negative time as the primary purpose is for configuration of the VMs.
Users can use a system command to reboot the system during positive time.
However, we should caution users that doing so may have unintended consequences.
For example, if a VMR at ``time=10`` requests a reboot (by using a system command).
Then a VMR at ``time=12`` likely will not launch be executed 12 seconds into the experiment.
Currently, any VMRs (including the one calling the reboot) that have an execution time that is in positive time (i.e. greater than ``time=0``) will be executed (for possibly a second time).
Therefore, we strongly recommend against rebooting the VM during positive time.

To request a (negative time) reboot, VMRs can use two approaches:

1. By creating a new file called ``reboot`` in the executing directory (i.e. writing to the relative path ``reboot``). This is case sensitive. The file name must be all lower case. The content of the ``reboot`` file is ignored.
2. By exiting with error code ``10``. This method is highly recommended for Windows-based VMRs as Windows seems to have trouble with disk access after reboots, the exit code has proven a more reliable check than file existence.

If the VM Resource Handler detects that either of these occur, it schedules a system reboot once all other VMRs executing at the same negative time have completed.
Once the VM has rebooted, the VM will resume time at the same negative time at which the reboot was indicated and rerun all VMRs that requested a reboot.
It will not restart VMRs scheduled at the same negative time which did not schedule a reboot.
Because reboot-requesting VMRs resume, the VMR needs some method of detecting that a reboot has occurred and then resume processing or exit successfully.
It is advised that a VMR create a ``state_file`` in its directory before rebooting.
The VMR can then check for the existence of the ``state_file`` to know that it is running post-reboot and act accordingly.
For example, here is a bash script that checks for ``state_file``:

 .. code-block:: bash
    :caption: Example Bash VMR which requests a reboot via a reboot file.
    :linenos:

    #!/bin/bash
    # Check to see if a reboot-state file exists and if it does
    # that means we have set the ulimit and can complete
    if [ -e has_rebooted ]
    then
        exit 0
    fi

    echo "This is an example VMR requesting a reboot"
    touch reboot
    touch has_rebooted

Another concrete example of how this can be done is shown in the example below which can be used to set the host name of Windows VMs.

 .. code-block:: powershell
    :caption: Example PowerShell VMR which requests a reboot via a reboot file.
    :linenos:

    Param(
    [Parameter(Mandatory=$True)][string]$hostname
    )

    if(Test-Path "state_file") {
        exit 0
    }

    $computer_info = Get-WmiObject Win32_ComputerSystem
    $computer_info.Rename($hostname.split('.')[0])

    echo $null >> "state_file"
    echo $null >> "reboot"

Finally, the :ref:`tests.reboot_mc` has various examples of Python VMRs requesting a reboot.

.. [#] For more details about why this is the case see https://www.howtogeek.com/182817/htg-explains-why-does-windows-want-to-reboot-so-often/

.. _vmr-env:

VMRs In-Experiment Environment
------------------------------
Because of how the VM Resources are executed within the VMs by the :ref:`QEMU Guest Agent <qga-driver>`, users should not make any assumptions about the `environment variables <https://en.wikipedia.org/wiki/Environment_variable>`_ which are available.
That is, users should **NOT** assume that standard Environment variables (e.g. ``$HOME``, ``$USER``, ``$SHELL``, etc.) are available.
Some software may make assumptions that these common environment variables exist, which may result in odd failures when attempting to run the software.
Below are some examples of environments which *might* be available.

Example output from a VMR which called ``/usr/bin/printenv`` within a Ubuntu 16.04 VM::

   PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
   PWD=/var/launch/-3/test.sh
   LANG=en_US.UTF-8
   SHLVL=2
   _=/usr/bin/printenv

Example output from :py:meth:`run_executable <base_objects.VMEndpoint.run_executable>` which calls ``/usr/bin/printenv`` within a Ubuntu 16.04 VM::

   PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
   PWD=/var/launch/-2/printenv
   LANG=en_US.UTF-8
   SHLVL=1
   OLDPWD=/
   _=/usr/bin/printenv


.. _vmr-location:

Location of VMRs within the VM
------------------------------
Prior to the start of :ref:`schedule-negative-time`, VMRs are uploaded onto the VM.
FIREWHEEL uses the ``/var/launch`` directory on Linux based VMs and the ``C:\launch`` directory on Windows based VMs.
Inside these directories is a series of directories with :ref:`start times <start-time>` that are used by the scheduled VMRs.

For example, if there are VMRs scheduled at -300, -250, -100, and 5 then ``/var/launch`` would look like:

 .. code-block:: bash

   $ ls /var/launch
   -100 -250 -300 5

Inside these ref:`<start-time>` directories is a directory for each VMR which is scheduled at the given time.

For example, if ``set_hostname.sh`` and ``get_stat.py`` both occurred at ``-250`` it would look like:

 .. code-block:: bash

   $ ls /var/launch/-250
   set_hostname.sh get_stat.py

.. note::
   To access negative time folders you will likely need to use either a full path (e.g. ``/var/launch/-100`` or a specific relative path ``./-100``. This is because the negative sign (i.e. the hyphen) is typically used to express a CLI option for most shell programs.

Each of the folders with the VMR name contains a file called ``call_arguments.sh`` which is a dynamically-generated script which executes the VMR.
Additionally, if there is other data, scripts, etc. which need to be executed for the given VMR, they are also located in this directory.
For example, here is the ``/var/launch/-250/set_hostname.sh`` directory:

 .. code-block:: bash

   $ ls /var/launch/-250/set_hostname.sh
   call_arguments.sh set_hostname.sh

Here is an example ``call_arguments.sh`` file for ``set_hostname.sh``:

.. code-block:: bash
   :caption: Example ``call_arguments.sh``

   #!/bin/bash
   CURRENT_DIR="$(dirname "$0")"
   cd /var/launch/-250/set_hostname.sh
   /var/launch/-250/set_hostname.sh/set_hostname.sh host.root.net

To re-run the VMR (for debugging purposes) a user can simply re-execute ``call_arguments.sh`` as the root user:

 .. code-block:: bash

   $ sudo /var/launch/-250/set_hostname.sh/call_arguments.sh

Becoming familiar with the locations of VMRs with the VMs is useful for developing and debugging new VMRs.

.. _vmr-output:

Extracting VMR data
-------------------
Many times VMRs will need to output useful information for later analysis.
For example, your VMR might monitor a process and output a particular statistic for which the user may want to analyze after the experiment.
To do this, VMRs can simply print the data to ``stdout`` and it will be captured by FIREWHEEL and logged to the :ref:`logging.vmr_log_dir <config-vmr_log_dir>` on the :ref:`compute node <cluster-compute-nodes>` which has launched the VM.
Each VM will have its own log file which details the output of the VM Resource Manager for that VM. The log files will be output with the VM name (e.g. the name of the vertex)

If the output is properly formatted `JSON <https://www.json.org>`_, it will be parsed and output to a separate ``.json`` file within the same log folder.
This is particularly useful for further data analysis either with Python or an `Elastic Stack <https://www.elastic.co/elastic-stack>`_.


Using Host-Based VM Resources
------------------------------

Host-based VM resources allow users to execute commands on the physical host where the VM is running, enabling more dynamic interactions with the environment.
Unlike traditional VM resource scheduling, which operates within the VM environment, host-based scheduling allows for direct interaction with the host system.
This can include minimega-specific actions such as replaying VNC sessions, adding network taps, or hotplugging USB devices, which impact the VM, but are not possible within the VM itself.

Additionally, when used thoughtfully (i.e., ideally in positive time), host-based VM resources can impact the entire experiment.
This could include running a script that modifies the entire network topology or makes call a to external APIs to inject new information into the experiment.

.. warning::

   Host-based VM resources should be used with caution, as they have the potential to affect the stability and security of the host system.
   It is essential to ensure that any commands executed on the host are safe and do not compromise the integrity of the host or other VMs running on it.
   - Ensure that the executable specified is either an absolute path or part of the VMR system.
   - Be aware of potential security implications when running host-based actions from untrusted experiments.
   - Recall that schedules are per-VM. Therefore, if there are host-based actions that impact the entire experiment, ensure that they are scheduled appropriately to avoid conflicts or redundant executions.

The primary method for scheduling host-based VM resources is through the use of the :py:meth:`run_host_mm_command <base_objects.VMEndpoint.run_host_mm_command>` method, which creates a :py:class:`RunHostExecutableScheduleEntry <base_objects.RunHostExecutableScheduleEntry>` for executing Minimega commands.
Additional interfaces into host-based scheduling may be added in the future to facilitate common tasks.

:py:meth:`run_host_mm_command <base_objects.VMEndpoint.run_host_mm_command>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The :py:meth:`run_host_mm_command <base_objects.VMEndpoint.run_host_mm_command>` method allows a user to schedule Minimega commands directly on the host.
The method needs a takes a :ref:`start-time` to know when to execute the specified program.
It next needs a list of arguments that represent the Minimega command to run on the host.
The first argument should typically be the Minimega subcommand (e.g., `vm <https://sandia-minimega.github.io/#header_4.6>`__, `tap <https://sandia-minimega.github.io/#header_5.63>`__, `vnc <https://sandia-minimega.github.io/#header_5.67>`__ etc.), followed by any additional parameters required for that command.
An optional `extra_files` parameter allows users to specify any files that are part of that command and must be available on the host executing the command.
These files should be included as VM resources in the model component's `MANIFEST` file.

Examples
""""""""

**Example: VNC Replay**
If a user has recorded a VNC session, they can replay it at a specific scheduled time during the experiment. First, ensure that the recorded VNC session is included as a VM resource and provided to the `extra_files` parameter. In this example, assume the session is called `open-browser.vnc`.

.. code-block:: yaml
   :caption: Example `MANIFEST` file snippet for scheduling a VNC replay.

   vm_resources:
     - vm_resources/**
     - open-browser.vnc

.. code-block:: python
   :caption: Example `plugin.py` for scheduling a VNC replay on the host.

   vm = Vertex(self.g, "desktop-0")
   vm_resource_schedule.decorate(Ubuntu2204Desktop)
   vm.run_host_mm_command(
       10,
       arguments=["vnc", "play", vm.name, "open-browser.vnc"],
       extra_files=["open-browser.vnc"]
   )

**Example: Hotplugging USB Drive**
Minimega can also dynamically hotplug (or unplug) USB devices.
The desired USB drive must be available as a VM resource during the experiment and provided to the `extra_files` parameter.
Assume we have a USB drive image called `mydrive.img`.

.. code-block:: yaml
   :caption: Example `MANIFEST` file snippet for hotplugging a USB drive.

   vm_resources:
     - vm_resources/**
     - mydrive.img

.. code-block:: python
   :caption: Example `plugin.py` for hotplugging a USB drive on the host.

   host = Vertex(self.g, "host")
   host.decorate(LinuxHost)
   host.run_host_mm_command(
       -100,
       arguments=["vm", "hotplug", "add", host.name, "mydrive.img", "2.0"],
       extra_files=["mydrive.img"]
   )


:py:class:`RunHostExecutableScheduleEntry <base_objects.RunHostExecutableScheduleEntry>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The :py:class:`RunHostExecutableScheduleEntry <base_objects.RunHostExecutableScheduleEntry>` class facilitates specifying a program to run from the physical host that launched the VM at a specified schedule time.

- **Constructor Parameters:**
  - `start_time`: The time at which to execute the command.
  - `program`: The program to run on the physical host, which can be an absolute path, the string `"minimega"`, or an executable specified as a VM resource.
  - `arguments`: Optional arguments to pass to the program.

This class is used internally by :py:class:`VMEndpoint <base_objects.VMEndpoint>` methods such as :py:meth:`run_host_mm_command <base_objects.VMEndpoint.run_host_mm_command>`.