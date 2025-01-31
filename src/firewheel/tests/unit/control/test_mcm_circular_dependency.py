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


class ModelComponentManagerCircularDependencyTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.test_manifests = []
        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")

        self.c11_depends = ["c2"]
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
        self.c12_provides = ["c2"]
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

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository(
            {"path": os.path.join(self.base_dir, self.repo_dir)}
        )

    def tearDown(self):
        shutil.rmtree(self.base_dir)

        for test_manifest in self.test_manifests:
            if test_manifest["name"] in sys.modules:
                del sys.modules[test_manifest["name"]]

        cleanup_repo_db(self.repository_db)

    # This should result in a useful ERROR-level log message.
    def test_simple_two_component_dependency_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c11, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c12, repository_db=self.repository_db)
        mc_list = [m1, m2]

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(mc_list)
