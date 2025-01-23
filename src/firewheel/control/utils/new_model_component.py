#!/usr/bin/env python

"""
This module implements automatic generation of ModelComponents in either
interactive or argument-only modes. The generation includes the ModelComponent
MANIFEST, documentation skeleton, and templates for Python modules.

This module may be run as a script in either mode. Also included are 2 related
classes: PythonModule and ModelComponentGenerator.


"""

import os
import sys
import argparse
import contextlib

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined

from firewheel.control.utils.paths import is_path_exists_or_creatable_portable


class PythonModule:
    """Template-based generation of a Python module and its associated
    documentation file. Use properties to set up the desired state, then
    call creation methods to realize the state on disk. Templates use Jinja2.

    """

    def __init__(self, jinja_env):
        """
        Initialize several class variables.

        :ivar module_extension: File extension for the Python module (default: "py").
        :vartype module_extension: str

        Args:
            jinja_env (jinja2.Environment):Jinja2 Environment instance capable
                                          of loading templates needed when
                                          creating this module.

        Raises:
            ValueError: If a jinja2.Environment is not provided.
        """
        if not isinstance(jinja_env, Environment):
            raise ValueError("Please provide an instance of jinja2.Environment.")

        self.jinja_env = jinja_env

        self.base_path = None
        self.module_name = None
        self.module_extension = "py"
        self.module_relpath = None
        self.class_name = None

        self.module_template = None

    def module_exists(self):
        """Determine if this instance's specified module path exists on disk.

        Returns:
            bool: True if self.module_path is a file on disk, False otherwise.
        """
        return os.path.isfile(self.module_path)

    @property
    def base_path(self):
        """
        Provides the directory that serves as a base for all other relative paths.

        Returns:
            str: The base path.

        Raises:
            ValueError: No path specified (read), or specified path is invalid
                        (write), or unable to write to specified path (write).
        """
        if self._base_path is None:
            raise ValueError("Must specify a base path.")
        return self._base_path

    @base_path.setter
    def base_path(self, value):
        if value is None:
            # pylint: disable=attribute-defined-outside-init
            self._base_path = value
            return
        if not isinstance(value, str):
            raise ValueError("Specified path is invalid or not writable.")
        if not is_path_exists_or_creatable_portable(os.path.abspath(value)):
            raise ValueError("Specified path is invalid or not writable.")
        # pylint: disable=attribute-defined-outside-init
        self._base_path = value

    @property
    def module_name(self):
        """
        Name of the Python module. No file extension (e.g ".py") is used.

        Returns:
            str: The name of the Python module without a file extension.

        Raises:
            ValueError: No module name specified (read), or specified name is not a
                valid Python module name (write).
        """
        if self._module_name is None:
            raise ValueError("Must specify a module name.")
        return self._module_name

    @module_name.setter
    def module_name(self, value):
        if value is not None and not value.isidentifier():
            raise ValueError("Must specify a valid Python module name.")
        # pylint: disable=attribute-defined-outside-init
        self._module_name = value

    @property
    def module_relpath(self):  # noqa: DOC502
        """Path to the Python module, relative to `self.base_path`.

        Returns:
            str: The path to the Python module, relative to the base path, or an
            empty string.

        Raises:
            ValueError: Path specified is not relative (write).
        """
        if self._module_relpath is None:
            return ""
        return self._module_relpath

    @module_relpath.setter
    def module_relpath(self, value):
        if value is not None and os.path.abspath(value) == value:
            raise ValueError("Module relpath must be relative.")
        # pylint: disable=attribute-defined-outside-init
        self._module_relpath = value

    @property
    def module_template(self):  # noqa: DOC502
        """Jinja2 template name for the Python module template.

        Returns:
            str: Jinja2 template name for the Python module template.

        Raises:
            ValueError: Jinja cannot load specified template (write).
        """
        return self._module_template

    @module_template.setter
    def module_template(self, value):
        if value is not None and value not in self.jinja_env.list_templates():
            raise ValueError("Must specify a module template file that exists.")
        # pylint: disable=attribute-defined-outside-init
        self._module_template = value

    @property
    def module_path(self):
        """
        The full path (including file extension) to the Python module file.

        Returns:
            str: The full path (including file extension) to the Python module file.
        """
        return os.path.join(
            self.base_path,
            self.module_relpath,
            f"{self.module_name}.{self.module_extension}",
        )

    def create_module(self, other_vars=None):
        """Create the Python module, along with the required directory structure
        to support it. Use the specified template, or a generic TODO comment
        if a template has not been specified.

        Args:
            other_vars (dict): Dictionary of additional template variables.
        """  # noqa: T10
        if not other_vars:
            other_vars = {}

        # Create the base path.
        os.makedirs(self.base_path, exist_ok=True)
        # Create the relpath.
        os.makedirs(os.path.dirname(self.module_path), exist_ok=True)

        # Create the module
        if self.module_template is None:
            # Use a comment.
            with open(self.module_path, "w", encoding="utf8") as module_file:
                # pylint: disable=fixme
                module_file.write("# TODO: Write code here.")  # noqa: T101
        else:
            # Use a template.
            template = self.jinja_env.get_template(self.module_template)
            template_vars = {}
            if self.class_name is not None:
                template_vars["class_name"] = self.class_name
            for key in other_vars.keys():
                template_vars[key] = other_vars[key]
            with open(self.module_path, "w", encoding="utf8") as module_file:
                template_stream = template.stream(template_vars)
                template_stream.dump(module_file)


