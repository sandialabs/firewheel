.. FIREWHEEL Complete Dependency List

.. _firewheel-dependencies:

System Dependencies
===================

.. dependencies-inclusion-marker

While FIREWHEEL is a Python package, it also depends on several system-level packages.
FIREWHEEL has been tested with the following operating systems:

* Ubuntu 18.04
* Ubuntu 20.04
* Ubuntu 22.04
* CentOS 7
* RHEL 8
* RHEL 9

The instructions provided in this documentation are tailored specifically for Ubuntu 22.04 and RHEL 9, although FIREWHEEL will likely be compatible with corresponding system packages on the majority of operating systems.

.. dependencies-inclusion-stop

In this section, we outline the required packages and a few optional ones which might be useful.

Required System Packages
------------------------
- ``minimega``
    + Version: 2.7 (or higher)
    + Description: A distributed VM management tool.
    + Purpose: Default mechanism for launching VMs.
    + Source: https://www.sandia.gov/minimega/
- ``discovery``
    + Version: 0.1 (or higher)
    + Description: A tool set to create network models.
    + Purpose: Convert FIREWHEEL graph into minimega commands.
    + Source: https://github.com/sandia-minimega/discovery
- ``git``
    + Version: We recommend version 2.17 or higher.
    + Description: Fast, scalable, distributed revision control system
    + Purpose: Be able to clone Model Component git repositories.
    + Source: https://git-scm.com/
- ``git-lfs``
    + Description: Git Large File Support
    + Purpose: Be able to clone Model Component git repositories containing large file objects.
    + Source: https://git-lfs.github.com/
- ``net-tools``
    + Description: A collection of programs that form the base set of the NET-3 networking distribution for the Linux operating system.
    + Purpose: Enable configuration of host network interfaces.
    + Source: https://sourceforge.net/projects/net-tools/
- ``procps``
    + Description: procps is a set of command line and full-screen utilities that provide information out of the pseudo-filesystem most commonly located at ``/proc``.
    + Purpose: Provide access to ``pkill`` and ``pgrep`` which are used to clean up experiments.
    + Source: https://gitlab.com/procps-ng/procps
- ``Python``
    + Version: 3.7 (or higher)
    + Purpose: Running FIREWHEEL.
    + Source: https://www.python.org/
- ``tar``
    + Description: GNU version of the tar archiving utility
    + Purpose: Decompress images to cache and launch them.

Optional System Packages (for Helpers)
--------------------------------------
Additionally, some FIREWHEEL :ref:`cli_helper_section` also require some system packages.
These packages are completely optional as users can avoid calling those Helpers.

- ``tmux``
    + Helpers: :ref:`helper_tmux_cluster`
    + Description: terminal multiplexer.
    + URL: https://github.com/tmux/tmux
- ``ethtool``
    Helpers: :ref:`helper_tshoot_check_nics`
    Description: ethtool is the standard Linux utility for controlling network drivers and hardware, particularly for wired Ethernet devices.
    + URL: https://mirrors.edge.kernel.org/pub/software/network/ethtool/
- ``uml-utilities``
    Helpers: :ref:`helper_vm_builder`
    Description: User-mode Linux is a port of the Linux kernel to its own system call interface. This is particularly useful for providing the `tunctl <https://linux.die.net/man/8/tunctl>`_ utility.
    + URL: https://packages.debian.org/sid/uml-utilities

Optional System Packages (for Developers)
-----------------------------------------
- Graph:
    + Purpose: Generating class diagrams.
    + Ubuntu Package(s): ``graphviz``
- Latex:
    + Purpose: Building Sphinx documentation
    + Ubuntu Package(s): ``texlive-latex-recommended texlive-fonts-recommended texlive-latex-extra latexmk``
- Enchant:
    + Purpose: For checking documentation spelling.
    + Ubuntu Package(s): ``libenchant-2-dev``
    + CentOS Package(s): ``enchant2-devel``

Python Dependencies
===================
Most FIREWHEEL dependencies are Python packages.
Many of these are used only for testing or development.
The complete lists are located in ``setup.py``.
For completeness sake, we have generated a table of *recursive* Python dependencies using `pip-licenses`_.

.. include:: pip-dependencies.rst

.. _pip-licenses: https://pypi.org/project/pip-licenses/
