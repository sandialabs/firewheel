.. _adb-driver:

Android Debug Bridge Driver
===========================

The `Android Debug Bridge (ADB) <https://developer.android.com/tools/adb>`_ driver enables the VM Resource Handler to communicate with Android guests.
It is selected using the VM Resource Handler engine name ``ADB``.

The ADB driver is intended for Android VMs launched through minimega's native ``android`` VM type.
It does not use the QEMU Guest Agent or a QGA socket.

Driver Selection
----------------

Android VM Resource Handler process configurations should use:

.. code-block:: json

   {
     "engine": "ADB",
     "adb_serial": "emulator-5554",
     "android_console_port": 5554,
     "android_adb_port": 5555,
     "require_root": true
   }

The ``adb_serial`` value is the primary identifier used by the driver. If it is
not provided, the driver can fall back to ``emulator-<android_console_port>``.

ADB, Console Ports, and Serial Names
------------------------------------

Android emulators normally use two sequential ports:

* an emulator console port, for example ``5554``;
* an ADB daemon port, typically ``5555``.

The ADB serial uses the console port:

.. code-block:: text

   emulator-5554

minimega is authoritative for the actual assigned port values.
If the requested port pair is unavailable, minimega may assign a different port pair.
FIREWHEEL should use the actual values reported by minimega before launching the VM Resource Handler.

Runtime Paths
-------------

The ADB driver uses Android-native FIREWHEEL runtime paths:

.. code-block:: text

   /data/local/tmp/firewheel/launch
   /data/local/tmp/firewheel/proc

Generated call scripts use:

.. code-block:: sh

   #!/system/bin/sh

This differs from QGA/Linux VMs, which traditionally use ``/var/launch`` and ``/bin/bash``.

Execution Model
---------------

The ADB driver executes VM resources by writing a small runner script under:

.. code-block:: text

   /data/local/tmp/firewheel/proc

The runner records:

* stdout
* stderr
* exit code
* a started marker

This avoids long-lived ADB stream parsing and provides reliable exit-code capture for Android VM resources.

Android Shell Limitations
-------------------------

Android guests should not be assumed to provide:

* ``/bin/bash``
* ``/bin/sh``
* Python
* systemd

VM resources intended for Android should generally use:

.. code-block:: sh

   #!/system/bin/sh

Android model components may provide optional Bash or Python runtimes, but these are not required by the ADB driver.

Root Access
-----------

The ADB driver can require root by setting ``require_root`` to ``true``.
This is the default for FIREWHEEL Android experiments that need to configure networking or system-level state.

If ``require_root`` is enabled, the Android image must support ``adb root``.

If ``require_root`` is false, the driver can connect to non-rooted devices, but VM resources that require privileged operations such as network configuration may fail.

File Transfer
-------------

The ADB driver uses ADB sync operations to push and pull files. File transfers are timestamp-filtered where possible using Android ``stat``/``toybox stat``.

Reboot Behavior
---------------

The ADB driver can reboot Android guests through ADB.
Runtime network state such as IP addresses, routes, policy rules, and firewall rules is generally lost on Android reboot.
Installed APKs typically persist across a normal Android reboot.

Android-specific reboot and runtime-state limitations are documented in the Android model component repository.
