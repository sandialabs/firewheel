# pylint: disable=invalid-name

import os
import sys
import shutil
import tempfile
import unittest

import yaml

from firewheel.lib.utilities import hash_file
from firewheel.control.image_store import ImageStore
from firewheel.control.repository_db import RepositoryDb
from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component import ModelComponent
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


class ModelComponentTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"
        self.test_manifests = []

        self.repo_path = os.path.join(self.base_dir, self.repo_dir)

        self.c11 = os.path.join(self.repo_path, "c11")

        self.depends = ["c1"]
        self.provides = ["c3", "c2"]
        self.precedes = []
        self.mc_depends = ["mca", "aa.bb"]
        self.manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.depends, "provides": self.provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.manifest))

        alt_manifest = {
            "name": "alt.component",
            "attributes": {"depends": self.depends, "provides": self.provides},
            "model_components": {"depends": self.mc_depends},
        }
        self.c12 = os.path.join(self.repo_path, "c12")
        self.test_manifests.append(alt_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(alt_manifest))

        self.invalid_as_dir_manifest = {
            "name": "invalid.component",
            "attributes": {"depends": [], "provides": []},
            "model_components": {"depends": []},
            "plugin": "/tmp",  # nosec
            "model_component_objects": "/tmp",  # nosec
        }
        self.invalid_as_dir_comp_path = os.path.join(
            self.repo_path, "invalid_as_dir_comp"
        )
        self.test_manifests.append(self.invalid_as_dir_manifest)
        os.makedirs(self.invalid_as_dir_comp_path)
        with open(
            os.path.join(self.invalid_as_dir_comp_path, "MANIFEST"),
            "w",
            encoding="utf8",
        ) as f:
            f.write(yaml.safe_dump(self.invalid_as_dir_manifest))

        self.invalid_file_comp_path = os.path.join(self.repo_path, "invalid_file_comp")
        self.invalid_file_manifest = {
            "name": "invalid.component",
            "attributes": {"depends": [], "provides": []},
            "model_components": {"depends": []},
            "plugin": os.path.join(self.invalid_file_comp_path, "not_there.py"),
            "model_component_objects": os.path.join(
                self.invalid_file_comp_path, "not_there.py"
            ),
        }
        self.test_manifests.append(self.invalid_file_manifest)
        os.makedirs(self.invalid_file_comp_path)
        with open(
            os.path.join(self.invalid_file_comp_path, "MANIFEST"), "w", encoding="utf8"
        ) as f:
            f.write(yaml.safe_dump(self.invalid_file_manifest))

        # MC devoid of attributes
        self.c20 = os.path.join(self.repo_path, "c20")

        self.manifest = {"name": "test.model_component2"}

        self.test_manifests.append(self.manifest)
        os.makedirs(self.c20)
        with open(os.path.join(self.c20, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.manifest))

        self.c21 = os.path.join(self.repo_path, "c21")

        self.manifest = {
            "name": "test.model_component3",
            "attributes": {},
            "model_components": {},
        }

        self.test_manifests.append(self.manifest)
        os.makedirs(self.c21)
        with open(os.path.join(self.c21, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.manifest))

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository({"path": self.repo_path})

        self.manifest = {"name": "test.model_component"}

    def tearDown(self):
        shutil.rmtree(self.base_dir)
        cleanup_repo_db(self.repository_db)
        for test_manifest in self.test_manifests:
            if test_manifest["name"] in sys.modules:
                del sys.modules[test_manifest["name"]]

    def test_invalid_construction(self):
        with self.assertRaises(ValueError):
            ModelComponent(None, None)

    def test_path_constructor(self):
        m = ModelComponent(None, self.c11)
        self.assertNotEqual(m, None)

        actual_depends, actual_provides, actual_precedes = m.get_attributes()
        self.assertEqual(self.depends, actual_depends)
        self.assertEqual(self.provides, actual_provides)
        self.assertEqual(self.precedes, actual_precedes)

        actual_mc_depends = m.get_model_component_depends()
        self.assertEqual(self.mc_depends, actual_mc_depends)

        # Make sure path is set correctly. This was a bug.
        self.assertEqual(m.path, self.c11)
        # Make sure name is set correctly.
        self.assertEqual(m.name, self.manifest["name"])

    def test_invalid_path_constructor(self):
        with self.assertRaises(RuntimeError):
            ModelComponent(path=os.path.join(self.base_dir, "invalid"))

    def test_invalid_mc_yaml(self):
        """This testcase checks that if the MC JSON is invalid then an exception is
        raised. In this instance the properties should be in double quotes rather than
        single quotes.
        """
        invalid_yaml = "{'name': 'invalid.component'},"  # noqa: FS003
        c13 = os.path.join(self.repo_path, "c13")
        os.makedirs(c13)
        with open(os.path.join(c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(invalid_yaml)
        with self.assertRaises(RuntimeError):
            ModelComponent(path=c13)

    def test_attributes(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        actual_depends, actual_provides, actual_precedes = m.get_attributes()
        self.assertEqual(self.depends, actual_depends)
        self.assertEqual(self.provides, actual_provides)
        self.assertEqual(self.precedes, actual_precedes)

    def test_attributes_no_attrs(self):
        m = ModelComponent(path=self.c20)
        self.assertNotEqual(m, None)

        actual_depends, actual_provides, actual_precedes = m.get_attributes()
        self.assertEqual([], actual_depends)
        self.assertEqual([], actual_provides)
        self.assertEqual([], actual_precedes)

    def test_attributes_no_attrs_keys(self):
        m = ModelComponent(path=self.c21)
        self.assertNotEqual(m, None)

        actual_depends, actual_provides, actual_precedes = m.get_attributes()
        self.assertEqual([], actual_depends)
        self.assertEqual([], actual_provides)
        self.assertEqual([], actual_precedes)

    def test_mc_depends(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        actual_mc_depends = m.get_model_component_depends()
        self.assertEqual(self.mc_depends, actual_mc_depends)

    def test_mc_precedes_empty(self):
        m = ModelComponent(path=self.c21)
        self.assertNotEqual(m, None)

        actual_mc_precedes = m.get_model_component_depends()
        self.assertEqual([], actual_mc_precedes)

    def test_no_dep_graph_id(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        gid = m.get_dependency_graph_id()
        self.assertEqual(gid, None)

    def test_use_int_dep_graph_id(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        expected_gid = 0
        m.set_dependency_graph_id(expected_gid)
        actual_gid = m.get_dependency_graph_id()
        self.assertEqual(expected_gid, actual_gid)

    def test_use_string_dep_graph_id(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        expected_gid = "string"
        m.set_dependency_graph_id(expected_gid)
        actual_gid = m.get_dependency_graph_id()
        self.assertEqual(expected_gid, actual_gid)

    def test_resolve_path(self):
        m = ModelComponent(
            name="test.model_component", repository_db=self.repository_db
        )
        self.assertNotEqual(m, None)

        actual_depends, actual_provides, actual_precedes = m.get_attributes()
        self.assertEqual(self.depends, actual_depends)
        self.assertEqual(self.provides, actual_provides)
        self.assertEqual(self.precedes, actual_precedes)

        actual_mc_depends = m.get_model_component_depends()
        self.assertEqual(self.mc_depends, actual_mc_depends)

        # Make sure path is set correctly. This was a bug.
        self.assertEqual(m.path, self.c11)
        # Make sure name is set correctly.
        self.assertEqual(m.name, self.manifest["name"])

    def test_repository_prop(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        self.assertIsInstance(m.repository_db, RepositoryDb)
        m.repository_db = None
        self.assertIsInstance(m.repository_db, RepositoryDb)

    def test_vm_resource_store_prop(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        self.assertIsInstance(m.vm_resource_store, VmResourceStore)
        m.vm_resource_store = None
        self.assertIsInstance(m.vm_resource_store, VmResourceStore)

    def test_image_store_prop(self):
        m = ModelComponent(path=self.c11)
        self.assertNotEqual(m, None)

        self.assertIsInstance(m.image_store, ImageStore)
        m.image_store = None
        self.assertIsInstance(m.image_store, ImageStore)

    def test_fail_resolve(self):
        with self.assertRaises(ValueError):
            ModelComponent(
                name="test.unknown_model_component", repository_db=self.repository_db
            )

    def test_invalid_name_with_path(self):
        with self.assertRaises(ValueError):
            ModelComponent(
                name="invalid", path=self.c11, repository_db=self.repository_db
            )

    def test_invalid_name_without_path(self):
        with self.assertRaises(ValueError):
            ModelComponent(name="invalid", repository_db=self.repository_db)

    # pylint: disable=comparison-with-itself
    def test_equality(self):
        m = ModelComponent(path=self.c11)
        n = ModelComponent(path=self.c11)
        alt = ModelComponent(path=self.c12)

        self.assertIsNotNone(m)
        self.assertIsNotNone(m)
        self.assertTrue(m == m)
        self.assertFalse(m != m)
        self.assertTrue(m == n)
        self.assertFalse(m != n)
        self.assertFalse(m == alt)
        self.assertTrue(m != alt)

        n.path = None
        self.assertFalse(m == n)
        self.assertTrue(m != n)

    def test_str(self):
        m = ModelComponent(path=self.c11, repository_db=self.repository_db)

        expected_str = (
            "{'attributes': {'depends': ['c1'], 'provides': ['c3', 'c2']},\n"  # noqa: FS003
            " 'model_components': {'depends': ['mca', 'aa.bb']},\n"  # noqa: FS003
            " 'name': 'test.model_component'}\n"
            f"Path: {self.c11}\n"
            "Dependency Graph ID: None"
        )
        actual_str = str(m)
        self.assertEqual(expected_str, actual_str)

        dep_id = 5
        m.set_dependency_graph_id(dep_id)

        expected_str = (
            "{'attributes': {'depends': ['c1'], 'provides': ['c3', 'c2']},\n"  # noqa: FS003
            " 'model_components': {'depends': ['mca', 'aa.bb']},\n"  # noqa: FS003
            " 'name': 'test.model_component'}\n"
            f"Path: {self.c11}\n"
            f"Dependency Graph ID: {dep_id}"
        )
        actual_str = str(m)
        self.assertEqual(expected_str, actual_str)

    def test_invalid_as_dir_plugin_path(self):
        m = ModelComponent(
            path=self.invalid_as_dir_comp_path, repository_db=self.repository_db
        )
        with self.assertRaises(RuntimeError):
            m.get_plugin_path()
        self.assertTrue(os.path.exists(self.invalid_as_dir_manifest["plugin"]))

    def test_invalid_as_dir_model_component_obj_path(self):
        m = ModelComponent(
            path=self.invalid_as_dir_comp_path, repository_db=self.repository_db
        )
        with self.assertRaises(RuntimeError):
            m.get_model_component_objects_path()
        self.assertTrue(
            os.path.exists(self.invalid_as_dir_manifest["model_component_objects"])
        )

    def test_invalid_file_plugin_path(self):
        m = ModelComponent(
            path=self.invalid_file_comp_path, repository_db=self.repository_db
        )
        with self.assertRaises(RuntimeError):
            m.get_plugin_path()
        self.assertFalse(os.path.exists(self.invalid_file_manifest["plugin"]))

    def test_invalid_file_model_component_obj_path(self):
        m = ModelComponent(
            path=self.invalid_file_comp_path, repository_db=self.repository_db
        )
        with self.assertRaises(RuntimeError):
            m.get_model_component_objects_path()
        self.assertFalse(
            os.path.exists(self.invalid_file_manifest["model_component_objects"])
        )

    def test_hash(self):
        # Write 'a'*1024 to a file with python3, then run sha1 on it.
        # We use a large file size so we are sure we will read multiple
        # chunks and exercise all hash code in our target function.
        expected_hash = "2727756cfee3fbfe24bf5650123fd7743d7b3465"

        ModelComponent(path=self.c11, repository_db=self.repository_db)
        target_file_name = os.path.join(self.c11, "hash")
        with open(target_file_name, "w", encoding="utf8") as f:
            f.write("a" * 8192)

        actual_hash = hash_file(target_file_name)
        self.assertEqual(expected_hash, actual_hash)

    def test_default_constructor(self):
        mc = ModelComponent(path=self.c11)
        self.assertTrue(isinstance(mc, ModelComponent))

        with self.assertRaises(ValueError):
            mc = ModelComponent(repository_db=self.repository_db)

        with self.assertRaises(ValueError):
            mc = ModelComponent(
                path=self.c11, name="asdf", repository_db=self.repository_db
            )

        with self.assertRaises(ValueError):
            mc = ModelComponent(name="asdf", repository_db=self.repository_db)

        with self.assertRaises(ValueError):
            mc = ModelComponent(
                path=self.c11, arguments={}, repository_db=self.repository_db
            )

    # pylint: disable=unused-variable
    def test_exercise_properties(self):
        mc = ModelComponent(
            name=self.manifest["name"], repository_db=self.repository_db
        )
        self.assertTrue(isinstance(mc, ModelComponent))

        # Failed when AttributeErrors were unhandled in properties.
        img_store = mc.image_store  # noqa: F841
        vm_resource_store = mc.vm_resource_store  # noqa: F841
        self.assertEqual(mc.repository_db, self.repository_db)
