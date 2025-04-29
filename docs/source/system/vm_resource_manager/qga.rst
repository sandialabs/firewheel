.. _qemu-guest-agent:

****************
QEMU Guest Agent
****************

The `QEMU Guest Agent (QGA) <https://wiki.qemu.org/Features/GuestAgent>`_ is a binary file located within a VM which receives QEMU Machine Protocol (QMP) messages and can be used to perform actions within the virtual machine.
The QGA is the primary way in which the :ref:`vm-resource-handler` communicates with VMs and enables the completion of VM resources.
Therefore, in order for a VM image to be "FIREWHEEL-compatible" the QGA should be installed on the system and set to run as a service on system start.

When a VM is launched, a virtual serial port that is added which enables the QGA to communicate to FIREWHEEL via the :py:class:`QemuGuestAgentDriver <firewheel.vm_resource_manager.drivers.qemu_guest_agent_driver.QemuGuestAgentDriver>`, which then works with the :ref:`vm-resource-handler` for scheduling and executing VMRs within the VM.

.. seealso::

    For more information on creating a :py:class:`VM Resource Handler <firewheel.vm_resource_manager.vm_resource_handler.VMResourceHandler>`-compatible image see the :ref:`image-creation-tutorial`.

.. _qga-driver:

QGA Modifications
=================

While it is possible to use the existing QGA code to work with FIREWHEEL, we have provided some small changes which enhance the behavior for Emulytics environments.
Namely, Python, by default, aggressively buffers ``stdout``, so printed output doesn't show up immediately on guest agent outputs unless explicitly flushed.
Therefore, we provide a small patch which changes the behavior of the QEMU Guest Agent such that output from executed binaries is not simply buffered until exit, but will be returned on each status request.

.. toctree::
   :hidden:

   qga_patch

Patching QEMU
-------------
Before compiling the QGA for any one VM, it needs to be patched.
To do this, you can clone the QEMU code, checkout the correct version (i.e. the version for which the patch was created), and apply the patch.
The code below will show you how to do this.
We saved the :ref:`qemu-patch-file` as ``0001-Allow-exceed-processes-to-ret-data-on-every-status.patch``.

.. code-block:: bash

    git clone https://github.com/qemu/qemu.git
    cd qemu
    git checkout v5.0.0
    patch -p1 < ../0001-Allow-exceed-processes-to-ret-data-on-every-status.patch

.. toctree::
   :hidden:

   qga_patch


Building the QGA for Linux
^^^^^^^^^^^^^^^^^^^^^^^^^^
#. Install the following prerequisite packages when building the QEMU Guest Agent on an Ubuntu system.
   Other packages might be required.
   We refer users to the official QEMU documentation for more details: https://wiki.qemu.org/Hosts/Linux#Building_QEMU_for_Linux.

   .. code-block:: bash

        sudo apt-get install -y pkgconf glib-2.0 libglib2.0-dev libsdl1.2-dev libaio-dev libcap-dev gcc libattr1-dev libpixman-1-dev make libffi-dev


#. Configure the system with the following parameters:

   .. code-block:: bash

        ./configure --target-list="x86_64-softmmu" --static --enable-guest-agent


#. Finally, build the binary:

   .. code-block:: bash

        make qemu-ga -j


#. The binary is located at ``./qemu-ga``.
   We recommend renaming it to ``qemu-ga-patched-static`` as a reminder that this binary has been statically compiled and patched.

   .. code-block:: bash

        mv qemu-ga qemu-ga-patched-static


Building the QGA for Windows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Windows installer for the QEMU Guest Agent can be built using `Cygwin <https://www.cygwin.com/>`__.

