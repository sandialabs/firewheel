.. _android-adb-tutorial:

*******************
Android Experiments
*******************

This tutorial walks through a small Android experiment in FIREWHEEL. We will
launch a `Pixel 9a <https://store.google.com/product/pixel_9a_specs>`_ emulator, install the `Kiwix <https://kiwix.org>`_ Android APK, load a subset of Wikipedia data onto the phone, automate the app with `Maestro <https://maestro.dev>`_, and collect application data for inspection after the experiment.

`Kiwix <https://kiwix.org>`_ is a useful tutorial target because it can work with offline content. Once
the APK and saved resources are staged, the experiment does not need external
network access for the application workflow.
The goal is to learn the Android/FIREWHEEL workflow, not to make a specific claim about Kiwix.

**Prerequisites**:

* FIREWHEEL is installed.
* The Android model component INSTALL steps have completed successfully.
* The FIREWHEEL node can download the Kiwix APK and ZIM file, or those files are otherwise accessible.
* Optional: If desiring to use manual interaction, `scrcpy <https://github.com/Genymobile/scrcpy>`_ is required.


.. toctree::
    :maxdepth: 2

    android_app_setup
    android_app_automation
    android_app_analysis
