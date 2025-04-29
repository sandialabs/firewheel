.. _vm-resource-handler:

*******************
VM Resource Handler
*******************

To facilitate the execution of VMRs, FIREWHEEL uses a :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>`, which is a process which launches on the :ref:`compute node <cluster-compute-nodes>` and manages the VMRs for that specific VM.
In addition to being in charge of loading VMRs on to a VM, it also facilitates executing commands on VMs and extracting information out of the environment (e.g. :ref:`helper_pull_file`).

Practically, the :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>` dynamically loads in drivers which perform the actual interactions between the VM and the :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>`.
Currently, there is only one driver (:py:class:`QemuGuestAgentDriver <firewheel.vm_resource_manager.drivers.qemu_guest_agent_driver.QemuGuestAgentDriver>`) which handles VMs of type ``QemuVM`` (see :ref:`qemu-guest-agent`).
However, this dynamic loading function enables future expansion of drivers that will work without changing the :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>` [#f1]_.

.. _vm-resource-logs:

VM Resource Logs
================
The :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>` also facilitates logging VMR data onto the physical host.

.. [#f1] For example, we hope to eventually create a driver for `miniccc <https://www.sandia.gov/minimega/module-28-miniccc-and-the-cc-api/>`_.
