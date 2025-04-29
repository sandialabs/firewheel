.. _dependency_management:

Dependency Management
---------------------
Dependencies come in two basic forms, object/resource dependencies, and experiment state dependencies.
Object and resource dependencies occur when a model component depends on importing model component objects or using VM resources or images contained in other model components.
Experiment state dependencies occur when one model component must only execute before another finishes (e.g. when the first must instantiate an experiment property before the second can modify it) or requires another to run after it finishes.
Dependency management is how FIREWHEEL determines which model components get loaded into it's Python Virtual Environment (FWPY) and order in which those components are loaded and executed when an experiment is launched.
This dependency system is akin to most package managers which will ensure that installing one package will recursively identify and install all new dependent packages.
Therefore, when developing new model components, it's only important to identify the direct dependency relationship for that component; the remainder of the necessary dependencies will be automatically resolved.

Model component's dependency relationships are ordered via a directed acyclic graph (DAG) to ensure that a repeatable experiment environment is created.
There are two methods for establishing relationships between model components.

  1. A *depends* relationship indicates that a second MC must be installed and executed **BEFORE** another MC.
  For example, if ``mc1`` *depends* on ``mc2``, then the ordering in the dependency graph would be ``mc2-->mc1``.

  2. A *precedes* relationship indicates that a second MC must be installed and executed **AFTER** another MC.
  For example, if ``mc1`` *precedes* ``mc2``, then the ordering in the dependency graph would be ``mc1-->mc2``.

By explicitly specifying *depends* and *precedes* relationships, users can minimize the effort for building a repeatable experiment graph.

There are three conventions by which users can identify dependencies to FIREWHEEL:

  1. Ordering of the model components listed on a ``firewheel experiment`` command line e.g. ``firewheel experiment mc1 mc2 mc3``.
  2. Using information in the model components' ``attribute`` block of the MANIFEST.
  3. Using information in the model components' ``model_components`` block of the MANIFEST.

This design enables multiple ways for achieving the same dependency graph combining each of these methods.
Therefore, each of the three methods are discussed in-detail below to ensure full understanding of how to best use each.
Additionally, some examples are provided to further clarify usage.

Model Component Ordering on the Command Line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To launch a FIREWHEEL experiment, you run FIREWHEEL from within a command shell using its :ref:`helper_experiment` Helper i.e. ``firewheel experiment``.
Immediately following the ``experiment`` Helper keyword, you then list the model components you want FIREWHEEL to run.
The order in which you list an experiment's model components on the command line is guaranteed to be the order in which they are executed.
That is, when building the dependency graph, there are assumed directional edges between the MCs listed on the command line.

For example, take the command: ::

  firewheel experiment tests.router_tree:5 tests.ping_all minimega.launch

In this case there are dependency relationships between the model components where ``tests.router_tree:5`` must be executed before ``tests.ping_all`` which must be executed before ``minimega.launch``.
Using command line dependencies is the most visible way to state the relationships between components.
However, when many model components are involved, it could become overwhelmingly complicated.
For example, if we were to list all dependencies required by the previous experiment, the command would look like: ::

  firewheel experiment misc.blank_graph base_objects linux.base_objects generic_vm_objects tests.router_tree:5 minimega.emulated_entities minimega.testbed_available linux.ubuntu linux.ubuntu1604 vyos vyos.helium118 tests.ping_all minimega.create_mac_addresses minimega.resolve_vm_images minimega.configure_ips ping_default_gateway minimega.schedules_ready vm_resource.schedule vm_resource.validate minimega.parse_experiment_graph minimega.launch

Therefore, we recommend minimizing the use of command line ordering in favor of the two methods described below.

.. _dependency_attributes:

Attributes: Depends, Provides, and Precedes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Model component attributes can be thought of as commodities which can be provided by the model component and depended on or precedes other MCs.
The :ref:`attributes <attributes_object>` field in a model component's ``MANIFEST`` is used to declare the names/labels of the *attributes* (if any) that a model component:

  * ``provides`` for use by other model components
  * ``depends`` on some other MC providing and must exist prior to the MC executing
  * ``precedes`` (i.e. it depends on these attributes occurring *AFTER* this MC runs)

