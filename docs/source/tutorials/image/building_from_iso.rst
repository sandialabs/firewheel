.. _building_iso:

#############################
Building a New Image from ISO
#############################

This tutorial will assume that you're starting from nothing with just an ISO that was downloaded from the Internet.
In the case where an image is already available, then skip ahead to :ref:`guest_agent`.

***********************
Downloading an ISO file
***********************

We can build a new ``Ubuntu 18.04 Server`` image to include in FIREWHEEL.
In order to do this we need the ISO file to do the installation.
It can be downloaded from the `Ubuntu website <https://old-releases.ubuntu.com/releases/18.10/ubuntu-18.10-live-server-amd64.iso>`_.
We will also need a desktop version if you choose to follow the steps in :ref:`optimizing_disk_size`.
That can be downloaded from `Ubuntu Desktop <https://old-releases.ubuntu.com/releases/18.10/ubuntu-18.10-desktop-amd64.iso>`_.

.. _create_disk:

*************
Create a Disk
*************

A disk is required to permanently install the operating system.
We can use ``qemu-img create`` in order to create a new disk image: ::

    $ qemu-img create -f qcow2 ubuntu-18.10-server-amd64.qcow2 10G

The command above creates a qcow2 formatted blank disk of size 10 GB that is named ``ubuntu-18.10-server-amd64.qcow2``.
You are free to adjust the size of the disk as needed.
Generally, installation is done with a small disk size to keep the disk compact.
We can then increase the disk size once the installation is complete.
This is covered in the section :ref:`optimizing_disk_size`.
To be clear, it is perfectly acceptable to give the disk a larger size at this point and not bother with the optimization steps.
In the case where you will not be optimizing the disk, then disk sizes between 20 and 50 GB are usually sufficient.

.. note::
    The permissions on the disk image should enable read and write access.
    Without correct disk permissions, the image will fail to run scheduled actions.


*******************
Starting Networking
*******************

Before booting the new disk with the ISO, we need to have a network for communication with the VM.
This can be done using the ``libvirt`` package. ::

    $ sudo apt-get install libvirt-bin

The ``libvirt`` package will handle all the NAT and DHCP settings for us and allow us to communicate with the VM from the underlying physical host.
Now that the package is installed, we can start the networking: ::

    $ sudo virsh net-create default

If that command fails then run the following: ::

    $ sudo virsh net-start default

This will create a virtual bridge called ``virbr0``.
You can confirm that is has been created by running: ::

    $ ip address

This will print all the networking interfaces on the physical machine.
You should see ``virbr0`` in the list.
We will use this bridge once the VM has been booted.

.. _booting_image:

*****************
Booting the Image
*****************

The installation requires that the image get booted with both the disk that was just created and the ISO that was just downloaded.
The following command will start the VM with all required settings: ::

    $ sudo  /usr/bin/qemu-system-x86_64 -nographic -nodefaults --enable-kvm -name ubuntu \
    -drive file=/opt/firewheel/ubuntu-18.10-server-amd64.qcow2,if=virtio,cache=writeback \
    -vnc 0.0.0.0:0 \
    -cpu qemu64 -smp sockets=1,cores=4,threads=2 \
    -m 8092 -vga std \
    -netdev tap,ifname=installer,id=hostnet0,script=no,downscript=no \
    -device virtio-net-pci,netdev=hostnet0,id=net0,mac=00:00:00:ff:ff:01 \
    -device piix3-usb-uhci -device usb-tablet -device piix3-usb-uhci \
    -chardev socket,id=qga0,server,nowait,path=/tmp/ga.sock \
    -device virtio-serial \
    -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \
    -drive file=/opt/firewheel/ubuntu-18.10-server-amd64.iso,index=2,media=cdrom

Let's walk through what some of the options are providing the VM and which ones can be modified.

* ``name``: This is a name that is provided by the user. It has no bearing on the final image and can be changed to anything you like.
* ``drive``: This tells the VM where to find the disk image that was just created. This should be the absolute path to the disk that was made above.
* ``vnc``: This creates a VNC server that allows access to the VM's console. In this case we chose VNC port ``0`` (which gets translated to ``5900``). Feel free to change this to any open VNC port.
* ``cpu``: We're using a default of ``qemu64`` for the CPU architecture. Some images may require a specific CPU architecture. CPU options can be viewed by running: ``qemu-system-x86_64 -cpu ?``
* ``smp``: The ``SMP`` options allow a user to specify the number of CPU sockets the image will have, how many cores each socket will have, and how many threads each core will have. Modify these values as needed.
* ``netdev``: This creates a network device. In this case we are naming it ``installer``. Feel free to change this name.
* ``device``: This is the the second part to creating a network interface. This plugs a network card into a ``PCI`` slot on the VM. It is tied to a specific ``netdev`` which is specified as a parameter.
* ``chardev``: This is a character device that is the first part of creating a virtual serial port. FIREWHEEL uses a serial port to orchestrate VM configuration.
* ``device``: This ``virtserialport`` is the second part of creating a virtual serial port. It is tied to a specific ``chardev`` which is specified as a parameter.
* ``drive``: This last ``drive`` specifies that a ``CDROM`` should be connected to the VM. The ``file`` parameter is the absolute path to the ISO file that was downloaded above.

