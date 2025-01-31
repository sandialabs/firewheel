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
    NoDefaultProviderError,
    InvalidDefaultProviderError,
)


class ModelComponentManagerDefaultsTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.test_manifests = []
        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")

        self.depends = ["c1"]
        self.provides = ["p1", "p2", "p3"]
        self.mc_depends = ["mca", "aa.bb"]
        self.c11_manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.depends, "provides": self.provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c11_manifest)
        os.makedirs(self.c11)
        with open(os.path.join(self.c11, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c11_manifest))

        self.c12 = os.path.join(self.base_dir, self.repo_dir, "c12")
        self.c12_manifest = {
            "name": "test.second_component",
            "attributes": {"depends": self.depends, "provides": ["p2", "p3", "p4"]},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c12_manifest)
        os.makedirs(self.c12)
        with open(os.path.join(self.c12, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c12_manifest))

        self.test_mcs = [self.c11, self.c12]
        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository(
            {"path": os.path.join(self.base_dir, self.repo_dir)}
        )

        self.attribute_defaults = {}
        self.attribute_defaults["p3"] = self.c12_manifest["name"]
        self.attribute_defaults["invalid"] = self.c11_manifest["name"]
        self.attribute_defaults["not installed"] = "not installed component"
        self.attribute_defaults["p4"] = "test.no_component"

    def tearDown(self):
        shutil.rmtree(self.base_dir)

        for test_manifest in self.test_manifests:
            if test_manifest["name"] in sys.modules:
                del sys.modules[test_manifest["name"]]

        cleanup_repo_db(self.repository_db)

    def test_default_single_installed(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        expected_component = ModelComponent(
            path=self.c11, repository_db=self.repository_db
        )
        actual_component = mcm.get_default_component_for_attribute("p1")
        self.assertEqual(actual_component, expected_component)

    def test_defaut_two_installed_no_config(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)
        with self.assertRaises(
            NoDefaultProviderError,
            msg='Multiple providers and no default found for attribute "p2".',
        ):
            mcm.get_default_component_for_attribute("p2")

    def test_default_two_installed_config(self):
        mcm = ModelComponentManager(
            attribute_defaults_config=self.attribute_defaults,
            repository_db=self.repository_db,
        )
        expected_component = ModelComponent(
            path=self.c12, repository_db=self.repository_db
        )

        self.assertEqual(self.attribute_defaults["p3"], self.c12_manifest["name"])
        actual_component = mcm.get_default_component_for_attribute("p3")
        self.assertEqual(expected_component, actual_component)

    def test_default_no_actual_provide(self):
        mcm = ModelComponentManager(
            attribute_defaults_config=self.attribute_defaults,
            repository_db=self.repository_db,
        )

        with self.assertRaises(InvalidDefaultProviderError):
            mcm.get_default_component_for_attribute("invalid")

    def test_default_not_installed(self):
        mcm = ModelComponentManager(
            attribute_defaults_config=self.attribute_defaults,
            repository_db=self.repository_db,
        )

        with self.assertRaises(InvalidDefaultProviderError):
            mcm.get_default_component_for_attribute("not installed")

    def test_single_default_not_installed(self):
        mcm = ModelComponentManager(
            attribute_defaults_config=self.attribute_defaults,
            repository_db=self.repository_db,
        )
        expected_component = ModelComponent(
            path=self.c12, repository_db=self.repository_db
        )

        actual_component = mcm.get_default_component_for_attribute("p4")
        self.assertEqual(expected_component, actual_component)

    def test_invalid_graph_constraint(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        with self.assertRaises(
            NoDefaultProviderError, msg='No provider found for attribute "invalid".'
        ):
            mcm.get_default_component_for_attribute("invalid")
