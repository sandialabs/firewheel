.. _installing-FIREWHEEL:

####################
Installing FIREWHEEL
####################

Once all of FIREWHEEL's :ref:`install-prereqs` have been completed, FIREWHEEL can be installed either via `pip <https://pip.pypa.io/en/stable/installing/>`_ or via source.

*************************************
Creating a Python virtual environment
*************************************
FIREWHEEL requires a modern version of Python (currently 3.8-3.13) to run.
For ease of use, we recommend installing FIREWHEEL into a virtual environment on all :ref:`cluster-nodes`.
In this example, we are creating a Python version 3.10 :mod:`venv` called ``fwpy``.

.. code-block:: bash

    python3.10 -m venv fwpy
    source fwpy/bin/activate

.. warning::
    The path to FIREWHEEL's virtual environment **MUST** be the same on each node in the cluster. Therefore, we recommend a common path (e.g. ``/opt/firewheel/fwpy``) rather than using a home directory.

***************************
Installing from Source Code
***************************

First, clone the FIREWHEEL git repository into a desired location (in this case ``/opt/firewheel``).
For this example, we assume that ``repo`` is a valid entry in a users ``~/.ssh/config`` file. E.g.

.. code-block:: bash

    Host repo
        Hostname github.com
        User git
        IdentityFile=~/.ssh/github_key

.. code-block:: bash

    # Make a directory and give it the correct permissions
    sudo mkdir /opt/firewheel
    sudo chown -R $(whoami): /opt/firewheel
    # Clone FIREWHEEL into the new directory
    git clone ssh://repo/firewheel/firewheel.git /opt/firewheel

FIREWHEEL's ``install.sh`` will make the remainder of the installation process easy.
However, before running that script, there are several environment variables which should be set.

.. _install-set-env-vars:

Set Environment Variables
=========================

Our installation script allows users to customize installation of FIREWHEEL.
The default values are found in ``provision_env.sh``, but they can be overwritten by setting the key as an environment variable.
For example, to change the default value of :envvar:`DISCOVERY_PORT`, you can use::

    export DISCOVERY_PORT=9090

Generally, the defaults are acceptable for most installations.
However :envvar:`PYTHON_BIN` is likely to change between environments (especially if not using a virtual environment).
Additionally, on clusters of more than one node, :envvar:`FIREWHEEL_NODES`, :envvar:`EXPERIMENT_INTERFACE`, and :envvar:`GRPC_THREADS` should be set.
Finally, if VLANs cannot be used to route traffic between FIREWHEEL nodes, then :envvar:`USE_GRE` should be set to ``true``.

A full list of environment variables used in ``install.sh`` is shown below.

.. envvar:: sid

    :description: The user account who will use FIREWHEEL.
    :default: ``"$(whoami)"``

.. envvar:: FIREWHEEL_NODES

    :description: The hostnames of the nodes in the FIREWHEEL Cluster in a space separated list.
    :default: ``"$(hostname)"``

.. envvar:: HEAD_NODE

    :description: The hostname of the :ref:`cluster-control-node`.
    :default: ``"$(echo $FIREWHEEL_NODES  | cut --delimiter ' ' --fields 1)"``

.. envvar:: FIREWHEEL_ROOT_DIR

    :description: For users installing FIREWHEEL from source, this is the root directory of the source code repository.
    :default: ``/opt/firewheel``

.. envvar:: FIREWHEEL_VENV

    :description: The location of the default FIREWHEEL virtual environment.
    :default: ``${FIREWHEEL_ROOT_DIR}/fwpy``

.. envvar:: PYTHON_BIN

    :description: The Python interpreter executable (a path or symlink).
    :default: ``python3``

.. envvar:: PIP_ARGS

    :description: Any additional arguments/options required for Pip.
    :default: ``""``

.. envvar:: EXPERIMENT_INTERFACE

    :description: The experimental network interface. That is, which NIC connects all nodes in the :ref:`FIREWHEEL-cluster`.
    :default: ``lo``

.. envvar:: USE_GRE

    :description: Whether to use GRE tunnels rather than VLANs to segment traffic for minimega.
    :default: ``false``

.. envvar:: MM_BASE

    :description: The location of minimega's run time files (e.g. VM logs, files, etc.)
    :default: ``"/tmp/minimega"``

.. envvar:: MM_GROUP

    :description: The minimega user group.
    :default: ``minimega``

