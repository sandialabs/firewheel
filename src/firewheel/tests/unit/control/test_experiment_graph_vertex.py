# pylint: disable=invalid-name

import unittest

from firewheel.control.experiment_graph import Edge, Vertex, ExperimentGraph


# pylint: disable=comparison-with-itself,unused-variable
class ExperimentGraphVertexTestCase(unittest.TestCase):
    def setUp(self):
        self.g = ExperimentGraph()

    def tearDown(self):
        pass

    def test_create(self):
        v = Vertex(self.g)
        self.assertNotEqual(v, None)
        self.assertTrue(isinstance(v.graph_id, int))
        self.assertEqual(v.graph_id, 1)

    def test_attribute(self):
        v = Vertex(self.g)
        v["name"] = "test"
        self.assertEqual(v["name"], "test")

    def test_name(self):
        v = Vertex(self.g, name="test")
        self.assertEqual(v.name, "test")

    def test_overwrite_attribute(self):
        v = Vertex(self.g)
        v["name"] = "test"
        self.assertEqual(v["name"], "test")
        v["name"] = "overwritten"
        self.assertEqual(v["name"], "overwritten")

    def test_get_invalid_attribute(self):
        v = Vertex(self.g)
        with self.assertRaises(KeyError):
            # pylint: disable=pointless-statement
            v["name"]

    def test_get(self):
        v = Vertex(self.g)
        self.assertIsNone(v.get("name"))

        v["name"] = "test"
        self.assertEqual(v.get("name"), "test")

    def test_get_alternate_default(self):
        v = Vertex(self.g)
        self.assertEqualNone(v.get("name", default="test"), "test")

    def test_has(self):
        v = Vertex(self.g)
        self.assertFalse("name" in v)
        self.assertFalse(v.has("name"))

        v["name"] = "test"
        self.assertTrue("name" in v)
        self.assertTrue(v.has("name"))

    def test_str(self):
        v = Vertex(self.g)
        expected_str = "{"
        for i in range(10):
            if expected_str != "{":
                expected_str += "\n "
            v[f"field{i}"] = f"val{i}"
            expected_str += f"'field{i}': 'val{i}',"
        expected_str += "\n}"

        actual_str = str(v)
        # We cannot predict the address given for the object reference, so
        # compare the other lines and ignore that one.
        position = 0
        expected_lines = expected_str.split("\n")
        for line in actual_str.split("\n"):
            if line.strip().startswith("'object'"):
                continue
            self.assertEqual(expected_lines[position], line)
            position += 1

    def test_same_graph_eq(self):
        v1 = Vertex(self.g)
        v3 = Vertex(self.g)

        self.assertFalse(v1 == self.g)

        self.assertTrue(v1 == v1)
        self.assertFalse(v1 != v1)

        self.assertTrue(v1 != v3)
        self.assertFalse(v1 == v3)

        self.assertIsNotNone(v1)

    def test_different_graph_eq(self):
        v1 = Vertex(self.g)
        g2 = ExperimentGraph()
        v2 = Vertex(g2)

        self.assertEqual(v1.graph_id, v2.graph_id)
        self.assertFalse(v1 == v2)
        self.assertTrue(v1 != v2)

    def test_get_neighbors(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)
        v3 = Vertex(self.g)
        v4 = Vertex(self.g)

        expected_list = [v2, v3]
        e1 = Edge(v1, v2)  # noqa: F841
        e2 = Edge(v1, v3)  # noqa: F841
        e3 = Edge(v3, v4)  # noqa: F841

        actual_list = []
        for v in v1.get_neighbors():
            actual_list.append(v)

        # Unsorted lists.
        self.assertEqual(len(expected_list), len(actual_list))
        for val in expected_list:
            self.assertTrue(val in actual_list)
        for val in actual_list:
            self.assertTrue(val in expected_list)

    def test_degree(self):
        v1 = Vertex(self.g)
        self.assertEqual(v1.get_degree(), 0)

        v2 = Vertex(self.g)
        self.assertEqual(v1.get_degree(), 0)
        self.assertEqual(v2.get_degree(), 0)

        e1 = Edge(v1, v2)  # noqa: F841
        self.assertEqual(v1.get_degree(), 1)
        self.assertEqual(v2.get_degree(), 1)

        v3 = Vertex(self.g)
        self.assertEqual(v1.get_degree(), 1)
        self.assertEqual(v2.get_degree(), 1)
        self.assertEqual(v3.get_degree(), 0)

        e2 = Edge(v1, v3)  # noqa: F841
        self.assertEqual(v1.get_degree(), 2)
        self.assertEqual(v2.get_degree(), 1)
        self.assertEqual(v3.get_degree(), 1)

    def test_delete(self):
        v1 = Vertex(self.g)

        counter = 0
        for _ in self.g.get_vertices():
            counter += 1
        self.assertEqual(counter, 1)

        self.assertEqual(v1.valid, True)
        v1.delete()
        counter = 0
        for _ in self.g.get_vertices():
            counter += 1
        self.assertEqual(counter, 0)

        self.assertEqual(v1.valid, False)
        with self.assertRaises(RuntimeError):
            v1.get_object()
        with self.assertRaises(RuntimeError):
            v1.keys()
        with self.assertRaises(RuntimeError):
            # pylint: disable=unnecessary-dunder-call
            v1.__getitem__(None)
        with self.assertRaises(RuntimeError):
            # pylint: disable=unnecessary-dunder-call
            v1.__setitem__(None, None)
        with self.assertRaises(RuntimeError):
            v1.has(None)
        with self.assertRaises(RuntimeError):
            # pylint: disable=unnecessary-dunder-call
            v1.__contains__(None)
        with self.assertRaises(RuntimeError):
            v1.get_neighbors()
        with self.assertRaises(RuntimeError):
            str(v1)
        with self.assertRaises(RuntimeError):
            # pylint: disable=pointless-statement
            v1 == v1  # noqa: B015
        with self.assertRaises(RuntimeError):
            # pylint: disable=pointless-statement
            v1 != v1  # noqa: B015
        with self.assertRaises(RuntimeError):
            # pylint: disable=unnecessary-dunder-call
            v1.__delitem__(None)
        with self.assertRaises(RuntimeError):
            v1.get_degree()
        with self.assertRaises(RuntimeError):
            # pylint: disable=pointless-statement
            v1 < v1  # noqa: B015
        with self.assertRaises(RuntimeError):
            # pylint: disable=pointless-statement
            v1 <= v1  # noqa: B015
        with self.assertRaises(RuntimeError):
            # pylint: disable=pointless-statement
            v1 > v1  # noqa: B015
        with self.assertRaises(RuntimeError):
            # pylint: disable=pointless-statement
            v1 >= v1  # noqa: B015

    def test_delete_with_edges(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)
        e1 = Edge(v1, v2)  # noqa: F841

        counter = 0
        for _ in self.g.get_vertices():
            counter += 1
        self.assertEqual(counter, 2)
        self.assertEqual(self.g.g.number_of_edges(), 1)

        v2.delete()
        counter = 0
        for _ in self.g.get_vertices():
            counter += 1
        self.assertEqual(counter, 1)
        self.assertEqual(self.g.g.number_of_edges(), 0)

        v3 = Vertex(self.g)
        e2 = Edge(v1, v3)  # noqa: F841
        counter = 0
        for _ in self.g.get_vertices():
            counter += 1
        self.assertEqual(counter, 2)
        self.assertEqual(self.g.g.number_of_edges(), 1)

    def test_delitem(self):
        v1 = Vertex(self.g)
        v1["foo"] = "bar"
        self.assertEqual(v1["foo"], "bar")

        del v1["foo"]
        with self.assertRaises(KeyError):
            # pylint: disable=pointless-statement
            v1["foo"]

    def test_eq_with_inheritance(self):
        class VertexSubclass(Vertex):
            pass

        v1 = VertexSubclass(self.g)
        v2 = VertexSubclass(self.g)

        self.assertTrue(v1 == v1)
        self.assertFalse(v1 == v2)

    def test_hash(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)

        h1 = hash(v1)
        h2 = hash(v2)

        self.assertFalse(v1 == v2)
        self.assertNotEqual(h1, h2)
        self.assertEqual(type(h1), int)
        self.assertEqual(type(h2), int)

        g2 = ExperimentGraph()
        v3 = Vertex(g2)

        h3 = hash(v3)
        self.assertEqual(type(h3), int)
        self.assertEqual(v1.graph_id, v3.graph_id)
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h2, h3)

    def test_iter(self):
        v1 = Vertex(self.g)
        v1["foo"] = 1
        v1["bar"] = 1

        expected_list = ["foo", "bar", "object"]
        expected_list.sort()

        actual_list = []
        for item in v1:
            actual_list.append(item)
        actual_list.sort()

        self.assertEqual(expected_list, actual_list)

    def test_lt(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)

        self.assertTrue(v1.graph_id < v2.graph_id)
        self.assertFalse(v1 < v1)
        self.assertTrue(v1 < v2)
        self.assertFalse(v2 < v1)

        with self.assertRaises(TypeError):
            # pylint: disable=pointless-statement
            v1 < self.g  # noqa: B015

    def test_le(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)

        self.assertTrue(v1.graph_id <= v2.graph_id)
        self.assertTrue(v1 <= v1)
        self.assertTrue(v1 <= v2)
        self.assertFalse(v2 <= v1)

        with self.assertRaises(TypeError):
            # pylint: disable=pointless-statement
            v1 <= self.g  # noqa: B015

    def test_gt(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)

        self.assertTrue(v2.graph_id > v1.graph_id)
        self.assertFalse(v1 > v1)
        self.assertFalse(v1 > v2)
        self.assertTrue(v2 > v1)

        with self.assertRaises(TypeError):
            # pylint: disable=pointless-statement
            v1 > self.g  # noqa: B015

    def test_ge(self):
        v1 = Vertex(self.g)
        v2 = Vertex(self.g)

        self.assertTrue(v2.graph_id >= v1.graph_id)
        self.assertTrue(v1 >= v1)
        self.assertFalse(v1 >= v2)
        self.assertTrue(v2 >= v1)

        with self.assertRaises(TypeError):
            # pylint: disable=pointless-statement
            v1 >= self.g  # noqa: B015

    def test_get_object(self):
        v1 = Vertex(self.g)

        vert = v1.get_object()
        self.assertEqual(vert, v1)

    def test_keys(self):
        v1 = Vertex(self.g)
        v1["test"] = "test"

        keys = v1.keys()
        expected_keys = ["test", "object"]
        expected_keys.sort()
        keys = list(keys)
        keys.sort()
        self.assertEqual(expected_keys, keys)
