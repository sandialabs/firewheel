.. _firewheel_configuration:

#######################
FIREWHEEL Configuration
#######################

While we recommend setting a few FIREWHEEL configuration options during installation (see :ref:`install-set-env-vars`).
There are numerous other options to set which are located in ``src/firewheel/firewheel.yaml``.

This section outlines how to change the configuration and of the available options.

*********************
Configuration Options
*********************

The main configuration options which must change are modified during installation with ``install.sh``.
Here are all configuration options which are available to be changed.

.. _config_ansible:

``ansible``
===========
This setting is a `YAML dictionary <https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html#yaml-basics>`_ which enables users to control cache settings which can be used to download unpackaged model component dependencies (e.g., VM resources, images, etc.).
Users are able to provide information expected by each Ansible cache method as defined in :ref:`mc_install_ansible`.

.. _config_attribute_defaults:

``attribute_defaults``
======================
This setting is a `YAML dictionary <https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html#yaml-basics>`_ which enables users to set a default model component if there is more than one which accomplishes the same :ref:`Attribute <attributes_object>`.
That is, if :ref:`model_components` ``mc.A`` and ``mc.B`` both `provides` the :ref:`Attribute <attributes_object>` ``hostname``, FIREWHEEL will be unable to automatically determine which Model Component should be selected.
To resolve this, the user can either add the Model Component on the command line or use this setting to enable FIREWHEEL to automatically assume the default Model Component, unless overwritten via the command line.
See :ref:`Dependency Management <dependency_attributes>` for more information.

.. table::

    +--------------------+--------------------------+-------------------------------------------------------------------------------------+
    |    Setting         |        Value             |                                     Description                                     |
    +====================+==========================+=====================================================================================+
    |``<Attribute Name>``|``<Model Component Name>``|The attribute for which FIREHWEEL should select the given Model Component by default.|
    +--------------------+--------------------------+-------------------------------------------------------------------------------------+

.. _config-cli:

``cli``
=======
These settings are used by FIREWHEEL's :ref:`cli`.

.. table::

    +-------------+----------+----------+---------------------------------------------------------------------------------------------------+
    |   Setting   |Value Type| Default  |                                           Description                                             |
    +=============+==========+==========+===================================================================================================+
    |``cache_dir``|string    |``fw_cli``|The folder name of the CLI Helper cache.                                                           |
    +-------------+----------+----------+---------------------------------------------------------------------------------------------------+
    |``root_dir`` |string    |``""``    |The path to the ``cache_dir``. If left empty, the ``system.default_output_dir`` value will be used.|
    +-------------+----------+----------+---------------------------------------------------------------------------------------------------+

.. _config-cluster:

``cluster``
===========
These settings control the :ref:`FIREWHEEL-cluster`.

.. table::

    +-----------+----------+-------+---------------------------------------------------------------------------------------------------------------------+
    |  Setting  |Value Type|Default|                                                     Description                                                     |
    +===========+==========+=======+=====================================================================================================================+
    |``compute``|list      |``[]`` |The list of IP address or hostname for :ref:`cluster-compute-nodes` in the :ref:`FIREWHEEL-cluster`.                 |
    +-----------+----------+-------+---------------------------------------------------------------------------------------------------------------------+
    |``control``|list      |``[]`` |A list with the **ONE** IP address or hostname for the :ref:`cluster-control-node` for your :ref:`FIREWHEEL-cluster`.|
    +-----------+----------+-------+---------------------------------------------------------------------------------------------------------------------+

.. _config-discovery:

``discovery``
=============

These settings are used for interaction between FIREWHEEL and `discovery <https://github.com/sandia-minimega/discovery>`_.

