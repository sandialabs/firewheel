# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component_manager import (
    InvalidStateError,
    ModelComponentManager,
)


class MCMExperimentGraphTestCase(unittest.TestCase):
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

        self.c11_depends = []
        self.mc_depends = []
        self.c11_manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.c11_depends, "provides": self.c11_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
            "plugin": "grapher.py",
        }

        self.test_manifests.append(self.c11_manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        objs_str = """
class TestObject(object):
    pass
"""

        with open(os.path.join(self.c11, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin

from test.model_component import TestObject

class Grapher(AbstractPlugin):
    def run(self):
        pass
"""

        with open(os.path.join(self.c11, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c12_manifest = {
            "name": "test.model_component2",
            "attributes": {"depends": self.c11_provides, "provides": self.c12_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
            "plugin": "grapher.py",
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Grapher(AbstractPlugin):
    def run(self):
        pass
"""

        with open(os.path.join(self.c12, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

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

    def test_working_single_comp_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c11_provides[0])
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time so we can compare more easily.
        for e in errors:
            if "time" in e:
                e["time"] = 0.0
            else:
                self.fail(f"Time missing from result {e}")

        expected_result = [
            {"model_component": self.c11_manifest["name"], "errors": False, "time": 0.0}
        ]
        self.assertEqual(expected_result, errors)

    def test_no_dependency_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        with self.assertRaises(InvalidStateError):
            mcm.build_experiment_graph()

    def test_two_comp_graph_with_one_error(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c12_provides[0])
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time so we can compare more easily.
        for e in errors:
            if "time" in e:
                e["time"] = 0.0
            else:
                self.fail(f"Time missing from result {e}")

        c11_expected_result = {
            "model_component": self.c11_manifest["name"],
            "errors": False,
            "time": 0.0,
        }
        c12_expected_result = {
            "model_component": self.c12_manifest["name"],
            "errors": True,
            "time": 0.0,
        }
        expected_result = [c11_expected_result, c12_expected_result]
        self.assertEqual(expected_result, errors)
