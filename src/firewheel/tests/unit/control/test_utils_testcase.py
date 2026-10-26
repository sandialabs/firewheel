# pylint: disable=invalid-name

import unittest

from firewheel.tests.unit.test_utils import compare_graph_structures


class TestUtilsTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_empty(self):
        with self.assertRaises(ValueError):
            compare_graph_structures({}, {})
        with self.assertRaises(ValueError):
            compare_graph_structures({"nodes": [], "edges": []}, {})

    def test_simple_equal(self):
        a = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
            "other2": "val2",
        }
        b = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
            "other2": "val2",
        }

        self.assertTrue(compare_graph_structures(a, b))

    def test_equal_odd_lists(self):
        a = {
            "nodes": [{"key1": 1}, {"key2": 2}],
            "edges": [{"k1": 1, "k2": 2}],
            "other1": "val1",
            "other2": "val2",
        }
        b = {
            "nodes": [{"key1": 1}, {"key2": 2}],
            "edges": [{"k1": 1, "k2": 2}],
            "other1": "val1",
            "other2": "val2",
        }

        self.assertTrue(compare_graph_structures(a, b))

    def test_different_nodes(self):
        a = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
            "other2": "val2",
        }
        b = {
            "nodes": [{"id": 1}, {"id": 3}],
            "edges": [{"source": 1, "target": 3}],
            "other1": "val1",
            "other2": "val2",
        }
        c = {
            "nodes": [{"id": 1}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
            "other2": "val2",
        }

        self.assertFalse(compare_graph_structures(a, b))
        # pylint: disable=arguments-out-of-order
        self.assertFalse(compare_graph_structures(b, a))

        self.assertFalse(compare_graph_structures(b, c))
        self.assertFalse(compare_graph_structures(c, b))

    def test_different_edges(self):
        a = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
            "other2": "val2",
        }
        b = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [],
            "other1": "val1",
            "other2": "val2",
        }
        c = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}, {"source": 2, "target": 1}],
            "other1": "val1",
            "other2": "val2",
        }

        self.assertFalse(compare_graph_structures(a, b))
        # pylint: disable=arguments-out-of-order
        self.assertFalse(compare_graph_structures(b, a))

        self.assertFalse(compare_graph_structures(a, c))
        self.assertFalse(compare_graph_structures(c, a))

    def test_different_other(self):
        a = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
            "other2": "val2",
        }
        b = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "other_val",
            "other2": "val2",
        }
        c = {
            "nodes": [{"id": 1}, {"id": 2}],
            "edges": [{"source": 1, "target": 2}],
            "other1": "val1",
        }

        self.assertFalse(compare_graph_structures(a, b))
        # pylint: disable=arguments-out-of-order
        self.assertFalse(compare_graph_structures(b, a))

        self.assertFalse(compare_graph_structures(a, c))
        self.assertFalse(compare_graph_structures(c, a))
