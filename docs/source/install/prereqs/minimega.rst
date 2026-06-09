.. _installing-discovery-minimega:


.. _installing-discovery:

####################
Installing discovery
####################
FIREWHEEL installs `discovery <https://github.com/sandia-minimega/discovery>`_ to help translate the :ref:`experiment-graph` into minimega commands.
You can download the cross-platform discovery binaries from https://github.com/sandia-minimega/discovery and then decompress them by using the command::

    sudo tar -C / -xf discovery.tgz

.. note::

    This installs discovery into ``/opt/discovery``.

.. _installing-minimega:

###################
Installing minimega
###################

To instantiate emulation-based experiments, FIREWHEEL relies on `minimega <https://www.sandia.gov/minimega>`_ version 3.0.1 or higher.
minimega should be installed on all :ref:`cluster-nodes` and configured as a `minimega mesh <https://www.sandia.gov/minimega/using-minimega/>`_.
Additionally, FIREWHEEL expects that minimega has been configured as a ``systemd`` service.
While we recommend that users review minimega documentation, found at https://www.sandia.gov/minimega, this section will provide some details about how to install minimega and configure it for use with FIREWHEEL.

*********************
minimega dependencies
*********************

Ubuntu
======
minimega has lots of optional dependencies, but you can install the dependencies necessary for using it with FIREWHEEL by using the following command::

    sudo apt install -y openvswitch-switch qemu-kvm qemu-utils dnsmasq ntfs-3g iproute2 libpcap-dev

Once the dependencies are installed, you can follow the instructions found here https://www.sandia.gov/minimega/module-4-installing-minimega/ to download and install minimega package.
We recommend using the DEB package, as it is easier.


CentOS
======

.. minimega-centos-inclusion-marker

Installing on CentOS is more complicated due to the necessity of installing external repositories in order to install additional dependencies.
You will likely need to install EPEL and IUS in order to capture all required packages.

.. warning::

    While many features of minimega/FIREWHEEL will work on default CentOS packages, newer versions of these tools (especially QEMU) are recommended.
    Specifically, we have encountered VNC-related issues with QEMU 2.0.0 (the default for CentOS) and **strongly** recommend using version 2.11.0 or higher.

You can install many of the dependencies necessary for using it with FIREWHEEL by using the following command::

    sudo yum install -y qemu qemu-kvm qemu-kvm-tools dnsmasq ntfs-3g dosfstools net-tools libpcap libpcap-devel qemu-system-x86

Additionally, minimega requires installing `Open vSwitch (OVS) <https://www.openvswitch.org>`_.
We recommend reviewing the installation procedure for your specific OS.
However, for ease of use, we provide some instructions to install OVS from source code, which have been tested on CentOS 7 [#]_:

.. warning::

    These instructions likely use an older version of OVS!

.. code-block:: bash

    # Installing OVS dependencies
    sudo yum install -y wget openssl-devel  python-sphinx gcc make python-devel openssl-devel kernel-devel graphviz kernel-debug-devel autoconf automake rpm-build redhat-rpm-config libtool python-twisted-core python-zope-interface PyQt4     desktop-file-utils libcap-ng-devel groff checkpolicy selinux-policy-devel python-six unbound unbound-devel

    # Create directories
    mkdir -p ~/rpmbuild/SOURCES

    # Download OVS source code
    wget https://www.openvswitch.org/releases/openvswitch-2.12.0.tar.gz
    cp openvswitch-2.12.0.tar.gz ~/rpmbuild/SOURCES/
    tar xfz openvswitch-2.12.0.tar.gz

    # Build the package
    rpmbuild -bb --nocheck openvswitch-2.12.0/rhel/openvswitch-fedora.spec

    # Install the newly created RPMs
    sudo yum localinstall -y ~/rpmbuild/RPMS/x86_64/openvswitch-2.12.0-1.el7.x86_64.rpm
    sudo yum localinstall -y ~/rpmbuild/RPMS/x86_64/openvswitch-debuginfo-2.12.0-1.el7.x86_64.rpm
    sudo yum localinstall -y ~/rpmbuild/RPMS/x86_64/openvswitch-devel-2.12.0-1.el7.x86_64.rpm

    # Restart OVS to ensure it is running
    systemctl start openvswitch.service
    systemctl enable openvswitch.service


Finally, users should create a new script which will run QEMU with the ``-enable-kvm`` option.
This script is installed via the Ubuntu version of the ``qemu-kvm`` [#]_, but not the CentOS version.
To enable the same functionality (which is required for minimega), run the following commands:

.. code-block:: bash

    sudo echo '#!/bin/sh
    exec /usr/libexec/qemu-kvm -enable-kvm "$@"
    ' >> /bin/kvm
    sudo chmod 751 /bin/kvm

Once the dependencies are installed, you can follow the instructions found at https://www.sandia.gov/minimega/module-4-installing-minimega/ to download and install minimega package.
We recommend using the RPM package, as it is easier.

.. [#] https://www.linuxtechi.com/install-use-openvswitch-kvm-centos-7-rhel-7/
.. [#] https://packages.ubuntu.com/bionic/amd64/qemu-kvm/filelist

.. minimega-centos-stop-marker

.. _configuring-minimega:

********************
Configuring minimega
********************

Once minimega has been installed, we should configure it for use with FIREWHEEL.
First, the minimega ``systemd`` service should be installed by running::

    echo -n "" | sudo /opt/minimega/misc/daemon/minimega.init install

.. note::

    This assumes that minimega was installed into ``/opt/minimega``.

Next, we need to update minimega's configuration file located at ``/etc/minimega/minimega.conf``.
The ``MM_DEGREE`` variable should be updated to be the size of your :ref:`FIREWHEEL-cluster`.
For example, if your :ref:`FIREWHEEL-cluster` contained 2 nodes, you should change it to be ``MM_DEGREE=2``.
To use the :ref:`helper-save`/:ref:`helper-load` functionality, users will also need to enable ``MM_ABSSNAPSHOT`` (i.e., ``MM_ABSSNAPSHOT=true``).
Here is are some find/replace commands which can be useful in scripting this action:

.. code-block:: bash

    sudo sed -i 's/MM_DEGREE=0/MM_DEGREE=1/g' /etc/minimega/minimega.conf
    sudo sed -i 's/MM_ABSSNAPSHOT=false/MM_ABSSNAPSHOT=true/g' /etc/minimega/minimega.conf

Next, it is important to set the correct permissions and ownership for both minimega and discovery.
We can use the following commands:

.. code-block:: bash

    sudo chown -R :minimega /opt/minimega
    sudo chown -R :minimega /opt/discovery
    sudo chmod -R g=u /opt/minimega

Next, the user should join the ``minimega`` system group.
For example, if you wanted the ``fw`` user to run experiments you can use the command::

    sudo usermod -a -G minimega fw

.. note::
    Be sure to log out of the system for the new group permissions to take effect.

The minimega installer leaves the minimega binaries in ``/opt/minimega/bin``.
We recommend linking these as system packages by using:

.. code-block:: bash

    # Link minimega binaries
    sudo ln -s /opt/minimega/bin/minimega /bin/minimega
    sudo ln -s /opt/minimega/bin/minimega /bin/mm

Lastly, make sure that the minimega service is running::

    sudo systemctl restart minimega