Attribute labels can be any descriptive string that describes a property that is provided by a given model component.
These labels enable model components to provide, depend, and precede *generic* attributes about the experiment.

For example, a model component that creates a website will depend on a web server existing first.
This website does not need to be run on a specific web server software (NGINX, Apache, etc.).
Therefore, it can depend on a generic attribute like `web_server`.
This attribute can then be provided by *any* model component which creates a web server.
If however, a user would like to use a specific web server software, they can either have that MC provide a more specific label (e.g. `nginx_web_server`) OR explicitly depend on the model component that creates the NGINX server.

Attributes can also be used to precede the execution of a MC that provides a specific attribute.
For example, if a user creates a new topology, they may want to customize the hostnames after the topology is created.
The MC which changes these hostnames is agnostic to which topology it modifies.
Therefore, a user can have their topology ``precedes`` the other MC and can be guaranteed that it will be executed after the topology.

**Are Attribute Labels Considered Reserved Words?**

Attribute labels are not reserved words -- at least not in the sense of reserved words in programming languages.
In practice, however, only one model component per experiment can provide any given attribute, in one sense they can become like reserved words.
For instance, the ``misc.blank_graph`` model component in the ``base`` repository (included by default with FIREWHEEL), declares that it ``provides`` *graph* in its ``MANIFEST`` file.