class ModelComponentGenerator:
    """Represents the state and actions required to produce a new
    ModelComponent. Set values in properties first, then call creation
    method.

    :ivar jinja_env: Jinja2 Environment capable of loading the templates used while
                     generating this ModelComponent.
    :vartype jinja_env: jinja2.Environment

    :ivar readme_filename: Name of the README file for this ModelComponent
                           (default: "README.rst")
    :vartype readme_filename: str

    :ivar plugin_module: Python module and associated API documentation for the
                         plugin, if one exists in this ModelComponent.
    :vartype plugin_module: PythonModule

    :ivar model_component_module: Python module and associated API documentation
                                  for the model_component objects, if used in this
                                  ModelComponent.
    :vartype model_component_module: PythonModule
    """

    def __init__(
        self, root_path, name, template_path="templates", strict_template_vars=True
    ):
        """
        Initialize several class variables.

        Args:
            root_path (str): The root path for the new model component.
            name (str): The name of the model component.
            template_path (str): The path to the Jinja templates.
            strict_template_vars (bool): If we want to set `self.jinja_env.undefined`
                to StrictUndefined.

        """
        self.root_path = root_path
        self.name = name

        jinja_loader = PackageLoader("firewheel.control.utils", template_path)
        self.jinja_env = Environment(loader=jinja_loader, autoescape=True)
        if strict_template_vars:
            self.jinja_env.undefined = StrictUndefined

        self.plugin_template = "plugin.py.template"
        self.model_component_obj_template = "model_component_objects.py.template"

        self.readme_template = "README.rst.template"
        self.readme_filename = "README.rst"

        self.install_template = "INSTALL.template"
        self.install_filename = "INSTALL"

        self.plugin_module = None
        self.model_component_module = None

    @property
    def name(self):  # noqa: DOC503
        """
        Name of the ModelComponent, appears in the MANIFEST.

        Returns:
            str: Name of the ModelComponent, appears in the MANIFEST.

        Raises:
            AttributeError: No name defined (read).
            TypeError: Tried to set a non-string name (write).
        """
        try:
            return self._name
        except AttributeError as exp:
            raise AttributeError("name is not defined.") from exp

    @name.setter
    def name(self, value):
        if not isinstance(value, str):
            raise TypeError("ModelComponent name must be a string.")
        # pylint: disable=attribute-defined-outside-init
        self._name = value

    @property
    def attribute_depends(self):
        """
        Provides list of strings which are graph attributes on which this
        ModelComponent depends.

        Returns:
            list: List of strings which are graph attributes on which this
            ModelComponent depends.

        Raises:
            TypeError: Not all list members are strings (write), value is not a list
                of string (which is converted to a
                1-element list) (write).  # noqa: DAR402
        """
        try:
            return self._attribute_depends
        except AttributeError:
            return []

    @attribute_depends.setter
    def attribute_depends(self, value):
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError("Attribute depends must be a list of strings.")
        else:
            raise TypeError(
                "ModelComponent must depend on one or a list of string attributes."
            )
        # pylint: disable=attribute-defined-outside-init
        self._attribute_depends = value

    @property
    def attribute_provides(self):
        """
        Provides list of strings which are graph attributes which this
        ModelComponent provides.

        Returns:
            list: List of strings which are graph attributes which this
            ModelComponent provides.

        Raises:
            TypeError: Not all list members are strings (write), value is not a list
                of string (which is converted to a
                1-element list) (write).  # noqa: DAR402
        """
        try:
            return self._attribute_provides
        except AttributeError:
            return []

    @attribute_provides.setter
    def attribute_provides(self, value):
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError("Attribute provides must be a list of strings.")
        else:
            raise TypeError(
                "ModelComponent must provide one or a list of string attributes."
            )
        # pylint: disable=attribute-defined-outside-init
        self._attribute_provides = value

    @property
    def attribute_precedes(self):
        """
        Provides list of strings which are graph attributes on which this
        ModelComponent precedes.

        Returns:
            list: List of strings which are graph attributes on which this
            ModelComponent precedes.

        Raises:
            TypeError: Not all list members are strings (write), value is not a list
                of string (which is converted to a
                1-element list) (write).  # noqa: DAR402
        """
        try:
            return self._attribute_precedes
        except AttributeError:
            return []

    @attribute_precedes.setter
    def attribute_precedes(self, value):
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError("Attribute precedes must be a list of strings.")
        else:
            raise TypeError(
                "ModelComponent must precede on one or a list of string attributes."
            )
        # pylint: disable=attribute-defined-outside-init
        self._attribute_precedes = value

    @property
    def model_component_depends(self):
        """List of ModelComponents this ModelComponent depends on, by name.

        Returns:
            list: List of strings containing ModelComponent names on which this
            ModelComponent depends.

        Raises:
            TypeError: Not all list members are strings (write), value is not a list
                of string (which is converted to a
                1-element list) (write).  # noqa: DAR402
        """
        try:
            return self._model_component_depends
        except AttributeError:
            return []

    @model_component_depends.setter
    def model_component_depends(self, value):
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError(
                    "Model Component dependencies must be a list of strings."
                )
        else:
            raise TypeError(
                "Model Component dependencies must provide one or a "
                "list of string names."
            )
        # pylint: disable=attribute-defined-outside-init
        self._model_component_depends = value

    @property
    def model_component_precedes(self):
        """List of ModelComponents this ModelComponent precedes, by name.

        Returns:
            list: List of strings containing ModelComponent names on which this
            ModelComponent precedes.

        Raises:
            TypeError: Not all list members are strings (write), value is not a list
                of string (which is converted to a
                1-element list) (write).  # noqa: DAR402
        """
        try:
            return self._model_component_precedes
        except AttributeError:
            return []

    @model_component_precedes.setter
    def model_component_precedes(self, value):
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError("Model Component precedes must be a list of strings.")
        else:
            raise TypeError(
                "Model Component precedes must provide one or a list of string names."
            )
        # pylint: disable=attribute-defined-outside-init
        self._model_component_precedes = value

    @property
    def plugin(self):
        """Relative path to the plugin file (including full file name).

        Returns:
            str: Relative path to the plugin file (including full file name).

        Raises:
            TypeError: Specified path is not a string (write).  # noqa: DAR402
            ValueError: Specified path is not relative (write).  # noqa: DAR402
        """
        try:
            return self._plugin
        except AttributeError:
            return None

    @plugin.setter
    def plugin(self, value):
        if not isinstance(value, str):
            raise TypeError("plugin must specify a string relative path.")
        if os.path.isabs(value):
            raise ValueError("ModelComponent plugin path must be relative.")
        # pylint: disable=attribute-defined-outside-init
        self._plugin = value

    @property
    def plugin_class(self):
        """Name of the plugin class for this ModelComponent.
        This plugin class is defined in the plugin file (`self.plugin`), and
        inherits from `firewheel.control.experiment_graph.AbstractPlugin`.

        Returns:
            str: Name of the plugin class for this ModelComponent.

        Raises:
            ValueError: Specified value is not a valid Python
                identifier (write).  # noqa: DAR402
        """
        try:
            return self._plugin_class
        except AttributeError:
            return "Plugin"

    @plugin_class.setter
    def plugin_class(self, value):
        if not value.isidentifier():
            raise ValueError("Must specify a valid Python class name.")
        # pylint: disable=attribute-defined-outside-init
        self._plugin_class = value

    @property
    def model_component_objects(self):
        """
        Relative path to the model_component objects file (including full file name).

        Returns:
            str: Relative path to the model_component objects file (including full file name).

        Raises:
            TypeError: Specified path is not a string (write).  # noqa: DAR402
            ValueError: Specified path is not relative (write).  # noqa: DAR402
        """
        try:
            return self._model_component_objects
        except AttributeError:
            return None

    @model_component_objects.setter
    def model_component_objects(self, value):
        if not isinstance(value, str):
            raise TypeError(
                "model_component_objects must specify a string relative path."
            )
        if os.path.isabs(value):
            raise ValueError(
                "ModelComponent model_component_objects path must be relative."
            )
        # pylint: disable=attribute-defined-outside-init
        self._model_component_objects = value

    @property
    def vm_resources(self):
        """List of vm_resources contained in this ModelComponent.

        Each vm_resource is a relative path from the MANIFEST to the
        executable (vm_resource) file.

        Returns:
            list: List of strings of `vm_resources` contained in this ModelComponent.

        Raises:
            TypeError: Value is not a string (automatically converted to a
                1-element list of strings) or a list of strings (write).  # noqa: DAR402
        """
        try:
            return self._vm_resources
        except AttributeError:
            return None

    @vm_resources.setter
    def vm_resources(self, value):
        if value is None:
            # pylint: disable=attribute-defined-outside-init
            self._vm_resources = None
            return
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError("VM Resources must be a string or a list of strings.")
        else:
            raise TypeError("VM Resources must be a string or a list of strings.")

        # pylint: disable=attribute-defined-outside-init
        self._vm_resources = value

    @property
    def image(self):  # noqa: DOC502
        """VM disk file in this ModelComponent. Each entry is the relative path
        from the MANIFEST to the disk file.

        Returns:
            str: VM disk file in this ModelComponent.

        Raises:
            TypeError: Value is not a string (automatically converted to a
                1-element list of strings) or a list of strings (write).
        """
        try:
            return self._image
        except AttributeError:
            return None

    @image.setter
    def image(self, value):
        if value is None:
            # pylint: disable=attribute-defined-outside-init
            self._image = None
            return
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            if not all(isinstance(attr, str) for attr in value):
                raise TypeError("Image must be a string or a list of strings.")
        else:
            raise TypeError("Image must be a string or a list of strings.")

        # pylint: disable=attribute-defined-outside-init
        self._image = value

    @property
    def arch(self):  # noqa: DOC502
        """Architecture for a specified image
        This value can be x86_64, x86, etc.

        Returns:
            str: Architecture for a specified image (typically x86_64).

        Raises:
            TypeError: Value is not a string
        """
        try:
            return self._arch
        except AttributeError:
            return None

    @arch.setter
    def arch(self, value):
        if value is None:
            # pylint: disable=attribute-defined-outside-init
            self._arch = None
            return
        if not isinstance(value, str):
            raise TypeError("Arch must be a string.")
        # pylint: disable=attribute-defined-outside-init
        self._arch = value

    @property
    def readme_path(self):
        """Relative path (including filename) to the README for
        this ModelComponent.

        Returns:
            str: Relative path (including filename) to the README for this ModelComponent.
            the default is derived from `self.root_path` and `self.readme_filename`.
        """
        with contextlib.suppress(AttributeError):
            if self._readme_path is not None:
                return self._readme_path
        return os.path.join(self.root_path, self.readme_filename)

    @readme_path.setter
    def readme_path(self, value):
        if value is None:
            # pylint: disable=attribute-defined-outside-init
            self._readme_path = value
            return
        if not isinstance(value, str):
            raise TypeError("README path must be a string.")
        # pylint: disable=attribute-defined-outside-init
        self._readme_path = value

    @property
    def install_path(self):
        """Relative path (including filename) to the INSTALL for
        this Model Component.

        Returns:
            str: Relative path (including filename) to the INSTALL for this ModelComponent.
            the default is derived from `self.root_path` and `self.install_filename`.
        """
        with contextlib.suppress(AttributeError):
            if self._install_path is not None:
                return self._install_path
        return os.path.join(self.root_path, self.install_filename)

    @install_path.setter
    def install_path(self, value):
        if value is None:
            # pylint: disable=attribute-defined-outside-init
            self._install_path = value
            return
        if not isinstance(value, str):
            raise TypeError("INSTALL path must be a string.")
        # pylint: disable=attribute-defined-outside-init
        self._install_path = value

    def write_manifest(self):
        """
        Write a MANIFEST file based on this instance's properties,
        including the creation of any necessary directory structure.
        """
        manifest = {
            "name": self.name,
            "attributes": {
                "depends": self.attribute_depends,
                "provides": self.attribute_provides,
                "precedes": self.attribute_precedes,
            },
            "model_components": {
                "depends": self.model_component_depends,
                "precedes": self.model_component_precedes,
            },
        }

        if self.plugin is not None:
            manifest["plugin"] = self.plugin
        if self.model_component_objects is not None:
            manifest["model_component_objects"] = self.model_component_objects
        if self.vm_resources is not None:
            manifest["vm_resources"] = self.vm_resources
        if self.image is not None:
            img = {"paths": self.image, "architecture": "x86_64"}
            if self.arch:
                img["architecture"] = self.arch
            manifest["images"] = [img]

        os.makedirs(self.root_path, exist_ok=True)
        manifest_path = os.path.join(self.root_path, "MANIFEST")
        with open(manifest_path, "w", encoding="utf8") as manifest_file:
            yaml.safe_dump(manifest, manifest_file, sort_keys=True, indent=2)

    def create_plugin_module(self):
        """
        Create a Python module for the ModelComponent's plugin.

        Raises:
            ValueError: If the plugin extension is not '.py'
        """
        plugin_module_name, plugin_ext = os.path.splitext(os.path.basename(self.plugin))
        if plugin_ext != ".py":
            raise ValueError('Plugin module extension must be ".py".')
        self.plugin_module = PythonModule(self.jinja_env)
        self.plugin_module.base_path = self.root_path
        self.plugin_module.module_relpath = os.path.dirname(self.plugin)
        self.plugin_module.module_name = plugin_module_name
        self.plugin_module.module_template = self.plugin_template
        self.plugin_module.class_name = self.plugin_class

        self.plugin_module.create_module(other_vars={"mc_name": self.name})

    def create_model_component_objects_module(self):
        """
        Create a Python module for the ModelComponent's model_component objects.

        Raises:
            ValueError: If the Model Component objects extension is not '.py'.
        """
        model_component_module_name, model_component_obj_ext = os.path.splitext(
            os.path.basename(self.model_component_objects)
        )
        if model_component_obj_ext != ".py":
            raise ValueError('Model Component objects module extension must be ".py".')
        self.model_component_module = PythonModule(self.jinja_env)
        self.model_component_module.base_path = self.root_path
        self.model_component_module.module_relpath = os.path.dirname(
            self.model_component_objects
        )
        self.model_component_module.module_name = model_component_module_name
        self.model_component_module.module_template = self.model_component_obj_template

        self.model_component_module.create_module(other_vars={"mc_name": self.name})

    def create_readme(self):
        """
        Create a README file. This is based on a template if one is
        specified.
        """
        template = self.jinja_env.get_template(self.readme_template)
        template_vars = {
            "mc_name": self.name,
            "name_heading": "#" * len(self.name),
        }

        if self.plugin is not None:
            template_vars["plugin"] = True

        if self.model_component_objects is not None:
            template_vars["model_component_objects"] = True

        attr_depends = ""
        for attr in self.attribute_depends:
            attr_depends += f"    * ``{attr}``\n"

        if attr_depends:
            template_vars["attr_depends"] = attr_depends

        attr_provides = ""
        for attr in self.attribute_provides:
            attr_provides += f"    * ``{attr}``\n"

        if attr_provides:
            template_vars["attr_provides"] = attr_provides

        attr_precedes = ""
        for attr in self.attribute_precedes:
            attr_precedes += f"    * ``{attr}``\n"

        if attr_precedes:
            template_vars["attr_precedes"] = attr_precedes

        mc_depends = ""
        for mc in self.model_component_depends:
            mc_depends += f"    * :ref:`{mc}_mc`\n"

        if mc_depends:
            template_vars["mc_depends"] = mc_depends

        mc_precedes = ""
        for mc in self.model_component_precedes:
            mc_precedes += f"    * :ref:`{mc}_mc`\n"

        if mc_precedes:
            template_vars["mc_precedes"] = mc_precedes

        with open(self.readme_path, "w", encoding="utf8") as readme_file:
            template_stream = template.stream(template_vars)
            template_stream.dump(readme_file)

    def create_install(self):
        """
        Create a INSTALL file. This is based on a template.
        """
        template = self.jinja_env.get_template(self.install_template)
        template_vars = {
            "mc_name": self.name,
        }

        with open(self.install_path, "w", encoding="utf8") as readme_file:
            template_stream = template.stream(template_vars)
            template_stream.dump(readme_file)

    def create_component(self, manifest_only=False):
        """
        Create this ModelComponent, based on the configuration of this object.

        Args:
            manifest_only (bool): Only generate a MANIFEST file (default False).
        """
        self.write_manifest()
        if not manifest_only:
            if self.plugin is not None:
                # pylint: disable=unexpected-keyword-arg
                self.create_plugin_module()

            if self.model_component_objects is not None:
                # pylint: disable=unexpected-keyword-arg
                self.create_model_component_objects_module()

            # Create the README file.
            self.create_readme()

            # Create the INSTALL file.
            self.create_install()


