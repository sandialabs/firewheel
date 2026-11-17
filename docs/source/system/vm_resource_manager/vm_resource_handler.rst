.. _vm-resource-handler:

VM Resource Handler
===================

To facilitate the execution of VMRs, FIREWHEEL uses a :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>`, which is a process which launches on the :ref:`compute node <cluster-compute-nodes>` and manages the VMRs for that specific VM.
In addition to being in charge of loading VMRs on to a VM, it also facilitates executing commands on VMs and extracting information out of the environment (e.g. :ref:`helper_pull_file`).

Practically, the :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>` dynamically loads in drivers which perform the actual interactions between the VM and the :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>`.
FIREWHEEL currently supports multiple VM Resource Handler communication drivers, including:

* :py:class:`QemuGuestAgentDriver <firewheel.vm_resource_manager.drivers.qemu_guest_agent_driver.QemuGuestAgentDriver>` for QEMU/KVM VMs using the QEMU Guest Agent. This driver is selected with engine ``QemuVM``. See :ref:`qemu-guest-agent`.
* :py:class:`ADBDriver <firewheel.vm_resource_manager.drivers.adb_driver.ADBDriver>` for Android guests using the Android Debug Bridge. This driver is selected with engine ``ADB``. See :ref:`adb-driver`.

.. note::

   Additional drivers may be added in the future for other guest communication mechanisms, such as `miniccc <https://www.sandia.gov/minimega/module-28-miniccc-and-the-cc-api/>`_.

This dynamic loading mechanism allows FIREWHEEL to support different guest communication mechanisms without changing the VM Resource Handler's scheduling logic.

.. _vm-resource-logs:

VM Resource Logs
----------------
The :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>` also facilitates logging VMR data onto the physical host.
