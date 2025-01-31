import os
import time
import shutil
import tempfile
import unittest
from datetime import datetime

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

    def test_upload_image_no_manifest_property(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )
        del mcp.manifest["images"]

        res = mcp._upload_images()
        self.assertFalse(res)

    def test_missing_image(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        mcp.manifest["images"][0] = {"paths": ["invalid"]}
        with self.assertRaises(MissingImageError):
            mcp._upload_images()

    def test_upload_image(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [])

        res = mcp._upload_images()
        self.assertEqual(res, ["no_date"])

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [self.image_file_name])

    def test_double_upload_image(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [])

        res = mcp._upload_images()
        self.assertEqual(res, ["no_date"])

        first_upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [self.image_file_name])

        # Make sure our upload time would change if we re-uploaded
        time.sleep(2)
        res = mcp._upload_images()
        self.assertEqual(res, [False])

        second_upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [self.image_file_name])

        self.assertEqual(first_upload_time, second_upload_time)

    def test_upload_subdir_image(self):
        mcp = ModelComponent(
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

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [])

        mcp.manifest["images"][0] = {"paths": [image_rel_path]}

        result = mcp._upload_images()
        self.assertEqual(result, ["no_date"])

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [image_name])

        result = mcp._upload_images()
        self.assertEqual(result, [False])

    def test_upload_new_time_same_hash(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        pre_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_hash = hash_file(self.image1_path)

        result = mcp._upload_images()
        self.assertEqual(result, ["no_date"])

        upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(upload_time, pre_time)
        self.assertEqual(upload_hash, pre_hash)

        # Sleep so we are sure we get a new time.
        time.sleep(2)
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write(self.image1)

        post_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)

        self.assertNotEqual(pre_time, post_time)
        self.assertTrue(upload_time < post_time)
        self.assertEqual(pre_hash, post_hash)

        self.assertTrue(post_time > pre_time)

        result = mcp._upload_images()
        self.assertEqual(result, ["same_hash"])

    def test_upload_new_time_new_hash(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        pre_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_hash = hash_file(self.image1_path)

        result = mcp._upload_images()
        self.assertEqual(result, ["no_date"])

        upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(upload_time, pre_time)
        self.assertEqual(upload_hash, pre_hash)

        # Sleep so we are sure we get a new time.
        time.sleep(2)
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        post_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)

        self.assertNotEqual(pre_time, post_time)
        self.assertTrue(upload_time < post_time)
        self.assertNotEqual(pre_hash, post_hash)

        self.assertTrue(post_time > pre_time)

        result = mcp._upload_images()
        self.assertEqual(result, ["new_hash"])

    def test_upload_old_time_new_hash(self):
        # What is this test case accomplishing?
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        subdir = "subdir"
        second_image_path = os.path.join(self.mc_dir, subdir, self.image_file_name)
        os.makedirs(os.path.join(self.mc_dir, subdir))
        time.sleep(2)
        with open(second_image_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        second_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        second_hash = hash_file(second_image_path)

        # Sleep so we are sure we get a new time.
        time.sleep(2)

        result = mcp._upload_images()
        self.assertEqual(result, ["no_date"])

        upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        self.assertEqual(upload_time, second_time)

        post_hash = hash_file(self.image1_path)
        store_hash = self.image_store.get_file_hash(self.image_file_name)

        self.assertEqual(store_hash, post_hash)
        self.assertNotEqual(second_hash, post_hash)

        result = mcp._upload_images()
        self.assertEqual(result, [False])

    def test_upload_revert_same_file(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        pre_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        pre_hash = hash_file(self.image1_path)

        result = mcp._upload_images()
        self.assertEqual(result, ["no_date"])

        upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)
        self.assertEqual(upload_time, pre_time)
        self.assertEqual(upload_hash, pre_hash)

        # Sleep so we are sure we get a new time.
        time.sleep(2)

        # Move the file elsewhere
        tmp_path = tempfile.mkstemp()
        shutil.move(self.image1_path, tmp_path[1])

        # Write new contents
        with open(self.image1_path, "w", encoding="utf8") as fname:
            fname.write("different contents")

        post_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)

        self.assertNotEqual(pre_time, post_time)
        self.assertTrue(upload_time < post_time)
        self.assertNotEqual(pre_hash, post_hash)

        self.assertTrue(post_time > pre_time)

        result = mcp._upload_images()
        self.assertEqual(result, ["new_hash"])

        upload_time = self.image_store.get_file_upload_date(self.image_file_name)
        upload_hash = self.image_store.get_file_hash(self.image_file_name)

        # Sleep so we are sure we get a new time.
        time.sleep(2)

        # Revert to previous file
        rev_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        rev_hash = hash_file(self.image1_path)
        shutil.move(tmp_path[1], self.image1_path)

        post_time = datetime.utcfromtimestamp(os.path.getmtime(self.image1_path))
        post_hash = hash_file(self.image1_path)

        # The file was moved so the pre/post time should be the same
        self.assertEqual(pre_time, post_time)

        # But the file is different than the file being reverted
        self.assertNotEqual(rev_time, post_time)
        self.assertNotEqual(rev_hash, post_hash)

        # Because the file was revered the time will be older than the upload_time
        self.assertTrue(upload_time > post_time)

        # And the file will be older than the reverted file
        self.assertTrue(rev_time > post_time)

        result = mcp._upload_images()

        # This should be uploaded because even though the time is "older" the contents
        # are newer.
        self.assertEqual(result, ["new_hash"])

    def test_upload_image_one_not_another_from_manifest(self):
        mcp = ModelComponent(
            path=self.mc_dir,
            repository_db=self.repository_db,
            image_store=self.image_store,
        )

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [])

        result = mcp._upload_images()
        self.assertTrue(result)

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        self.assertEqual(image_list, [self.image_file_name])
        first_upload_date = self.image_store.get_file_upload_date(self.image_file_name)

        second_image_name = "second_image"
        second_image_contents = "SECOND IMAGE!"
        second_image_path = os.path.join(self.mc_dir, second_image_name)
        time.sleep(1)
        with open(second_image_path, "w", encoding="utf8") as fname:
            fname.write(second_image_contents)

        old_image_list = mcp.manifest["images"]
        mcp.manifest["images"] = [{"paths": [second_image_name]}]
        mcp.manifest["images"].extend(old_image_list)

        # Make sure we get different upload dates.
        time.sleep(2)

        result = mcp._upload_images()
        self.assertTrue(result)

        image_list = self.image_store.list_contents()
        image_list = [image[self.fn_key] for image in image_list]
        image_list.sort()
        expected_list = [second_image_name, self.image_file_name]
        expected_list.sort()

        self.assertEqual(image_list, expected_list)

        second_upload_date = self.image_store.get_file_upload_date(self.image_file_name)
        second_image_upload_date = self.image_store.get_file_upload_date(
            second_image_name
        )
        self.assertEqual(first_upload_date, second_upload_date)
        self.assertNotEqual(second_upload_date, second_image_upload_date)
