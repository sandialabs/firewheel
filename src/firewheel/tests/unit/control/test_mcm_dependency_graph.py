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
    InvalidStateError,
    ModelComponentManager,
    UnsatisfiableDependenciesError,
)


class ModelComponentManagerDependencyGraphTestCase(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.repo_dir = "repo"

        self.test_manifests = []
        self.c11 = os.path.join(self.base_dir, self.repo_dir, "c11")

        self.c11_depends = []
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
        self.c12_provides = []
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

        self.c13_depends = ["cycler"]
        self.c13_provides = ["cycler"]
        self.c13 = os.path.join(self.base_dir, self.repo_dir, "c13")
        self.c13_manifest = {
            "name": "test.third_component",
            "attributes": {"depends": self.c13_depends, "provides": self.c13_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c13_manifest)
        os.makedirs(self.c13)
        with open(os.path.join(self.c13, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c13_manifest))

        self.c14_depends = []
        self.c14_provides = ["c1"]
        self.c14 = os.path.join(self.base_dir, self.repo_dir, "c14")
        self.c14_manifest = {
            "name": "test.fourth_component",
            "attributes": {"depends": self.c14_depends, "provides": self.c14_provides},
            "model_components": {"depends": []},
        }

        self.test_manifests.append(self.c14_manifest)
        os.makedirs(self.c14)
        with open(os.path.join(self.c14, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c14_manifest))

        self.c15_depends = ["c3", "c1"]
        self.c15_provides = []
        self.c15 = os.path.join(self.base_dir, self.repo_dir, "c15")
        self.c15_manifest = {
            "name": "test.fifth_component",
            "attributes": {"depends": self.c15_depends, "provides": self.c15_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c15_manifest)
        os.makedirs(self.c15)
        with open(os.path.join(self.c15, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c15_manifest))

        self.c16_depends = []
        self.c16_provides = ["c3"]
        self.c16 = os.path.join(self.base_dir, self.repo_dir, "c16")
        self.c16_manifest = {
            "name": "test.sixth_component",
            "attributes": {"depends": self.c16_depends, "provides": self.c16_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c16_manifest)
        os.makedirs(self.c16)
        with open(os.path.join(self.c16, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c16_manifest))

        self.c17_depends = ["z19"]
        self.c17_provides = []
        self.c17 = os.path.join(self.base_dir, self.repo_dir, "c17")
        self.c17_manifest = {
            "name": "test.seventh_component",
            "attributes": {"depends": self.c17_depends, "provides": self.c17_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c17_manifest)
        os.makedirs(self.c17)
        with open(os.path.join(self.c17, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c17_manifest))

        self.c18_depends = ["a20"]
        self.c18_provides = []
        self.c18 = os.path.join(self.base_dir, self.repo_dir, "c18")
        self.c18_manifest = {
            "name": "test.eigth_component",
            "attributes": {"depends": self.c18_depends, "provides": self.c18_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c18_manifest)
        os.makedirs(self.c18)
        with open(os.path.join(self.c18, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c18_manifest))

        self.c19_depends = []
        self.c19_provides = ["c19", "z19"]
        self.c19 = os.path.join(self.base_dir, self.repo_dir, "c19")
        self.c19_manifest = {
            "name": "test.z19",
            "attributes": {"depends": self.c19_depends, "provides": self.c19_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c19_manifest)
        os.makedirs(self.c19)
        with open(os.path.join(self.c19, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c19_manifest))

        self.c20_depends = []
        self.c20_provides = ["a20"]
        self.c20 = os.path.join(self.base_dir, self.repo_dir, "c20")
        self.c20_manifest = {
            "name": "test.a20",
            "attributes": {"depends": self.c20_depends, "provides": self.c20_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c20_manifest)
        os.makedirs(self.c20)
        with open(os.path.join(self.c20, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c20_manifest))

        self.c21_depends = ["c19"]
        self.c21_provides = []
        self.c21 = os.path.join(self.base_dir, self.repo_dir, "c21")
        self.c21_manifest = {
            "name": "test.c21",
            "attributes": {"depends": self.c21_depends, "provides": self.c21_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c21_manifest)
        os.makedirs(self.c21)
        with open(os.path.join(self.c21, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c21_manifest))

        self.c22_depends = []
        self.c22_provides = ["z19"]
        self.c22 = os.path.join(self.base_dir, self.repo_dir, "c22")
        self.c22_manifest = {
            "name": "test.c22",
            "attributes": {"depends": self.c22_depends, "provides": self.c22_provides},
            "model_components": {"depends": self.mc_depends},
        }

        self.test_manifests.append(self.c22_manifest)

        # Create a bunch extra to test scaling of group numbers. Also need to
        # create attribute depends/provides relationships to test sorting when
        # attribute name is used.
        self.extra_mc_paths = []
        for group_num in range(3, 20):
            for i in range(3):
                mc_str = f"c{group_num}{i}"
                if i == 0:
                    mc_dep = []
                    mc_prov = [f"c{group_num}{i}"]
                elif i == 1:
                    mc_dep = []
                    mc_prov = [f"c{group_num}{i}"]
                else:
                    mc_dep = [f"c{group_num}0", f"c{group_num}1"]
                    mc_prov = []
                mc_path = os.path.join(self.base_dir, self.repo_dir, mc_str)

                self.extra_mc_paths.append(mc_path)
                manifest = {
                    "name": f"test.{mc_str}",
                    "attributes": {"depends": mc_dep, "provides": mc_prov},
                    "model_components": {"depends": self.mc_depends},
                }
                os.makedirs(mc_path)
                with open(os.path.join(mc_path, "MANIFEST"), "w", encoding="utf8") as f:
                    f.write(yaml.safe_dump(manifest))

        self.test_mcs = [
            self.c11,
            self.c12,
            self.c13,
            self.c14,
            self.c15,
            self.c16,
            self.c17,
            self.c18,
            self.c19,
            self.c20,
            self.c21,
            self.c22,
        ]
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

    def test_unsat_dependency_attrs(self):
        """
        In this test case, we want to ensure that we do not get a duplicate
        provider error if a specified provider has been presented earlier in
        the pipeline.
        That is:

        * A depends on B
        * B provides B and C
        * D depends on C
        * X provides C

        The command line for: A D should result in the graph::
                B<-A<-D
        """
        # Only have the duplicate provider in this test case
        os.makedirs(self.c22)
        with open(os.path.join(self.c22, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(self.c22_manifest))

        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c17, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c19, repository_db=self.repository_db)
        m3 = ModelComponent(path=self.c21, repository_db=self.repository_db)
        mc_list = [m2, m3, m1]

        mcm.build_dependency_graph([m3, m1])

        actual_list = mcm.dg.get_ordered_entity_list()

        self.assertEqual(mc_list, actual_list)

    def test_simple_two_component_dependency_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c11, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c12, repository_db=self.repository_db)
        mc_list = [m1, m2]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        self.assertEqual(mc_list, actual_list)

    def test_simple_cycle_component_dependency_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m = ModelComponent(path=self.c13, repository_db=self.repository_db)
        mc_list = [m]

        with self.assertRaises(UnsatisfiableDependenciesError):
            mcm.build_dependency_graph(mc_list)

    def test_mc_depends(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c14)
        m2 = ModelComponent(path=self.c12)
        mc_list = [m1, m2]

        mcm.build_dependency_graph(mc_list)

        actual_list = mcm.dg.get_ordered_entity_list()
        self.assertEqual(mc_list, actual_list)

    def test_mc_depends_list_no_dep_graph(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        with self.assertRaises(InvalidStateError):
            mcm.get_ordered_model_component_list()

    def test_dependency_graph_with_defaults(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c14)
        # c16 ends up here
        m2 = ModelComponent(path=self.c15)
        mc_list = [m1, m2]

        mcm.build_dependency_graph(mc_list)

        expected_list = [
            "test.fourth_component",
            "test.sixth_component",
            "test.fifth_component",
        ]
        actual_list = mcm.dg.get_ordered_entity_list()
        actual_names = [comp.name for comp in actual_list]
        self.assertEqual(expected_list, actual_names)

    def test_router_tree_exercise(self):
        topo_provides = ["topology"]
        topo_depends = []
        topo_mcdepends = ["test.basic", "test.generic"]
        topo_manifest = {
            "name": "test.topo",
            "attributes": {"depends": topo_depends, "provides": topo_provides},
            "model_components": {"depends": topo_mcdepends},
        }
        topo_dir = os.path.join(self.base_dir, self.repo_dir, "topo")
        os.makedirs(topo_dir)
        with open(os.path.join(topo_dir, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(topo_manifest))

        basic_provides = []
        basic_depends = []
        basic_mcdepends = []
        basic_manifest = {
            "name": "test.basic",
            "attributes": {"depends": basic_depends, "provides": basic_provides},
            "model_components": {"depends": basic_mcdepends},
        }
        basic_dir = os.path.join(self.base_dir, self.repo_dir, "basic")
        os.makedirs(basic_dir)
        with open(os.path.join(basic_dir, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(basic_manifest))

        generic_provides = []
        generic_depends = []
        generic_mcdepends = ["test.basic"]
        generic_manifest = {
            "name": "test.generic",
            "attributes": {"depends": generic_depends, "provides": generic_provides},
            "model_components": {"depends": generic_mcdepends},
        }
        generic_dir = os.path.join(self.base_dir, self.repo_dir, "generic")
        os.makedirs(generic_dir)
        with open(os.path.join(generic_dir, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(generic_manifest))

        router_provides = []
        router_depends = []
        router_mcdepends = ["test.basic", "test.generic"]
        router_manifest = {
            "name": "test.router",
            "attributes": {"depends": router_depends, "provides": router_provides},
            "model_components": {"depends": router_mcdepends},
        }
        router_dir = os.path.join(self.base_dir, self.repo_dir, "router")
        os.makedirs(router_dir)
        with open(os.path.join(router_dir, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(router_manifest))

        nested_provides = ["nested"]
        nested_depends = []
        nested_mcdepends = ["test.router"]
        nested_manifest = {
            "name": "test.nested",
            "attributes": {"depends": nested_depends, "provides": nested_provides},
            "model_components": {"depends": nested_mcdepends},
        }
        nested_dir = os.path.join(self.base_dir, self.repo_dir, "nested")
        os.makedirs(nested_dir)
        with open(os.path.join(nested_dir, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(nested_manifest))

        launch_provides = []
        launch_depends = ["topology", "nested"]
        launch_mcdepends = []
        launch_manifest = {
            "name": "test.launch",
            "attributes": {"depends": launch_depends, "provides": launch_provides},
            "model_components": {"depends": launch_mcdepends},
        }
        launch_dir = os.path.join(self.base_dir, self.repo_dir, "launch")
        os.makedirs(launch_dir)
        with open(os.path.join(launch_dir, "MANIFEST"), "w", encoding="utf8") as f:
            f.write(yaml.safe_dump(launch_manifest))

        mcm = ModelComponentManager(repository_db=self.repository_db)
        topo_comp = ModelComponent(path=topo_dir)
        launch_comp = ModelComponent(path=launch_dir)

        mcm.build_dependency_graph([topo_comp, launch_comp])

        actual_list = mcm.dg.get_ordered_entity_list()
        expected_list = [
            "test.basic",
            "test.generic",
            "test.topo",
            "test.router",
            "test.nested",
            "test.launch",
        ]
        actual_names = [comp.name for comp in actual_list]
        self.assertEqual(expected_list, actual_names)

    def test_dependency_grouping(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        m1 = ModelComponent(path=self.c17, repository_db=self.repository_db)
        m2 = ModelComponent(path=self.c18, repository_db=self.repository_db)
        m3 = ModelComponent(path=self.c19, repository_db=self.repository_db)
        m4 = ModelComponent(path=self.c20, repository_db=self.repository_db)
        mc_list = [m1, m2]
        expected_list = [m3.name, m1.name, m4.name, m2.name]

        mcm.build_dependency_graph(mc_list)

        actual_object_list = mcm.dg.get_ordered_entity_list()
        actual_list = [component.name for component in actual_object_list]

        self.assertEqual(expected_list, actual_list)

    def test_large_dependency_grouping(self):
        mcm = ModelComponentManager(repository_db=self.repository_db)

        expected_list = []

        mcs = []
        for mc_path in self.extra_mc_paths:
            mc = ModelComponent(path=mc_path, repository_db=self.repository_db)
            expected_list.append(mc.name)
            if mc_path.endswith("0") or mc_path.endswith("1"):
                continue
            mcs.append(mc)

        mcm.build_dependency_graph(mcs)

        actual_object_list = mcm.dg.get_ordered_entity_list()
        actual_list = [component.name for component in actual_object_list]

        self.assertEqual(expected_list, actual_list)
