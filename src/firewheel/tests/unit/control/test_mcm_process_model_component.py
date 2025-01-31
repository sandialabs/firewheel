# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component_manager import ModelComponentManager
from firewheel.control.model_component_exceptions import ModelComponentImportError


class MCMProcessModelComponentTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

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
            "attributes": {"depends": self.c11_depends, "provides": self.c12_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "invalid.py",
            "plugin": "grapher.py",
        }

        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        with open(os.path.join(self.c12, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Grapher(AbstractPlugin):
    def run(self):
        pass
"""

        with open(os.path.join(self.c12, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": self.c11_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
            "plugin": "invalid.py",
        }

        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

        with open(os.path.join(self.c13, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        with open(os.path.join(self.c13, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.c14_manifest = {
            "name": "test.model_component4",
            "attributes": {"depends": self.c11_depends, "provides": self.c14_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "grapher.py",
        }

        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))

        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Grapher(AbstractPlugin):
    def run(self):
        raise ImportError()
"""

        with open(os.path.join(self.c14, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository(
            {"path": os.path.join(self.base_dir, self.repo_dir)}
        )

    def tearDown(self):
        shutil.rmtree(self.base_dir)

        cleanup_repo_db(self.repository_db)

        if self.c11_manifest["name"] in sys.modules:
            del sys.modules[self.c11_manifest["name"]]

    def test_working_single_comp(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c11_provides[0])
        (errors, _g) = mcm.process_model_component(comp, None)

        self.assertFalse(errors)

    def test_objs_invalid_path(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c12_provides[0])
        (errors, _g) = mcm.process_model_component(comp, None)

        self.assertTrue(errors)

    def test_plugin_invalid_path(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c13_provides[0])
        (errors, _g) = mcm.process_model_component(comp, None)

        self.assertTrue(errors)

    def test_plugin_run_import_error_return(self):
        plugin_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Grapher(AbstractPlugin):
    def run(self):
        pass

class Grapher2(AbstractPlugin):
    def run(self):
        pass
"""

        with open(os.path.join(self.c14, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c14_provides[0])
        errors = mcm.process_model_component(comp, None)
        self.assertTrue(errors)

    def test_plugin_name_error(self):
        plugin_str = """
class Grapher(AbstractPlugin):
    def run(self):
        pass
"""

        with open(os.path.join(self.c14, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin_str)

        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c14_provides[0])
        with self.assertRaises(ModelComponentImportError):
            mcm.process_model_component(comp, None)

    def test_plugin_run_import_error(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c14_provides[0])
        with self.assertRaises(ImportError):
            mcm.process_model_component(comp, None)

    def test_plugin_import_import_error(self):
        with open(
            os.path.join(self.c14, self.c14_manifest["plugin"]), "w", encoding="utf8"
        ) as f:
            f.write("raise ImportError()")

        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c14_provides[0])
        with self.assertRaises(ModelComponentImportError):
            mcm.process_model_component(comp, None)

    def test_model_component_object_import_import_error(self):
        with open(
            os.path.join(self.c11, self.c11_manifest["model_component_objects"]),
            "w",
            encoding="utf8",
        ) as f:
            f.write("raise ImportError()")

        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c11_provides[0])
        with self.assertRaises(ModelComponentImportError):
            mcm.process_model_component(comp, None)

    def test_model_component_object_run_import_error(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c11_provides[0])

        # Cause an import error in _import_model_component_objects
        sys.modules["test.model_component"] = None
        errors = mcm.process_model_component(comp, None)
        self.assertTrue(errors)