def python_file(value):
    """
    Function that can perform ArgParse type checking for python files.
    Enforces the value given ends with the string ".py".

    Args:
        value (str): The value to check.

    Returns:
        str: The value converted into a string.

    Raises:
        argparse.ArgumentTypeError: Given value does not end in ".py".
    """
    value = str(value)
    if not value.endswith(".py"):
        raise argparse.ArgumentTypeError('Python file name must end in ".py".')
    return value


ARG_DESCRIPTION = {
    "MANIFEST": {
        "--name": {
            "dest": "name",
            "type": str,
            "required": True,
            "nargs": 1,
            "help": "ModelComponent name",
            "action": "store",
        },
        "--attribute_depends": {
            "dest": "attribute_depends",
            "type": str,
            "required": False,
            "nargs": "+",
            "help": "(space-separated-strings) Graph Attribute(s) depended on by "
            "the new ModelComponent",
            "action": "store",
        },
        "--attribute_provides": {
            "dest": "attribute_provides",
            "type": str,
            "required": False,
            "nargs": "+",
            "help": "(space-separated-strings) Graph Attribute(s) provided by "
            "the new ModelComponent",
            "action": "store",
        },
        "--attribute_precedes": {
            "dest": "attribute_precedes",
            "type": str,
            "required": False,
            "nargs": "+",
            "help": "(space-separated-strings) Graph Attribute(s) preceded by "
            "the new ModelComponent",
            "action": "store",
        },
        "--model_component_depends": {
            "dest": "model_component_depends",
            "type": str,
            "required": False,
            "nargs": "+",
            "help": "(space-separated-strings) ModelComponent(s) required by name",
            "action": "store",
        },
        "--model_component_precedes": {
            "dest": "model_component_precedes",
            "type": str,
            "required": False,
            "nargs": "+",
            "help": "(space-separated-strings) ModelComponent(s) that will be preceded by name",
            "action": "store",
        },
        "--plugin": {
            "dest": "plugin",
            "type": python_file,
            "required": False,
            "nargs": 1,
            "help": "File for a plugin",
            "action": "store",
        },
        "--model_component_objects": {
            "dest": "model_component_objects",
            "type": python_file,
            "required": False,
            "nargs": 1,
            "help": "File for Model Component Objects",
            "action": "store",
        },
        "--location": {
            "dest": "location",
            "type": str,
            "required": True,
            "nargs": 1,
            "help": "Location for the new ModelComponent",
            "action": "store",
        },
        "--plugin_class": {
            "dest": "plugin_class",
            "type": str,
            "required": False,
            "nargs": 1,
            "help": "Name for the new plugin class",
            "action": "store",
            "default": "Plugin",
        },
        "--vm_resource": {
            "dest": "vm_resources",
            "type": str,
            "required": False,
            "nargs": "+",
            "help": "(space-separated-strings) File(s) to be used as a vm_resource",
            "action": "store",
        },
        "--image": {
            "dest": "image",
            "type": str,
            "required": False,
            "nargs": 1,
            "help": "File to be used as a VM disk",
            "action": "store",
        },
        "--arch": {
            "dest": "arch",
            "type": str,
            "required": False,
            "nargs": 1,
            "help": "Architecture for specified image",
            "action": "store",
        },
    },
    "Configuration": {
        "--non-interactive": {
            "dest": "non_interactive",
            "type": bool,
            "required": False,
            "nargs": 1,
            "help": "Require minimum parameters as arguments and do not prompt for any values",
            "action": "store_true",
            "default": False,
        },
        "--template_dir": {
            "dest": "template_dir",
            "type": str,
            "required": False,
            "nargs": 1,
            "help": "Override the configured templates directory",
            "action": "store",
            "default": "templates",
        },
        "--no_templates": {
            "dest": "no_templates",
            "type": bool,
            "required": False,
            "nargs": 1,
            "help": "Do not generate files from templates. Only generate a MANIFEST",
            "action": "store_true",
            "default": False,
        },
    },
}
""":obj:`dict`: Declaration of the arguments and their sections. Structured
here instead of pure ArgParse to enable the interactive/prompting functionality.
All arguments are optional to ArgParse, but custom functionality enforces their
use (so interactive mode works correctly). Type specification is also enforced
in interactive mode using values specified here.

Each section of arguments is a top-level key in this dictionary::

    {
        'SECTION': {
        }
    }

Each section dictionary is made up of keys representing arguments::

    'SECTION': {
        '--arg': {
        }
    }

Finally, each argument dictionary defines some attributes::

    '--arg': {
        'dest': 'template_dir',
        'type': str,
        'required': False,
        'nargs': 1,
        'help': 'Help text',
        'action': 'store',
        'default': 'DefaultValue'
    }

Each of these keys is a keyword passed to the add_argument() method, with some
notable exceptions:

    * required is used by custom code, and the required keyword in add_argument has
      the value False.
    * nargs is omitted from the call to add_argument if the value is 1.
    * default is optional, and omitted from the call to add_argument is omitted
      from this dictionary.
"""

