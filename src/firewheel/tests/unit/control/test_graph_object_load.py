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


# pylint: disable=protected-access
class TestGraphObjectLoad(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.test_manifests = []
        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")
        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c14 = os.path.join(self.base_dir, self.repo_dir, "c14")
        self.c15 = os.path.join(self.base_dir, self.repo_dir, "c15")
        self.c16 = os.path.join(self.base_dir, self.repo_dir, "c16")

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
            "model_component_objects": "objs.py",
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

        self.c12_manifest = {
            "name": "test.model_component2",
            "attributes": {"depends": self.c11_depends, "provides": self.c12_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "invalid.py",
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        self.c13_manifest = {
            "name": "test.model_component3",
            "attributes": {"depends": self.c11_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

        self.c14_manifest = {
            # Deliberately conflicts with self.c11_manifest['name'].
            "name": "test.model_component",
            "attributes": {"depends": self.c11_provides, "provides": self.c14_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
        }

        self.test_manifests.append(self.c14_manifest)
        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))

        objs_str = """
class TestObject2(object):
    pass
"""

        with open(os.path.join(self.c14, "objs.py"), "w", encoding="utf8") as f:
            f.write(objs_str)

        self.c16_manifest = {
            "name": "test.model_component6",
            "attributes": {"depends": self.c11_depends, "provides": self.c16_provides},
            "model_components": {"depends": self.mc_depends},
            "model_component_objects": "objs.py",
        }

        self.test_manifests.append(self.c16_manifest)
        os.makedirs(self.c16)
        with open(os.path.join(self.c16, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c16_manifest))

        objs_str = """
from base_objects import VMEndpoint

class TestObject6(object):
    pass
"""

        with open(os.path.join(self.c16, "objs.py"), "w", encoding="utf8") as f:
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

    def test_local_import(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c11_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        for mc in ordered_entity_list:
            go = mc.get_model_component_objects_path()
            cur_path = os.path.join(mc.path, go)
            mcm._import_model_component_objects(cur_path, mc.name)
        # pylint: disable=no-name-in-module,import-error,import-outside-toplevel,unused-import
        from test.model_component import TestObject  # noqa: F401

    def test_invalid_objects_file(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c12_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        for mc in ordered_entity_list:
            with self.assertRaises(RuntimeError):
                mc.get_model_component_objects_path()

    def test_invalid_objects_file_import(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c12_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        for mc in ordered_entity_list:
            with self.assertRaises(ImportError):
                mcm._import_model_component_objects(
                    mc.manifest["model_component_objects"], mc.name
                )

    def test_no_module_specified(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c13_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        for mc in ordered_entity_list:
            go = mc.get_model_component_objects_path()
            cur_path = os.path.join(mc.path, go)
            with self.assertRaises(ImportError):
                mcm._import_model_component_objects(cur_path, mc.name)

    def test_duplicate_component_names(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c14_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        count = 0
        for mc in ordered_entity_list:
            go = mc.get_model_component_objects_path()
            cur_path = os.path.join(mc.path, go)
            if count > 0:
                with self.assertRaises(ImportError):
                    mcm._import_model_component_objects(cur_path, mc.name)
            else:
                mcm._import_model_component_objects(cur_path, mc.name)
            count += 1

    def test_import_depencency_error(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        comp = mcm.get_default_component_for_attribute(self.c16_provides[0])
        mcm.build_dependency_graph([comp])
        ordered_entity_list = mcm.dg.get_ordered_entity_list()

        for mc in ordered_entity_list:
            go = mc.get_model_component_objects_path()
            cur_path = os.path.join(mc.path, go)
            with self.assertRaises(ModelComponentImportError):
                mcm._import_model_component_objects(cur_path, mc.name)
