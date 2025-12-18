import networkx as nx

from firewheel.lib.log import Log
from firewheel.control.model_component import ModelComponent
from firewheel.control.dependency_graph import (
    DependencyGraph,
    InvalidNodeError,
    UnsatisfiableDependenciesError,
)


class ModelComponentDependencyGraph(DependencyGraph):
    """
    This class provides a specific implementation of `DependencyGraph()` which is
    made for tracking Model Component dependencies.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize `DependencyGraph()` and our logger.

        Args:
            *args: Positional arguments that will be passed into `DependencyGraph()`.
            **kwargs: Keyword arguments that will be passed into `DependencyGraph()`.
        """
        super().__init__(*args, **kwargs)

        self.component_map = {}
        self.grouping_map = {}

        self.log = Log(name="ModelComponentDependencyGraph").log

    def insert(self, model_component, grouping, duplicate=False):
        """
        Insert a ModelComponent into the graph.

        Args:
            model_component (ModelComponent): The model component to insert.
            grouping (int): The model component's grouping.
            duplicate (bool): If the model component is a duplicate.

        Returns:
            bool: True if insertion was successful, False otherwise.

        Raises:
            ValueError: If the passed in `model_component` is not an instance
                of `ModelComponent()`.
        """
        if not isinstance(model_component, ModelComponent):
            raise ValueError(
                "Invalid type for model_component parameter. "
                "Must be ModelComponent (or subclass)."
            )

        if not duplicate:
            if self.count_model_component_occurrences(model_component) > 0:
                self.log.debug(
                    'Not inserting duplicate ModelComponent "%s".', model_component.name
                )
                return False

        depends, provides, _precedes = model_component.get_attributes()
        comp_id = self.insert_entity(depends, provides, grouping)
        model_component.set_dependency_graph_id(comp_id)
        self.component_map[comp_id] = model_component
        self.grouping_map[comp_id] = grouping
        return True

    def count_model_component_occurrences(self, model_component):  # pylint: disable=invalid-name
        """
        Count the number of times a model component occurs in the `component_map`.

        Args:
            model_component (ModelComponent): The model component to count.

        Returns:
            int: The number of ModelComponent's of the same name are present
            in this dependency graph.
        """
        counter = 0
        for value in self.component_map.values():
            if value == model_component:
                counter += 1
        return counter

    def associate_model_components(self, prev_component, component):
        """
        Create a relationship between two model components in the graph.
        A directional edge will be created like: `component ---> prev_component`.
        A component may not have actually been added to the dependency
        graph (for example it was already present). In this case,
        make sure to fill in some missing info we need.

        Args:
            prev_component (ModelComponent): The predecessor in the graph.
            component (ModelComponent): The current node.

        Raises:
            InvalidNodeError: If the dependency graph ID for one of the
                inputs is not found.
        """
        try:
            self.associate_entities(
                prev_component.get_dependency_graph_id(),
                component.get_dependency_graph_id(),
            )
        except InvalidNodeError as exp:
            self.log.error(
                "Could not find dependency graph ID for model "
                "component that should have been present."
            )
            raise InvalidNodeError("Lost a dependency graph ID.") from exp

    def get_ordered_entity_list(self):
        """
        Return a list of entities in dependency-valid canonical order. For a
        given graph, the order returned is always the same--lexicographical
        order is used.

        Returns:
            list: ModelComponents in canonical, dependency-satisfying order.
        """
        try:
            return [
                self.component_map[node_id]
                for node_id in super().get_ordered_entity_list()
            ]
        except nx.HasACycle:
            self.dependency_cycle_handler()

    def get_ordered_entity_list_with_grouping(self):
        """
        Return a list of tuples (entity, grouping) in dependency-valid canonical order. For a
        given graph, the order returned is always the same--lexicographical
        order is used.

        Returns:
            list: (ModelComponent, grouping) in canonical, dependency-satisfying order.
        """
        try:
            return [
                (self.component_map[node_id], self.grouping_map[node_id])
                for node_id in super().get_ordered_entity_list()
            ]
        except nx.HasACycle:
            self.dependency_cycle_handler()

    def get_first(self, model_component):
        """
        Get the first time a model component is found in the
        ordered list of dependencies.

        Args:
            model_component (ModelComponent): The model component to find.

        Returns:
            ModelComponent: The instance of the ModelComponent which matches
            model_component.name. This is None if none are found.
        """
        ordered_list = self.get_ordered_entity_list()
        for comp in ordered_list:
            if comp.name == model_component.name:
                return comp
        return None

    def dependency_cycle_handler(self):
        """
        The dependency graph had cycles so we should retrieve those cycles and alert
        the user.

        Raises:
            UnsatisfiableDependenciesError: Output the cycles in the graph.
        """
        all_human_cycles = self.get_cycles()
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

    def get_cycles(self):
        """
        Try to identify all the cycles in the DiGraph that could be created by
        a user. These errors are then logged.

        Returns:
            list: A list of cycles created by a user.
        """
        all_human_cycles = []
        for cycle in nx.simple_cycles(self.dg):
            human_cycle = []
            for element in cycle:
                if isinstance(element, str):
                    human_cycle.append(
                        str(f"[magenta]{element}[/magenta] [cyan](Attribute)[/cyan]")
                    )
                else:
                    human_cycle.append(
                        str(
                            f"[magenta]{self.component_map[element].name}[/magenta] "
                            "[cyan](Model Component)[/cyan]"
                        )
                    )
            self.log.error("Circular dependency detected: %s", human_cycle)
            all_human_cycles.append(human_cycle)
        return all_human_cycles
