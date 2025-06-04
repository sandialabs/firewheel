import json

import networkx as nx
from networkx.readwrite import json_graph


class InvalidNodeError(Exception):
    """Exception thrown if the Node is not found"""


class UnsatisfiableDependenciesError(Exception):
    """Exception thrown if there are dependencies that cannot be met."""


class TopologicalCompare:
    """
    A class to enable custom sorting when using networkx's
    ``lexicographical_topological_sort``. Nodes are first sorted based on their
    model component group number (integer comparison). If those are equal, we
    sort based on their node ID (str comparison).

    Note:
        Only the ``__lt__`` function is needed for sorting, not ``__gt__``.
    """

    def __init__(self, grouping, node):
        """
        Initialize the comparison object.

        Args:
            grouping (int): The grouping of model components' dependencies.
            node (str|int): The node ID
        """
        self.grouping = grouping
        self.node = node

    def __lt__(self, other):
        """
        Function to perform custom comparison for ``<`` operator. Nodes are first
        sorted based on their model component group number (integer
        comparison). If those are equal, we sort based on their node ID (str
        comparison).

        Args:
            other (TopologicalCompare): The other node to compare to.

        Returns:
            bool: True if self is less than other.
        """
        if self.grouping < other.grouping:
            return True
        if self.grouping > other.grouping:
            return False

        # Groups are equal, compare node this time
        if str(self.node) < str(other.node):
            return True
        return False


class DependencyGraph:
    """
    A dependency graph. The graph consists of two vertex types: entities and
    constraints. Each entity may depend on a set of constraints and provide
    a set of constraints. Entities may additionally be "associated" or ordered
    among other entities. The dependencies represented may be satisfied as long
    as there are no cycles in the graph.

    The end goal of the data structure is to produce a list of entities in a
    canonicalized order which satisfies all constraints. This is done with the
    `get_ordered_entity_list()` method.

    Entities are represented using an arbitrary identifier which is returned to
    the caller when they are created. Constraints are represented using strings
    (names).
    """

    def __init__(self):
        """
        Initialize the dependency graph by creating a new networkx DiGraph.
        """
        self.dg = nx.DiGraph()

        self.entity_type = "entity"
        self.constraint_type = "constraint"

    def insert_entity(self, depends, provides, grouping):
        """
        Add an entity to the graph with associated constraints.

        Args:
            depends (list): Iterable of constraint names the entity depends on.
            provides (list): Iterable of constraint names the entity provides.
            grouping (int): The grouping of model components' dependencies.

        Returns:
            int: Identifier for the created entity.
        """
        entity_id = self.dg.number_of_nodes() + 1
        self.dg.add_node(entity_id, type=self.entity_type, grouping=grouping)
        for dependency in depends:
            self.dg.add_edge(dependency, entity_id)
            self.dg.nodes[dependency]["type"] = self.constraint_type
            self.dg.nodes[dependency]["grouping"] = grouping
        for provide in provides:
            self.dg.add_edge(entity_id, provide)
            self.dg.nodes[provide]["type"] = self.constraint_type
            self.dg.nodes[provide]["grouping"] = grouping

        return entity_id

    def associate_entities(self, source, dest):
        """
        Associate two entities with a directional relationship.

        Args:
            source (int): Identifier of the entity at the source of the relationship.
            dest (int): Identifier of the entity at the destination of the relationship.

        Raises:
            InvalidNodeError: If the node is not a valid type or not found.
        """
        try:
            if self.dg.nodes[source]["type"] != self.entity_type:
                raise InvalidNodeError(f"Identifier {source!s} is not an entity.")
        except KeyError as exp:
            raise InvalidNodeError(f"Identifier {source!s} does not exist.") from exp
        try:
            if self.dg.nodes[dest]["type"] != self.entity_type:
                raise InvalidNodeError(f"Identifier {dest!s} is not an entity.")
        except KeyError as exp:
            raise InvalidNodeError(f"Identifier {dest!s} does not exist.") from exp
        self.dg.add_edge(source, dest)

    def get_in_degree_zero_constraints(self):
        """
        Retrieve a list of all constraints that have an in-degree of zero.

        Returns:
            list: Constraint IDs for constraint vertices with in-degree zero.
        """
        zero_deg_list = []

        for node_id, in_degree in self.dg.in_degree:
            if (
                in_degree == 0
                and self.dg.nodes[node_id]["type"] == self.constraint_type
            ):
                zero_deg_list.append((node_id, self.dg.nodes[node_id]["grouping"]))

        return zero_deg_list

    def topological_compare(self, node):
        """
        Comparison function for the 'key' parameter of networkx's
        lexicographical_topological_sort function.

        The node IDs are a mix of strings and integers and the
        value for grouping is not unique, therefore simply comparing
        the grouping value is not enough information to make a unique
        sorting decision. Therefore, prepend the grouping ID to the
        node ID so that when the grouping ID is the same, the comparison
        returns to the default of comparing the node IDs as strings.

        Args:
            node (int): A node ID from the graph

        Returns:
            str: A unique key that can be used for sorting nodes
        """
        return TopologicalCompare(self.dg.nodes[node]["grouping"], node)

    def get_ordered_entity_list(self):
        """
        Return a list of entities in dependency-valid canonical order. For a
        given graph, the order returned is always the same--lexicographical
        order is used.

        Returns:
            list: Entity IDs in canonical, dependency-satisfying order.

        Raises:
            UnsatisfiableDependenciesError: Occurs if there are cycles.
        """
        entity_ordering = []
        # Raises UnsatisfiableDependenciesError if there are cycles.
        # Lambda allows ordering of mixed ints and strings by making everything a string.
        try:
            for node_id in nx.algorithms.lexicographical_topological_sort(
                self.dg, self.topological_compare
            ):
                if self.dg.nodes[node_id]["type"] == self.entity_type:
                    entity_ordering.append(node_id)
        except nx.NetworkXUnfeasible as exp:
            raise UnsatisfiableDependenciesError from exp

        return entity_ordering

    def has_cycles(self):
        """
        Determine if cycles exist in the graph.

        Returns:
            bool: True if cycles exist.
        """
        return not nx.is_directed_acyclic_graph(self.dg)

    def get_graph_json(self):
        """
        Return a JSON formatted string representation of the graph. The
        representation is based on the D3 nodes-links format with links
        referencing node ID rather than list position.

        Returns:
            str: Has the following format::

            {
                "nodes": [
                    {"id": <id>, "type": <"entity" or "constraint">},
                    ...
                ],
                "edges": [
                    {"source": <id>, "target": <id>},
                    ...
                ],
                "graph": {},
                "directed": True,
                "multigraph": False
            }
        """
        data = json_graph.node_link_data(self.dg, edges="edges")

        nodes = {}
        for node in data["nodes"]:
            nodes[node["id"]] = node

        for edge in data["edges"]:
            edge["source"] = nodes[edge["source"]]["id"]
            edge["target"] = nodes[edge["target"]]["id"]

        return json.dumps(data)
