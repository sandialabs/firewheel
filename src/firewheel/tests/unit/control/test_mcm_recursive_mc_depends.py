# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component import ModelComponent
from firewheel.control.model_component_manager import ModelComponentManager


class MCMRecursiveMCDependsTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"
        self.test_manifests = []

        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")

        self.c11_name = "test.model_component"
        self.c12_name = "test.second_component"
        self.c13_name = "test.third_component"

        self.c11_depends = []
        self.c11_provides = []
        self.c11_mc_depends = [self.c12_name]
        self.c11_manifest = {
            "name": self.c11_name,
            "attributes": {"depends": self.c11_depends, "provides": self.c11_provides},
            "model_components": {"depends": self.c11_mc_depends},
        }

        self.test_manifests.append(self.c11_manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        self.c12_depends = []
        self.c12_provides = []
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c12_mc_depends = [self.c13_name]
        self.c12_manifest = {
            "name": self.c12_name,
            "attributes": {"depends": self.c12_depends, "provides": self.c12_provides},
            "model_components": {"depends": self.c12_mc_depends},
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        self.c13_depends = []
        self.c13_provides = []
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c13_mc_depends = []
        self.c13_manifest = {
            "name": self.c13_name,
            "attributes": {"depends": self.c13_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.c13_mc_depends},
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

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

    def test_recursive_mc_dependency_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c11, repository_db=self.repository_db)
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        expected_list = [self.c13_name, self.c12_name, self.c11_name]
        self.assertEqual(expected_list, [comp.name for comp in actual_list])