Since the ``base`` repository is available in every FIRWHEEL installation, and the *graph* attribute label is already declared as provided by it, and since arguably every experiment needs to depend on *graph* to define its network topology, then essentially *graph* acts like a reserved word among attribute labels.
(Unless, of course, you define another way of providing an instance of FIREWHEEL's :class:`ExperimentGraph <firewheel.control.experiment_graph.ExperimentGraph>` to your model component.)

To discover attributes that are already provided/available you can use the FIREWHEEL :ref:`helper_mc_list` Helper: ::

  firewheel mc list -g provides


.. _special_attribute_labels:

**Can multiple Model Components provide the same Attribute?**

It is important to note that multiple Model Components **can** provide the same attribute.
However, FIREWHEEL will be unable to automatically determine which to use during experiment creation.
Therefore, there are two options:

1. You can add the preferred Model Component to the command line.
2. A default Model Component can be set using the :ref:`config_attribute_defaults` configuration option. Note that even if a default is set, it can be overwritten by applying a different one on the command line.

Special Attribute Labels
************************

There are two *special* attribute labels. They're *special* because they're (likely) necessary for every experiment to consume and produce. They are *graph* and *topology*.

**graph**

The ``misc.blank_graph`` model component, located in FIREWHEEL's ``base`` repository, ``provides`` the *graph* attribute.
This attribute represents the FIREWHEEL *Graph* object that every experiment must add vertices and edges to when constructing their network topologies.
In other words, the object instance of the :class:`ExperimentGraph <firewheel.control.experiment_graph.ExperimentGraph>` class that ``misc.blank_graph`` provides each experiment, and as modified by an experiment's model components, is the definition of the experiment.
Everything about an experiment is stored in its instance of the experiment graph.

Since FIREWHEEL provides a *blank graph* to any model component that lists *graph* as a dependency, then only the very first model component that will modify the *graph* for an experiment should declare a dependency on *graph*.

**topology**

The *topology* attribute is also *special* in FIREWHEEL.
It must be provided by a model component in an experiment in order to complete the experiment.
This is because other model component's in FIREWHEEL's ``base`` repository ``depends`` on it, namely the ``minimega.launch`` MC, which launches the experiment via minimega.

.. _dependency_mcs:

Model Components: Depends and Precedes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :ref:`model_components <model_components_object>` field in a ``MANIFEST`` is also used to declare which model components (if any) a model component ``depends`` on or ``precedes``.
The main difference, between the ``attributes`` object and the ``model_components`` object is that with with ``model_components``, the values use the exact ``name`` of a model component (as declared in its ``MANIFEST`` file's ``name`` field).
Whereas ``attributes`` are generalized, ``model_components`` are specific.
This is useful when a user wants specificity when selecting a type of MC that provides a general attribute (e.g. choosing an Apache web server over an NGINX one).
Additionally, using the ``model_components`` ``depends`` field is required when a user needs to import and use an Object, located in the named dependencies' ``model_components_objects.py`` file, in the dependent MCs ``plugin``.

Model components can also be explicitly required to run after the current model component by using the ``precedes`` field.
One practical example is when you know that your experiment should be launched with minimega (using the ``minimega.launch`` MC).
Users could either add ``minimega.launch`` as an argument to ``firewheel experiment`` or in their topology MANIFEST file, they can ``precedes`` the ``minimega.launch`` MC.

Examples
^^^^^^^^
Typical Experiment
******************
Let's consider an example experiment. Suppose you've created an experiment consisting of a ``my_basic_topology`` model component that defines a simple star LAN topology, which contains a switch that's connected to six hosts. ::

                 host2    host3
                    \    /
         host1 -- LAN_switch -- host4
                    /    \
                host6    host5

Now, your ``my_basic_topology`` model component will need to list the *graph* attribute label (which the ``misc.blank_graph`` model component provides as an ``attributes`` dependency in its ``MANIFEST``.
Additionally, let's also say it provides *basic_topology* to other model components.
So its ``MANIFEST`` would include: ::

        attributes:
          depends:
            - graph
          provides:
            - topology
          precedes: []

Next, the ``my_basic_topology`` model component needs to decorate the *switch* vertex in the graph with the ``Switch``  object (provided by the ``base_objects`` component.
Therefore, it will also need to depend on ``base_objects`` in order to be able to import and use the ``Switch()`` class in its ``plugin`` python module.
Lastly, you want to decorate the *host* vertices with ``Ubuntu1604Server`` object (found in the ``linux.ubuntu1604`` MC).
Therefore, the ``MANIFEST`` would also include: ::

        model_components:
          depends:
            - base_objects
            - linux.ubuntu1604
          precedes: []

Next you have a model component named ``tests.ping_all``, which will add a VM resource to each host and check for connectivity by sending ICMP packets.

Now, the ``tests.ping_all`` MC would depend on the *topology* attribute label in it's ``MANIFEST`` because it needs hosts to exist to install the VM resource.
Its ``MANIFEST`` would include: ::

        attributes:
          depends:
            - topology
          provides: []
          precedes: []

Then you want this to be an emulated experiment so it should be launched with minimega after the ``tests.ping_all`` VM resources are scheduled.
You would run your experiment as follows: ::

    $ firewheel experiment my_basic_topology tests.ping_all minimega.launch


The dependency graph for this experiment would generally [#]_ look like the following: ::

  misc.blank_graph   base_objects      linux.ubuntu1604
        +                +                    +
        |                |                    |
        |                |                    |
        |                v                    |
        +------->  my_basic_topology  <-------+
                          +
                          |
                          |
                          v
                    tests.ping_all
                          +
                          |
                          |
                          v
                    minimega.launch

The exact (and deterministic) order of execution as determined by our algorithm would be:
  1. ``misc.blank_graph``
  2. ``base_objects``
  3. ``linux.ubuntu1604``
  4. ``my_basic_topology``
  5. ``tests.ping_all``
  6. ``minimega.launch``

.. [#] In this example we do not recursively show dependencies for readability purposes.

Using Precedes
**************
Suppose we have the same ``my_basic_topology`` from the previous section.
In this experiment we do not want to use ``tests.ping_all``,but want to immediately launch it.
In this case, we have two options.
We can simply launch it from the command line by using: ::

    $ firewheel experiment my_basic_topology minimega.launch

Alternatively, we can update the ``my_basic_topology`` ``MANIFEST`` file to include: ::

        model_components:
          depends:
            - base_objects
            - linux.ubuntu1604
          precedes:
            - minimega.launch

Both options will produce the same result.
It is important to realize that an MC (or attribute) that is preceded is only guaranteed to be executed after the MC that precedes it.
It is NOT guaranteed to be executed as the "last" model component.
To do this, you should use command line ordering.