.. envvar:: MM_CONTEXT

    :description: The context for finding minimega meshage peers. It should distinguish your minimega instances from any others on the network. See https://www.sandia.gov/minimega/using-minimega/ for more information.
    :default: ``${HEAD_NODE}``

.. envvar:: MM_INSTALL_DIR

    :description: The installation directory for minimega.
    :default: ``"/opt/minimega"``

.. envvar:: DISCOVERY_PORT

    :description: The HTTP port for the Discovery service.
    :default: ``8080``

.. envvar:: DISCOVERY_HOSTNAME

    :description: The hostname for the Discovery service.
    :default: ``localhost``

.. envvar:: GRPC_HOSTNAME

    :description: The hostname for FIREWHEEL's GRPC server.
    :default: ``${HEAD_NODE}``

.. envvar:: GRPC_PORT

    :description: The port number to use for FIREWHEEL's GRPC server.
    :default: ``50051``


.. envvar:: GRPC_THREADS

    :description: The number of threads to use for FIREWHEEL's GRPC server.
    :default: ``2``

.. envvar:: FIREWHEEL_GROUP

    :description: The FIREWHEEL's user group (if any).
    :default: ``${MM_GROUP}``

.. envvar:: MC_BRANCH

    :description: The Git branch for the model component repositories that will be cloned.
    :default: ``master``

.. envvar:: MC_DIR

    :description: The location of the model component repositories.
    :default: ``${FIREWHEEL_ROOT_DIR}/model_components``

.. envvar:: MC_REPO_GROUP

    :description: The URL which contains FIREWHEEL's model component repositories.
    :default: ``https://repo/firewheel/model_components``

.. envvar:: DEFAULT_OUTPUT_DIR

    :description: The default directory for FIREWHEEL's various logs, cached Helpers, and other outputs.
    :default: ``/tmp/firewheel``


Running ``install.sh``
======================

Once the configuration options have been set, run ``install.sh``:

.. code-block:: bash

    cd /opt/firewheel
    chmod +x install.sh
    ./install.sh

This script will create necessary directories, install and configure FIREWHEEL, and install our default model component repositories.
The script will optionally install additional FIREWHEEL development dependencies by using either the ``-d`` or ``--development`` flag::

    ./install.sh -d


Post Installation Steps
=======================

Once the entire cluster has been provisioned, we recommend running the :ref:`command_sync` command to cache :ref:`cli_helper_section` across the cluster::

    firewheel sync

Installing Model Component Repositories
---------------------------------------
Before running any experiments, you will likely need to install several Model Component repositories.
Model Component repositories provide extra features and customizations that give FIREWHEEL experiments their flexibility and modularity.

There are two ways to install Model Components.
The first and easiest way is to use a premade Model Component repository which has been converted into a (pip-installable) Python package.
Several of the most commonly used FIREWHEEL Model Components exist in this format, for example the ``base`` and ``linux`` Model Components.

.. code-block:: bash

   pip install firewheel_repo_base

A selection of these MCs are installed by the ``install.sh`` script.

The second way to install a Model Component is using FIREWHEEL's helpers.
This is a good solution for Model Component repositories that are either built or cloned to a local directory.
We recommend putting all these Model Component repositories in ``/opt/firewheel/model_components``.
Then you can use the :ref:`helper_repository_install` to add this location as a known FIREWHEEL Model Component repository::


    firewheel repository install /opt/firewheel/model_components

For more information see :ref:`repositories`.
For information about available Model Components see :ref:`available_model_components`.

Environment Enhancements
------------------------

Once FIREWHEEL has been installed, we recommend symbolically linking FIREWHEEL's CLI to ``/usr/bin/firewheel`` to avoid activating the virtual environment for each new terminal session.

.. code-block:: bash

    sudo ln -s "$(which firewheel)" /usr/bin/firewheel


We also recommend configuring tab-complete for FIREWHEEL's CLI. If using bash, the simplest approach is:

.. code-block:: bash

    sudo cp <path-to-FIREWHEEL>/firewheel_completion.sh /usr/share/bash-completion/completions/firewheel

Alternatively, the following command can be added to a ``.bashrc``, ``.zshrc``, etc.

.. code-block:: bash

    source  <path-to-FIREWHEEL>/firewheel_completion.sh

If the FIREWHEEL configuration changes, the tab completion script ``<path-to-FIREWHEEL>/firewheel_completion.sh`` may be automatically regenerated at any point.

.. code-block:: bash

   python -m firewheel.cli.completion.prepare_completion_script
