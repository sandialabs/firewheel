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


# pylint: disable=unused-variable
class ModelComponentManagerPrecedesTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        os.mkdir(os.path.join(self.base_dir, self.repo_dir))

        self.test_manifests = []
        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository(
            {"path": os.path.join(self.base_dir, self.repo_dir)}
        )

    def gen_mc(
        self,
        name,
        attr_dep=None,
        attr_prec=None,
        attr_prov=None,
        mc_dep=None,
        mc_prec=None,
    ):
        path = os.path.join(self.base_dir, self.repo_dir, name)

        if attr_dep is None:
            attr_dep = []

        if attr_prec is None:
            attr_prec = []

        if attr_prov is None:
            attr_prov = []

        if mc_dep is None:
            mc_dep = []
        if mc_prec is None:
            mc_prec = []

        manifest = {
            "name": name,
            "attributes": {
                "depends": attr_dep,
                "provides": attr_prov,
                "precedes": attr_prec,
            },
            "model_components": {"depends": mc_dep, "precedes": mc_prec},
        }

        self.test_manifests.append(manifest)
        os.makedirs(path)
        with open(os.path.join(path, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(manifest))

        return ModelComponent(path=path, repository_db=self.repository_db)

    def tearDown(self):
        shutil.rmtree(self.base_dir)

        for test_manifest in self.test_manifests:
            if test_manifest["name"] in sys.modules:
                del sys.modules[test_manifest["name"]]

        cleanup_repo_db(self.repository_db)

    def test_simple_precede_attr(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=["mc2_attr"],
            attr_prov=[],
            mc_dep=[],
            mc_prec=[],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m1.name, m2.name], actual_list)

    def test_simple_precede_mc(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc2"]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m1.name, m2.name], actual_list)

    def test_precede_same_mc_and_attr(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=["mc2_attr"],
            attr_prec=[],
            attr_prov=[],
            mc_dep=[],
            mc_prec=["mc2"],
        )
        m2 = self.gen_mc(  # noqa: F841
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(mc_list)

    def test_precede_diff_mc_and_attr(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=["mc2_attr"],
            attr_prec=[],
            attr_prov=[],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m2.name, m1.name, m3.name], actual_list)

    def test_precede_chain_attr(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=["mc2_attr"],
            attr_prov=[],
            mc_dep=[],
            mc_prec=[],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=["mc3_attr"],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m1.name, m2.name, m3.name], actual_list)

    def test_precede_chain_mc(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc2"]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m1.name, m2.name, m3.name], actual_list)

    def test_precede_and_depend_1(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=[],
            attr_prov=[],
            mc_dep=["mc3"],
            mc_prec=["mc2"],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m3.name, m1.name, m2.name], actual_list)

    def test_precede_and_depend_2(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=[],
            attr_prov=[],
            mc_dep=["mc2", "mc3"],
            mc_prec=[],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m2.name, m3.name, m1.name], actual_list)

    def test_precede_and_depend_3(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=[],
            attr_prov=[],
            mc_dep=["mc3", "mc2"],
            mc_prec=[],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m2.name, m3.name, m1.name], actual_list)

    def test_precede_and_depend_4(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=["mc3_attr"],
            attr_prov=[],
            mc_dep=[],
            mc_prec=[],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=["mc2"],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]

        # There are two possible correct orderings
        is_valid = False
        try:
            self.assertEqual([m1.name, m2.name, m3.name], actual_list)
            is_valid = True
        except AssertionError:
            pass
        try:
            self.assertEqual([m2.name, m1.name, m3.name], actual_list)
            is_valid = True
        except AssertionError:
            pass

        self.assertTrue(is_valid)

    def test_precede_and_depend_5(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc3"]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=["mc2"],
            mc_prec=[],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]

        # There are two possible correct orderings
        is_valid = False
        try:
            self.assertEqual([m1.name, m2.name, m3.name], actual_list)
            is_valid = True
        except AssertionError:
            pass
        try:
            self.assertEqual([m2.name, m1.name, m3.name], actual_list)
            is_valid = True
        except AssertionError:
            pass

        self.assertTrue(is_valid)

    def test_complex_1(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=[],
            attr_prov=[],
            mc_dep=["mc3", "mc2"],
            mc_prec=[],
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=["mc1"],
        )
        mc_list = [m1]

        mcm.build_dependency_graph(mc_list)
        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]

        self.assertEqual([m2.name, m3.name, m1.name], actual_list)

    def test_cycle_1(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1",
            attr_dep=[],
            attr_prec=["mc3_attr"],
            attr_prov=[],
            mc_dep=[],
            mc_prec=[],
        )
        m2 = self.gen_mc(  # noqa: F841
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=["mc1"],
        )
        mc_list = [m3, m1]

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(mc_list)

    def test_cycle_2(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc3"]
        )
        m2 = self.gen_mc(  # noqa: F841
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=["mc1"],
        )
        mc_list = [m3, m1]

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(mc_list)

    def test_cycle_3(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=["mc3"], mc_prec=[]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=["mc3_attr"],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m3 = self.gen_mc(  # noqa: F841
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m2]

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(mc_list)

    def test_precede_cmd_line(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc2"]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m3]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]

        # There are two possible correct orderings
        is_valid = False
        try:
            self.assertEqual([m1.name, m2.name, m3.name], actual_list)
            is_valid = True
        except AssertionError:
            pass
        try:
            self.assertEqual([m1.name, m3.name, m2.name], actual_list)
            is_valid = True
        except AssertionError:
            pass

        self.assertTrue(is_valid)

    def test_precede_cmd_line_2(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc3"]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(  # noqa: F841
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m2]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]

    def test_precede_cmd_line_3(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=["mc3"]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=["mc3"],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m2]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        actual_list = [mc.name for mc in actual_list]
        self.assertEqual([m1.name, m2.name, m3.name], actual_list)

    def test_check_list_ordering_bad_parent(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=[]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m2]

        with self.assertRaises(ValueError):
            mcm.check_list_ordering(mc_list, m3.name, m1.name)

    def test_check_list_ordering_bad_child(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=[]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m2]

        with self.assertRaises(ValueError):
            mcm.check_list_ordering(mc_list, m1.name, m3.name)

    def test_check_list_ordering_correct(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=[]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(  # noqa: F841
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m1, m2]

        self.assertTrue(mcm.check_list_ordering(mc_list, m1.name, m2.name))

    def test_check_list_ordering_incorrect(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = self.gen_mc(
            "mc1", attr_dep=[], attr_prec=[], attr_prov=[], mc_dep=[], mc_prec=[]
        )
        m2 = self.gen_mc(
            "mc2",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc2_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        m3 = self.gen_mc(  # noqa: F841
            "mc3",
            attr_dep=[],
            attr_prec=[],
            attr_prov=["mc3_attr"],
            mc_dep=[],
            mc_prec=[],
        )
        mc_list = [m2, m1]

        self.assertFalse(mcm.check_list_ordering(mc_list, m1.name, m2.name))
