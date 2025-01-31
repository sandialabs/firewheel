# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest
import unittest.mock

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component_manager import ModelComponentManager


class RequireClassTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.test_manifests = []
        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c14 = os.path.join(self.base_dir, self.repo_dir, "c14")
        self.c15 = os.path.join(self.base_dir, self.repo_dir, "c15")

        self.c11_provides = ["c1"]
        self.c12_provides = ["c2"]
        self.c13_provides = ["c3"]
        self.c14_provides = ["c4"]
        self.c15_provides = ["c5"]

        self.graph_comp = os.path.join(self.base_dir, self.repo_dir, "graph")
        self.graph_manifest = {
            "name": "test.blank_graph",
            "attributes": {"depends": [], "provides": ["graph"]},
            "model_components": {"depends": []},
            "plugin": "plugin.py",
        }

        self.test_manifests.append(self.graph_manifest)
        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin, ExperimentGraph

class Graph(AbstractPlugin):
    def run(self):
        self.g = ExperimentGraph()
"""

        os.makedirs(self.graph_comp)
        with open(os.path.join(self.graph_comp, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.graph_manifest))

        with open(
            os.path.join(self.graph_comp, "plugin.py"), "w", encoding="utf8"
        ) as f:
            f.write(plugin_str)

        self.c11_depends = ["graph"]
        self.mc_depends = []
        self.c11_manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.c11_depends, "provides": self.c11_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
        }

        self.test_manifests.append(self.c11_manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        objs_str = """
class TestObject(object):
    def __init__(self):
        self.test1 = 'test'
"""

        with open(os.path.join(self.c11, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        self.c12_manifest = {
            "name": "test.model_component2",
            "attributes": {"depends": self.c11_depends, "provides": self.c12_provides},
            "model_components": {"depends": ["test.model_component"]},
            "plugin": "plugin.py",
            "model_component_objects": "objs.py",
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        objs_str = """
from firewheel.control.experiment_graph import require_class

from test.model_component import TestObject

@require_class(TestObject)
class TestComponent2Object(object):
    def __init__(self):
        self.test2 = 'test'
