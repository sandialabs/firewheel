.. _model_components:

Model Component Specification
=============================

Model components (MCs) are the building blocks of a FIREWHEEL experiment.
Essentially they are folders within :ref:`repositories <repositories>`, which may contain code, VM images, and other resources.
A FIREWHEEL experiment is constructed by informing FIREWHEEL which model components define the network topology and any actions to be taken, and how to instantiate the experiment (typically via minimega).
A model component's folder must contain metadata that identifies it to FIREWHEEL as a model component, by declaring its name, contents, dependencies, and what it provides that other MCs could then depend on being able to use.

Model components provide a place to colocate all the new files required to accomplish a specific objective.
A model component's function, or purpose (as defined by it's developer), can be anything that an experiment might need. For instance, they can provide:

    * Functions for constructing an experiment network's topology
    * Definitions of vertex and edge types that can then be included in an experiment
    * Configuration scripts designed for individual VMs or whole classes of VMs
    * Executable code for performing experiment-related actions on the network at a given time
    * Scheduling instructions for when to execute actions on designated VMs in an experiment
    * A launcher for a FIREWHEEL experiment composed of other model components
    * Any combination of these and many other possibilities

Simply, a model component is a single place where code and data related to the model component's purpose can be found, along with metadata that allows FIREWHEEL to locate its dependencies, match what it provides to other model components' needs, and enforce certain constraints.

What's in a Model Component?
----------------------------

A model component is pretty flexible, and it's folder can include many types of files.
The different kinds of files that can be present, and that provide the model component's functionality, include *plugins*, *VM resources*, *model component objects*, and *images*.
Another file, called the ``MANIFEST`` file, contains the metadata that describes a model component to FIREWHEEL, and this is the only file that **must** be present in a model component's folder.
Each of these file types will be explained in sections that follow.
In addition to the files, it's highly recommended and encouraged (though optional), that a model component's folder contain either a ``README.rst`` or a ``README.md``.
This file should contain RST (or Markdown) formatted documentation about the model component (i.e. what it is and how to use it).
Additionally, this file will automatically be generated if the :ref:`helper_mc_generate` CLI Helper is used to create the model component skeleton.

Lastly, Model Components may sometimes require downloading data (e.g. VM Resources) from the Internet.
To facilitate this, developers should add an ``INSTALL`` file, which enables other users to automatically download or configure any external resources.
More information about this file can be found in :ref:`mc_install`.

.. note::

    FIREWHEEL provides a CLI command to generate a skeleton of a model component called :ref:`helper_mc_generate`.
    In general most users will create a new model component by running this Helper (i.e. ``firewheel mc generate``).


.. _manifest_file:

The MANIFEST File
-----------------

