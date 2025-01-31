# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component_manager import ModelComponentManager


class TestGraphObjectRecursiveDepends(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")

        self.c11_provides = ["c1"]
        self.c12_provides = ["c2"]
        self.c13_provides = ["c3"]

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
            "attributes": {"depends": self.c11_depends, "provides": self.c12_provides},
            "model_components": {"depends": ["test.model_component"]},
        }

        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": [], "provides": self.c13_provides},
            "model_components": {"depends": ["test.model_component2"]},
        }

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

        if self.c11_manifest["name"] in sys.modules:
            del sys.modules[self.c11_manifest["name"]]

    def test_recursive_depends(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c13_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        expected_entity_list = [
            "test.model_component",
            "test.model_component2",
            "test.model_component3",
        ]

        self.assertEqual(
            [comp.name for comp in ordered_entity_list], expected_entity_list
        )