.. table::

    +---------------+----------+------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |    Setting    |Value Type|     Default      |                                                                                          Description                                                                                          |
    +===============+==========+==================+===============================================================================================================================================================================================+
    |``hostname``   |string    |``localhost``     |The hostname or IP address of the `discovery <https://github.com/sandia-minimega/discovery>`_ service.                                                                                         |
    +---------------+----------+------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``install_dir``|string    |``/opt/discovery``|The installation directory of `discovery <https://github.com/sandia-minimega/discovery>`_. This is used to locate the `discovery <https://github.com/sandia-minimega/discovery>`_ binary files.|
    +---------------+----------+------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``port``       |int       |``8080``          |The port number for the `discovery <https://github.com/sandia-minimega/discovery>`_ service.                                                                                                   |
    +---------------+----------+------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. _config-grpc:

``grpc``
========

These settings are used by FIREWHEEL's gRPC service.

.. table::

    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    |   Setting   |Value Type|  Default  |                                                                     Description                                                                      |
    +=============+==========+===========+======================================================================================================================================================+
    |``cache_dir``|string    |``fw_grpc``|The folder name of the gRPC database cache.                                                                                                           |
    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``db``       |string    |``prod``   |The name of the database to use. We use ``prod`` for production and ``test`` for running our test suite.                                              |
    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``hostname`` |string    |``""``     |The hostname or IP address of FIREWHEEL's gRPC service. This is typically the :ref:`cluster-control-node`.                                            |
    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``port``     |int       |``50051``  |The port number for FIREWHEEL's gRPC service.                                                                                                         |
    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``root_dir`` |string    |``""``     |The path to the ``cache_dir``. If left empty, the ``system.default_output_dir`` value will be used.                                                   |
    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``threads``  |int       |``2``      |The number of threads used for the gRPC service. If the cluster is larger, the number of threads should be increased to facilitate better performance.|
    +-------------+----------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------+

.. _config-logging:

``logging``
===========

These settings are used to manage FIREWHEEL's logging capabilities.


.. table::

    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |     Setting             |Value Type|      Default       |                                                           Description                                                           |
    +=========================+==========+====================+=================================================================================================================================+
    |``cli_log``              |string    |``cli.log``         |The name of the CLI log file. This file contains the responses for all CLI commands issued.                                      |
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |``discovery_log``        |string    |``discovery.log``   |The name of the discovery log file.                                                                                              |
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |``firewheel_log``        |string    |``firewheel.log``   |The name of the primary FIREWHEEL log file.                                                                                      |
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |``level``                |string    |``DEBUG``           |The logging level for FIREWHEEL. Valid values are found `here <https://docs.python.org/3/library/logging.html#logging-levels>`__.|
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |``minimega_log``         |string    |``minimega.log``    |The name of the minimega log file.                                                                                               |
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |.. _config-root_log_dir: |          |                    |                                                                                                                                 |
    |                         |          |                    |                                                                                                                                 |
    |``root_dir``             |string    |``""``              |The path to the log files. If left empty, the ``system.default_output_dir`` value will be used.                                  |
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+
    |.. _config-vmr_log_dir:  |          |                    |                                                                                                                                 |
    |                         |          |                    |                                                                                                                                 |
    |``vmr_log_dir``          |string    |``vm_resource_logs``|The folder name for VM Resource logs. The full path will be ``<root_dir>/<vmr_log_dir>``.                                        |
    +-------------------------+----------+--------------------+---------------------------------------------------------------------------------------------------------------------------------+

.. _config-minimega:

``minimega``
============

These settings are used for interaction between FIREWHEEL and `minimega <https://www.sandia.gov/minimega>`_.

