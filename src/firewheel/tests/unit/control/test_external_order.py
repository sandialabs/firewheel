# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component import ModelComponent
from firewheel.control.model_component_manager import (
    ModelComponentManager,
    UnsatisfiableDependenciesError,
)


class TestExternalOrderDepends(unittest.TestCase):
    def _setup_double_add_bug(self):
        self.basic_graph_objects = os.path.join(
            self.base_dir, self.repo_dir, "basic_graph_objects"
        )
        self.generic_vm_objects = os.path.join(
            self.base_dir, self.repo_dir, "generic_vm_objects"
        )
        self.router_tree = os.path.join(self.base_dir, self.repo_dir, "router_tree")
        self.vyos = os.path.join(self.base_dir, self.repo_dir, "vyos")

        self.basic_graph_objects_manifest = {
            "name": "basic_graph_objects",
            "attributes": {"depends": [], "provides": []},
            "model_components": {"depends": []},
        }

        self.generic_vm_objects_manifest = {
            "name": "generic_vm_objects",
            "attributes": {"depends": [], "provides": []},
            "model_components": {"depends": ["basic_graph_objects"]},
        }

        self.router_tree_manifest = {
            "name": "tests.router_tree",
            "attributes": {"depends": [], "provides": ["topology"]},
            "model_components": {
                "depends": ["basic_graph_objects", "generic_vm_objects"]
            },
        }

        self.vyos_manifest = {
            "name": "router.vyos",
            "attributes": {"depends": [], "provides": []},
            "model_components": {
                "depends": ["basic_graph_objects", "generic_vm_objects"]
            },
        }

        def _write_mc(mc_path, manifest):
            os.makedirs(mc_path)
            with open(os.path.join(mc_path, "MANIFEST"), "w", encoding="utf8") as f:
                f.write(yaml.safe_dump(manifest))

        _write_mc(self.basic_graph_objects, self.basic_graph_objects_manifest)
        _write_mc(self.generic_vm_objects, self.generic_vm_objects_manifest)
        _write_mc(self.router_tree, self.router_tree_manifest)
        _write_mc(self.vyos, self.vyos_manifest)

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self._setup_double_add_bug()

        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c14 = os.path.join(self.base_dir, self.repo_dir, "c14")
        self.c15 = os.path.join(self.base_dir, self.repo_dir, "c15")

        self.c11_provides = ["c1"]
        self.c12_provides = ["c2"]
        self.c13_provides = ["c3"]
        self.c14_provides = ["c4"]

        self.c11_depends = []
        self.mc_depends = []
        self.c11_manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.c11_depends, "provides": self.c11_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
        }

        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        objs_str = """
class TestObject(object):
    pass
"""

        with open(os.path.join(self.c11, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        self.c12_manifest = {
            "name": "test.model_component2",
            "attributes": {"depends": self.c11_provides, "provides": self.c12_provides},
            "model_components": {"depends": []},
        }

        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": self.c11_provides, "provides": self.c13_provides},
            "model_components": {"depends": []},
        }

        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

        self.c14_manifest = {
            "name": "test.model_component4",
            "attributes": {
                "depends": self.c12_provides,
                "provides": self.c14_provides,
            },
            "model_components": {"depends": []},
        }

        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))

        self.c15_provides = ["c5"]
        self.c15_depends = []
        self.c15_mc_depends = ["test.model_component"]
        self.c15_manifest = {
            "name": "test.model_component5",
            "attributes": {"depends": self.c15_depends, "provides": self.c15_provides},
            "model_components": {"depends": self.c15_mc_depends},
        }

        os.makedirs(self.c15)
        with open(os.path.join(self.c15, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c15_manifest))

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository(
            {"path": os.path.join(self.base_dir, self.repo_dir)}
        )

    def tearDown(self):
        shutil.rmtree(self.base_dir)
        cleanup_repo_db(self.repository_db)

        if self.c11_manifest["name"] in sys.modules:
            del sys.modules[self.c11_manifest["name"]]

    def test_order1(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp4 = mcm.get_default_component_for_attribute(self.c14_provides[0])
        comp3 = mcm.get_default_component_for_attribute(self.c13_provides[0])
        comp2 = mcm.get_default_component_for_attribute(self.c12_provides[0])
        # pylint: disable=unused-variable
        comp1 = mcm.get_default_component_for_attribute(  # noqa: F841
            self.c11_provides[0]
        )
        mcm.build_dependency_graph([comp2, comp4, comp3])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        expected_entity_list = [
            "test.model_component",
            "test.model_component2",
            "test.model_component4",
            "test.model_component3",
        ]

        self.assertEqual(
            [comp.name for comp in ordered_entity_list], expected_entity_list
        )

    def test_duplicate_from_cmd_line(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp5 = mcm.get_default_component_for_attribute(self.c15_provides[0])
        comp2 = mcm.get_default_component_for_attribute(self.c12_provides[0])
        comp1 = mcm.get_default_component_for_attribute(self.c11_provides[0])

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph([comp5, comp1, comp2])

    def test_double_mc_bug(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        vyos_mc = ModelComponent(path=self.vyos)
        router_tree_mc = ModelComponent(path=self.router_tree)
        # pylint: disable=unused-variable
        generic_vm_objects_mc = ModelComponent(  # noqa: F841
            path=self.generic_vm_objects
        )
        basic_graph_objects_mc = ModelComponent(path=self.basic_graph_objects)

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(
                [router_tree_mc, basic_graph_objects_mc, vyos_mc]
            )
