.. _install-prereqs:

"""""""""""""
Prerequisites
"""""""""""""

This section outlines all the prerequisites for FIREWHEEL and how to prepare your system to install FIREWHEEL.

System Dependencies
===================

.. include:: prereqs/dependencies.rst
   :start-after: dependencies-inclusion-marker
   :end-before: dependencies-inclusion-stop

Below is a brief outline of the system packages needed for full FIREWHEEL functionality with the exception of Python, discovery, minimega, git, and git-lfs as those are discussed in further detail in subsequent sections.

Full details about FIREWHEEL's dependencies be found in :ref:`firewheel-dependencies`.

Ubuntu
------
The following command will install all required system packages for FIREWHEEL and optional packages used in :ref:`cli_helper_section`::

    sudo apt-get install -y tar net-tools procps tmux ethtool uml-utilities

For users who are improving FIREWHEEL, building documentation, or running the FIREWHEEL tests, these packages are also needed::

    sudo apt-get install -y graphviz texlive-latex-recommended texlive-fonts-recommended texlive-latex-extra latexmk libenchant-2-dev

CentOS
------
The following command will install all required system packages for FIREWHEEL and optional packages used in :ref:`cli_helper_section`::

    sudo yum install -y tar net-tools procps-ng tmux ethtool

.. note::

    You may need to install the IUS and/or EPEL repositories for some packages.

Additional Dependencies and Configuration
=========================================

Once the main system packages have been installed, there are a couple of more complicated dependencies and system configuration which **must** occur.
These include:

* :ref:`Enabling passwordless-sudo access for your user account <sudo>`.
* :ref:`Enabling passwordless-SSH access between FIREWHEEL cluster nodes <install-ssh-config>`.
* :ref:`Installing git-lfs <git-lfs>`.
* :ref:`Installing discovery and minimega <installing-discovery-minimega>`.

.. toctree::
    :hidden:

    prereqs/dependencies
    prereqs/sudo
    prereqs/ssh_keys
    prereqs/git
    prereqs/minimega
