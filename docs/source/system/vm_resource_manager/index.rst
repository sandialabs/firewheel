.. _vm_resource_system:

###################
VM Resource Manager
###################

The system for automated configuration of virtual machines (VM) in FIREWHEEL is called the *VM Resource Manager*.
This system is responsible for monitoring and managing the execution of any scheduled actions that need to be performed on the experiment network.
These in-experiment changes happen using VM resources (VMRs).

VM resources (VMRs) can be used to execute any function you want to have operate on a VM.
A VMR can be a script, configuration file for a service, tarballs, zip files, or even binary installers.
VMRs are used to configure VMs, install and configure applications on them, and to carry out other actions needed to conduct an experiment, such as generating network traffic and collecting data for analysis.
VM Resources are covered briefly in :ref:`vm_resources_field`.

When creating an Emulytics experiment, we recommend always starting with a base image and then further configuring it during the experiment.
Using this approach is NOT required as it is completely feasible to "pre-bake" an image and use it for an experiment.
However, there are several benefits to dynamic, automated configuration of VMs on experiment creation.

#. **Reproducibility**: Every VM has an explicit order of configuration steps that were run in order to create the VM.
   There are no experiment specific changes "baked-in" to the VM that can be forgotten or incorrectly documented in the future.
   Recreating the VM is as simple as rerunning the configuration.
#. **Deduplication of Effort**: Many images will require very similar changes across differing experiments.
   Instead of manually making image or experiment specific changes, making a reusable VM resource to accomplish the task reduces long-term effort.
#. **Shareability**: VM Resources can be shared across experiments.
   Once a VMR has been created to accomplish a specific task, there is no need to recreate that functionality.
   Different experiments can take advantage of all available VMRs.
#. **Smaller VM Library**: Automated configuration of base images reduces the overall number of images used per experiment.
   A smaller VM library means less disk space is required on each compute machine.

.. toctree::
   :maxdepth: 2

   vmr_schedule
   vmr_in_experiment
   vm_resource_handler
   qga
