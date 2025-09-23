.. _FIREWHEEL-architecture:

*********************
Software Architecture
*********************

FIREWHEEL provides capabilities for the automated orchestration of VM deployments, virtual network provisioning, host/device application management, run time activity execution, and data collection for user defined cyber experiments.
To accomplish this, FIREWHEEL's *Control* system interprets user defined experiment models and interfaces with several open source technologies that handle things such as computer hardware virtualization, network virtualization, and persistent data storage, to name a few.

.. _fw_sw_arch:

.. figure:: fw20_sw_arch.png
   :align: center
   :scale: 55%
   :alt: FIREWHEEL Software Architecture

   FIREWHEEL Software Architecture

FIREWHEEL's software architecture, as shown in :numref:`Figure %s <fw_sw_arch>`, consists of a Command Line Interface (CLI), Experiment Models, and three other major components (*Control*, minimega, and the *VM Resource Manager*) that convert experiment models into running experiments, and manage FIREWHEEL's VM deployment, virtual network and VM provisioning, and run time execution capabilities.
These FIREWHEEL software components are executed within a Python Virtual Environment, which we will refer to as ``fwpy``, and interact with the Hardware Virtualization components, QEMU/KVM and Open vSwitch (OVS), to instantiate experiment models as configured VMs communicating via virtual networks.
We'll next discuss each of FIREWHEEL's major software components.

.. note::

    For more detailed insight into how FIREWHEEL's components interact with one another, see the full :ref:`class_diagrams` and :ref:`package_diagrams`.

.. toctree::
   :hidden:

   diagrams

.. _fw_cli:

Command Line Interface
======================

The FIREWHEEL Command Line Interface (CLI) allows interaction with and management of FIREWHEEL.
The CLI (:py:mod:`cli/firewheel_cli.py <firewheel.cli.firewheel_cli>`) uses Python's
:py:mod:`cmd` module.
However, there is one notable difference: the CLI is designed to work with a FIREWHEEL cluster which means that commands may need to be executed on one or many hosts.
To accomplish this, the CLI has been extended with :ref:`cli_helper_section`.
:ref:`cli_helper_section` do not use the standard `Cmd <https://docs.python.org/3/library/cmd.html>`_ format, but they enable us to use Python and Shell scripting to perform various actions across the cluster (see :ref:`cli_executors`).
The CLI automatically distributes Helpers to enable performing actions over the entire cluster.
Therefore, the CLI may be accessed from any node in the cluster.
The distinction between commands and Helpers is not relevant for most users so we will use these terms interchangeably.
CLI commands may output error message to the screen, but remote commands will indicate an error through a non-zero exit code.


.. note::

   For more information on the design of the FIREWHEEL CLI, please see :ref:`cli_design`.

.. _experiment-models:

Model Components
================
A FIREWHEEL experiment is simply a collection of model components which, when combined, define everything about an experiment.
The model components that make up an experiment define its network topology, which can include:

    * Its vertices, which will become computing, networking, or other device VMs
    * The edges that represent network connections amongst the vertices
    * :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` and :py:class:`Edges <firewheel.control.experiment_graph.Edge>` class types that can be assigned to individual vertices
    * The VM images associated with the various :py:class:`Vertex <firewheel.control.experiment_graph.Vertex>` class types
    * VM resource files that will alter the state of a VM once booted
    * Scheduling info for when and where those VM resources will modify the VM

FIREWHEEL's model components depend on one another to provide reusable, modular building blocks for constructing a wide variety of LAN, WAN, or even Internet scale experiments.

Users build experiment models by creating and combining the sets of model components that define the topologies, attributes, configurations, and scheduled actions for their experiments.
Model components can depend on the outputs or capabilities of other model components, and ultimately the set of model components that make up a given experiment depend on model components provided by `firewheel_repo_base <https://github.com/sandialabs/firewheel_repo_base>`_.

.. note::

   For more information on the design of the Model Components, please see :ref:`mc_design`.

.. _control-system:

