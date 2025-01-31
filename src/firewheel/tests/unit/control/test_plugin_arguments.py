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


class PluginArgumentsTestcase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.test_manifests = []
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
            "plugin": "grapher.py",
        }

        self.test_manifests.append(self.c11_manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Grapher(AbstractPlugin):
    def run(self, arg1, kw1=None):
        pass
"""
        with open(os.path.join(self.c11, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c12_manifest = {
            "name": "test.model_component2",
            "attributes": {"depends": self.c11_depends, "provides": self.c12_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "grapher2.py",
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))
        plugin2_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Plugin(AbstractPlugin):
    def run(self, kwarg1=None):
        pass
"""
        with open(os.path.join(self.c12, "grapher2.py"), "w", encoding="utf8") as f:
            f.write(plugin2_str)

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": self.c11_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "grapher3.py",
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))
        plugin3_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Plugin(AbstractPlugin):
    def run(self, arg1, kwarg1=None):
        pass
"""
        with open(os.path.join(self.c13, "grapher3.py"), "w", encoding="utf8") as f:
            f.write(plugin3_str)

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

    def test_anonymous_args_list(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp_args = {"plugin": {"": ["value"]}}
        comp = ModelComponent(
            name=self.c11_manifest["name"],
            arguments=comp_args,
            repository_db=self.repository_db,
        )
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time.
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
        expected_result = [c11_expected_result]
        self.assertEqual(expected_result, errors)

    def test_anonymous_args_string(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp_args = {"plugin": {"": "value"}}
        comp = ModelComponent(
            name=self.c11_manifest["name"],
            arguments=comp_args,
            repository_db=self.repository_db,
        )
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time.
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
        expected_result = [c11_expected_result]
        self.assertEqual(expected_result, errors)

    def test_kwargs(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp_args = {"plugin": {"kwarg1": "value2"}}
        comp = ModelComponent(
            name=self.c12_manifest["name"],
            arguments=comp_args,
            repository_db=self.repository_db,
        )
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time.
        for e in errors:
            if "time" in e:
                e["time"] = 0.0
            else:
                self.fail(f"Time missing from result {e}")

        c12_expected_result = {
            "model_component": self.c12_manifest["name"],
            "errors": False,
            "time": 0.0,
        }
        expected_result = [c12_expected_result]
        self.assertEqual(expected_result, errors)

    def test_combo_args(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp_args = {"plugin": {"": ["value1"], "kwarg1": "value2"}}
        comp = ModelComponent(
            name=self.c13_manifest["name"],
            arguments=comp_args,
            repository_db=self.repository_db,
        )
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time.
        for e in errors:
            if "time" in e:
                e["time"] = 0.0
            else:
                self.fail(f"Time missing from result {e}")

        c13_expected_result = {
            "model_component": self.c13_manifest["name"],
            "errors": False,
            "time": 0.0,
        }
        expected_result = [c13_expected_result]
        self.assertEqual(expected_result, errors)

    def test_missing_kwarg(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp_args = {"plugin": {"": ["value1"]}}
        comp = ModelComponent(
            name=self.c13_manifest["name"],
            arguments=comp_args,
            repository_db=self.repository_db,
        )
        mcm.build_dependency_graph([comp])
        errors = mcm.build_experiment_graph()

        # Clean up time.
        for e in errors:
            if "time" in e:
                e["time"] = 0.0
            else:
                self.fail(f"Time missing from result {e}")

        c13_expected_result = {
            "model_component": self.c13_manifest["name"],
            "errors": False,
            "time": 0.0,
        }
        expected_result = [c13_expected_result]
        self.assertEqual(expected_result, errors)

    def test_missing_positional_arg(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp_args = {"plugin": {"kwarg1": "value2"}}
        comp = ModelComponent(
            name=self.c13_manifest["name"],
            arguments=comp_args,
            repository_db=self.repository_db,
        )
        mcm.build_dependency_graph([comp])
        with self.assertRaises(TypeError):
            mcm.build_experiment_graph()

    def test_invalid_args_no_dict(self):
        with self.assertRaises(ValueError):
            ModelComponent(
                name=self.c11_manifest["name"],
                arguments="invalid",
                repository_db=self.repository_db,
            )

    def test_invalid_args_no_plugin(self):
        with self.assertRaises(ValueError):
            ModelComponent(
                name=self.c11_manifest["name"],
                arguments={"invalid": "value"},
                repository_db=self.repository_db,
            )

    def test_invalid_args_plugin_not_dict(self):
        with self.assertRaises(ValueError):
            ModelComponent(
                name=self.c11_manifest["name"],
                arguments={"plugin": "invalid"},
                repository_db=self.repository_db,
            )