"""

        with open(os.path.join(self.c12, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin, Vertex

from test.model_component2 import TestComponent2Object

class Plugin2(AbstractPlugin):
    def run(self):
        v1 = Vertex(self.g)
        v1.decorate(TestComponent2Object)

        assert(v1.test1 == 'test')
        assert(v1.test2 == 'test')
"""

        with open(os.path.join(self.c12, "plugin.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": self.c11_depends, "provides": self.c13_provides},
            "model_components": {
                "depends": ["test.model_component", "test.model_component2"]
            },
            "plugin": "plugin.py",
            "model_component_objects": "objs.py",
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

        objs_str = """
from firewheel.control.experiment_graph import require_class

from test.model_component import TestObject
from test.model_component2 import TestComponent2Object

@require_class(TestComponent2Object)
class TestComponent3Object(object):
    def __init__(self):
        self.test3 = 'test'

@require_class(TestObject)
@require_class(TestComponent3Object)
class TestComponent3Object2(object):
    def __init__(self):
        self.double_test3 = 'test'
"""

        with open(os.path.join(self.c13, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin, Vertex

from test.model_component3 import TestComponent3Object, TestComponent3Object2

class Plugin3(AbstractPlugin):
    def run(self):
        v1 = Vertex(self.g)
        v1.decorate(TestComponent3Object)

        assert(v1.test1 == 'test')
        assert(v1.test2 == 'test')
        assert(v1.test3 == 'test')
        try:
            assert(v1.double_test3 != 'test')
            # Fail if we reach this statement.
            assert(False)
        except AttributeError:
            pass

        v2 = Vertex(self.g)
        v2.decorate(TestComponent3Object2)

        assert(v2.test1 == 'test')
        assert(v2.test2 == 'test')
        assert(v2.test3 == 'test')
        assert(v2.double_test3 == 'test')
"""

        with open(os.path.join(self.c13, "plugin.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c14_manifest = {
            "name": "test.model_component4",
            "attributes": {"depends": self.c11_depends, "provides": self.c14_provides},
            "model_components": {"depends": ["test.model_component"]},
            "plugin": "plugin.py",
            "model_component_objects": "objs.py",
        }
        self.test_manifests.append(self.c14_manifest)

        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))

        objs_str = """
from firewheel.control.experiment_graph import require_class

from test.model_component import TestObject

@require_class(TestObject)
@require_class(TestObject)
class TestObject4(object):
    def __init__(self):
        self.test4 = 'test'
"""

        with open(os.path.join(self.c14, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin, Vertex

from test.model_component4 import TestObject4

class Plugin4(AbstractPlugin):
    def run(self):
        v1 = Vertex(self.g)
        v1.decorate(TestObject4)

        assert(v1.test1 == 'test')
        assert(v1.test4 == 'test')
        try:
            assert(v1.test2 != 'test')
            # Fail if we reach this statement.
            assert(False)
        except AttributeError:
            pass
"""

        with open(os.path.join(self.c14, "plugin.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c15_manifest = {
            "name": "test.model_component5",
            "attributes": {"depends": self.c11_depends, "provides": self.c15_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "plugin.py",
            "model_component_objects": "objs.py",
        }
        self.test_manifests.append(self.c15_manifest)

        os.makedirs(self.c15)
        with open(os.path.join(self.c15, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c15_manifest))

        objs_str = """
from firewheel.control.experiment_graph import require_class

class DependsObject5(object):
    def __init__(self, arg):
        self.test5 = arg

@require_class(DependsObject5)
class TestObject5(object):
    def __init__(self):
        self.test5_test = 'test'
"""

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin, Vertex, DecorationError

from test.model_component5 import TestObject5

class Plugin5(AbstractPlugin):
    def run(self):
        v1 = Vertex(self.g)
        try:
            v1.decorate(TestObject5)
            # We should trigger an error.
            assert(False)
        except DecorationError:
            assert(True)
"""

        with open(os.path.join(self.c15, "plugin.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        with open(os.path.join(self.c15, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository(
            {"path": os.path.join(self.base_dir, self.repo_dir)}
        )

    def tearDown(self):
        shutil.rmtree(self.base_dir)

        cleanup_repo_db(self.repository_db)

        for test_manifest in self.test_manifests:
            if test_manifest["name"] in sys.modules:
                del sys.modules[test_manifest["name"]]

    def mocked_list_repo(self):
        return iter([{"path": os.path.join(self.base_dir, self.repo_dir)}])

    @unittest.mock.patch(
        "firewheel.control.repository_db.RepositoryDb.list_repositories"
    )
    def test_single_depends(self, mock_rdb):
        mock_rdb.side_effect = self.mocked_list_repo
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c12_provides[0])
        mcm.build_dependency_graph([comp])
        mcm.build_experiment_graph()

    @unittest.mock.patch(
        "firewheel.control.repository_db.RepositoryDb.list_repositories"
    )
    def test_chain_depends(self, mock_rdb):
        mock_rdb.side_effect = self.mocked_list_repo
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c13_provides[0])
        mcm.build_dependency_graph([comp])
        mcm.build_experiment_graph()

    @unittest.mock.patch(
        "firewheel.control.repository_db.RepositoryDb.list_repositories"
    )
    def test_double_depends(self, mock_rdb):
        mock_rdb.side_effect = self.mocked_list_repo
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c14_provides[0])
        mcm.build_dependency_graph([comp])
        mcm.build_experiment_graph()

    @unittest.mock.patch(
        "firewheel.control.repository_db.RepositoryDb.list_repositories"
    )
    def test_init_args(self, mock_rdb):
        mock_rdb.side_effect = self.mocked_list_repo
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c15_provides[0])
        mcm.build_dependency_graph([comp])
        mcm.build_experiment_graph()
