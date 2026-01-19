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
from firewheel.control.model_component import ImageStore, ModelComponent
from firewheel.control.model_component_exceptions import MissingImageError


# pylint: disable=protected-access
class ModelComponentImageUploadTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_base = os.path.join(self.tmpdir, "base")
        self.image_cache = os.path.join(self.cache_base, "image")

        self.repo_path = os.path.join(self.tmpdir, "repo")
        os.mkdir(self.repo_path)
        self.mc_dir = os.path.join(self.repo_path, "mc")

        self.repository_db = initalize_repo_db()
        self.repository_db.add_repository({"path": self.repo_path})

        test_image_store = config["test"]["image_db"]
        self.image_store = ImageStore(store=test_image_store)
        self.fn_key = 1

        self.image_file_name = "image1"

        self.depends = []
        self.provides = []
        self.mc_depends = []
        self.manifest = {
            "name": "test.model_component",
            "attributes": {"depends": self.depends, "provides": self.provides},
            "model_components": {"depends": self.mc_depends},
            "images": [{"paths": [self.image_file_name]}],
        }

        os.makedirs(self.mc_dir)
        with open(os.path.join(self.mc_dir, "MANIFEST"), "w", encoding="utf8") as fname:
            fname.write(yaml.safe_dump(self.manifest))

        self.image1_path = os.path.join(self.mc_dir, self.image_file_name)
        self.image1 = """
#!/bin/bash
echo 'Hello, World!'
"""
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write(self.image1)

    def tearDown(self):
        self.image_store.remove_file("*")

        cleanup_repo_db(self.repository_db)

        # remove the temp directories
        shutil.rmtree(self.tmpdir)

    def _get_image_store_files(self):
        return [image[self.fn_key] for image in self.image_store.list_contents()]

    def test_upload_image_no_manifest_property(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )
        del mc.manifest["images"]

        mc.upload_files()
        self.assertEqual(self._get_image_store_files(), [])

    def test_missing_image(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        mc.manifest["images"][0] = {"paths": ["invalid"]}
        with self.assertRaises(MissingImageError):
            mc.upload_files()

    def test_upload_image(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        self.assertEqual(self._get_image_store_files(), [])

        mc.upload_files()

        self.assertEqual(self._get_image_store_files(), [self.image_file_name])

    def test_existing_images_not_reuploaded_single(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )
        with patch.object(
            mc.image_store, "add_image_file", wraps=mc.image_store.add_image_file
        ) as mock_image_upload_method:
            self.assertEqual(self._get_image_store_files(), [])

            mc.upload_files()
            mock_image_upload_method.assert_called_once()
            self.assertEqual(self._get_image_store_files(), [self.image_file_name])

            mock_image_upload_method.reset_mock()
            mc.upload_files()
            # Ensure no uploads occurred after the reset (image exists)
            mock_image_upload_method.assert_not_called()
            self.assertEqual(self._get_image_store_files(), [self.image_file_name])

    def test_existing_images_not_reuploaded_double(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )
        with patch.object(
            mc.image_store, "add_image_file", wraps=mc.image_store.add_image_file
        ) as mock_image_upload_method:
            self.assertEqual(self._get_image_store_files(), [])

            mc.upload_files()
            mock_image_upload_method.assert_called_once()
            self.assertEqual(self._get_image_store_files(), [self.image_file_name])

            second_image_name = "second_image"
            second_image_contents = "SECOND IMAGE!"
            second_image_path = os.path.join(self.mc_dir, second_image_name)
            time.sleep(1)
            with open(second_image_path, "w", encoding="utf8") as fname:
                fname.write(second_image_contents)

            old_image_list = mc.manifest["images"]
            mc.manifest["images"] = [{"paths": [second_image_name]}]
            mc.manifest["images"].extend(old_image_list)

            mock_image_upload_method.reset_mock()
            mc.upload_files()
            # Ensure that only one upload occurs after reset (for the second image)
            mock_image_upload_method.assert_called_once()
            self.assertEqual(
                sorted(self._get_image_store_files()),
                sorted([self.image_file_name, second_image_name]),
            )

    def test_upload_subdir_image(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        image_name = "subdir_image"
        image_contents = "I am a subdir image"
        image_subdir = "subdir"
        image_dir = os.path.join(self.mc_dir, image_subdir)
        os.makedirs(image_dir)
        image_path = os.path.join(image_dir, image_name)
        image_rel_path = os.path.join(image_subdir, image_name)
        time.sleep(1)
        with open(image_path, "w", encoding="utf8") as fname:
            fname.write(image_contents)

        self.assertEqual(self._get_image_store_files(), [])

        mc.manifest["images"][0] = {"paths": [image_rel_path]}
        mc.upload_files()

        self.assertEqual(self._get_image_store_files(), [image_name])

    def test_upload_new_time_same_hash(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        pre_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_hash = hash_file(self.image1_path)

        mc.upload_files()

        upload_timestamp = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(upload_timestamp, pre_timestamp)
        self.assertEqual(upload_hash, pre_hash)

        # Rewrite the file after a delay to ensure a new timestamp
        time.sleep(1)
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write(self.image1)

        post_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)
        self.assertTrue(pre_timestamp < post_timestamp)
        self.assertTrue(upload_timestamp < post_timestamp)
        self.assertEqual(pre_hash, post_hash)

        mc.upload_files()

        new_upload_timestamp = self.image_store.get_file_upload_date(self.image_file_name)
        new_upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(new_upload_timestamp, upload_timestamp)
        self.assertEqual(new_upload_hash, upload_hash)

    def test_upload_new_time_new_hash(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        pre_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_hash = hash_file(self.image1_path)

        mc.upload_files()

        upload_timestamp = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(upload_timestamp, pre_timestamp)
        self.assertEqual(upload_hash, pre_hash)

        # Rewrite the file after a delay to ensure a new timestamp and new contents
        time.sleep(1)
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        post_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)
        self.assertTrue(pre_timestamp < post_timestamp)
        self.assertTrue(upload_timestamp < post_timestamp)
        self.assertNotEqual(pre_hash, post_hash)

        mc.upload_files()

        new_upload_timestamp = self.image_store.get_file_upload_date(self.image_file_name)
        new_upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertNotEqual(new_upload_timestamp, upload_timestamp)
        self.assertNotEqual(new_upload_hash, upload_hash)

    def test_upload_old_time_new_hash(self):
        # What is this test case accomplishing?
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        subdir = "subdir"
        second_image_path = os.path.join(self.mc_dir, subdir, self.image_file_name)
        os.makedirs(os.path.join(self.mc_dir, subdir))
        time.sleep(1)
        with open(second_image_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        second_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        second_hash = hash_file(second_image_path)

        # Sleep so we are sure we get a new time.
        time.sleep(1)

        mc.upload_files()
        # self.assertEqual(result, {self.image_file_name: "no_date"})

        upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        self.assertEqual(upload_time, second_time)

        post_hash = hash_file(self.image1_path)
        store_hash = self.image_store.get_file_hash(self.image_file_name)

        self.assertEqual(store_hash, post_hash)
        self.assertNotEqual(second_hash, post_hash)

        mc.upload_files()
        # self.assertEqual(result, {self.image_file_name: False})
        assert False

    def test_upload_revert_same_file(self):
        mc = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        pre_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_hash = hash_file(self.image1_path)

        mc.upload_files()

        upload_timestamp = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(upload_timestamp, pre_timestamp)
        self.assertEqual(upload_hash, pre_hash)

        # Sleep so we are sure we get a new time.
        time.sleep(1)

        # Move the file elsewhere
        tmp_path = tempfile.mkstemp()
        shutil.move(self.image1_path, tmp_path[1])

        # Write new contents
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        post_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)
        self.assertTrue(pre_timestamp < post_timestamp)
        self.assertTrue(upload_timestamp < post_timestamp)
        self.assertNotEqual(pre_hash, post_hash)

        mc.upload_files()

        new_upload_timestamp = self.image_store.get_file_upload_date(self.image_file_name)
        new_upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(new_upload_timestamp, post_timestamp)
        self.assertEqual(new_upload_hash, post_hash)

        # Sleep so we are sure we get a new time.
        time.sleep(1)

        # Revert to previous file
        pre_rev_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_rev_hash = hash_file(self.image1_path)
        shutil.move(tmp_path[1], self.image1_path)
        post_rev_timestamp = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_rev_hash = hash_file(self.image1_path)
        # The file was moved so the original and post-reversion times should be the same
        self.assertEqual(pre_timestamp, post_rev_timestamp)
        # ...but the file is different than the file being reverted
        self.assertNotEqual(pre_rev_timestamp, post_rev_timestamp)
        self.assertNotEqual(pre_rev_hash, post_rev_hash)
        # ...and the reverted timestamp will be older than the one in the file store
        self.assertTrue(post_rev_timestamp < new_upload_timestamp)

        mc.upload_files()

        # This should be uploaded because even though the time is "older" the contents
        # are newer.
        assert False