*************************
Connecting the Networking
*************************

The ``qemu-system-x86_64`` command above created a network interface called ``installer``.
Run the following command to confirm that it exists: ::

    $ ip address

We can put that interface on the bridge that was created above to give the VM access to the network. ::

    $ sudo brctl addif virbr0 installer
    $ sudo ip link set dev installer up
    $ sudo ip link set dev virbr0 up

This will provide the VM with an IP address via DHCP.
Commonly, this ends up being ``192.168.122.19/24``.

*******************************
Installing the Operating System
*******************************

Connect to the VNC server at port ``0``.
An easy way to do this is to use minimega's version of noVNC.
Assuming minimega is installed at ``/opt/minimega``, to start the client, you can use:

.. code-block:: bash

    $ cd /opt/minimega/web/novnc
    $ ./utils/launch.sh

This will launch a VNC client that you can connect to in a browser.
Note that you may have to forward the port to a local desktop and change hostnames to ``127.0.0.1`` if you are running FIREWHEEL on a remote server.

You should see a screen that is giving you the option to install the operating system.
Follow the on screen instructions through the completion of the installation.
You will eventually be asked to restart the VM.
Go ahead and do so.

.. _guest_agent:

****************************************
Adding the QEMU Guest Agent to the Image
****************************************

Now that you have an image with an operating system installed, we need to make it so that FIREWHEEL can communicate and orchestrate the configuration of the VM.
This is done through the :ref:`qemu-guest-agent` (QGA).
The QGA is a process that runs inside the VM and talks to the FIREWHEEL infrastructure through the virtual serial port that is added when the VM is launched.
We need to load the QGA into the VM and set it to be a service.

Installing the VirtIO Serial Port Driver on Windows
===================================================

As mentioned above, FIREWHEEL uses a serial port in order to orchestrate the configuration of VMs.
Windows VMs do not have the ability to use a ``VirtIO`` serial port by default, therefore the driver needs to be installed.
The latest ``virtio-win`` ISO file can be found via the `virtio-win-pkg-scipts GitHub page <https://github.com/virtio-win/virtio-win-pkg-scripts>`__.
This can be attached to the VM via a CDROM in the same way the operating system ISO was attached to the VM during building (see :ref:`booting_image` for more details).
These instructions follow the steps provided by `Redhat <https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/6/html/virtualization_host_configuration_and_guest_installation_guide/form-virtualization_host_configuration_and_guest_installation_guide-para_virtualized_drivers-mounting_the_image_with_virt_manager>`_ starting at ``Procedure 10.2``.
The steps are included below for completeness.

* Once the VM has booted with the ``VirtIO`` ISO attached, we need to get to the ``Device Manager``.
* This is accessed through the ``Computer Management`` window.
* You can get to the ``Computer Management`` window by selecting ``Start`` and then right clicking on ``Computer`` and selecting ``Manage`` from the menu that appears.
* On the left pane you should see ``Device Manager`` in the drop down below ``System Tools``, select ``Device Manager``.
* You should see a device called ``Other Devices``, expand that drop down arrow.
* Another device should appear below ``Other Devices`` that is labeled ``PCI Simple Communication Controller``.
* Right click ``PCI Simple Communication Controller`` and select ``Update Driver Software``.
* You will then see a pop-up window asking how to search for the driver software, select ``Browse my computer for driver software``.
* Click the ``Browse`` button and then navigate to ``virtio-win.iso`` that was attached as a CDROM.
* We need the ``vioserial`` driver that corresponds to the version of Windows that is being used.
* This will be a folder and then select ``OK``.
* Then select the ``Next`` button to install the ``vioserial`` driver.
* Once the installation has finished select ``Close``.

**************************
Moving the QGA into the VM
**************************

There are a couple ways to get the required QGA files into the VM.
Which method to use will depend on whether or not the VM is running a SSH server.

QGA Files for Linux
===================

The directions for building a statically compiled QGA can be found in :ref:`qga-driver`.
The ``qemu-ga-patched-static`` binary is the actual guest agent executable.
The ``qemu-guest-agent.service`` file defines a ``systemd`` service.
Most versions of Linux support ``systemd``, which makes it a good choice for turning the QGA into a service on the VM.

.. _qga_windows:

QGA File for Windows
====================

