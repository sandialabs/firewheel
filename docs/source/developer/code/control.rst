*Control*
=========

experiment_graph.py
-------------------

.. automodule:: firewheel.control.experiment_graph
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__,object_dir,__getstate__,__setstate__

model_component.py
------------------

.. automodule:: firewheel.control.model_component
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__,repository_db,vm_resource_store,image_store,__hash__

model_component_install.py
--------------------------

.. automodule:: firewheel.control.model_component_install
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

model_component_manager.py
--------------------------

.. automodule:: firewheel.control.model_component_manager
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

dependency_graph.py
-------------------

.. automodule:: firewheel.control.dependency_graph
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__,__str__

model_component_dependency_graph.py
-----------------------------------

.. automodule:: firewheel.control.model_component_dependency_graph
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

image_store.py
--------------

.. automodule:: firewheel.control.image_store
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

repository_db.py
----------------

.. automodule:: firewheel.control.repository_db
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

model_component_iterator.py
---------------------------

.. automodule:: firewheel.control.model_component_iterator
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__,__iter__,__next__

model_component_path_iterator.py
--------------------------------

.. automodule:: firewheel.control.model_component_path_iterator
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__,__iter__

model_component_exceptions.py
-----------------------------

.. automodule:: firewheel.control.model_component_exceptions
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

utils/new_model_component.py
----------------------------

.. automodule:: firewheel.control.utils.new_model_component
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

utils/vm_builder.py
-------------------

.. automodule:: firewheel.control.utils.vm_builder
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

utils/paths.py
--------------

.. automodule:: firewheel.control.utils.paths
    :members:
    :undoc-members:
    :special-members:
    :private-members:
    :exclude-members: __dict__,__weakref__,__module__

New Model Component Templates
-----------------------------

.. literalinclude:: ../../../src/firewheel/control/utils/templates/INSTALL.template
    :language: bash
    :caption: The template for a new model component INSTALL file.
    :name: install_template

.. literalinclude:: ../../../src/firewheel/control/utils/templates/model_component_objects.py.template
    :language: python
    :caption: The template for a new model component ``model_component_objects.py`` file.
    :name: model_component_objects_template

.. literalinclude:: ../../../src/firewheel/control/utils/templates/plugin.py.template
    :language: python
    :caption: The template for a new model component ``plugin.py`` file.
    :name: plugin_template

.. literalinclude:: ../../../src/firewheel/control/utils/templates/README.rst.template
    :language: rst
    :caption: The template for a new model component README.rst file.
    :name: readme_template