ARGUMENT_PROMPT_SECTIONS = ["MANIFEST"]
""":obj:`list`: Defined which sections of arguments will be prompted for in
interactive mode. If an argument is both required and outside of one of the
sections in this list then it must be specified on the command line regardless
of interactive or non-interactive mode being used.
"""


def get_arg_parser():  # pragma: no cover
    """Construct an :class:`argparse.ArgumentParser` based on the `ARG_DESCRIPTION` dictionary.

    Returns:
        argparse.ArgumentParser: Argument parser instance.
    """
    parser = argparse.ArgumentParser(
        description="Generate a new ModelComponent", prog="firewheel mc generate"
    )

    for section, value in ARG_DESCRIPTION.items():
        arg_sec = parser.add_argument_group(section)
        for arg_name, arg_value in value.items():
            kw_args = {
                "dest": arg_value["dest"],
                "required": False,
                "action": arg_value["action"],
                "help": arg_value["help"],
            }
            if kw_args["action"] != "store_true":
                if arg_value["nargs"] != 1:
                    kw_args["nargs"] = arg_value["nargs"]
                kw_args["type"] = arg_value["type"]
                with contextlib.suppress(KeyError):
                    kw_args["default"] = arg_value["default"]
            arg_sec.add_argument(arg_name, **kw_args)

    return parser


