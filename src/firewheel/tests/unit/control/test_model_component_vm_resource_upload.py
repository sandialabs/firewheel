import os
import time
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import yaml

from firewheel.config import config
from firewheel.lib.utilities import hash_file
from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component import ModelComponent
from firewheel.control.model_component_exceptions import (
    MissingVmResourceError,
    MissingRequiredVMResourcesError,
)
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


# pylint: disable=protected-access
class ModelComponentVMResourceUploadTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_base = os.path.join(self.tmpdir, "base")
        self.metadata_cache = os.path.join(self.cache_base, "vm_resource")

        self.repo_path = os.path.join(self.tmpdir, "repo")
        os.mkdir(self.repo_path)
        self.mc_dir = os.path.join(self.repo_path, "mc")

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository({"path": self.repo_path})

        test_vmr_store = config["test"]["vm_resource_store_test_database"]
        self.vm_resource_store = VmResourceStore(store=test_vmr_store)
        self.fn_key = 1

        self.resource_file_name = "resource1.sh"

        self.depends = []
        self.provides = []
        self.mc_depends = []
        self.manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.depends, "provides": self.provides},
            "model_components": {"depends": self.mc_depends},
            "vm_resources": [self.resource_file_name],
        }

        os.makedirs(self.mc_dir)
        with open(os.path.join(self.mc_dir, "MANIFEST"), "w", encoding="utf8") as fname:
            fname.write(yaml.safe_dump(self.manifest))

        self.resource1_path = os.path.join(self.mc_dir, self.resource_file_name)
        self.resource1 = """
#!/bin/bash
echo 'Hello, World!'
"""
        with open(self.resource1_path, "w", encoding="utf8") as fname:
            fname.write(self.resource1)

    def tearDown(self):
        self.vm_resource_store.remove_file("*")

        cleanup_repo_db(self.repository_db)

        # remove the temp directories
        shutil.rmtree(self.tmpdir)

    def _get_vm_resource_store_files(self):
        return [
            resource[self.fn_key] for resource in self.vm_resource_store.list_contents()
        ]

    def test_upload_resource_no_manifest_property(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )
        del mc.manifest["vm_resources"]

        mc.upload_files()
        self.assertEqual(self._get_vm_resource_store_files(), [])

    def test_missing_resource(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        mc.manifest["vm_resources"] = ["invalid"]
        with self.assertRaisesRegex(MissingVmResourceError, ".*is not present.*"):
            mc.upload_files()

    def test_upload_resource(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [self.resource_file_name])

    def test_upload_vmr_invalid_string(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = "string"
        with self.assertRaisesRegex(RuntimeError, ".*must be a list.*"):
            mc.upload_files()

    def test_upload_vmr_invalid_int(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = 52
        with self.assertRaisesRegex(RuntimeError, ".*must be a list.*"):
            mc.upload_files()

    def test_upload_vmr_dict(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = {}
        with self.assertRaisesRegex(RuntimeError, ".*must be a list.*"):
            mc.upload_files()

    def test_existing_vmr_not_reuploaded_single(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )
        with patch.object(
            mc.vm_resource_store, "add_file", wraps=mc.vm_resource_store.add_file
        ) as mock_vmr_upload_method:
            self.assertEqual(self._get_vm_resource_store_files(), [])

            mc.upload_files()
            mock_vmr_upload_method.assert_called_once()
            self.assertEqual(self._get_vm_resource_store_files(), [self.resource_file_name])

            mock_vmr_upload_method.reset_mock()
            mc.upload_files()
            # Ensure that no uploads occurred after the reset (VMR exists)
            mock_vmr_upload_method.assert_not_called()
            self.assertEqual(self._get_vm_resource_store_files(), [self.resource_file_name])

    def test_existing_vmr_not_reuploaded_double(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )
        with patch.object(
            mc.vm_resource_store, "add_file", wraps=mc.vm_resource_store.add_file
        ) as mock_vmr_upload_method:
            self.assertEqual(self._get_vm_resource_store_files(), [])

            mc.upload_files()
            mock_vmr_upload_method.assert_called_once()
            self.assertEqual(self._get_vm_resource_store_files(), [self.resource_file_name])

            second_resource_name = "resource2.sh"
            second_resource_contents = "#!/bin/bash"
            second_resource_path = os.path.join(self.mc_dir, second_resource_name)
            time.sleep(1)
            with open(second_resource_path, "w", encoding="utf8") as fname:
                fname.write(second_resource_contents)

            old_resource_list = mc.manifest["vm_resources"]
            mc.manifest["vm_resources"] = [second_resource_name]
            mc.manifest["vm_resources"].extend(old_resource_list)

            mock_vmr_upload_method.reset_mock()
            mc.upload_files()
            # Ensure that only one upload occurs after the reset (for the second VMR)
            mock_vmr_upload_method.assert_called_once()
            self.assertEqual(
                sorted(self._get_vm_resource_store_files()),
                sorted([self.resource_file_name, second_resource_name]),
            )

    def test_upload_subdir_resource(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir)
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        resource_rel_path = os.path.join(resource_subdir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}/{resource_name}"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [resource_name])

    def test_upload_from_manifest_star(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        # Add a sub dir and new VM Resources
        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir)
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}/*"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [resource_name])

    def test_upload_from_manifest_doublestar(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        # Add a sub dir and new VM Resources
        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir)
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}/**"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [resource_name])

    def test_upload_from_manifest_double_star_star(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        # Add a sub dir and new VM Resources
        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir)
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}/**/*"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [resource_name])

    def test_upload_from_manifest_double_star_limit(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        # Add a sub dir and new VM Resources
        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir)
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}/**/*.py"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [])

    def test_upload_from_manifest_double_star_recurse(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        # Add a sub dir and new VM Resources
        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir, "subsubdir")
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}/**"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [resource_name])

    def test_upload_from_manifest_is_dir(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        # Add a sub dir and new VM Resources
        resource_name = "subdir_vm_resource.sh"
        resource_contents = "#!/bin/bash"
        resource_subdir = "subdir"
        resource_dir = os.path.join(self.mc_dir, resource_subdir)
        os.makedirs(resource_dir)
        resource_path = os.path.join(resource_dir, resource_name)
        time.sleep(1)
        with open(resource_path, "w", encoding="utf8") as fname:
            fname.write(resource_contents)

        self.assertEqual(self._get_vm_resource_store_files(), [])

        mc.manifest["vm_resources"] = [f"{resource_subdir}"]
        mc.upload_files()

        self.assertEqual(self._get_vm_resource_store_files(), [resource_name])

    def test_upload_new_time_same_hash(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        pre_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        pre_hash = hash_file(self.resource1_path)

        mc.upload_files()

        upload_timestamp = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        upload_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)
        self.assertEqual(upload_timestamp, pre_timestamp)
        self.assertEqual(upload_hash, pre_hash)

        # Rewrite the file after a delay to ensure a new timestamp
        time.sleep(1)
        with open(self.resource1_path, "w", encoding="utf8") as fname:
            fname.write(self.resource1)

        post_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        post_hash = hash_file(self.resource1_path)
        self.assertTrue(pre_timestamp < post_timestamp)
        self.assertTrue(upload_timestamp < post_timestamp)
        self.assertEqual(pre_hash, post_hash)

        mc.upload_files()

        new_upload_timestamp = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        new_upload_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)
        self.assertEqual(new_upload_timestamp, upload_timestamp)
        self.assertEqual(new_upload_hash, upload_hash)

    def test_manifest_resource_upload_same_hash(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        pre_time = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        pre_hash = hash_file(self.resource1_path)

        mc.upload_files()

    def test_upload_new_time_new_hash(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        pre_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        pre_hash = hash_file(self.resource1_path)

        mc.upload_files()

        upload_timestamp = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        upload_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)
        self.assertEqual(upload_timestamp, pre_timestamp)
        self.assertEqual(upload_hash, pre_hash)

        # Rewrite the file after a delay to ensure a new timestamp and new contents
        time.sleep(1)
        with open(self.resource1_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        post_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        post_hash = hash_file(self.resource1_path)
        self.assertTrue(pre_timestamp < post_timestamp)
        self.assertTrue(upload_timestamp < post_timestamp)
        self.assertNotEqual(pre_hash, post_hash)

        mc.upload_files()

        new_upload_timestamp = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        new_upload_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)
        self.assertNotEqual(new_upload_timestamp, upload_timestamp)
        self.assertNotEqual(new_upload_hash, upload_hash)

    def test_upload_old_time_new_hash(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        subdir = "subdir"
        second_vm_resource_path = os.path.join(
            self.mc_dir, subdir, self.resource_file_name
        )
        os.makedirs(os.path.join(self.mc_dir, subdir))
        time.sleep(1)
        with open(second_vm_resource_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        second_time = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        second_hash = hash_file(second_vm_resource_path)

        # Sleep so we are sure we get a new time.
        time.sleep(1)

        result = mc._upload_vm_resource(self.resource_file_name)
        self.assertEqual(result, "no_date")

        upload_time = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        self.assertEqual(upload_time, second_time)

        post_hash = hash_file(self.resource1_path)
        store_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)

        self.assertEqual(store_hash, post_hash)
        self.assertNotEqual(second_hash, post_hash)

        result = mc._upload_vm_resource(os.path.join(subdir, self.resource_file_name))
        self.assertEqual(result, "new_hash")
        assert False

    def test_upload_revert_same_file(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            vm_resource_store=self.vm_resource_store,
        )

        pre_time = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        pre_hash = hash_file(self.resource1_path)

        result = mc._upload_vm_resource(self.resource_file_name)
        self.assertEqual(result, "no_date")

        upload_time = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        upload_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)
        self.assertEqual(upload_time, pre_time)
        self.assertEqual(upload_hash, pre_hash)

        # Sleep so we are sure we get a new time.
        time.sleep(1)

        # Move the file elsewhere
        tmp_path = tempfile.mkstemp()
        shutil.move(self.resource1_path, tmp_path[1])

        # Write new contents
        with open(self.resource1_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        post_time = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        post_hash = hash_file(self.resource1_path)

        self.assertNotEqual(pre_time, post_time)
        self.assertTrue(upload_time < post_time)
        self.assertNotEqual(pre_hash, post_hash)

        self.assertTrue(post_time > pre_time)

        result = mc._upload_vm_resource(self.resource_file_name)
        self.assertEqual(result, "new_hash")
        upload_time = self.vm_resource_store.get_file_upload_date(
            self.resource_file_name
        )
        upload_hash = self.vm_resource_store.get_file_hash(self.resource_file_name)

        # Sleep so we are sure we get a new time.
        time.sleep(1)

        # Revert to previous file
        rev_time = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        rev_hash = hash_file(self.resource1_path)
        shutil.move(tmp_path[1], self.resource1_path)

        post_time = datetime.utcfromtimestamp(os.path.getmtime(self.resource1_path))
        post_hash = hash_file(self.resource1_path)

        # The file was moved so the pre/post time should be the same
        self.assertEqual(pre_time, post_time)

        # But the file is different than the file being reverted
        self.assertNotEqual(rev_time, post_time)
        self.assertNotEqual(rev_hash, post_hash)

        # Because the file was revered the time will be older than the upload_time
        self.assertTrue(upload_time > post_time)

        # And the file will be older than the reverted file
        self.assertTrue(rev_time > post_time)

        result = mc._upload_vm_resource(self.resource_file_name)

        # This should be uploaded because even though the time is "older" the contents
        # are newer.
        self.assertEqual(result, "new_hash")
        assert False

    def test_missing_required_exp(self):
        vm_resources = ["test.sh", "run.py"]
        with self.assertRaises(MissingRequiredVMResourcesError) as assertion:
            raise MissingRequiredVMResourcesError(vm_resources)
        self.assertEqual(
            f"These vm_resources have not been uploaded: {vm_resources}",
            str(assertion.exception),
        )