.. table::

    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |        Setting         |Value Type|        Default        |                                                                                         Description                                                                                         |
    +========================+==========+=======================+=============================================================================================================================================================================================+
    |``base_dir``            |string    |``/tmp/minimega``      |minimega's ``MINIMEGA_DIR`` configuration option. This is where minimega stores all of its run time files.                                                                                   |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``control_bridge``      |string    |``mega_bridge``        |The bridge which is used by minimega to manage communication with the :ref:`FIREWHEEL-cluster`.                                                                                              |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``degree``              |int       |``1``                  |The minimega degree for the cluster. This specifies the number of other nodes minimega should try to connect to and should be equal to the number of nodes in your :ref:`FIREWHEEL-cluster`. |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``experiment_interface``|string    |``""``                 |The NIC for the current host for which will be used to connect to other :ref:`cluster-nodes`.                                                                                                |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``files_dir``           |string    |``/tmp/minimega/files``|minimega's ``filepath``  option, which is used in their `iomeshage capability <https://www.sandia.gov/minimega/using-minimega/>`_.                                                           |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``install_dir``         |string    |``""``                 |The installation  directory for minimega. This is set with ``install.sh`` and is typically ``/opt/minimega``.                                                                                |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``namespace``           |string    |``firewheel``          |The name of the minimega `namespace <https://sandia-minimega.github.io/#header_5.41>`_.                                                                                                      |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
    |``use_gre``             |boolean   |``false``              |minimega defaults to using VLANs to segment traffic between :ref:`cluster-nodes`, to use GRE tunnels instead of VLAns, set this to ``true``.                                                 |
    +------------------------+----------+-----------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. _config-python:

``python``
==========

These settings are used to specify the Python version, virtual environment, and executable to be used by FIREWHEEL.

.. table::

    +--------+----------+-------------+-------------------------------------------------------------------------------------------------------------------------------------------+
    |Setting |Value Type|Default      |                                                            Description                                                                    |
    +========+==========+=============+===========================================================================================================================================+
    |``bin`` |string    |``python3``  |The Python executable to use for running FIREWHEEL. This is set with ``install.sh`` and is typically just ``python3``.                     |
    +--------+----------+-------------+-------------------------------------------------------------------------------------------------------------------------------------------+
    |``venv``|string    |``""``       |The path to the virtual environment to use for running FIREWHEEL. This is set with ``install.sh`` and is typically ``/opt/firewheel/fwpy``.|
    +--------+----------+-------------+-------------------------------------------------------------------------------------------------------------------------------------------+

.. _config-ssh:

``ssh``
=======

These settings are used for SSH/SCP amongst nodes in the :ref:`FIREWHEEL-cluster`.

.. table::

    +--------+----------+--------+-----------------------------------------------------------------------------------------------------------------+
    |Setting |Value Type|Default |                                                   Description                                                   |
    +========+==========+========+=================================================================================================================+
    |``user``|string    |``null``|A username for SSH and SCP between :ref:`cluster-nodes`. This is only needed if it differs from the current user.|
    +--------+----------+--------+-----------------------------------------------------------------------------------------------------------------+

.. _config-system:

``system``
==========

These settings are used for system-level interactions.

.. table::

    +----------------------+----------+------------------+----------------------------------------------------------------------------------------------------------+
    |      Setting         |Value Type|     Default      |                                                               Description                                |
    +======================+==========+==================+==========================================================================================================+
    |``default_group``     |string    |``minimega``      |The user group for FIREWHEEL.                                                                             |
    +----------------------+----------+------------------+----------------------------------------------------------------------------------------------------------+
    |``default_output_dir``|string    |``/tmp/firewheel``|The default directory for FIREWHEEL outputs (e.g. logs, cached data, etc.).                               |
    +----------------------+----------+------------------+----------------------------------------------------------------------------------------------------------+
    |``firewheel_root_dir``|string    |``/opt/firewheel``|For users installing FIREWHEEL from source code, this is the root directory of the source code repository.|
    +----------------------+----------+------------------+----------------------------------------------------------------------------------------------------------+
    |``umask``             |int       |``0o0``           |The default `umask <https://en.wikipedia.org/wiki/Umask>`_ settings, if any.                              |
    +----------------------+----------+------------------+----------------------------------------------------------------------------------------------------------+

.. _config-test:

``test``
========

These settings are used for testing FIREWHEEL without interfering with the production settings.