The QEMU Guest Agent has a MSI installer for Windows.
Therefore, if you are building a Windows machine, you only need to move that installer over to the VM using one of the methods listed below.
Instructions for building a modified QGA can be found in :ref:`qga-driver` and a link to download the latest unmodified ``qemu-ga.msi`` can be found via the `virtio-win-pkg-scipts GitHub page <https://github.com/virtio-win/virtio-win-pkg-scripts>`_.

Moving Files with SCP
=====================

If the VM has a SSH server running then you can simply SCP the files to the VM.
Assuming both the binary and ``systemd`` file are in the current directory on the physical host, the VM has an IP address of ``192.168.122.19``, and the VM has a username of ``ubuntu`` then the following command will send the files to the ``ubuntu`` user's home directory: ::

    $ scp qemu-ga-patched-static ubuntu@192.168.122.19:
    $ scp qemu-guest-agent.service ubuntu@192.168.122.19:

You can check the IP address of the VM by running ``ip address`` from within the VNC session.
Change the username above to whatever username was created during installation.

Moving Files over HTTP
======================

If the VM does not have a SSH server running (i.e. Windows or Linux Desktops), then the next best option for getting the files to the VM is to use a web server.
A Python web server can easily host the files on the physical host so that they can be accessed from within the VM.
Run the following command from directory where the binary and ``systemd`` files are located:

.. code-block:: bash

    $ python3 -m http.server 8000

This will create a web server on the physical host at port ``8000`` (which is the default port).
Feel free to change the port as desired.

From within the VM's VNC session you can now open a web browser and browse to the QGA files and download them.
The files should be available at ``http://192.168.122.1:8000``.

If a browser is not an option then you can use a tool like `wget <https://linux.die.net/man/1/wget>`__ or `curl <https://curl.se>`__ to download the files as well:

.. code-block:: bash

    $ wget http://192.168.122.1:8000/qemu-ga-patched-static
    $ wget http://192.168.122.1:8000/qemu-guest-agent.service

********************************
Configuring the QEMU Guest Agent
********************************

Configuring the QGA on Linux
============================

Now that the files are located on the VM, there are just a couple more steps before we're done.

#. First, move ``qemu-ga-patched-static`` to ``/usr/sbin``:

   .. code-block:: bash

        $ sudo mv qemu-ga-patched-static /usr/sbin

#. Make sure that the binary is executable:

   .. code-block:: bash

        $ sudo chmod +x /usr/sbin/qemu-ga-patched-static

#. Next, move ``qemu-guest-agent.service`` to ``/etc/systemd/system``.

   .. code-block:: bash

        $ sudo mv qemu-guest-agent.service  /etc/systemd/system

#. The QGA expects to be able to use a directory at ``/usr/local/var/run``.

   .. code-block:: bash

        $ sudo mkdir -p /usr/local/var/run

#. Finally, enable the QGA service:

   .. code-block:: bash

        $ sudo systemctl enable qemu-guest-agent.service

#. You can now shutdown the VM:

   .. code-block:: bash

        $ sudo poweroff

Configuring the QGA on Windows
==============================

Configuring the guest agent on Windows is generally easier than on Linux.
First, ensure that you have booted the Windows image with the QEMU arguments::

    -chardev socket,id=qga0,server,nowait,path=/tmp/ga.sock \
    -device virtio-serial \
    -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0 \

If you followed the instructions in the :ref:`booting_image` section, you will have already done this.
We have found that the QGA will not run correct if it was installed without these arguments.
Once you have started the image, simply run the MSI installer (see :ref:`qga_windows`) as an administrator and you are done.
Generally, the user that was created during the installation of a Windows image is a local administrator so if you are logged in as that user then you simply double click the installer to run it.
You can shutdown the VM.

.. _xz_image:

**********************
Packaging up the Image
**********************

It's a good idea to compress the image file before using it within FIREWHEEL.
If you are planning on following the steps in :ref:`optimizing_disk_size` then skip this step for now.
It will be revisited once those steps have been completed.
This can be done with the following command:

.. code-block:: bash

    $ xz -k -z ubuntu-18.10-server-amd64.qcow2

This will create a file called ``ubuntu-18.10-server-amd64.qcow2.xz``.
The ``-k`` flag tells ``xz`` to keep the original file after the compression is done.
If you do not want to keep the original file then omit the ``-k`` flag.
This file will be tied to a model component object.
That will be discussed in the next section.

.. note::

    FIREWHEEL will automatically detect and decompress images that are using tar or LZMA compression.
    That is, if your file uses LZMA compression (e.g. the `xz <https://linux.die.net/man/1/xz>`_ utility) or `tar <https://linux.die.net/man/1/tar>`_ compression (including tar with gzip), then it will automatically be decompressed by FIREWHEEL.
    See :ref:`images_object` for more details.
