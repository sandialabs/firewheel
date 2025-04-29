.. _firewheel_security:

#######################
Security Considerations
#######################
FIREWHEEL is a complex cluster-based software and there are a number of potential security concerns.
This section explores each known issue/assumption and addresses ways to reduce risk.
While several of these issues are a function of FIREWHEEL dependencies (e.g. minimega), we included them to provide complete transparency to users.
Additionally, we are working with the developers of these tools to address potential concerns.

************
Known Issues
************

Passwordless SSH
================
FIREWHEEL's CLI depends on having SSH access to the entire :ref:`FIREWHEEL-cluster`.
This remains true even when running on a single node.
This access enables FIREWHEEL to be able to :ref:`command_sync` the Helper cache and to execute CLI :ref:`Helpers <cli_helper_section>`.
For convenience, users likely will not set a password on the SSH private key file.
For more information about this topic, people can review `this article <https://www.redhat.com/sysadmin/passwordless-ssh>`_.

Risks
-----
Generally, using SSH keys is more secure than passwords.
However, key reuse across multiple services could enable attackers broader access in the event of a key compromise.
Additionally, while not entirely security-related, administrators should be aware that FIREWHEEL's SSH usage may also hinder auditing system logs.
That is, some login events attributed to the user could have been the result of the user executing a FIREWHEEL command.

Mitigations
-----------
#. We recommend generating a new key each time a FIREWHEEL cluster is initialized.
   This will eliminate reuse concerns.
#. Use proper network segmentation techniques to separate each FIREWHEEL clusters from each other and from the remainder of the network.
#. For auditing purposes, administrators should save FIREWHEEL's ``cli.log``, ``firewheel.log``, and ``cli_history.log``.
   This will enable correlation between access events and automated action taken by FIREWHEEL's CLI.


Passwordless ``sudo``
=====================
Currently, we recommend that FIREWHEEL users have passwordless ``sudo`` access to facilitate easy use of privileged commands.
FIREWHEEL uses ``sudo`` for the following actions:

* Restarting the minimega service.
  Found in :ref:`helper_start`, :ref:`helper_stop_hard`, and :ref:`helper_mm_make_bridge`.
* Removing logs created by services started by minimega (they have root permissions).
  Found in :ref:`helper_stop_hard`.
* Setting correct group permissions on minimega's base directory (typically ``/tmp/minimega``).
  Found in :ref:`helper_stop_hard`.
* Ensuring all :ref:`VM Resource Handler's <vm-resource-handler>` have been terminated.
  Found in :ref:`helper_stop_hard` and :ref:`helper_stop`.
* Creating an experiment bridge and setting up correct routing for minimega using Open vSwitch.
  Found in :ref:`helper_mm_make_bridge`.

Risks
-----
It is considered best practice for ``root`` access to be restricted due to the permission level.
Passwordless ``sudo`` enables programs to automatically escalate privileges posing obvious risks.

Mitigations
-----------
#. We **strongly** recommend that only a single user (or small set of trusted users) should have access to the :ref:`FIREWHEEL-cluster`.
   To easily facilitate this, we recommend using bare metal provisioning system like igor_ or MAAS_ to create a fresh installation for each user.
#. We recommend only installing trusted software on your FIREWHEEL cluster.
#. For situations where the previous suggestions cannot be implemented, administrator can provide passwordless ``sudo`` for specific commands (for example see `this post <https://askubuntu.com/a/159009>`_).
#. For single-node clusters, administrators can require users to always enter a password for ``sudo``.
   Users who are required to enter a password should minimize the use of :ref:`helper_stop_hard` to improve work-flow.


minimega Permissions
====================
minimega currently requires ``root`` permissions to run.
This level of access is necessary for running system-level tasks like launching VMs and using `Open vSwitch <http://www.openvswitch.org/>`_.

Risks
-----
These permissions extend to all minimega commands_.
This means that each of the commands can be executed with ``root`` permissions.

Mitigations
-----------
#. The minimega team is currently working on addressing this issue.
   Once this has been fixed, this will no longer be an issue.
#. A recent `pull request <https://github.com/sandia-minimega/minimega/pull/1414>`_ enables users part of the `minimega` group to have permissions.
   This prevents all users from needing ``root`` permissions.
   We recommend using this group and only adding those users to the minimega group which are trusted to have ``root`` permissions on the physical host.


Arbitrary Command Execution With minimega
=========================================
minimega enables users to execute shell commands through the use of the shell_ and background_ commands.
FIREWHEEL leverages these commands to launch the :exc:`gRPC Server <firewheel.lib.grpc.firewheel_grpc_server>`, miniweb_, Discovery_, and the :exc:`VM Resource Handler's <firewheel.vm_resource_manager.vm_resource_handler>` needed during an experiment.

