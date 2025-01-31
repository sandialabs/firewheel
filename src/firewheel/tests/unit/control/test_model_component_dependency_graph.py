# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component import ModelComponent
from firewheel.control.dependency_graph import InvalidNodeError
from firewheel.control.model_component_dependency_graph import (
    ModelComponentDependencyGraph,
)


class ModelComponentDependencyGraphTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"
        self.test_manifests = []

        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")

        self.c11_depends = []
        self.c11_provides = ["c1"]
        self.mc_depends = []
        self.c11_manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.c11_depends, "provides": self.c11_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c11_manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        self.c12_depends = ["c1"]
        self.c12_provides = []
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c12_manifest = {
            "name": "test.second_component",
            "attributes": {"depends": self.c12_depends, "provides": self.c12_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        self.c13_depends = ["cycler"]
        self.c13_provides = ["cycler"]
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c13_manifest = {
            "name": "test.third_component",
            "attributes": {"depends": self.c13_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

        self.c14_depends = []
        self.c14_provides = ["c1"]
        self.c14 = os.path.join(self.base_dir, self.repo_dir, "c14")
        self.c14_manifest = {
            "name": "test.fourth_component",
            "attributes": {"depends": self.c14_depends, "provides": self.c14_provides},
            "model_components": {"depends": []},
        }

        self.test_manifests.append(self.c14_manifest)
        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))

        self.c15_depends = ["c3", "c1"]
        self.c15_provides = []
        self.c15 = os.path.join(self.base_dir, self.repo_dir, "c15")
        self.c15_manifest = {
            "name": "test.fifth_component",
            "attributes": {"depends": self.c15_depends, "provides": self.c15_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c15_manifest)
        os.makedirs(self.c15)
        with open(os.path.join(self.c15, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c15_manifest))

        self.c16_depends = []
        self.c16_provides = ["c3"]
        self.c16 = os.path.join(self.base_dir, self.repo_dir, "c16")
        self.c16_manifest = {
            "name": "test.sixth_component",
            "attributes": {"depends": self.c16_depends, "provides": self.c16_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c16_manifest)
        os.makedirs(self.c16)
        with open(os.path.join(self.c16, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c16_manifest))

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

    def test_simple_two_component_dependency_graph(self):
        dg = ModelComponentDependencyGraph()

        m1 = ModelComponent(path=self.c11, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c12, repository_db=self.repository_db)
        mc_list = [m1, m2]

        dg.insert(m1, 0)
        dg.insert(m2, 0)
        dg.associate_model_components(m1, m2)

        actual_list = dg.get_ordered_entity_list()
        self.assertEqual(mc_list, actual_list)

    def test_simple_cycle_component_dependency_graph(self):
        dg = ModelComponentDependencyGraph()

        m = ModelComponent(path=self.c13, repository_db=self.repository_db)

        dg.insert(m, 0)
        dg.associate_model_components(m, m)

    def test_invalid_insert(self):
        dg = ModelComponentDependencyGraph()

        m1 = {"Not MC": 1}
        with self.assertRaises(ValueError):
            dg.insert(m1, 0)

    def test_associate_mc_invalid_source_entity(self):
        dg = ModelComponentDependencyGraph()

        m1 = ModelComponent(path=self.c11, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c12, repository_db=self.repository_db)

        dg.insert(m1, 0)
        dg.insert(m2, 0)

        m2.set_dependency_graph_id(42)

        with self.assertRaises(InvalidNodeError):
            dg.associate_model_components(m1, m2)

    def test_mc_depends(self):
        dg = ModelComponentDependencyGraph()

        m1 = ModelComponent(path=self.c14)
        m2 = ModelComponent(path=self.c12)
        mc_list = [m1, m2]

        dg.insert(m1, 0)
        dg.insert(m2, 0)
        dg.associate_model_components(m1, m2)

        actual_list = dg.get_ordered_entity_list()
        self.assertEqual(mc_list, actual_list)

    def test_double_insert(self):
        dg = ModelComponentDependencyGraph()

        m1 = ModelComponent(path=self.c11, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c12, repository_db=self.repository_db)

        dg.insert(m1, 0)
        dg.insert(m2, 0)
        dg.associate_model_components(m1, m2)

        self.assertEqual([m1, m2], dg.get_ordered_entity_list())

    def test_in_degree_zero_constraints(self):
        dg = ModelComponentDependencyGraph()

        m1 = ModelComponent(path=self.c15, repository_db=self.repository_db)

        dg.insert(m1, 0)

        expected_list = []
        for c15_depend in self.c15_depends:
            expected_list.append((c15_depend, 0))
        expected_list.sort()
        actual_list = dg.get_in_degree_zero_constraints()
        actual_list.sort()
        self.assertEqual(expected_list, actual_list)
