.. _manifest_examples:

Example MANIFEST Files
----------------------

The following ``MANIFEST`` file is for the ``ubuntu1604`` model component.

.. code-block:: yaml

    name: linux.ubuntu1604
    attributes:
        depends: []
        provides: []
        precedes: []
    model_components:
        depends:
            - linux.ubuntu
        precedes: []
    images:
        - paths:
            - "images/ubuntu-16.04.4-server-amd64.qcow2.xz"
        architecture: x86_64
        - paths:
            - "images/ubuntu-16.04.4-desktop-amd64.qcow2.xz"
        architecture: x86_64
    model_component_objects: model_component_objects.py

The following ``MANIFEST`` file is for a model component that creates the ``ACME`` topology.

.. code-block:: yaml

    name: acme.topology
    attributes:
        depends:
            - graph
        provides:
            - topology
            - acme_topology
        precedes: []
    model_components:
        depends:
            - base_objects
            - vyos.helium118
            - linux.ubuntu1604
        precedes: []

    plugin: plugin.py

The following ``MANIFEST`` file is for a model component that provides the ``SetHostname`` plugin.

.. code-block:: yaml

    name: acme.set_hostname
    attributes:
        depends:
            - acme_topology
        provides:
            - hostnames
    model_components:
        depends:
            - linux.ubuntu1604
        precedes: []
    plugin: plugin.py
    vm_resources:
        - set_hostname.py