def prompt_arg(arg_name, arg_dict):  # pragma: no cover
    """
    Used by interactive mode to prompt for arguments that have no value specified.

    Args:
        arg_name (str): Name of the argument to prompt for.
        arg_dict (dict): Dictionary specifying parameters for the argument.
                    Uses 'type', 'default', 'required', 'help'.

    Returns:
        list: Value(s) given by the user.
    """
    try:
        default = f"[{arg_dict['default']}]"
    except KeyError:
        default = "[]"

    if arg_dict["required"] and default == "[]":
        default = ""

    user_val = None
    reprompt = True
    while reprompt:
        reprompt = False
        user_val = input(f"({arg_name}) {arg_dict['help']} {default}: ")
        if not user_val.strip():
            if arg_dict["required"]:
                reprompt = True
                continue
            try:
                return arg_dict["default"]
            except KeyError:
                return None
        else:
            try:
                # Ensure that the user value converts properly
                _ = arg_dict["type"](user_val)
                if arg_dict["nargs"] == "+" and isinstance(user_val, str):
                    user_val = user_val.split()
            except KeyError:
                break
            except argparse.ArgumentTypeError as arg_err:
                print(f"ERROR: {arg_err}")
                reprompt = True
                continue

    return user_val


def check_and_prompt_args(args):  # pragma: no cover
    """
    Used by interactive mode to fill in values for all prompt-able arguments.

    Sets values in the `args` argument.

    Args:
        args (Namespace): :obj:`argparse.ArgumentParser`'s argument parsing
                          results.
    """
    for section, value in ARG_DESCRIPTION.items():
        if section not in ARGUMENT_PROMPT_SECTIONS:
            continue
        for arg_name, arg_value in value.items():
            try:
                try:
                    attr_name = arg_value["dest"]
                except KeyError:
                    attr_name = arg_name.strip("-")
                new_value = getattr(args, attr_name)
            except AttributeError:
                setattr(
                    args,
                    attr_name,
                    prompt_arg(attr_name, arg_value),
                )
                continue
            if new_value is None:
                setattr(
                    args,
                    attr_name,
                    prompt_arg(attr_name, arg_value),
                )


