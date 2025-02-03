import os
import sys
import inspect
import textwrap
import traceback
import importlib.util
from pathlib import Path
from datetime import datetime

import networkx as nx
from rich.console import Console

from firewheel.config import config
from firewheel.lib.log import Log
from firewheel.control.repository_db import RepositoryDb
from firewheel.control.model_component import ModelComponent
from firewheel.control.dependency_graph import UnsatisfiableDependenciesError
from firewheel.control.experiment_graph import AbstractPlugin
from firewheel.control.model_component_iterator import ModelComponentIterator
from firewheel.control.model_component_exceptions import ModelComponentImportError
from firewheel.control.model_component_dependency_graph import (
    ModelComponentDependencyGraph,
)


class NoDefaultProviderError(Exception):
    """
    An exception that is thrown if there is more than one provider for a given
    model component attribute but no default provider is defined in `attribute_default_config`.
    """


class InvalidDefaultProviderError(Exception):
    """
    This exception is caused if a given default provider is not valid.
    """


class InvalidStateError(Exception):
    """
    This is caused if the dependency graph is in an invalid state.
    """


class ModelComponentManager:
    """
    This class manages creating the dependency graph for a given experiment. It
    ensures that all the constraints (dependencies) are met by model components.
    """

    def __init__(self, repository_db=None, attribute_defaults_config=None):
        """
        Initialize class variables.

        Args:
            repository_db (RepositoryDb): Users can provide a different repository
                                          database.
            attribute_defaults_config (dict): A set of default attributes to use when
                                              selecting model components.
        """
        self.dg = None

        if attribute_defaults_config is None:
            self.attribute_defaults = config["attribute_defaults"]
        else:
            self.attribute_defaults = attribute_defaults_config

        if repository_db:
            self.repository_db = repository_db
        else:
            self.repository_db = RepositoryDb()

        self.log = Log(name="ModelComponentManager").log

    def get_ordered_model_component_list(self):
        """
        Get an ordered list of model components from the dependency graph.

        Returns:
            list: The list of model components.

        Raises:
            InvalidStateError: If the dependency graph does not exist.
        """
        if not self.dg:
            raise InvalidStateError("Dependency graph not constructed yet.")
        return self.dg.get_ordered_entity_list()

    def get_default_component_for_attribute(self, attribute, install_mcs=None):
        """
        Get the default model component which provides a given attribute. We
        first, check for a single model component installed that provides the
        attribute. If more than one is found, `attribute_defaults` is checked.

        Args:
            attribute (str): The attribute which a model component needs to provide.
            install_mcs (bool): A flag indicating whether to install
                model components automatically. By default, this method
                will defer to the default defined by the model component
                object's constructor. If set to :py:data:`False`, model
                components will not be installed.

        Returns:
            ModelComponent: The model component which provides the attribute.

        Raises:
            InvalidDefaultProviderError: If there is an error with the model
                component which should provide the attribute or the defaults table.
            NoDefaultProviderError: If no default provider was found but it
                is necessary for there to be one.
        """
        found_default_component = None
        multiple = False
        model_component_iter = ModelComponentIterator(
            self.repository_db.list_repositories()
        )

        for mc in model_component_iter:
            _depends, provides, _precedes = mc.get_attributes()
            if attribute in provides:
                if found_default_component is None:
                    found_default_component = mc
                else:
                    multiple = True
                    break

        if found_default_component is None or multiple is True:
            try:
                found_default_component = ModelComponent(
                    name=self.attribute_defaults[attribute],
                    repository_db=self.repository_db,
                    install=install_mcs,
                )

                _depends, provides, _precedes = found_default_component.get_attributes()
                if attribute not in provides:
                    raise InvalidDefaultProviderError(
                        f"Component '{found_default_component.name}' does "
                        f"not provide '{attribute}'."
                    )
            except (
                KeyError
            ) as exp:  # KeyError occurs on a failed lookup in the defaults table.
                if multiple is True:
                    self.log.error(
                        'Multiple providers and no default found for attribute "%s".',
                        attribute,
                    )
                    raise NoDefaultProviderError(
                        "Too many providers found for "
                        f"attribute '{attribute}'. Please specify a default."
                    ) from exp

                self.log.error('No provider found for attribute "%s".', attribute)
                raise NoDefaultProviderError(
                    "No provider found for "
                    f"attribute '{attribute}'. Please install at least one."
                ) from exp
            except (
                ValueError
            ) as exp:  # ValueError occurs when the table has a value we can't find.
                raise InvalidDefaultProviderError(
                    f'Default provider "{self.attribute_defaults[attribute]}" for '
                    f'"{attribute}" was not found.'
                ) from exp

        return found_default_component

    def build_dependency_graph(self, initial_component_list, install_mcs=None):
        """
        This is the primary method which generates the dependency graph.

        Args:
            initial_component_list (list): An initial list of model components
                which need to be added to the graph.
            install_mcs (bool): A flag indicating whether to install
                model components automatically. By default, this method
                will defer to the default defined by the model component
                object's constructor. If set to :py:data:`False`, model
                components will not be installed.

        Raises:
            RuntimeError: If there is an infinite loop building the graph.
        """
        self.dg = ModelComponentDependencyGraph()
        changed = True

        # Insert the initial model components into the graph.
        # Duplicate graph insertions allowed.
        mc_depends_components = []
        prev_component = None
        for grouping, component in enumerate(initial_component_list):
            mc_depends = component.get_model_component_depends()
            for mcdep_name in mc_depends:
                mcdep = ModelComponent(
                    name=mcdep_name,
                    repository_db=self.repository_db,
                    install=install_mcs,
                )
                mc_depends_components.append((mcdep, component, grouping))

            self.dg.insert(component, grouping, duplicate=True)
            if prev_component is not None:
                self.dg.associate_model_components(prev_component, component)
            prev_component = component

        # Did anything change this iteration? If no, we are finished.
        loops = 0
        while changed is True:
            loops += 1
            if loops > 1000:
                self.log.critical(
                    "Apparent infinite loop building dependency graph. "
                    "mc_depends_components: %s",
                    mc_depends_components,
                )
                raise RuntimeError("Apparent infinite loop building dependency graph!")
            changed = False

            # Process the mc_depends_components.
            # Duplicate graph insertions not allowed.
            next_mc_dep_comp = []
            inner_loops = 0
            while len(mc_depends_components) > 0:
                inner_loops += 1
                if inner_loops > 1000:
                    self.log.critical(
                        "Apparent mc_depends_components infinite loop: %s",
                        mc_depends_components,
                    )
                    raise RuntimeError("Apparent mc_depends_components infinite loop")
                changed = True
                for component, parent, grouping in mc_depends_components:
                    did_insert = self.dg.insert(component, grouping, duplicate=False)
                    # If more than one of a particular component is present, it had
                    # to have been specified more than once in the initial_component
                    # list. In this case, there must be an ordering relationship
                    # among the multiple occurrences.
                    # We will build the new ordering relationship among the first
                    # occurrence of component and the parent.
                    if not did_insert:
                        try:
                            component = self.dg.get_first(component)
                        except UnsatisfiableDependenciesError:
                            self._dependency_cycle_handler()
                    else:
                        mc_depends = component.get_model_component_depends()
                        for mcdep_name in mc_depends:
                            mcdep = ModelComponent(
                                name=mcdep_name,
                                repository_db=self.repository_db,
                                install=install_mcs,
                            )
                            next_mc_dep_comp.append((mcdep, component, grouping))
                    self.dg.associate_model_components(component, parent)
                mc_depends_components = next_mc_dep_comp
                next_mc_dep_comp = []

            # For each attribute with in degree 0, find the default component
            # that provides the attribute.
            unsat_attr = self.dg.get_in_degree_zero_constraints()
            self.log.debug("Have unsatisfied graph constraints: %s", unsat_attr)
            for attr, grouping in unsat_attr:
                # We should double check if the previously loaded component resolved
                # any of our unsatified attributes. If the current attribute
                # is no longer unstatified, we can continue.
                if attr not in dict(self.dg.get_in_degree_zero_constraints()):
                    continue
                changed = True
                component = self.get_default_component_for_attribute(
                    attr, install_mcs=install_mcs
                )
                did_insert = self.dg.insert(component, grouping, duplicate=False)
                if did_insert:
                    mc_depends = component.get_model_component_depends()
                    for mcdep_name in mc_depends:
                        mcdep = ModelComponent(
                            name=mcdep_name,
                            repository_db=self.repository_db,
                            install=install_mcs,
                        )
                        mc_depends_components.append((mcdep, component, grouping))

            # We now need to order any `precedes` model components
            for component, grouping in self.dg.get_ordered_entity_list_with_grouping():
                # Get any preceded model components
                mc_precedes = component.get_model_component_precedes()
                for mcdef_name in mc_precedes:
                    # Get a list of MCs currently in the graph by name
                    # This is easier to verify than by Object
                    mc_list = self.dg.get_ordered_entity_list()
                    cur_mc_list = [mc.name for mc in mc_list]
                    try:
                        # If there is an instance of the preceded MC in the graph
                        # Then we can locate that instance and check to see if
                        # it is already correctly ordered.
                        mc_index = cur_mc_list.index(mcdef_name)
                        mc = mc_list[mc_index]

                        # If the ordering is NOT correct, then we need to build
                        # an association to ensure ordering correctness.
                        if not self.check_list_ordering(
                            mc_list, component.name, mc.name
                        ):
                            self.dg.associate_model_components(component, mc)
                    except ValueError:
                        # If there is not an existing instance of the model component in
                        # the graph. It should be added.
                        mc = ModelComponent(
                            name=mcdef_name,
                            repository_db=self.repository_db,
                            install=install_mcs,
                        )
                        self.dg.insert(mc, grouping, duplicate=False)

                        # Once the new MC is added to the graph, we need to identify
                        # all dependencies within that MC and add them to the
                        # mc_depends_components list.
                        mc_depends = mc.get_model_component_depends()
                        for mcdep_name in mc_depends:
                            mcdep = ModelComponent(
                                name=mcdep_name,
                                repository_db=self.repository_db,
                                install=install_mcs,
                            )
                            mc_depends_components.append((mcdep, mc, grouping))

                        # Finally, we need to add the newly added MC to the mc_depends_components
                        # list and ensure that the loop takes at least one more iteration.
                        mc_depends_components.append((component, mc, grouping))
                        changed = True

                # Get any preceded attributes
                attr_precedes = component.get_attribute_precedes()

                # Iterate through all preceded attributes
                for attr in attr_precedes:
                    mc_list = self.dg.get_ordered_entity_list()
                    cur_mc_list = [mc.name for mc in mc_list]

                    # Get the default MC for the given attribute
                    mc = self.get_default_component_for_attribute(
                        attr, install_mcs=install_mcs
                    )
                    try:
                        # If there is an instance of the preceded MC in the graph
                        # Then we can locate that instance and check to see if
                        # it is already correctly ordered.
                        mc_index = cur_mc_list.index(mc.name)
                        mc = mc_list[mc_index]

                        # If the ordering is NOT correct, then we need to build
                        # an association to ensure ordering correctness.
                        if not self.check_list_ordering(
                            mc_list, component.name, mc.name
                        ):
                            self.dg.associate_model_components(component, mc)
                    except ValueError:
                        # If there is not an existing instance of the model component in
                        # the graph. It should be added.
                        self.dg.insert(mc, grouping, duplicate=False)

                        # Once the new MC is added to the graph, we need to identify
                        # all dependencies within that MC and add them to the
                        # mc_depends_components list.
                        mc_depends = mc.get_model_component_depends()
                        for mcdep_name in mc_depends:
                            mcdep = ModelComponent(
                                name=mcdep_name,
                                repository_db=self.repository_db,
                                install=install_mcs,
                            )
                            mc_depends_components.append((mcdep, component, grouping))

                        # Finally, we need to add the newly added MC to the mc_depends_components
                        # list and ensure that the loop takes at least one more iteration.
                        mc_depends_components.append((component, mc, grouping))
                        changed = True

            # Check for cycles. If one is found our graph cannot be satisfied.
            if self.dg.has_cycles():
                self._dependency_cycle_handler()

    def check_list_ordering(self, cur_mc_list, parent, component):
        """
        This method verifies that a given parent is before a given component
        in the dependency graph.

        Args:
            cur_mc_list (list): The list of model components in which the parent and component
                                are located.
            parent (str): The name of the parent model component.
            component (str): The name of the child model component.

        Raises:
            ValueError: If either `parent` or `component` are not found in the `cur_mc_list`.

        Returns:
            bool: True if the ordering is correct, False if it is not.
        """
        # Get the names from the list of MC objects.
        name_list = [mc.name for mc in cur_mc_list]
        try:
            if name_list.index(parent) > name_list.index(component):
                return False
        except ValueError:
            self.log.exception(
                "There was an error locating either %s or %s in the current list "
                "of model components: %s.",
                parent,
                component,
                name_list,
            )
            raise

        return True

    def _dependency_cycle_handler(self):
        """
        The dependency graph had cycles so we should retrieve those cycles and alert
        the user.

        Raises:
            UnsatisfiableDependenciesError: Output the cycles in the graph.
        """
        all_human_cycles = self.dg.get_cycles()
        all_cycle_graphs = ""
        for cycle in all_human_cycles:
            cdg = nx.DiGraph()
            for node in cycle:
                cdg.add_node(node)

            for i, node in enumerate(cycle[:-1]):
                cdg.add_edge(node, cycle[i + 1])
            cdg.add_edge(cycle[0], cycle[-1])

            for line in nx.generate_network_text(cdg):
                all_cycle_graphs += f"{line}\n"

            all_cycle_graphs += "\n\n"

        # Improving upon the default networkx diagrams
        backedge: str = "╾"
        all_cycle_graphs = all_cycle_graphs.replace(backedge, "◄─")
        all_cycle_graphs = all_cycle_graphs.replace("╼", "►")

        self.log.error(
            "Unsatisfiable dependency graph contained %s cycles", len(all_human_cycles)
        )
        raise UnsatisfiableDependenciesError(
            "Unsatisfiable: Circular dependency relationship(s) found.\n"
            f"Simple cycles:\n{all_cycle_graphs}"
        )

    def _import_model_component_objects(self, path, mc_name):
        """
        This method imports a model components objects file so that it can be added
        to the `sys.modules` path of the experiment.

        Args:
            path (str): The path of the `model_component_objects` file.
            mc_name (str): The name of the model component.

        Raises:
            ImportError: If the file cannot be found or if the model component has
                already been imported.
            ModelComponentImportError: If an ImportError occurs when executing the
                Model Component.
        """
        self.log.debug("Checking for model component objects in %s", (path,))
        spec = importlib.util.spec_from_file_location(mc_name, path)
        if spec is None:
            raise ImportError(f"Model component objects file not found at path {path}.")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except ImportError as exp:
            self.log.exception(exp)
            # Raise our specific error but suppress the previous error.
            # See: https://stackoverflow.com/a/17092033
            traceback.format_exc().splitlines()
            exceptiondata = traceback.format_exc().splitlines()
            raise ModelComponentImportError(mc_name, exceptiondata[-3:]) from None
        except FileNotFoundError as exp:
            raise ImportError(
                f"Specified model component objects file not found: {exp}"
            ) from exp
        # Allow importing objects using "from mc_name import Obj".
        if mc_name in sys.modules:
            raise ImportError(f"Model component has already been imported: {mc_name}")
        sys.modules[mc_name] = module

    def _import_plugin(self, path, mc_name):
        """
        This method imports a model components plugin file so that it can
        be executed.

        Args:
            path (str): The path of the ``Plugin`` file.
            mc_name (str): The name of the model component.

        Returns:
            AbstractPlugin: The plugin class which will be run.

        Raises:
            ImportError: If the file cannot be found or if there are multiple plugins
                in the module.
            ModelComponentImportError: If the Model Component has an import error.
        """
        self.log.debug("Checking for plugin in %s", (path,))
        spec = importlib.util.spec_from_file_location(mc_name, path)
        if spec is None:
            raise ImportError("Plugin file not found.")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except (ImportError, NameError) as exp:
            self.log.exception(exp)
            # Raise our specific error but suppress the previous error.
            # See: https://stackoverflow.com/a/17092033
            traceback.format_exc().splitlines()
            exceptiondata = traceback.format_exc().splitlines()
            raise ModelComponentImportError(mc_name, exceptiondata[-3:]) from None
        except FileNotFoundError as exp:
            raise ImportError(f"Specified plugin file not found: {exp}") from exp

        found_plugin_class = None
        for k in module.__dict__:
            if type(module.__dict__[k]) == type:  # noqa: E721
                if (
                    issubclass(module.__dict__[k], AbstractPlugin)
                    and module.__dict__[k] != AbstractPlugin
                ):
                    if found_plugin_class is None:
                        self.log.debug("Found plugin class %s", k)
                        found_plugin_class = module.__dict__[k]
                    else:
                        raise ImportError(f"Found multiple plugins in module at {path}")

        if found_plugin_class is None:
            raise ImportError(f"No plugin found in module at {path}")

        return found_plugin_class

    def process_model_component(self, mc, experiment_graph, dry_run=False):
        """
        This method helps process model components for execution. It:
        * Uploads/prepares any necessary files (images/vm_resources).
        * Loads any model component objects, if they exist.
        * Loads and runs the plugin, if it exists.

        Args:
            mc (ModelComponent): The model component to process.
            experiment_graph (ExperimentGraph): The experiment graph. This is passed
                to the plugin and also returned by this method.
            dry_run (bool): Indicates whether the model components should be run (:py:data:`False`)
                or simply imported (i.e. checked for syntax errors). Defaults to :py:data:`False`.

        Returns:
            tuple: Tuple containing a bool of whether errors occurred and the
            experiment graph.

        Raises:
            TypeError: If the Plugin doesn't run due to issues with passed-in arguments.
        """
        errors = False

        # Load any model component objects, if they exist.
        self.log.debug(
            "Checking model component objects for model component %s", mc.name
        )
        try:
            unqualified_mc_objs_path = mc.get_model_component_objects_path()
        except RuntimeError:
            self.log.exception(
                "Unable to get model components objects path for model component %s.",
                mc.name,
            )
            errors = True
            return (errors, experiment_graph)
        if unqualified_mc_objs_path:
            mc_objs_path = Path(mc.path) / unqualified_mc_objs_path
            try:
                self._import_model_component_objects(str(mc_objs_path), mc.name)
            except ImportError as exp:
                self.log.exception(
                    "Unable to import model component objects for "
                    "model component %s: %s",
                    mc.name,
                    exp,
                )
                errors = True
                # Return here so we don't attempt to use failed Objects
                return (errors, experiment_graph)

        # Load and run the plugin, if it exists.
        try:
            unqualified_plugin_path = mc.get_plugin_path()
        except RuntimeError:
            self.log.exception(
                "Unable to get plugin path for model component %s.", (mc.name,)
            )
            errors = True
            return (errors, experiment_graph)
        self.log.debug(
            'Checking plugin objects for model component %s at path "%s"',
            mc.name,
            unqualified_plugin_path,
        )
        if unqualified_plugin_path:
            plugin_path = os.path.join(mc.path, unqualified_plugin_path)
            self.log.debug("Loading plugin for entity %s", (mc.name,))
            try:
                plugin_class = self._import_plugin(plugin_path, mc.name)
            except ImportError as exp:
                self.log.exception(
                    "Unable to import plugin for model component %s: %s", mc.name, exp
                )
                errors = True
                # Return here so we don't attempt to run the plugin that just failed
                # import.
                return (errors, experiment_graph)

            # We want all errors from running the plugin (including any ImportError)
            # to propagate up, so don't run this in the try/except block.
            plugin_log = Log(name=mc.name).log
            plugin_instance = plugin_class(experiment_graph, plugin_log)
            if not dry_run:
                plugin_args = mc.arguments["plugin"].copy()
                # Positional arguments should be formatted as a list
                positional_args = plugin_args.pop("", [])
                args = (
                    positional_args
                    if isinstance(positional_args, list)
                    else [positional_args]
                )

                # Keyword arguments are all remaining plugin arguments
                kwargs = plugin_args

                try:
                    plugin_instance.run(*args, **kwargs)
                except TypeError:
                    self._print_plugin_initialization_help(
                        mc.name, plugin_instance, args, kwargs
                    )
                    raise
            experiment_graph = plugin_instance.get_experiment_graph()

        # Upload/prepare any necessary files.
        if not dry_run:
            mc.upload_files()

        return (errors, experiment_graph)

    def _print_plugin_initialization_help(
        self, mc_name, plugin_instance, call_args, call_kwargs
    ):
        """
        Print helpful information when plugin initialization fails.

        Arguments:
            mc_name (str): The model component name.
            plugin_instance (AbstractPlugin): The instance of the MC's Plugin.
            call_args (list): A list of the arguments passed to the Plugin.
            call_kwargs (dict): A dictionary of the key word arguments passed to the Plugin.
        """
        fill_params = {
            "width": 85,
            "initial_indent": 3 * " ",
            "subsequent_indent": 3 * " ",
        }
        filled_args = textwrap.fill(f"{call_args}", **fill_params)
        filled_kwargs = textwrap.fill(f"{call_kwargs}", **fill_params)
        filled_sig = textwrap.fill(
            f"{inspect.signature(plugin_instance.run)}", **fill_params
        )

        console = Console()
        console.print(
            "\n\n[b red]Failed to initialize the plugin for model component "
            f"[magenta]{mc_name}[/magenta]."
            f"\n[yellow]Arguments:\n[magenta]{filled_args}[/magenta]"
            f"\nKeyword Arguments:\n[magenta]{filled_kwargs}[/magenta]"
            "\n\nThe expected initialization signature for the plugin is:"
            f"\n[cyan]{filled_sig}[/cyan]"
        )

    def build_experiment_graph(self, dry_run=False):
        """
        Builds the experiment graph by processing all the model components

        Args:
            dry_run (bool): Indicates whether the model components should be run (:py:data:`False`)
                or simply imported (i.e. checked for syntax errors). Defaults to :py:data:`False`.

        Returns:
            list: A list of errors that were reported when trying to execute.


        Raises:
            InvalidStateError: If the dependency graph does not exist.
        """
        errors_list = []
        if self.dg is None:
            raise InvalidStateError("No dependency graph generated yet.")
        experiment_graph = None

        for mc in self.get_ordered_model_component_list():
            self.log.debug("Processing model component %s", mc.name)
            start = datetime.now()
            error, experiment_graph = self.process_model_component(
                mc, experiment_graph, dry_run
            )
            end = datetime.now()
            errors_list.append(
                {
                    "model_component": mc.name,
                    "errors": error,
                    "time": (end - start).total_seconds(),
                }
            )

        return errors_list
