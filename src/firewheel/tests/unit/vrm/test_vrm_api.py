import os
import math
import time
import shutil
import tempfile
import unittest

import pytest

from firewheel.config import config
from firewheel.vm_resource_manager import api
from firewheel.vm_resource_manager.vm_mapping import VMMapping, VMState
from firewheel.vm_resource_manager.schedule_db import ScheduleDb
from firewheel.vm_resource_manager.experiment_start import ExperimentStart
from firewheel.vm_resource_manager.vm_resource_store import VmResourceStore


class APITestCase(unittest.TestCase):
    def setUp(self):
        # Create valid and invalid repository directories
        self.vmmapping_entries = [
            {"server_name": "1", "control_ip": "2", "server_uuid": "1234"},
            {
                "server_name": "2",
                "control_ip": "3",
                "state": "testing",
                "current_time": "0",
                "server_uuid": "4321",
            },
        ]

        # A database connections we'll use.
        self.vmmapping = VMMapping(
            hostname=config["grpc"]["hostname"],
            port=config["grpc"]["port"],
            db=config["test"]["grpc_db"],
        )

        self.tmpdir = tempfile.mkdtemp()
        self.cache_base = os.path.join(self.tmpdir, "base")
        self.metadata_cache = os.path.join(self.cache_base, "vm_resources")

        self.test_vmr_store_name = config["test"]["vm_resource_store_test_database"]
        self.vm_resource_store = VmResourceStore(store=self.test_vmr_store_name)
        self.metadata_cache = self.vm_resource_store.cache
        self.test_schedule_db_name = config["test"]["schedule_test_database"]
        self.schedule_db = ScheduleDb(cache_name=self.test_schedule_db_name)
        self.fn_key = 1

        self.experiment_start = ExperimentStart(
            hostname=config["grpc"]["hostname"],
            port=config["grpc"]["port"],
            db=config["test"]["grpc_db"],
        )

        self.vm_resource1_name = "vm_resource1.sh"
        self.vm_resource1_path = os.path.join(self.tmpdir, self.vm_resource1_name)
        self.vm_resource1 = """
#!/bin/bash
echo 'Hello, World!'
"""
        with open(self.vm_resource1_path, "w", encoding="utf8") as fname:
            fname.write(self.vm_resource1)

    def tearDown(self):
        self.vmmapping.destroy_all()
        self.schedule_db.destroy_all()
        self.experiment_start.clear_start_time()

        self.vm_resource_store.remove_file("*")

        # remove the temp directories
        shutil.rmtree(self.tmpdir)

    def test_add_vm(self):
        api.add_vm(
            self.vmmapping_entries[0]["server_uuid"],
            self.vmmapping_entries[0]["server_name"],
            self.vmmapping_entries[0]["control_ip"],
            mapping=self.vmmapping,
        )

        result = self.vmmapping.get(
            server_uuid=self.vmmapping_entries[0]["server_uuid"]
        )
        self.assertEqual(
            result["server_uuid"], self.vmmapping_entries[0]["server_uuid"]
        )
        self.assertEqual(
            result["server_name"], self.vmmapping_entries[0]["server_name"]
        )
        self.assertEqual(result["control_ip"], self.vmmapping_entries[0]["control_ip"])
        self.assertEqual(
            result["state"], VMState.UNINITIALIZED
        )

    def test_add_vm_no_vm_resources(self):
        api.add_vm(
            self.vmmapping_entries[0]["server_uuid"],
            self.vmmapping_entries[0]["server_name"],
            self.vmmapping_entries[0]["control_ip"],
            use_vm_manager=False,
            mapping=self.vmmapping,
        )

        result = self.vmmapping.get(
            server_uuid=self.vmmapping_entries[0]["server_uuid"]
        )
        self.assertEqual(
            result["server_uuid"], self.vmmapping_entries[0]["server_uuid"]
        )
        self.assertEqual(
            result["server_name"], self.vmmapping_entries[0]["server_name"]
        )
        self.assertEqual(result["control_ip"], self.vmmapping_entries[0]["control_ip"])
        self.assertEqual(result["state"], VMState.NA)

    def test_get_vm_times(self):
        self.vmmapping.batch_put(self.vmmapping_entries)

        times = api.get_vm_times(mapping=self.vmmapping)
        self.assertEqual(len(times), len(self.vmmapping_entries))
        for entry in self.vmmapping_entries:
            self.assertTrue(entry["server_name"] in times)
        self.assertEqual(
            times[self.vmmapping_entries[1]["server_name"]],
            self.vmmapping_entries[1]["current_time"],
        )

    def test_get_vm_times_with_filter(self):
        self.vmmapping.batch_put(self.vmmapping_entries)

        times = api.get_vm_times(
            filter_time=self.vmmapping_entries[1]["current_time"],
            mapping=self.vmmapping,
        )
        self.assertEqual(len(times), 1)
        self.assertTrue(self.vmmapping_entries[1]["server_name"] in times)
        self.assertEqual(
            self.vmmapping_entries[1]["current_time"],
            times[self.vmmapping_entries[1]["server_name"]],
        )

    def test_get_vm_states(self):
        self.vmmapping.batch_put(self.vmmapping_entries)

        states = api.get_vm_states(mapping=self.vmmapping)
        self.assertEqual(len(states), len(self.vmmapping_entries))
        for entry in self.vmmapping_entries:
            self.assertTrue(entry["server_name"] in states)
        self.assertEqual(
            states[self.vmmapping_entries[1]["server_name"]],
            self.vmmapping_entries[1]["state"],
        )
        self.assertEqual(
            states[self.vmmapping_entries[0]["server_name"]],
            VMState.UNINITIALIZED,
        )

    def test_get_vm_states_with_filter(self):
        self.vmmapping.batch_put(self.vmmapping_entries)

        states = api.get_vm_states(
            filter_state=self.vmmapping_entries[1]["state"], mapping=self.vmmapping
        )
        self.assertEqual(len(states), 1)
        self.assertTrue(self.vmmapping_entries[1]["server_name"] in states)
        self.assertEqual(
            states[self.vmmapping_entries[1]["server_name"]],
            self.vmmapping_entries[1]["state"],
        )

    def test_get_start(self):
        added_time = self.experiment_start.add_start_time()

        found_time = api.get_experiment_start_time(start=self.experiment_start)
        self.assertEqual(added_time, found_time)

    def test_destroy_all(self):
        self.vmmapping.batch_put(self.vmmapping_entries)

        sched_val = b""
        for entry in self.vmmapping_entries:
            self.schedule_db.put(entry["server_name"], sched_val, entry["control_ip"])
        sched_result = self.schedule_db.get(self.vmmapping_entries[0]["server_name"])
        self.assertEqual(sched_result, sched_val)

        self.experiment_start.add_start_time()

        api.destroy_all(
            mapping=self.vmmapping,
            schedule=self.schedule_db,
            start=self.experiment_start,
        )

        self.assertEqual(self.experiment_start.get_start_time(), None)
        sched_result = self.schedule_db.get(self.vmmapping_entries[0]["server_name"])
        self.assertEqual(sched_result, None)
        result = self.vmmapping.get(
            server_uuid=self.vmmapping_entries[0]["server_uuid"]
        )
        self.assertEqual(result, None)

    def test_get_vm_states_empty(self):
        result = api.get_vm_states(mapping=self.vmmapping)
        self.assertEqual(result, {})

    def test_get_vm_times_empty(self):
        result = api.get_vm_times(mapping=self.vmmapping)
        self.assertEqual(result, {})

    def test_get_start_empty(self):
        result = api.get_experiment_start_time(start=self.experiment_start)
        self.assertEqual(result, None)

    def test_get_launch_empty(self):
        result = api.get_experiment_launch_time(start=self.experiment_start)
        self.assertEqual(result, None)

    def test_set_launch_empty(self):
        result = api.get_experiment_launch_time(start=self.experiment_start)
        self.assertEqual(result, None)

        result = api.set_experiment_launch_time(start=self.experiment_start)
        determined_start_time = self.experiment_start.get_launch_time()
        self.assertEqual(result, determined_start_time)

    def test_set_start_empty(self):
        result = api.get_experiment_start_time(start=self.experiment_start)
        self.assertEqual(result, None)

        result = api.add_experiment_start_time(start=self.experiment_start)
        determined_start_time = self.experiment_start.get_start_time()
        self.assertEqual(result, determined_start_time)

    def test_time_to_start(self):
        # Set launch time
        inserted_time = self.experiment_start.set_launch_time()
        determined_launch_time = self.experiment_start.get_launch_time()
        self.assertEqual(inserted_time, determined_launch_time)

        # Should return none if the experiment hasn't started
        delta = self.experiment_start.get_time_to_start()
        self.assertEqual(None, delta)

        # Set the start time
        inserted_time = self.experiment_start.add_start_time()
        determined_start_time = self.experiment_start.get_start_time()
        self.assertEqual(inserted_time, determined_start_time)

        # The time should be "close" to 60 seconds
        delta = api.get_experiment_time_to_start(start=self.experiment_start)
        self.assertTrue(math.isclose(delta, 60, rel_tol=0.05))

    @pytest.mark.long
    def test_get_time_since_start(self):
        # Should return none if the experiment hasn't started
        delta = self.experiment_start.get_time_since_start()
        self.assertEqual(None, delta)

        # Set the start time
        inserted_time = self.experiment_start.add_start_time()
        determined_start_time = self.experiment_start.get_start_time()
        self.assertEqual(inserted_time, determined_start_time)

        time.sleep(65)

        # The time should be "close" to 5 seconds
        delta = api.get_experiment_time_since_start(start=self.experiment_start)
        self.assertTrue(math.isclose(delta, 5, rel_tol=0.05))

    def test_add_vm_resource_file(self):
        start_contents = self.vm_resource_store.list_contents()
        for item in start_contents:
            self.assertNotEqual(item[self.fn_key], self.vm_resource1_name)

        api.add_vm_resource_file(self.vm_resource1_path, store=self.vm_resource_store)

        end_contents = self.vm_resource_store.list_contents()
        found_items = []
        for item in end_contents:
            if item[self.fn_key] == self.vm_resource1_name:
                found_items.append(item)
        self.assertEqual(len(found_items), 1)

    def test_vm_resource_list(self):
        self.vm_resource_store.add_file(self.vm_resource1_path)
        store_contents = self.vm_resource_store.list_contents()
        store_contents_list = []
        for item in store_contents:
            store_contents_list.append(item)

        api_contents = api.vm_resource_list(store=self.vm_resource_store)

        original_len = len(store_contents_list)
        self.assertEqual(len(store_contents_list), len(api_contents))
        for item in store_contents_list:
            self.assertTrue(item[self.fn_key] in api_contents)

        # Re-add the file to make sure we only get unique entries
        self.vm_resource_store.add_file(self.vm_resource1_path)
        store_contents = self.vm_resource_store.list_contents()
        store_contents_list = []
        for item in store_contents:
            store_contents_list.append(item)

        api_contents = api.vm_resource_list(store=self.vm_resource_store)
        self.assertEqual(len(api_contents), original_len)
        for item in store_contents_list:
            self.assertTrue(item[self.fn_key] in api_contents)
