# pylint: disable=invalid-name

import json
import unittest

import networkx as nx

from firewheel.tests.unit.test_utils import compare_graph_structures
from firewheel.control.dependency_graph import (
    DependencyGraph,
    InvalidNodeError,
)


# pylint: disable=unused-variable
class DependencyGraphTestCase(unittest.TestCase):
    def setUp(self):
        self.dependencyGraph = DependencyGraph()

    def tearDown(self):
        pass

    def test_insert_entity(self):
        depends = ["test_depends1", "test_depends2"]
        provides = ["test_provides1", "test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends, provides, 0)

        self.assertEqual(id1, 1)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": "test_depends1", "type": "constraint", "grouping": 0},
                {"id": "test_depends2", "type": "constraint", "grouping": 0},
                {"id": "test_provides1", "type": "constraint", "grouping": 0},
                {"id": "test_provides2", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": "test_depends1", "target": 1},
                {"source": "test_depends2", "target": 1},
                {"source": 1, "target": "test_provides1"},
                {"source": 1, "target": "test_provides2"},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))
        self.assertFalse(self.dependencyGraph.has_cycles())

    # Make sure we don't duplicate constraints.
    def test_insert_entity_twice(self):
        depends = ["test_depends1", "test_depends2"]
        provides = ["test_provides1", "test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends, provides, 0)
        self.assertEqual(id1, 1)

        depends = ["test_depends1", "test_depends2"]
        provides = ["test_provides1", "test_provides2"]
        id2 = self.dependencyGraph.insert_entity(depends, provides, 0)
        self.assertEqual(id2, 6)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 6, "type": "entity", "grouping": 0},
                {"id": "test_depends1", "type": "constraint", "grouping": 0},
                {"id": "test_depends2", "type": "constraint", "grouping": 0},
                {"id": "test_provides1", "type": "constraint", "grouping": 0},
                {"id": "test_provides2", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": "test_depends1", "target": 1},
                {"source": "test_depends2", "target": 1},
                {"source": "test_depends1", "target": 6},
                {"source": "test_depends2", "target": 6},
                {"source": 1, "target": "test_provides1"},
                {"source": 1, "target": "test_provides2"},
                {"source": 6, "target": "test_provides1"},
                {"source": 6, "target": "test_provides2"},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))
        self.assertFalse(self.dependencyGraph.has_cycles())

    def test_associate_entities(self):
        depends1 = ["test_depends1"]
        depends2 = []
        provides1 = ["test_provides1"]
        provides2 = ["test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)

        self.dependencyGraph.associate_entities(id1, id2)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 4, "type": "entity", "grouping": 0},
                {"id": "test_depends1", "type": "constraint", "grouping": 0},
                {"id": "test_provides1", "type": "constraint", "grouping": 0},
                {"id": "test_provides2", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": "test_depends1", "target": 1},
                {"source": 1, "target": "test_provides1"},
                {"source": 4, "target": "test_provides2"},
                {"source": 1, "target": 4},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))
        self.assertFalse(self.dependencyGraph.has_cycles())

    def test_associate_invalid_source_entity(self):
        depends1 = ["test_depends1"]
        depends2 = []
        provides1 = ["test_provides1"]
        provides2 = ["test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)
        invalid_id = 42

        with self.assertRaises(InvalidNodeError):
            self.dependencyGraph.associate_entities(invalid_id, id2)

    def test_associate_source_constraint(self):
        depends1 = ["test_depends1"]
        depends2 = []
        provides1 = ["test_provides1"]
        provides2 = ["test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)

        with self.assertRaises(InvalidNodeError):
            self.dependencyGraph.associate_entities("test_provides1", id2)

    def test_associate_invalid_dest_entity(self):
        depends1 = ["test_depends1"]
        depends2 = []
        provides1 = ["test_provides1"]
        provides2 = ["test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841
        invalid_id = 42

        with self.assertRaises(InvalidNodeError):
            self.dependencyGraph.associate_entities(id1, invalid_id)

    def test_associate_dest_constraint(self):
        depends1 = ["test_depends1"]
        depends2 = []
        provides1 = ["test_provides1"]
        provides2 = ["test_provides2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841

        with self.assertRaises(InvalidNodeError):
            self.dependencyGraph.associate_entities(id1, "test_provides1")

    def test_insert_one_element_cycle(self):
        depends = ["test_depends_cycler"]
        provides = ["test_depends_cycler"]

        self.dependencyGraph.insert_entity(depends, provides, 0)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": "test_depends_cycler", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": "test_depends_cycler", "target": 1},
                {"source": 1, "target": "test_depends_cycler"},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))
        self.assertTrue(self.dependencyGraph.has_cycles())

    def test_insert_two_element_cycle(self):
        depends = ["test_depends_cycler"]
        provides = ["test_provides_cycler"]

        self.dependencyGraph.insert_entity(depends, provides, 0)
        self.dependencyGraph.insert_entity(provides, depends, 0)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 4, "type": "entity", "grouping": 0},
                {"id": "test_depends_cycler", "type": "constraint", "grouping": 0},
                {"id": "test_provides_cycler", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": "test_depends_cycler", "target": 1},
                {"source": 1, "target": "test_provides_cycler"},
                {"source": "test_provides_cycler", "target": 4},
                {"source": 4, "target": "test_depends_cycler"},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))
        self.assertTrue(self.dependencyGraph.has_cycles())

    def test_zero_zero_in_degree_constraints(self):
        depends1 = []
        depends2 = ["c1"]
        provides1 = ["c1"]
        provides2 = ["c2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 3, "type": "entity", "grouping": 0},
                {"id": "c1", "type": "constraint", "grouping": 0},
                {"id": "c2", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": 1, "target": "c1"},
                {"source": "c1", "target": 3},
                {"source": 3, "target": "c2"},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))

        zl = self.dependencyGraph.get_in_degree_zero_constraints()
        self.assertEqual(len(zl), 0)

    def test_one_zero_in_degree_constraints(self):
        depends1 = []
        depends2 = ["c1", "c3"]
        provides1 = ["c1"]
        provides2 = ["c2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 3, "type": "entity", "grouping": 0},
                {"id": "c1", "type": "constraint", "grouping": 0},
                {"id": "c2", "type": "constraint", "grouping": 0},
                {"id": "c3", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": 1, "target": "c1"},
                {"source": "c1", "target": 3},
                {"source": 3, "target": "c2"},
                {"source": "c3", "target": 3},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))

        zl = self.dependencyGraph.get_in_degree_zero_constraints()
        self.assertEqual(len(zl), 1)

    def test_two_zero_in_degree_constraints(self):
        depends1 = ["c4"]
        depends2 = ["c1", "c3"]
        provides1 = ["c1"]
        provides2 = ["c2"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 4, "type": "entity", "grouping": 0},
                {"id": "c1", "type": "constraint", "grouping": 0},
                {"id": "c2", "type": "constraint", "grouping": 0},
                {"id": "c3", "type": "constraint", "grouping": 0},
                {"id": "c4", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": 1, "target": "c1"},
                {"source": "c1", "target": 4},
                {"source": 4, "target": "c2"},
                {"source": "c3", "target": 4},
                {"source": "c4", "target": 1},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))

        zl = self.dependencyGraph.get_in_degree_zero_constraints()
        self.assertEqual(len(zl), 2)

    def test_ordered_entity_list_with_cycle(self):
        depends = ["test_depends_cycler"]
        provides = ["test_provides_cycler"]

        self.dependencyGraph.insert_entity(depends, provides, 0)
        self.dependencyGraph.insert_entity(provides, depends, 0)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": 4, "type": "entity", "grouping": 0},
                {"id": "test_depends_cycler", "type": "constraint", "grouping": 0},
                {"id": "test_provides_cycler", "type": "constraint", "grouping": 0},
            ],
            "links": [
                {"source": "test_depends_cycler", "target": 1},
                {"source": 1, "target": "test_provides_cycler"},
                {"source": "test_provides_cycler", "target": 4},
                {"source": 4, "target": "test_depends_cycler"},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))
        self.assertTrue(self.dependencyGraph.has_cycles())
        with self.assertRaises(nx.HasACycle):
            self.dependencyGraph.get_ordered_entity_list()

    def test_ordered_entity_list(self):
        depends1 = []
        provides1 = ["c1"]
        depends2 = ["c1"]
        provides2 = ["c2"]
        depends3 = ["c1"]
        provides3 = []
        depends4 = ["c3"]
        provides4 = ["c4"]
        depends5 = ["c1"]
        provides5 = []
        depends6 = ["c5"]
        provides6 = ["c6"]
        depends7 = ["c4"]
        provides7 = ["c5"]
        depends8 = ["c2"]
        provides8 = ["c3"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)
        id3 = self.dependencyGraph.insert_entity(depends3, provides3, 0)
        id4 = self.dependencyGraph.insert_entity(depends4, provides4, 0)
        id5 = self.dependencyGraph.insert_entity(depends5, provides5, 0)
        id6 = self.dependencyGraph.insert_entity(depends6, provides6, 0)
        id7 = self.dependencyGraph.insert_entity(depends7, provides7, 0)
        id8 = self.dependencyGraph.insert_entity(depends8, provides8, 0)

        self.dependencyGraph.associate_entities(id2, id3)
        self.dependencyGraph.associate_entities(id3, id4)
        self.dependencyGraph.associate_entities(id4, id5)
        self.dependencyGraph.associate_entities(id5, id6)

        expected_structure = {
            "nodes": [
                {"id": 1, "type": "entity", "grouping": 0},
                {"id": "c1", "type": "constraint", "grouping": 0},
                {"id": 3, "type": "entity", "grouping": 0},
                {"id": "c2", "type": "constraint", "grouping": 0},
                {"id": 5, "type": "entity", "grouping": 0},
                {"id": 6, "type": "entity", "grouping": 0},
                {"id": "c3", "type": "constraint", "grouping": 0},
                {"id": "c4", "type": "constraint", "grouping": 0},
                {"id": 9, "type": "entity", "grouping": 0},
                {"id": 10, "type": "entity", "grouping": 0},
                {"id": "c5", "type": "constraint", "grouping": 0},
                {"id": "c6", "type": "constraint", "grouping": 0},
                {"id": 13, "type": "entity", "grouping": 0},
                {"id": 14, "type": "entity", "grouping": 0},
            ],
            "links": [
                {"source": 1, "target": "c1"},
                {"source": "c1", "target": 3},
                {"source": 3, "target": "c2"},
                {"source": "c1", "target": 5},
                {"source": "c3", "target": 6},
                {"source": 6, "target": "c4"},
                {"source": "c1", "target": 9},
                {"source": "c5", "target": 10},
                {"source": 10, "target": "c6"},
                {"source": "c4", "target": 13},
                {"source": 13, "target": "c5"},
                {"source": "c2", "target": 14},
                {"source": 14, "target": "c3"},
                {"source": 3, "target": 5},
                {"source": 5, "target": 6},
                {"source": 6, "target": 9},
                {"source": 9, "target": 10},
            ],
            "graph": {},
            "directed": True,
            "multigraph": False,
        }

        json_str = self.dependencyGraph.get_graph_json()
        actual_structure = json.loads(json_str)

        self.assertTrue(compare_graph_structures(expected_structure, actual_structure))

        expected_entity_list = [id1, id2, id3, id8, id4, id5, id7, id6]
        actual_entity_list = self.dependencyGraph.get_ordered_entity_list()
        self.assertEqual(expected_entity_list, actual_entity_list)

    def test_add_entity_while_sorting(self):
        depends1 = []
        provides1 = ["c1"]
        depends2 = ["c1"]
        provides2 = ["c2"]
        depends3 = ["c1"]
        provides3 = []
        depends4 = ["c3"]
        provides4 = ["c4"]
        depends5 = ["c1"]
        provides5 = []
        depends6 = ["c5"]
        provides6 = ["c6"]
        depends7 = ["c4"]
        provides7 = ["c5"]
        depends8 = ["c2"]
        provides8 = ["c3"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841
        id3 = self.dependencyGraph.insert_entity(depends3, provides3, 0)  # noqa: F841
        id4 = self.dependencyGraph.insert_entity(depends4, provides4, 0)  # noqa: F841
        id5 = self.dependencyGraph.insert_entity(depends5, provides5, 0)  # noqa: F841
        id6 = self.dependencyGraph.insert_entity(depends6, provides6, 0)  # noqa: F841
        id7 = self.dependencyGraph.insert_entity(depends7, provides7, 0)  # noqa: F841
        id8 = self.dependencyGraph.insert_entity(depends8, provides8, 0)  # noqa: F841

        self.dependencyGraph.associate_entities(id2, id3)
        self.dependencyGraph.associate_entities(id3, id4)
        self.dependencyGraph.associate_entities(id4, id5)
        self.dependencyGraph.associate_entities(id5, id6)

        with self.assertRaises(RuntimeError):
            # pylint: disable=unnecessary-lambda
            for _node_id in nx.algorithms.lexicographical_topological_sort(
                self.dependencyGraph.dg, lambda x: str(x)
            ):
                self.dependencyGraph.insert_entity(
                    ["c1", "c2", "c3", "c4", "c5", "c6"],
                    ["c1", "c2", "c3", "c4", "c5", "c6"],
                    0,
                )

    def test_remove_entity_while_sorting(self):
        depends1 = []
        provides1 = ["c1"]
        depends2 = ["c1"]
        provides2 = ["c2"]
        depends3 = ["c1"]
        provides3 = []
        depends4 = ["c3"]
        provides4 = ["c4"]
        depends5 = ["c1"]
        provides5 = []
        depends6 = ["c5"]
        provides6 = ["c6"]
        depends7 = ["c4"]
        provides7 = ["c5"]
        depends8 = ["c2"]
        provides8 = ["c3"]

        id1 = self.dependencyGraph.insert_entity(depends1, provides1, 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity(depends2, provides2, 0)  # noqa: F841
        id3 = self.dependencyGraph.insert_entity(depends3, provides3, 0)  # noqa: F841
        id4 = self.dependencyGraph.insert_entity(depends4, provides4, 0)  # noqa: F841
        id5 = self.dependencyGraph.insert_entity(depends5, provides5, 0)  # noqa: F841
        id6 = self.dependencyGraph.insert_entity(depends6, provides6, 0)  # noqa: F841
        id7 = self.dependencyGraph.insert_entity(depends7, provides7, 0)  # noqa: F841
        id8 = self.dependencyGraph.insert_entity(depends8, provides8, 0)  # noqa: F841

        self.dependencyGraph.associate_entities(id2, id3)
        self.dependencyGraph.associate_entities(id3, id4)
        self.dependencyGraph.associate_entities(id4, id5)
        self.dependencyGraph.associate_entities(id5, id6)

        delif = self.dependencyGraph.insert_entity([], ["c6"], 0)

        with self.assertRaises(RuntimeError):
            counter = 0
            # pylint: disable=unnecessary-lambda
            for _node_id in nx.algorithms.lexicographical_topological_sort(
                self.dependencyGraph.dg, lambda x: str(x)
            ):
                if counter == 0:
                    self.dependencyGraph.dg.remove_node(delif)
                counter += 1

    def test_sort_with_default_key(self):
        id1 = self.dependencyGraph.insert_entity([100], [200], 0)  # noqa: F841
        id2 = self.dependencyGraph.insert_entity([200], [300], 0)  # noqa: F841

        expected_list = [100, 1, 200, 4, 300]
        actual_list = []
        for x in nx.algorithms.lexicographical_topological_sort(
            self.dependencyGraph.dg
        ):
            actual_list.append(x)

        self.assertEqual(expected_list, actual_list)