.. table::

    +-----------------------------------+----------+--------------------+-----------------------------------------------------------------------------------------------------------------------------+
    |              Setting              |Value Type|      Default       |                                        Description                                                                          |
    +===================================+==========+====================+=============================================================================================================================+
    |``grpc_db``                        |string    |``test``            |The name of the gRPC database to use. We use ``test`` for running our test suite.                                            |
    +-----------------------------------+----------+--------------------+-----------------------------------------------------------------------------------------------------------------------------+
    |``image_db``                       |string    |``testImageStoreDb``|The name of the test :class:`ImageStore <firewheel.control.image_store.ImageStore>` database.                                |
    +-----------------------------------+----------+--------------------+-----------------------------------------------------------------------------------------------------------------------------+
    |``schedule_test_database``         |string    |``testScheduleDB``  |The name of the test :class:`ScheduleDb <firewheel.vm_resource_manager.schedule_db.ScheduleDb>` database.                    |
    +-----------------------------------+----------+--------------------+-----------------------------------------------------------------------------------------------------------------------------+
    |``vm_resource_store_test_database``|string    |``testVmResourceDB``|The name of the test :class:`VmResourceStore <firewheel.vm_resource_manager.vm_resource_store.VmResourceStore>` database.    |
    +-----------------------------------+----------+--------------------+-----------------------------------------------------------------------------------------------------------------------------+
    |``vmmapping_test_database``        |string    |``testVmMappingDB`` |The name of the test :class:`VMMapping <firewheel.vm_resource_manager.vm_mapping.VMMapping>` database.                       |
    +-----------------------------------+----------+--------------------+-----------------------------------------------------------------------------------------------------------------------------+

.. _config-vrm:

``vm_resource_manager``
=======================

These settings are used with FIREWHEEL's :ref:`vm-resource-manager`.

.. table::

    +-------------------------------+----------+-----------------+-----------------------------------------------------------------------------------------------------------+
    |            Setting            |Value Type|     Default     |                                                Description                                                |
    +===============================+==========+=================+===========================================================================================================+
    |.. _config-default_state:      |          |                 |                                                                                                           |
    |                               |          |                 |                                                                                                           |
    |``default_state``              |string    |``uninitialized``|The default *state* of VMs after they are launched.                                                        |
    +-------------------------------+----------+-----------------+-----------------------------------------------------------------------------------------------------------+
    |.. _config-exp_start:          |          |                 |                                                                                                           |
    |                               |          |                 |                                                                                                           |
    |``experiment_start_buffer_sec``|int       |``60``           |The number of seconds after all experiment VMs have been configured to start :ref:`schedule-positive-time`.|
    +-------------------------------+----------+-----------------+-----------------------------------------------------------------------------------------------------------+

***************************
Changing FIREWHEEL Settings
***************************
To get and set configuration values, there are two commands: :ref:`command_config_get` and :ref:`command_config_set`.

The :ref:`command_config_set` command enables replacing the entire configuration file or modifying a given setting.

Additionally, :ref:`command_config_get` command enables retrieving the entire configuration file or only a given setting.

When updating or retrieving a single setting, a nested option is indicated with a period separating the keys.
For example, to set the value for the config key ``{'logging':{'level':'DEBUG'}}``, you can use the command::

    firewheel config set -s logging.level INFO

To get the value of ``{'cluster':{'compute':[]}}``, you can use the command::

    firewheel config get cluster.compute

Please see :ref:`command_config_get` and :ref:`command_config_set` for more details.

**************************
Changing minimega Settings
**************************
Some minimega settings are used by FIREWHEEL (e.g. those used in :ref:`minimega configuration <config-minimega>` section above).
However, while FIREWHEEL uses these settings, users have to modify both the underlying minimega settings  *and* the corresponding FIREWHEEL configuration.
Therefore, if you would like to modify where minimega caches files then the minimega configuration file (see :ref:`configuring-minimega`) setting ``MM_FILEPATH`` should be updated then the corresponding FIREWHEEL setting ``minimega.files_dir`` should be updated.
Once both settings have been updated, a simple :ref:`firewheel restart hard <helper_restart_hard>` will help the settings take effect.


*********************
Default Configuration
*********************

The file ``src/firewheel/firewheel.yaml`` contains the settings for FIREWHEEL.
The default file is shown below.

.. literalinclude:: ../../../src/firewheel/firewheel.yaml
    :language: yaml
    :caption: `firewheel.yaml`
    :name: firewheel_yaml