Every model component has a ``MANIFEST`` that describes it to FIREWHEEL, and a model component's ``MANIFEST`` is contained in a file, appropriately named ``MANIFEST``, that's located in the model component's folder. A model component's ``MANIFEST`` consists of YAML formatted data (the model component's metadata) that specifies to FIREWHEEL:

    * The unique *name* of the model component
    * The types of *attributes* the model component *depends*, *provides*, and *precedes*
    * The names of other *model components* it explicitly *depends* on and *precedes*
    * The types and names of *files* (either images or VM resources) contained within it.

A ``MANIFEST`` file **must be included** in a model component's folder in order for FIREWHEEL to recognize the folder as a model component.

Each model component's ``MANIFEST`` contains at least three elements: a ``name`` field, an ``attributes`` object, and a ``model_components`` object. Other, optional elements (fields and objects) that may be included in the ``MANIFEST`` are: ``plugin``, ``vm_resources``, ``model_component_objects``, and ``images``.

.. _yaml:

A Note About YAML
*****************

While YAML (https://yaml.org/) is a human-readable data-serialization language, FIREWHEEL only uses it to make MANIFEST files more human-readable.
YAML is a superset of JSON, making any [#]_ JSON MANIFEST files valid. There are several benefits for using YAML over JSON:

1. It is difficult to write valid JSON manually. For users that will be developing new model components
   without using the MC generation tool, JSON has a more complex syntax. Editing JSON MANIFEST files has
   a similar issue. These challenges can be alleviated using the more human-readable (and human writable) YAML.
2. YAML works with version control systems such as Git better than JSON does because it does not require commas
   to separate items in arrays and lists (https://en.wikipedia.org/wiki/YAML#Comparison_with_JSON).
3. YAML is less verbose than JSON. It does not require strings to be in quotation marks and does not require
   brackets or curly braces around objects. This saves some development time with manual MANIFEST editing.

Here are a few YAML examples:

**Creating a list**

.. code-block:: yaml

    vm_resources: [vmr1.sh, vmr2.py]
    "vm_resources": ["vmr1.sh", vmr2.py]
    vm_resources:
        - vmr1.sh
        - "vmr2.py"

**Creating a dictionary**

.. code-block:: yaml

    attributes: {depends: [], provides: [], precedes: []}
    "attributes": {
        depends: [],
        provides: [],
        precedes: []
    }
    attributes:
        depends: []
        provides: []
        precedes: []

**Creating a string**

.. code-block:: yaml

    name: "test.mc"
    name: test.mc

.. [#] Tabs are NOT valid in YAML, but are valid JSON. See https://yaml.org/faq.html for more details. You should avoid using tabs when creating MANIFEST files.

.. _name_field:

The Name field
^^^^^^^^^^^^^^

The ``name`` field's value can be any valid string, but needs to be unique among all model components contained in all repositories collectively available on a :ref:`cluster-control-node`.
The ``name`` of a model component does *not* need to be the same as the name of it's folder.
A model component's ``name`` can be used by model component developers to refer to it when they need to explicitly depend on it in their model component's ``MANIFEST`` (see the :ref:`Model Components object <model_components_object>` for more details).

It takes the following form:

.. code-block:: yaml

    name: <model_component_name>

A common naming convention is ``<repository>.<purpose name>``, e.g.:

.. code-block:: yaml

    name: acme.topology

In this example, the model component is named ``acme.topology`` because it is part of the ``acme`` tutorial and it does the primary construction of the ``acme`` network ``topology``.
While this naming convention isn't enforced by FIREWHEEL, it's a good idea to use it to avoid name collisions amongst model components across repositories.

.. _attributes_object:

The Attributes Object
^^^^^^^^^^^^^^^^^^^^^
Model component attributes can be thought of as commodities which can be provided by the model component and depended on or precede other MCs.
The ``attributes`` object in a ``MANIFEST`` specifies any *attributes* a model component ``provides`` to other model components, any *attributes*  it ``depends`` on other model components to provide to it, and any *attributes* which it ``precedes`` and must be resolved after completion.
Declaring that a model component ``depends`` on or *precedes* an *attribute* will generate a dependency between it and a model component that ``provides`` that *attribute*.
However, unlike depending on another model component explicitly (see the :ref:`Model Components object <model_components_object>` for details), declaring that a model component ``depends`` on a *attribute* is laissez-faire with regard to which specific model component will ``provide`` the *attribute* at run time.

The ``attributes`` object contains three fields, ``depends``, ``provides``, and ``precedes``, each expecting an array of strings for their values.
Each field's value array can contain zero or more **attribute labels**.
In the ``depends`` field's value array, **attribute labels** specify which  *attributes* (if any) that a model component expects will be provided to it by some other model component at run time, without caring in any way which model component provides the *attribute* to it.
In the ``provides`` field's value array, **attribute labels** declare the *types* of *attributes* (if any) that a model component produces for others to consume.
In the ``precedes`` field's value array, **attribute labels** specify which  *attributes* (if any) that are required to be provided by a model component that runs **after** the current MC completes execution.

Functionally, **attribute labels** are used by FIREWHEEL to create relationships amongst model components in an experiment.
This information is used at run time, along with the values in the :ref:`Model Components object <model_components_object>` and the ordering of model components listed on the command line, to create a dependency tree representing the interdependencies amongst all of the model components required to run any given FIREWHEEL experiment, across all available repositories.
See the section on :ref:`dependency management <dependency_attributes>` for more information on how and when to use **attribute labels**.

The ``attributes`` object is *required* to be present in a ``MANIFEST``, but its ``depends``, ``provides`` and/or ``precedes`` fields' value arrays can be empty.

It takes the following form:

.. code-block:: yaml

    attributes:
        depends: []
        provides: []
        precedes: []

For example, the first model component in an experiment to begin creating the experiment's network topology will need to ``depend`` on the ``graph`` *attribute* (since it will need to add vertices and edges to it) and possibly it ``provides`` a ``topology`` *attribute* to other model components in the experiment, e.g.:

.. code-block:: yaml

    attributes:
        depends:
            - graph
        provides:
            - topology
        precedes: []

Now, if there is another model component that has the purpose of modifying vertices in a topology in some way (e.g. by assigning ``hostnames`` to each one), then its ``attributes`` object would declare that that it ``depends`` on having a ``topology`` provided to it by another model component, and also that it ``provides`` something (e.g. ``hostnames``) that other model components can depend on having been provided by it.
Therefore, a model component that sets the ``hostnames`` for each vertex in a ``topology``, thus providing a modified topology where each vertex has a unique hostname assigned to it, would have an ``attributes`` object that resembles the following:

.. code-block:: yaml

    attributes:
        depends:
            - topology
        provides:
            - hostnames
        precedes: []

.. note::

    **Attribute labels** in ``provides`` fields' value arrays are *made up* by the developers of the various model components provide *attributes*. Therefore, if you create a model component that provides something, it's up to you to determine the **attribute labels** that get declared in the ``MANIFEST``, as being provided by your model component. We strongly suggest that you choose a name that is clearly connected to whatever the model component achieves.

The ``attributes`` object's ``depends`` value array only allows users to specify the *roots* of a model component's attribute-based dependency tree, and then FIREWHEEL adds any further attribute-based dependencies in the tree for you.
This facilitates sharing repositories with others without burdening them with knowing the exact required dependencies within and across them. See :ref:`dependency_management` for more information on how FIREWHEEL manages dependencies between model components.

.. _model_components_object:

The Model Components object
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``model_components`` object in a ``MANIFEST`` explicitly specifies the specific, uniquely named MCs that it ``depends`` on and ``precedes``. The ``model_components`` object contains two fields, ``depends`` and ``precedes``, and they expects an array of strings as the value. The value array can contain zero or more *names* of other model components, as declared using :ref:`name_field` in their ``MANIFEST`` files.

This information is used at run time, along with the values in the :ref:`attributes <attributes_object>` object and the ordering of MCs listed on the command line, to create a dependency tree representing the interdependencies amongst all of the model components required to run any given FIREWHEEL experiment, across all available repositories.
See :ref:`Model Component Dependencies <dependency_mcs>` for more information on when and why to declare dependencies using the ``model_components`` object.

The ``model_components`` object is required to be present in a ``MANIFEST``, but the ``depends`` and ``precedes`` field's value arrays can be empty.

It takes the following form:

.. code-block:: yaml

    model_components:
        depends: []
        precedes: []

For example, the ``acme.topology`` model component adds vertices and edges to the ``graph``, and needs some of those vertices to be of type ``Ubuntu1604Server``.
The ``Ubuntu1604Server`` class is defined in the ``linux.ubuntu1604`` MC, therefore, ``acme.topology`` will need to attempt to import the ``Ubuntu1604Server`` class into its *plugin* python module e.g. using ``from linux.ubuntu1604 import Ubuntu1604Server``) before it can assign this object to the appropriate vertices.

The ``linux.ubuntu1604`` model component, and any python objects
within it, will be made explicitly available to the ``acme.topology`` model component if, and only if, the ``acme.topology`` ``MANIFEST`` includes it in the ``model_components`` object, e.g.:

.. code-block:: yaml

    model_components:
        depends:
            - linux.ubuntu1604
        precedes: []

Similarly, since ``acme.topology`` needs to be able to create a ``Helium118`` (VyOS router) then it will need to depend on the model component that defines the ``Helium118`` *model component objects* class, ``vyos.helium118``, e.g.:

.. code-block:: yaml

    model_components:
        depends:
            - linux.ubuntu1604
            - vyos.helium118
        precedes: []

Finally, ``acme.topology`` also needs to be able to create a ``Switch`` which is defined in the ``base_graph_objects`` MC, so it is also required, e.g.:

.. code-block:: yaml

    model_components:
        depends:
            - linux.ubuntu1604
            - vyos.helium118
            - base_graph_objects
        precedes: []

.. _plugin_field:

The Plugin field
^^^^^^^^^^^^^^^^^

The ``plugin`` field specifies the name of the file, located within the model component's folder, that contains the Python Class that defines the functionality of a model component's ``plugin`` module (if it has one). The ``plugin`` field expects a string as its value. The role of a model component's plugin is to operate on the ``graph`` and a model component can contain *at most* one plugin. The ``plugin`` field's value is used by FIREWHEEL at run time to locate and execute a model component's plugin module at the appropriate time.

The ``plugin`` field is only required to be present in a ``MANIFEST`` if the model component contains a plugin module file.

It takes the following form:

.. code-block:: yaml

    "plugin": "<plugin_file_name>"

For example, in :ref:`attributes_object` section above we considered a model component called ``acme.set_hostname``. In this model component there would be a file that contains a ``SetHostname`` class that walks the ``topology`` graph, provided by its ``topology`` attribute provider, setting the ``hostnames`` for all the vertices. To identify the plugin file containing the ``SetHostname`` class, the ``acme.set_hostname`` model component's ``MANIFEST`` file would need to include the ``plugin`` parameter, e.g.:

.. code-block:: yaml

    plugin: plugin.py

This states that the ``SetHostname`` class that needs to be run is located in the ``plugin.py`` file, which itself is located in the ``acme.set_hostname`` model component's folder. [#plugin]_

.. [#plugin] The convention is to name the plugin's python module *plugin.py*. This is not strictly enforced by FIREWHEEL, but has been found to make file management a bit easier.

Within the plugin module, a single class determines the execution behavior of the plugin.
This plugin class is defined by the user as a subclass of FIREWHEEL's :py:class:`AbstractPlugin <firewheel.control.experiment_graph.AbstractPlugin>`, and it requires a ``run`` method be defined to describe the plugin's actions.

This plugin class is automatically loaded by the model component, so only one plugin class may be defined per plugin module (more than one plugin class would result in ambiguity and cause FIREWHEEL to raise an error).

.. _vm_resources_field:

The VM Resources field
^^^^^^^^^^^^^^^^^^^^^^

The ``vm_resources`` field specifies the names of the files, located within the model component's folder, which are to be scheduled for execution/use using Schedule Entries. The ``vm_resources`` field expects an array of strings as its value. The role of VM resources is to either perform some action(s) on a VM, or provide some other resource used for accomplishing an action, and a model component can contain zero or more VM resources.

VM resources can be scripts, executables, data files, or blobs, etc., that are added to vertices and scheduled for use on the VM images assigned to vertices in a network topology, once FIREWHEEL has instantiated them while launching an experiment. VM resources can be used to execute any function you want to have operate on a VM. They are used to configure VMs, install and configure applications on them, and to carry out other actions needed to conduct an experiment, such as generating network traffic and collecting data for analysis. The ``vm_resources`` field's values are used by FIREWHEEL at run time to locate a model component's VM resource files at the appropriate time during experiment launch/execution.

.. note::

    Only the names of VM resource files that a model component contains are included in the ``vm_resources`` field's value array. A model component may depend on using VM resources contained in other model components, e.g. to assign them to vertices and schedule their execution times, but those VM resources imported from other model components are NOT included in the ``vm_resources`` field's value array. However, you would need to depend on the model components that contain those VM resources, e.g. by listing them in the ``attributes`` or ``model_components`` objects' ``depends`` value arrays in the dependent model component's ``MANIFEST``.

Including the ``vm_resources`` field in a ``MANIFEST`` is only required if the model component contains one or more VM resource files.

It takes the following form:

.. code-block:: yaml

    vm_resources: []

To continue the ``acme.set_hostname`` example, its plugin schedules a VM resource called ``set_hostname.py`` on every vertex in the experiment ``topology`` graph. Since this VM resource is contained within the ``acme.set_hostname`` model component's folder, its ``MANIFEST`` must include the following ``vm_resources`` parameter:

.. code-block:: yaml

    vm_resources:
        - set_hostname.py

If the model component provides many ``vm_resources`` we recommend putting them in a folder (called ``vm_resources``). Then you can set the parameter:

.. code-block:: yaml

    "vm_resources":["vm_resources/**"]

Here are the following permutations which are valid paths for ``vm_resources``:

    * Non-recursively provide access to a directories files: ``path_to_dir`` OR  ``path_to_dir/``
    * Non-recursively, provide access to directory files matching a pattern: ``path_to_dir/*.ext``
    * Recursively provide access to all files: ``path_to_dir/**`` OR ``path_to_dir/**/``
    * Recursively provide access to all files matching a pattern: ``path_to_dir/**/*.ext``

.. _model_component_objects_field:

The Model Component Objects field
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``model_component_objects`` field specifies the name of the file, located within the model component's folder, that contains one or more Python Classes that define new objects you want/need to have for use in your experiments. The ``model_component_objects`` field expects a string as its value. The types of python classes you might include in a model component objects file include:

    * Classes that define vertex and edge types that can then be added to the experiment graph when defining a topology
    * Classes that add schedule entries to vertices in an experiment topology, to schedule actions performed by VM resources
    * Classes that expose helper functions for performing any number of tasks needed by an experiment

The ``model_component_objects`` field's value is used by FIREWHEEL at run time to locate and execute a model component's model component object classes when needed.

Every vertex in a graph that will instantiate a VM has a model component object class associated with it, to define it's properties, and every VM resource that will be used in an experiment is scheduled for use by adding a model component object class to a vertex, to identify the resource and define its execution time. When model component contains a model component objects file, which includes one or more python classes that define vertex types, schedule entries, or helper functions, FIREWHEEL ensures those python classes are available to the experiment through the ``model_component_objects`` parameter.

Including the ``model_component_objects`` field in a ``MANIFEST`` is only necessary if the model component contains a files that defines model component objects.

It takes the following form:

.. code-block:: yaml

    "model_component_objects": "<model_component_objects_file_name>"

For example, if a model component contains a model component object to specify a ``Win7`` vertex, and the ``Win7`` python class is defined in ``model_component_objects.py`` [#mco]_, then the model component's ``MANIFEST`` would need to include:

.. code-block:: yaml

    model_component_objects: model_component_objects.py

It's important to note that model component objects don't only have to apply to vertices within the graph. Model components can have model component objects that apply to edges as well.

.. [#mco] The convention is to name the python module that contains model component object class definitions as *model_component_objects.py*. This is not strictly enforced by FIREWHEEL, but has been found to make file management a bit easier.

.. _images_object:

The Images field
^^^^^^^^^^^^^^^^

The ``images`` field in a ``MANIFEST`` specifies information about all VM image files, located within the model component's folder, that a model component contains and may provide to other model components. The ``images`` field expects an array of objects as its value. Each object in the ``images`` field's value array contains two fields, called ``paths`` and ``architecture``, with ``paths`` expecting an array of strings for its value, and ``architecture`` expecting a string for its value.

The ``images`` field's value array can contain zero or more objects. Each object in an ``images`` field's value array can specify the names of one or more files containing VM images, but the image files listed in any single object must all share the same ``architecture`` specification. The ``images`` field's values are used by FIREWHEEL at run time to locate the VM image files needed for instantiating their corresponding graph objects when launching an experiment topology that includes them.

Many times it makes sense to have the images compressed for storage purposes (especially when using version control).
Therefore, FIREWHEEL will automatically detect and decompress images that are using tar or LZMA compression.
That is, if your file uses LZMA compression (e.g. the `xz <https://linux.die.net/man/1/xz>`_ utility) or `tar <https://linux.die.net/man/1/tar>`_ compression (including tar with gzip), then it will automatically be decompressed by FIREWHEEL.
Specifically, we support the following extensions: ``.xz``, ``.tar``, ``.tar.gz``, and ``.tgz``.

The ``images`` field only needs to be included in a ``MANIFEST`` if the model component contains one or more VM image files.

It takes the following form:

.. code-block:: yaml

    images:
      - paths: []
        architecture: ""

For example, the ``Win7`` graph object specified in :ref:`model_component_objects_field` specifies the ``windows-7-enterprise.qc2.xz`` image file, and since this image file is also contained in the same model component as the graph object, then that model component would also need the following ``images`` field in its ``MANIFEST`` file:

.. code-block:: yaml

    images:
      - paths:
          - windows-7-enterprise.qc2.xz
        architecture: "x86_64"

It's worth pointing out here that the file containing a VM image, used for instantiating a graph object, and the file defining the graph object's class don't both necessarily need to reside in the same model component, though they often will.
There are cases where, for instance, you might want to develop a new graph object that uses the same VM image as another graph object does, and that VM image already exists in that other graph object's model component.

In this case, your new graph object's model component would simply need to depend on the model component containing the VM image file i.e. in the :ref:`Model Components object <model_components_object>` in its ``MANIFEST``.
Then you'd reference it in your new graph component class and FIREWHEEL would be able to locate the VM image for instantiating your new graph object at run time.

.. note::

    It is recommended that images are compressed before being added to model components to save space.
    In this case, ``xz`` was used to compress the image.
    FIREWHEEL will decompress it when loading it into the image cache the first time it is used.
