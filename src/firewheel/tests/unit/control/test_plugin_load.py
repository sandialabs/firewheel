# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml
import pytest

from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component_manager import ModelComponentManager
from firewheel.control.model_component_exceptions import ModelComponentImportError


# pylint: disable=protected-access
class TestPluginLoad(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c14 = os.path.join(self.base_dir, self.repo_dir, "c14")
        self.c15 = os.path.join(self.base_dir, self.repo_dir, "c15")
        self.c16 = os.path.join(self.base_dir, self.repo_dir, "c16")
        self.test_manifests = []

        self.c11_provides = ["c1"]
        self.c12_provides = ["c2"]
        self.c13_provides = ["c3"]
        self.c14_provides = ["c4"]
        self.c15_provides = ["c5"]
        self.c16_provides = ["c6"]

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
    def __init__(self, graph):
        pass
    def run(self):
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
class Plugin(object):
    def __init__(self, graph):
        pass
    def run(self):
        pass
"""
        with open(os.path.join(self.c12, "grapher2.py"), "w", encoding="utf8") as f:
            f.write(plugin2_str)

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": self.c11_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "grapher.py",
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))
        plugin3_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Plugin(AbstractPlugin):
    def __init__(self, graph):
        pass
    def run(self):
        pass

class SecondPlugin(AbstractPlugin):
    def __init__(self, graph):
        pass
    def run(self):
        pass
"""
        with open(os.path.join(self.c13, "grapher.py"), "w", encoding="utf8") as f:
            f.write(plugin3_str)

        self.c14_manifest = {
            "name": "test.model_component4",
            "attributes": {"depends": self.c11_depends, "provides": self.c14_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "invalid.py",
        }

        self.test_manifests.append(self.c14_manifest)
        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))
        plugin4_str = """
from firewheel.control.experiment_graph import AbstractPlugin

class Plugin(AbstractPlugin):
    def __init__(self, graph):
        pass
    def run(self):
        pass
"""
        with open(os.path.join(self.c14, "plugin.py"), "w", encoding="utf8") as f:
            f.write(plugin4_str)

        self.c15_manifest = {
            "name": "test.model_component5",
            "attributes": {"depends": self.c11_depends, "provides": self.c15_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c15_manifest)
        os.makedirs(self.c15)
        with open(os.path.join(self.c15, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c15_manifest))

        self.c16_manifest = {
            "name": "test.model_component6",
            "attributes": {"depends": self.c11_depends, "provides": self.c16_provides},
            "model_components": {"depends": self.mc_depends},
            "plugin": "plugin6.py",
        }

        self.test_manifests.append(self.c16_manifest)
        os.makedirs(self.c16)
        with open(os.path.join(self.c16, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c16_manifest))
        plugin6_str = """
from firewheel.control.experiment_graph import AbstractPlugin

from base_objects import VMEndpoint

class Plugin(AbstractPlugin):
    def __init__(self, graph):
        pass
    def run(self):
        pass
"""
        with open(os.path.join(self.c16, "plugin6.py"), "w", encoding="utf8") as f:
            f.write(plugin6_str)

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

    def test_valid_plugin(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c1")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            plugin_path = os.path.join(mc.path, mc.get_plugin_path())
            mcm._import_plugin(plugin_path, mc.name)

    def test_no_inheritence_plugin(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c2")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            plugin_path = os.path.join(mc.path, mc.get_plugin_path())
            with self.assertRaises(ImportError):
                mcm._import_plugin(plugin_path, mc.name)

    def test_invalid_multiple_plugin(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c3")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            plugin_path = os.path.join(mc.path, mc.get_plugin_path())
            with self.assertRaises(ImportError):
                mcm._import_plugin(plugin_path, mc.name)

    def test_invalid_plugin_file(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c4")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            with self.assertRaises(RuntimeError):
                os.path.join(mc.path, mc.get_plugin_path())

    def test_invalid_plugin_file_import(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c4")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            with self.assertRaises(ImportError):
                plugin_path = os.path.join(mc.path, mc.manifest["plugin"])
                mcm._import_plugin(plugin_path, mc.name)

    def test_no_plugin_specified(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c5")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            plugin_path = os.path.join(mc.path, mc.get_plugin_path())
            with self.assertRaises(ImportError):
                mcm._import_plugin(plugin_path, mc.name)

    @unittest.mock.patch("importlib.util.module_from_spec", new=unittest.mock.Mock())
    @unittest.mock.patch("importlib.util.spec_from_file_location")
    def test_import_dependency_error(self, mock_spec_method):
        error_msg_excerpt = "typically caused by either importing a model component"
        # Set the return value and execptions for the mock methods
        mock_spec = mock_spec_method.return_value
        mock_spec.loader.exec_module.side_effect = ImportError
        # Test the MCM's handling of the import error
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute("c6")
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()
        for mc in ordered_entity_list:
            plugin_path = os.path.join(mc.path, mc.get_plugin_path())
            with pytest.raises(ModelComponentImportError) as exc_info:
                mcm._import_plugin(plugin_path, mc.name)
            assert error_msg_excerpt in str(exc_info.value)
