.. _FIREWHEEL-cluster:

***********************
Hardware Infrastructure
***********************

FIREWHEEL runs on standard commodity hardware, and uses standard commodity network devices when needed. No specialty hardware is required.

A FIREWHEEL cluster consists of a ":ref:`cluster-control-node`" and ":ref:`cluster-compute-nodes`".
The control node is where a user interacts with the system and where various necessary background services run.
The compute nodes are where the virtual machines that make up the experiment run.
A cluster can vary in size from a single laptop where one machine plays both control and compute roles to hundreds of high-performance servers.

.. _cluster-nodes:

Cluster Nodes
=============

Cluster nodes can be any compute hardware (and corresponding OS) capable of running VMs.
FIREWHEEL's components are run within a Python virtual environment, so it likely that any operating system that supports minimega and other necessary dependencies will also support FIREWHEEL.
The primary limiting factor for experiment size is compute resources including CPU cores, RAM, hard disk space, and network capacity.
We recommend at least 24 logical CPUs, 128GB RAM, and a 500GB (ideally NVMe) solid state disk.
These specifications should be able to launch an experiment with 50-100 small VMs).
These are just recommendations and the more robust the hardware, the larger the experiment can become.
If more compute power is needed, the size of a cluster can always be increased by adding more nodes.
See the :ref:`install-documentation` for more details about installation requirements and how to set-up and configure (or reconfigure) a FIREWHEEL cluster.

.. _cluster-control-node:

Control Node
------------

Each cluster contains a single control node.
This control node, also called a head node, is the cluster node from where FIREWHEEL manages deployment of the virtual machines and network configurations that make up a FIREWHEEL experiment network.
A FIREWHEEL cluster's head node can be the only node in the cluster, in which case all VMs in an experiment will also be running on it when deployed.
However, with only one server's resources available, the size of the virtual network that can be deployed may be limited.
See the :ref:`install-documentation` for FIREWHEEL head node configuration and software installation instructions.

.. _cluster-compute-nodes:

Compute Nodes
-------------

FIREWHEEL clusters also contain compute nodes.
These nodes extend the size of the virtual networks that FIREWHEEL can deploy, with the maximum size being dependent on the total amount of compute resources available across the cluster (e.g. RAM and CPUs), and the amount of resources required by the VMs being deployed for a given network topology.
As stated above, a FIREWHEEL cluster can grow in size as needs increase by adding or upgrading compute nodes.

.. _cluster-switch:

Cluster Switch
==============

The switch is used to network two or more nodes together in a FIREWHEEL cluster.
The switch supports the transport of packets amongst nodes to enable both distributed experiment management (e.g. multi-node topology deployment, tear down) and in-experiment virtual network communications.
FIREWHEEL uses minimega to manage the communication between nodes in a cluster.
This communication can happen via GRE tunnels of VLANs.
We do not assume that access to the switch is provided, and the only requirement is that all nodes in a cluster can directly communicate with one another.
We recommend that cluster nodes are networked together using 10Gb links, but that is not a hard requirement.
For more information about running minimega in on a cluster please see `minimega's install documentation <https://www.sandia.gov/minimega/using-minimega/>`_.