def check_required_args(args):  # pragma: no cover
    """
    Determine which required arguments are missing.

    Used by non-interactive mode to enforce required arguments.

    Args:
        args (Namespace): :obj:`argparse.ArgumentParser`'s argument parsing
                               results.

    Returns:
        list: A list of strings which are the required arguments that have not
        been specified.
    """
    missing_args = []
    for value in ARG_DESCRIPTION.values():
        for arg_name, arg_value in value.items():
            if arg_value["required"]:
                namespace_arg_name = arg_name.strip("-")
                try:
                    if getattr(args, namespace_arg_name) is None:
                        missing_args.append(arg_name)
                except AttributeError:
                    missing_args.append(arg_name)
    return missing_args


def main():  # pragma: no cover
    """
    Determine ModelComponent configuration and generate a new ModelComponent.
    """
    arg_parser = get_arg_parser()
    args = arg_parser.parse_args()

    if args.non_interactive:
        missing_list = check_required_args(args)
        # Evaluates True if any elements in missing_list.
        if missing_list:
            print(
                f"{sys.argv[0]}: error: the following arguments are"
                f" required: {' '.join(missing_list)}"
            )
            return
    else:
        check_and_prompt_args(args)

    mcg = ModelComponentGenerator(args.location, args.name, args.template_dir)

    for argument in ARG_DESCRIPTION["MANIFEST"]:
        try:
            argument_attr = ARG_DESCRIPTION["MANIFEST"][argument]["dest"]
        except KeyError:
            argument_attr = argument.strip("-")
        try:
            user_value = getattr(args, argument_attr)
            if user_value is None:
                continue
            with contextlib.suppress(TypeError):
                # user_value will evaluate False if it is empty.
                if not user_value:
                    continue
            setattr(mcg, argument_attr, user_value)
        except AttributeError:
            pass

    mcg.create_component(manifest_only=args.no_templates)


if __name__ == "__main__":
    main()