*Control*
=========

Once an experiment has been defined through a set of model components, it's ready to be launched and instantiated as VMs and virtual networks.
The first step in this process is to translate the experiment's model, as described by the model components that it's comprised of, into an internal in-memory representation of the experiment's network topology.
This internal experiment representation includes all the information that's needed for instantiating the experiment model on a virtualization platform.
This translation process is the job of FIREWHEEL's *Control* system, and the fully populated internal representation of an experiment is what it produces.

.. _experiment-graph:

Experiment Graph
^^^^^^^^^^^^^^^^

The output of the *Control* system (FIREWHEEL's internal, intermediate, run-time representation of an experiment) is called an experiment graph.
It's represented as a graph, with vertices and edges, to best provide an abstract representation of the experiment network topology the user wants instantiated as VMs and virtual network links.
The experiment graph contains all the information about each VM (the vertices) and the network connections amongst them (the edges) that were collectively specified in the experiment's set of model components.
Once constructed, the experiment graph will be passed to a virtualization management component that will instruct hardware virtualization systems to instantiate the experiment graph on a their platforms.
FIREWHEEL uses `NetworkX <https://networkx.org/>`_ [#netx]_, a Python library for studying graphs and networks, to implement an experiment graph.

.. [#netx] Aric A. Hagberg, Daniel A. Schult and Pieter J. Swart, `Exploring network structure, dynamics, and function using NetworkX <https://doi.org/10.25080/TCWV9851>`_, in `Proceedings of the 7th Python in Science Conference (SciPy2008) <https://doi.org/10.25080/PFVC8793>`_, Gäel Varoquaux, Travis Vaught, and Jarrod Millman (Eds), (Pasadena, CA USA), pp. 1-15, Aug 2008



.. _minimega:

minimega
========

`minimega <https://www.sandia.gov/minimega/>`__, is the name of the virtualization management component that's currently available with FIREWHEEL. minimega will instantiate an experiment using QEMU/KVM for VMs, and OVS networks.
minimega receives an experiment graph from FIREWHEEL's *Control* system, then determines and sends the appropriate set of instructions to the QEMU/KVM hypervisor and OVS virtual networking systems that are needed to instantiate the experiment model as an emulated computer network.
At this stage the experiment network's topology has been fully instantiated on the virtualization platform, but has yet to have any of its scheduled actions applied to it -- which may further configure the compute systems and network devices as needed before beginning the intended cyber experiment.

.. _vm-resource-manager:

*VM Resource Manager*
=====================

The last step in the process of launching a FIREWHEEL experiment is to monitor and manage the execution of any scheduled actions that need to be performed on the experiment network.
Scheduled actions can be separated into two temporal categories, pre and post experiment start.
Pre-start-time actions can be used to further configure VMs and networking prior to executing any experiment actions, and post-start-time actions can perform any number of actions needed for conducting the experiment.
The *VM Resource Manager* is the FIREWHEEL component that performs this job.
It receives the information about all actions that need to be performed (i.e. the vertices to perform them on, when they are to be performed, the commands, scripts or executables that need to be run, and/or any other resources required for accomplishing the action), and manages the execution of each action on each VM as required and at the designated time.
Once the *VM Resource Manager* has successfully finished monitoring and managing pre-start-time scheduled actions, then the experiment's emulated computer network is ready for conducting the intended experiment, and the *VM Resource Manager* will now do the same for actions that are scheduled to happen post-start-time i.e. actions that are part of the experiment.

.. note::

   For more information on the design of the *VM Resource Manager*, please see :ref:`vm_resource_system`.

Analytics
=========

Once the experiment is launched, gathering and analyzing experimental data becomes crucial.
To facilitate this process, FIREWHEEL provides seamless logging of VM resource output and generates JSON-formatted logs that can be easily ingested into data analysis tools such as Elasticsearch or Jupyter Notebooks.
After the data has been ingested into your preferred tool, users can visually display the experimental data or conduct analyses as needed.
