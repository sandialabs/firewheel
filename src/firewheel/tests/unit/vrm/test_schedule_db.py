import unittest
import tempfile
from fnmatch import fnmatch
from pathlib import Path
from unittest.mock import patch

from firewheel.vm_resource_manager.schedule_db import (
    ScheduleDb,
    _build_schedule_document,
    _decode_schedule_document,
)


class FakeScheduleCache:
    def __init__(self, cache_name, log=None):  # noqa: ARG002
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def add_file_from_content(self, content, filename, broadcast=True):  # noqa: ARG002
        self.root.joinpath(filename).write_text(content, encoding="utf8")

    def get_path(self, filename):
        path = self.root.joinpath(filename)
        if not path.exists():
            raise FileNotFoundError(filename)
        return path

    def list_distinct_contents(self, pattern=None):
        filenames = sorted(path.name for path in self.root.iterdir() if path.is_file())
        if pattern is None:
            return filenames
        return [filename for filename in filenames if fnmatch(filename, pattern)]

    def remove_file(self, pattern):
        for filename in self.list_distinct_contents(pattern):
            self.root.joinpath(filename).unlink()

    def cleanup(self):
        self.tmpdir.cleanup()


class ScheduleDocumentHelperTestCase(unittest.TestCase):
    def test_build_schedule_document_encodes_payload(self):
        document = _build_schedule_document("vm-1", b"schedule-bytes", "10.0.0.1")

        self.assertEqual(
            document,
            {
                "server_name": "vm-1",
                "text": "c2NoZWR1bGUtYnl0ZXM=",
                "ip": "10.0.0.1",
            },
        )

    def test_decode_schedule_document_decodes_payload_without_mutating_input(self):
        document = {
            "server_name": "vm-1",
            "text": "c2NoZWR1bGUtYnl0ZXM=",
            "ip": "10.0.0.1",
        }

        decoded = _decode_schedule_document(document)

        self.assertEqual(
            decoded,
            {
                "server_name": "vm-1",
                "text": b"schedule-bytes",
                "ip": "10.0.0.1",
            },
        )
        self.assertEqual(document["text"], "c2NoZWR1bGUtYnl0ZXM=")

    def test_schedule_document_helpers_round_trip_empty_payload(self):
        document = _build_schedule_document("vm-1", b"", "")

        self.assertEqual(
            _decode_schedule_document(document),
            {
                "server_name": "vm-1",
                "text": b"",
                "ip": "",
            },
        )


class ScheduleDbTestCase(unittest.TestCase):
    def setUp(self):
        self.file_store_patch = patch(
            "firewheel.vm_resource_manager.schedule_db.FileStore",
            FakeScheduleCache,
        )
        self.file_store_patch.start()
        self.schedule_db = ScheduleDb(cache_name="testScheduleDB")

        # Create valid and invalid repository directories
        self.entries = [
            {"server_name": "1", "text": b"", "ip": ""},
            {"server_name": "2", "text": b"", "ip": ""},
        ]
        self.invalid_entry_1 = {
            "server_name": "test-invalid",
            "text": b"asdf",
            "vm_resources_ip": "",
            "invalid": "value",
        }
        self.invalid_entry_2 = {"invalid": "value"}

    def tearDown(self):
        self.schedule_db.cache.remove_file("*")
        self.schedule_db.cache.cleanup()
        self.schedule_db.close()
        self.file_store_patch.stop()

    def test_put_schedule(self):
        self.schedule_db.put(self.entries[0]["server_name"], b"", self.entries[0]["ip"])
        found = self.schedule_db.list_all()

        self.assertEqual(self.entries[0]["server_name"], found[0]["server_name"])

    def test_batch_put(self):
        self.schedule_db.batch_put(self.entries)
        found1 = self.schedule_db.list_all(self.entries[0]["server_name"])[0]
        found2 = self.schedule_db.list_all(self.entries[1]["server_name"])[0]
        self.assertEqual(self.entries[0]["server_name"], found1["server_name"])
        self.assertEqual(self.entries[0]["text"], found1["text"])
        self.assertEqual(self.entries[1]["server_name"], found2["server_name"])
        self.assertEqual(self.entries[1]["text"], found2["text"])

    def test_add_too_many_keys(self):
        with self.assertRaises(TypeError):
            # pylint: disable=unexpected-keyword-arg
            self.schedule_db.put(**self.invalid_entry_1)

    def test_add_wrong_key(self):
        with self.assertRaises(TypeError):
            # pylint: disable=unexpected-keyword-arg
            self.schedule_db.put(**self.invalid_entry_2)

    def test_duplicate_put(self):
        self.schedule_db.put(
            self.entries[0]["server_name"], b"a", self.entries[0]["ip"]
        )
        self.schedule_db.put(
            self.entries[0]["server_name"], b"b", self.entries[0]["ip"]
        )
        found1 = self.schedule_db.list_all()[0]
        self.assertEqual(self.entries[0]["server_name"], found1["server_name"])
        self.assertEqual(b"b", found1["text"])

    def test_destroy_one(self):
        self.schedule_db.put(
            self.entries[0]["server_name"],
            self.entries[0]["text"],
            self.entries[0]["ip"],
        )
        self.schedule_db.destroy_one(self.entries[0]["server_name"])
        with self.assertRaises(IndexError):
            # pylint: disable=expression-not-assigned
            self.schedule_db.list_all()[0]
        self.assertEqual(self.schedule_db.get(self.entries[0]["server_name"]), None)

    def test_destroy_all(self):
        self.schedule_db.put(
            self.entries[0]["server_name"],
            self.entries[0]["text"],
            self.entries[0]["ip"],
        )
        self.schedule_db.put(
            self.entries[1]["server_name"],
            self.entries[1]["text"],
            self.entries[1]["ip"],
        )
        self.schedule_db.destroy_all()
        with self.assertRaises(IndexError):
            # pylint: disable=expression-not-assigned
            self.schedule_db.list_all()[0]

    def test_get(self):
        n_entries = []
        for entry in self.entries:
            self.schedule_db.put(entry["server_name"], entry["text"], entry["ip"])
            n_entries.append(entry["server_name"])

        got_entries = []
        for entry in n_entries:
            cur_text = self.schedule_db.get(entry)
            got_entries.append({"text": cur_text, "server_name": entry, "ip": ""})
        self.assertEqual(got_entries, self.entries)

        for ent in got_entries:
            del n_entries[n_entries.index(ent["server_name"])]

        self.assertEqual(len(n_entries), 0)

    def test_invalid_get(self):
        result = self.schedule_db.get("invalid")
        self.assertEqual(result, None)