#.  Download `Cygwin <https://www.cygwin.com/>`__.
#.  Install Cygwin and when prompted to install packages, select the following::

        mingw64-x86_64-atk1.0
        mingw64-x86_64-atkmm1.6
        mingw64-x86_64-babl0.1
        mingw64-x86_64-binutils
        mingw64-x86_64-bzip2
        mingw64-x86_64-cairo
        mingw64-x86_64-cairomm1.0
        mingw64-x86_64-celt051
        mingw64-x86_64-crypt
        mingw64-x86_64-expat
        mingw64-x86_64-flac
        mingw64-x86_64-fontconfig
        mingw64-x86_64-freeglut
        mingw64-x86_64-freetype2
        mingw64-x86_64-fribidi
        mingw64-x86_64-gc
        mingw64-x86_64-gcc-core
        mingw64-x86_64-gcc-g++
        mingw64-x86_64-gdk-pixbuf2.0
        mingw64-x86_64-gdl3
        mingw64-x86_64-gegl0.2
        mingw64-x86_64-gettext
        mingw64-x86_64-glib2.0
        mingw64-x86_64-glib2.0-networking
        mingw64-x86_64-glibmm2.4
        mingw64-x86_64-gmp
        mingw64-x86_64-gnutls
        mingw64-x86_64-gsettings-desktop-schemas
        mingw64-x86_64-gstreamer1.0
        mingw64-x86_64-gstreamer1.0-plugins-base
        mingw64-x86_64-gtk3
        mingw64-x86_64-gtkmm3.0
        mingw64-x86_64-harfbuzz
        mingw64-x86_64-headers
        mingw64-x86_64-icu
        mingw64-x86_64-ilmbase
        mingw64-x86_64-jasper
        mingw64-x86_64-jbigkit
        mingw64-x86_64-libcdio
        mingw64-x86_64-libcdio-paranoia
        mingw64-x86_64-libcroco0.6
        mingw64-x86_64-libepoxy
        mingw64-x86_64-libffi
        mingw64-x86_64-libgcrypt
        mingw64-x86_64-libgnurx
        mingw64-x86_64-libgpg-error
        mingw64-x86_64-libjpeg-turbo
        mingw64-x86_64-libmodplug
        mingw64-x86_64-libmpc
        mingw64-x86_64-libogg
        mingw64-x86_64-libpng
        mingw64-x86_64-libproxy
        mingw64-x86_64-librsvg2
        mingw64-x86_64-libsigc++2.0
        mingw64-x86_64-libssh2
        mingw64-x86_64-libtasn1
        mingw64-x86_64-libtheora
        mingw64-x86_64-libusb1.0
        mingw64-x86_64-libvorbis
        mingw64-x86_64-libwebp
        mingw64-x86_64-libxml++2.6
        mingw64-x86_64-libxml2
        mingw64-x86_64-libxslt
        mingw64-x86_64-libzip
        mingw64-x86_64-lzo2
        mingw64-x86_64-mpfr
        mingw64-x86_64-ncurses
        mingw64-x86_64-nettle
        mingw64-x86_64-openexr
        mingw64-x86_64-openjpeg
        mingw64-x86_64-openssl
        mingw64-x86_64-opus
        mingw64-x86_64-orc0.4
        mingw64-x86_64-p11-kit
        mingw64-x86_64-pango1.0
        mingw64-x86_64-pangomm1.4
        mingw64-x86_64-pcre
        mingw64-x86_64-pixman
        mingw64-x86_64-pkg-config
        mingw64-x86_64-pthreads
        mingw64-x86_64-readline
        mingw64-x86_64-runtime
        mingw64-x86_64-spice-glib2.0
        mingw64-x86_64-spice-gtk3.0
        mingw64-x86_64-tiff
        mingw64-x86_64-usbredir
        mingw64-x86_64-win-iconv
        mingw64-x86_64-windows-default-manifest
        mingw64-x86_64-winpthreads
        mingw64-x86_64-xz
        mingw64-x86_64-zlib
        girepository-msi0-0.95-1
        libmsi-devel-0.95-1
        libmsi0-0.95-1
        msitools-0.95-1
        vala-msi0-0.95-1
        wixl-0.95-1
        gcab-0.7-1
        girepository-gcab1.0-0.7-1
        libgcab-devel-0.7-1
        libgcab-doc-0.7-1
        libgcab1.0_0-0.7-1
        vala-gcab1.0-0.7-1

#. Other necessary packages that need to be installed can be searched for in Cygwin.
   These include::

        make
        git
        bison
        flex
        vim

#. Install the MS Volume Shadow Copy Service (VSS) SDK. The link to download it is here: https://learn.microsoft.com/en-us/windows/win32/vss/volume-shadow-copy-service-portal.

#. Configure the build with the following (**make sure to update the paths with your username**):

   .. code-block:: bash

        ./configure --target-list="x86_64-softmmu" --cc=x86_64-w64-mingw32-gcc --cxx=x86_64-w64-mingw32-g++ --host-cc=/usr/bin/gcc --cross-prefix=x86_64-w64-mingw32- --prefix="/home/username/Documents/Qemu-windows" --with-confsuffix=/Bios --docdir="/home/username/Documents/Qemu-windows/Doc" --disable-sdl --enable-gtk --with-gtkabi=3.0 --disable-libusb --enable-guest-agent --enable-guest-agent-msi --with-vss-sdk="C:\Program Files (x86)\Microsoft\VSSSDK72" --disable-werror --disable-strip $*

#. Finally, build the guest agent:

   .. code-block:: bash

        make -j


#. This will result in the creation of a MSI installer as well as an executable.
   To install the guest agent, copy the MSI installer to the VM and run it.

.. note::

    Users that would like to install an unmodified QGA on Windows can find a link to download the latest ``qemu-ga.msi`` via the `virtio-win-pkg-scipts GitHub page <https://github.com/virtio-win/virtio-win-pkg-scripts>`_.

Running QGA as a Service
========================
In this section, we have provided several methods for running the QGA as a service.
We assume that the QGA binary was renamed to ``qemu-ga-patched-static``.

``systemd``
-----------
You can save the following file as ``qemu-guest-agent.service``.

.. code-block:: text

    [Unit]
    Description=Qemu Guest Agent

    [Service]
    Type=simple
    Restart=always
    RestartSec=5
    ExecStart=/usr/sbin/qemu-ga-patched-static
    LimitNOFILE=102400

    [Install]
    WantedBy=multi-user.target

``sysvinit``
------------
You can save the following file as ``qemu-guest-agent``.

.. code-block:: bash

    #!/bin/bash

    case "$1" in
    start)
        /usr/sbin/qemu-ga-patched-static &
        echo $!>/usr/local/var/run/qga.pid
        ;;
    stop)
        kill `cat /usr/local/var/run/qga.pid`
        rm /usr/local/var/run/qga.pid
        ;;
    restart)
        $0 stop
        $0 start
        ;;
    status)
        if [ -e /usr/local/var/run/qga.pid ]; then
            echo qemu-guest-agent is running, pid=`cat /usr/local/var/run/qga.pid`
        else
            echo qemu-guest-agent is NOT running
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
    esac

    exit 0

``upstart``
-----------
You can save the following file as ``qemu-guest-agent``.

.. code-block:: text

    description "Qemu Guest Agent"
    author "FIREWHEEL Developers"
    start on runlevel [2345]

    respawn

    exec /usr/sbin/qemu-ga-patched-static
