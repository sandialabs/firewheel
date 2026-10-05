.. _android-app-setup:

******************************
Creating an Android Experiment
******************************

In this section, we will create a FIREWHEEL model component that launches one
Android Pixel 9a emulator, installs the Kiwix Android APK, and stages an offline
Wikipedia ZIM file on the Android device.

We will launch this initial version once to verify that the APK and ZIM file are
available before adding Maestro automation.

Create the Model Component
==========================

Create a new model component named ``tutorials.android_app_analysis``:

.. code-block:: bash

    firewheel mc generate --non-interactive \
      --name tutorials.android_app_analysis \
      --location tutorials/android_app_analysis \
      --attribute_depends graph \
      --attribute_provides topology \
      --model_component_depends base_objects android.base_objects android.pixel9a android.maestro \
      --plugin plugin.py \
      --vm_resource "vm_resources/**"

This creates the model component skeleton with the dependencies and VM resource
pattern needed for this tutorial.

The generated ``MANIFEST`` should look like this:

.. code-block:: yaml
    :caption: MANIFEST

    attributes:
      depends:
      - graph
      precedes: []
      provides:
      - topology
    model_components:
      depends:
      - base_objects
      - android.base_objects
      - android.pixel9a
      - android.maestro
      precedes: []
    name: tutorials.android_app_analysis
    plugin: plugin.py
    vm_resources:
    - vm_resources/**

.. note::
    The ``android.maestro`` dependency is included now because we will add `Maestro <https://maestro.dev>`_ automation in the next section.

Prepare the APK and ZIM Resources
=================================

Create the model component's VM resource directory:

.. code-block:: bash

    mkdir -p tutorials/android_app_analysis/vm_resources

Download the version-pinned Kiwix Android APK:

.. code-block:: bash

    cd tutorials/android_app_analysis

    wget https://mirror.download.kiwix.org/release/kiwix-android/org.kiwix.kiwixmobile.standalone-v3.14.1.apk \
      -O vm_resources/org.kiwix.kiwixmobile.standalone.apk

    echo "353e84ccda154802ed6841ad46c3140b9256c147836578817d5da8321b181ba0  vm_resources/org.kiwix.kiwixmobile.standalone.apk" \
      | sha256sum -c -

Download the offline Wikipedia computer ZIM file:

.. code-block:: bash

    wget https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en_computer_nopic_2026-06.zim \
      -O vm_resources/wikipedia_en_computer_nopic_2026-06.zim

    echo "7272620e85e98cbf45a23d1ccbb4a8d4fedc02602b3de6071e0492de6d308170  vm_resources/wikipedia_en_computer_nopic_2026-06.zim" \
      | sha256sum -c -

.. note::

    For improving the reusability and shareability of model components, users should generally use a :ref:`mc_install` rather than an ad hoc download.

Create the Initial Plugin
=========================

Modify the generated ``plugin.py`` to look like:

.. code-block:: python
    :caption: plugin.py

    from android.pixel9a import AndroidPixel9a

    from firewheel.control.experiment_graph import Vertex, AbstractPlugin


    class Plugin(AbstractPlugin):
        """
        Android application analysis tutorial topology.

        This initial version launches one Android Pixel 9a emulator, installs
        the Kiwix APK, and stages an offline ZIM file.
        """

        def run(self):
            """
            Build the initial Android application analysis experiment.
            """
            phone = Vertex(self.g, name="android-phone")
            phone.decorate(AndroidPixel9a)

            # Installing the Kiwix app
            phone.install_apk(
                start_time=-50,
                filenames="org.kiwix.kiwixmobile.standalone.apk",
            )

            # Ensure the directories are available
            phone.run_executable(
                -40,
                "/system/bin/mkdir",
                ["-p", "/sdcard/Download/Kiwix"],
                vm_resource=False,
            )

            # Copy the offline Wikipedia ZIM file to shared storage.
            phone.drop_file(
                -30,
                "/sdcard/Download/Kiwix/wikipedia_en_computer_nopic_2026-06.zim",
                "wikipedia_en_computer_nopic_2026-06.zim",
            )

This first version:

1. Creates a Pixel 9a Android VM named ``android-phone``;
2. Installs ``org.kiwix.kiwixmobile.standalone.apk``;
3. Copies ``wikipedia_en_computer_nopic_2026-06.zim`` to ``/sdcard/Download/Kiwix/`` on the Android device.

Launch and Verify the Initial Experiment
========================================

Launch the experiment:

.. code-block:: bash

    firewheel experiment -r tutorials.android_app_analysis minimega.launch

Wait for the Android VM to boot and for the VM Resource Handler to configure the
device. The Android emulator can take a few minutes to become ready. You can use
:ref:`helper_vm_list` or :ref:`helper_vm_mix` to monitor experiment state.

Check the Android VM from minimega:

.. code-block:: bash

    minimega -e ".columns name,type,state,android_console_port,android_adb_port,android_serial vm info"

The output should look similar to:

.. code-block:: text

    host      | name          | type    | state   | android_console_port | android_adb_port | android_serial
    fw-server | android-phone | android | RUNNING | 5554                 | 5555             | emulator-5554

.. note::

   If your minimega instance is not using the default base directory, include
   the ``-base`` option. For example:

   .. code-block:: bash

      minimega -base /scratch/minimega -e ".columns name,type,state,android_console_port,android_adb_port,android_serial vm info"

Identify the runtime ADB serial:

.. code-block:: bash

    adb devices

Then verify that Kiwix is installed:

.. code-block:: bash

    adb -s emulator-5554 shell pm list packages | grep kiwix

Expected output:

.. code-block:: text

    package:org.kiwix.kiwixmobile.standalone

Verify that the ZIM file was copied to the device:

.. code-block:: bash

    adb -s emulator-5554 shell ls -lh /sdcard/Download/Kiwix

Expected output should look similar to:

.. code-block:: text

    total 411K
    -rw-rw---- 1 u0_a205 media_rw 411M 2026-08-11 15:30 wikipedia_en_computer_nopic_2026-06.zim

If your ADB serial is not ``emulator-5554``, replace it with the serial reported by ``adb devices``.

You can also check the VM resource log:

.. code-block:: bash

    tail -n 50 /scratch/firewheel/vm_resource_logs/android-phone.log

At this point, the Android device is running, the `Kiwix <https://kiwix.org>`_ APK is installed, and
the offline ZIM file is staged. Next we will add `Maestro <https://maestro.dev>`_ automation.