Risks
-----
When combining this risk with running minimega as ``root`` enables users to execute shell commands with those privileges.
The shell_ and background_ minimega commands are available via the minimega CLI, the minimega Python bindings, and FIREWHEEL's :class:`minimegaAPI <firewheel.lib.minimega.api.minimegaAPI>`, which improves ease of use of the minimega Python bindings.
Therefore, any model components (or any Python code operating in the same environment as FIREWHEEL or minimega) can easily leverage this potentially dangerous functionality.

Mitigations
-----------
While the minimega team is working to address running as ``root``, this is a fundamental property of minimega and will likely not be changed.
To reduce risk, we recommend:

#. Only allowing trusted users on the system running FIREWHEEL.
   That is, do not share hardware among untrusted participants.
#. Use proper network segmentation techniques to separate each FIREWHEEL clusters from each other and from the remainder of the network.
#. Do not load untrusted Python packages into your environment.
#. Do not run untrusted model components within your experiment.
   You can potentially search through unknown model components and verify if they are calling minimega.


Using Python Pickle for Schedule Entries
========================================
FIREWHEEL uses :py:mod:`pickle` to send VM resource schedules to the :exc:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler>`.
Using :py:mod:`pickle` enables generating and transferring complex :py:class:`ScheduleEntry <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>` objects containing binary or Python object data which is not possible using a safer alternative (like JSON).

Risks
-----
There is inherent risk to using :py:mod:`pickle` because:

   It is possible to construct malicious pickle data which will **execute arbitrary code during unpickling**. Never unpickle data that could have come from an untrusted source, or that could have been tampered with.

In the case of FIREWHEEL, malicious model components can add harmful :py:class:`ScheduleEntries <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>` and perform arbitrary code execution across the cluster.

Mitigations
-----------
#. The FIREWHEEL developers are investigating using JSON to transfer ScheduleEntries.
   We will be doing a full assessment of what (if any) functionality will be lost using JSON and the potential impacts.
#. Until a safer alternative is used, we recommend users to avoid using untrusted Model Components as they could contain malicious :py:class:`ScheduleEntries <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>`.
#. As we have previously mentioned, we **strongly** recommend that only a single user (or small set of trusted users) should have access to the FIREWHEEL cluster.
   This mitigates the possibility of an untrusted user creating a malicious model component or accessing the picked data.


Executing Helpers
=================
In FIREWHEEL users have the ability to *extend* the CLI using :ref:`cli_helper_section`.
These Helpers can be shell or Python scripts.
New Helpers can easily be created which will then be executed on the physical nodes via our :mod:`firewheel.cli.host_accessor`.

Risks
-----
If a malicious Helper is installed, this could pose a risk to your cluster.

Mitigations
-----------
#. Review the list of :ref:`cli_helpers` to identify possible security issues.
   Please report any issues to the FIREWHEEL development team.
#. We recommend only installing Helpers from trusted parties.
#. You can validate which Helpers are installed using the :ref:`command_list` command.
   Additionally, you can view the Helper cache (typically located in ``/scratch/fw-cli``) and ensure only expected files are present.

Installing Model Component Repositories
=======================================
Because the Model Component framework is flexible, users have the ability to share groups of Model Components via :ref:`repositories`.
When these repositories are installed using the :ref:`helper_repository_install` Helper, users have the option to run a Model Component-specific script to download/install other data (i.e. a :ref:`mc_install`).
These INSTALL files are executed and can contain any arbitrary executable code.
Therefore, it is critical that users fully trust the repository/Model Component developers prior to installing the repository.

Risks
-----
If a malicious Model Component INSTALL file is executed, it has the ability to conduct arbitrary code execution.

Mitigations
-----------
#. We recommend only installing Model Components from trusted parties.
#. By default, users have to use the :option:`repository install -s` option when installing repositories to prevent accidentally running these files.
#. When using the :option:`repository install -s` option, a prompt helps users view the INSTALL files and manually confirm that they can be installed.
#. We do **NOT** recommend using the :option:`repository install --insecure` option, which can bypass individual confirmation.


.. _commands: https://sandia-minimega.github.io/
.. _shell: https://sandia-minimega.github.io/#header_5.51
.. _background: https://sandia-minimega.github.io/#header_5.3
.. _miniweb: https://www.sandia.gov/minimega/module-10-web-interface-and-connecting-to-a-virtual-machine-with-vnc/
.. _Discovery: https://github.com/sandia-minimega/discovery/
.. _igor: https://www.sandia.gov/igor/
.. _MAAS: https://maas.io/
.. _PyPI: https://pypi.org/
