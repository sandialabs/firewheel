# test_lib_file_store.py
"""Unit tests for :mod:`firewheel.lib.minimega.file_store`."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from firewheel.lib.minimega.file_store import FileStore, FileStoreFile


def _build_filestore(tmp_path: Path) -> FileStore:
    """Create a FileStore instance without running __init__."""
    store = object.__new__(FileStore)
    store.store = "saved"
    store.decompress = False
    store.log = Mock()
    store.mm_api = Mock()
    store.cache_base = str(tmp_path)
    store.cache = str(tmp_path / "saved")
    return store


def test_filestorefile_read_and_close(tmp_path: Path) -> None:
    """Verify FileStoreFile reads data and closes cleanly."""
    data_file = tmp_path / "file.bin"
    data_file.write_bytes(b"abcdef")

    database = Mock()
    database.get_path.return_value = str(data_file)

    with FileStoreFile("file.bin", database) as handle:
        assert handle.read(3) == b"abc"
        assert handle.read() == b"def"

    assert handle.handle.closed is True


def test_filestorefile_read_without_enter_raises() -> None:
    """Verify reading without opening raises RuntimeError."""
    database = Mock()
    handle = FileStoreFile("file.bin", database)

    with pytest.raises(RuntimeError):
        handle.read()


def test_get_lock_release_lock(tmp_path: Path) -> None:
    """Verify local lock directories can be created and released."""
    store = _build_filestore(tmp_path)
    target = str(tmp_path / "target")

    assert store._get_lock(target) is True
    assert os.path.isdir(target + "-lock")
    assert store._release_lock(target) is True
    assert not os.path.exists(target + "-lock")


def test_release_lock_missing_returns_false(tmp_path: Path) -> None:
    """Verify releasing a missing lock returns False."""
    store = _build_filestore(tmp_path)
    assert store._release_lock(str(tmp_path / "missing")) is False


def test_file_lock_context_manager(tmp_path: Path) -> None:
    """Verify file_lock acquires and releases lock around context body."""
    store = _build_filestore(tmp_path)
    target = str(tmp_path / "target")

    with store.file_lock(target) as acquired:
        assert acquired is True
        assert os.path.isdir(target + "-lock")

    assert not os.path.exists(target + "-lock")


def test_strip_extension() -> None:
    """Verify supported compressed suffixes are removed."""
    store = _build_filestore(Path("/tmp"))
    assert store._strip_extension("file.xz") == "file"
    assert store._strip_extension("file.tar.gz") == "file"
    assert store._strip_extension("file.tar") == "file"
    assert store._strip_extension("file.tgz") == "file"
    assert store._strip_extension("file.raw") == "file.raw"


def test_decompress_error_removes_files(tmp_path: Path) -> None:
    """Verify decompression cleanup attempts to remove temp files."""
    store = _build_filestore(tmp_path)
    tmp_local = tmp_path / "tmp.xz"
    host_file = tmp_path / "host"
    tmp_local.write_text("x", encoding="utf-8")
    host_file.write_text("y", encoding="utf-8")

    store._decompress_error(OSError("bad"), str(tmp_local), str(host_file))
    assert not tmp_local.exists()
    assert not host_file.exists()


def test_get_file() -> None:
    """Verify get_file returns a FileStoreFile wrapper."""
    store = _build_filestore(Path("/tmp"))
    file_obj = store.get_file("name.txt")
    assert isinstance(file_obj, FileStoreFile)
    assert file_obj.filename == "name.txt"


def test_get_file_path_without_decompress(monkeypatch) -> None:
    """Verify local cache path is built directly when not decompressing."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", "/files")
    store = _build_filestore(Path("/tmp"))
    store.store = "saved"
    store.decompress = False

    assert store.get_file_path("backup.tar") == "/files/saved/backup.tar"


def test_get_file_path_with_decompress(monkeypatch) -> None:
    """Verify compressed suffix is stripped for decompressed cache paths."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", "/files")
    store = _build_filestore(Path("/tmp"))
    store.store = "saved"
    store.decompress = True

    assert store.get_file_path("backup.tar.gz") == "/files/saved/backup"


def test_check_path(tmp_path: Path, monkeypatch) -> None:
    """Verify check_path uses computed local cache path existence."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"

    full = tmp_path / "saved" / "thing"
    full.parent.mkdir(parents=True)
    full.write_text("x", encoding="utf-8")

    assert store.check_path("thing") is True


def test_get_path_success() -> None:
    """Verify get_path returns resolved local path on success."""
    store = _build_filestore(Path("/tmp"))
    with (
        patch.object(store, "get_file_path", return_value="/tmp/file"),
        patch.object(store, "_minimega_get_data", return_value=("/tmp/file", "")),
    ):
        assert store.get_path("file") == "/tmp/file"


def test_get_path_failed_raises() -> None:
    """Verify get_path raises FileNotFoundError on failed fetch."""
    store = _build_filestore(Path("/tmp"))
    with (
        patch.object(store, "get_file_path", return_value="/tmp/file"),
        patch.object(store, "_minimega_get_data", return_value=("", "failed")),
    ):
        with pytest.raises(FileNotFoundError):
            store.get_path("file")


def test_get_path_decompress_raises() -> None:
    """Verify get_path raises RuntimeError on decompression failure."""
    store = _build_filestore(Path("/tmp"))
    with (
        patch.object(store, "get_file_path", return_value="/tmp/file"),
        patch.object(store, "_minimega_get_data", return_value=("", "decompress")),
    ):
        with pytest.raises(RuntimeError):
            store.get_path("file")


def test_get_file_size() -> None:
    """Verify file size lookup reads a single list_contents result."""
    store = _build_filestore(Path("/tmp"))
    store.list_contents = Mock(return_value=[("host", "file.txt", "123")])
    assert store.get_file_size("file.txt") == 123


def test_get_file_size_not_found() -> None:
    """Verify file size lookup raises when file is absent."""
    store = _build_filestore(Path("/tmp"))
    store.list_contents = Mock(return_value=[])
    with pytest.raises(FileNotFoundError):
        store.get_file_size("file.txt")


def test_get_file_size_multiple_raises() -> None:
    """Verify file size lookup raises when result count is not one."""
    store = _build_filestore(Path("/tmp"))
    store.list_contents = Mock(
        return_value=[("host", "file1.txt", "1"), ("host", "file2.txt", "2")]
    )
    with pytest.raises(RuntimeError):
        store.get_file_size("file.txt")


def test_get_file_hash(tmp_path: Path, monkeypatch) -> None:
    """Verify file hashing is returned for existing cached files."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"

    target = tmp_path / "saved" / "file.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("data", encoding="utf-8")

    value = store.get_file_hash("file.txt")
    assert value


def test_get_file_hash_missing(tmp_path: Path, monkeypatch) -> None:
    """Verify missing cached files produce an empty hash string."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"

    assert store.get_file_hash("missing.txt") == ""


def test_get_file_upload_date(tmp_path: Path, monkeypatch) -> None:
    """Verify upload date is read from filesystem mtime."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"

    target = tmp_path / "saved" / "file.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("data", encoding="utf-8")

    result = store.get_file_upload_date("file.txt")
    assert isinstance(result, datetime)


def test_get_file_upload_date_missing(tmp_path: Path, monkeypatch) -> None:
    """Verify missing upload date returns None."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"

    assert store.get_file_upload_date("missing.txt") is None


def test_list_contents() -> None:
    """Verify file_list output is normalized into tuples."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.mm.file_list.return_value = [
        {"Tabular": [["host1", "saved/file1.txt", "10"]]}
    ]

    result = store.list_contents()
    assert result == [("host1", "file1.txt", "10")]


def test_list_contents_invalid_response_raises() -> None:
    """Verify malformed file_list responses raise RuntimeError."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.mm.file_list.return_value = [{"NoTabular": []}]

    with pytest.raises(RuntimeError):
        store.list_contents()


def test_list_distinct_contents() -> None:
    """Verify distinct contents returns only the relative names."""
    store = _build_filestore(Path("/tmp"))
    store.list_contents = Mock(return_value=[("h", "a", "1"), ("h", "b", "2")])

    assert store.list_distinct_contents() == ["a", "b"]


def test_check_mesh_file_consistency_consistent() -> None:
    """Verify mesh consistency check returns consistent=True for matching hosts."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.get_mesh_size.return_value = 2
    local = [{"Tabular": [["host", "saved/file", "10"]]}]
    remote = [{"Tabular": [["host", "saved/file", "10"]]}]
    store.mm_api.mm.file_list.return_value = local
    store.mm_api.mm.mesh_send.return_value = remote

    result = store._check_mesh_file_consistency("saved/file")
    assert result["consistent"] is True
    assert result["exists"] is True


def test_check_mesh_transfer_success() -> None:
    """Verify mesh transfer polling returns True once consistency is achieved."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.mm.mesh_send.side_effect = [
        [{"Host": "host1", "Header": ["filename"], "Tabular": [["saved/file"]]}],
        [{"Host": "host1", "Header": ["filename"], "Tabular": []}],
    ]
    store.mm_api.mmr_map.side_effect = [
        {"host1": [{"filename": "saved/file"}]},
        {"host1": []},
    ]
    store._check_mesh_file_consistency = Mock(
        return_value={"consistent": True, "exists": True}
    )

    assert store._check_mesh_transfer("saved/file") is True


def test_broadcast_get_file_short_circuit_for_single_node() -> None:
    """Verify mesh broadcast is skipped for a single-node mesh."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.get_mesh_size.return_value = 1

    assert store.broadcast_get_file("saved/file") is True


def test_broadcast_get_file_success() -> None:
    """Verify mesh broadcast calls transfer check and returns its result."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.get_mesh_size.return_value = 2
    store._check_mesh_transfer = Mock(return_value=True)

    assert store.broadcast_get_file("saved/file") is True
    store.mm_api.mm.mesh_send.assert_called()


def test_add_file_from_content(tmp_path: Path, monkeypatch) -> None:
    """Verify file content is written locally and optionally broadcast."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"
    store.remove_file = Mock()
    store.broadcast_get_file = Mock()

    (tmp_path / "saved").mkdir(parents=True, exist_ok=True)
    store.add_file_from_content("hello", "file.txt", force=True, broadcast=True)

    assert (tmp_path / "saved" / "file.txt").read_text(encoding="utf-8") == "hello"
    store.broadcast_get_file.assert_called_once_with("saved/file.txt")


def test_add_file(tmp_path: Path, monkeypatch) -> None:
    """Verify a local source file is copied into the files directory."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"
    store.remove_file = Mock()

    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    (tmp_path / "saved").mkdir(parents=True, exist_ok=True)

    store.add_file(str(source), force=True)
    assert (tmp_path / "saved" / "source.txt").read_text(encoding="utf-8") == "payload"


def test_remove_file() -> None:
    """Verify file deletion commands are sent to local and mesh minimega."""
    store = _build_filestore(Path("/tmp"))
    store._check_mesh_file_consistency = Mock()

    store.remove_file("file.txt")

    store.mm_api.mm.file_delete.assert_called_once_with("saved/file.txt")
    store.mm_api.mm.mesh_send.assert_called_once_with(
        "all", "file delete saved/file.txt"
    )


def test_wait_for_lock_exits_when_lock_disappears(tmp_path: Path) -> None:
    """Verify lock wait loop exits once the lock directory is removed."""
    store = _build_filestore(tmp_path)
    target = tmp_path / "target"
    lock_dir = Path(str(target) + "-lock")
    lock_dir.mkdir()

    calls = {"count": 0}

    def fake_sleep(_interval: float) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            lock_dir.rmdir()

    with patch("firewheel.lib.minimega.file_store.time.sleep", side_effect=fake_sleep):
        store._wait_for_lock(str(target))

    assert calls["count"] >= 2


def test_wait_for_lock_warns_after_five_minutes(tmp_path: Path) -> None:
    """Verify long waits emit a warning."""
    store = _build_filestore(tmp_path)
    target = tmp_path / "target"
    lock_dir = Path(str(target) + "-lock")
    lock_dir.mkdir()

    count = {"value": 0}

    def fake_exists(_path: str) -> bool:
        count["value"] += 1
        return count["value"] < 1202

    with (
        patch(
            "firewheel.lib.minimega.file_store.os.path.exists", side_effect=fake_exists
        ),
        patch("firewheel.lib.minimega.file_store.time.sleep"),
    ):
        store._wait_for_lock(str(target))

    assert store.log.warning.called


def test_file_lock_when_get_lock_raises(tmp_path: Path) -> None:
    """Verify file_lock yields None if lock acquisition fails."""
    store = _build_filestore(tmp_path)

    with patch.object(store, "_get_lock", side_effect=OSError("lock fail")):
        with store.file_lock(str(tmp_path / "target")) as acquired:
            assert acquired is None


def test_minimega_get_data_download_timeout_waits_for_other(tmp_path: Path) -> None:
    """Verify timeout during local fetch waits for another downloader."""
    store = _build_filestore(tmp_path)
    host_file_path = str(tmp_path / "saved" / "file.txt")
    Path(host_file_path).parent.mkdir(parents=True, exist_ok=True)

    with (
        patch.object(store, "file_lock") as file_lock,
        patch.object(store, "_minimega_get_file", side_effect=TimeoutError("busy")),
        patch.object(store, "_wait_for_lock") as wait_for_lock,
    ):
        file_lock.return_value.__enter__.return_value = True
        file_lock.return_value.__exit__.return_value = False

        local_path, error = store._minimega_get_data(host_file_path, "file.txt", False)

    assert local_path == host_file_path
    assert error == ""
    wait_for_lock.assert_called_once_with(host_file_path)


def test_minimega_get_data_existing_file_only_waits_for_lock(tmp_path: Path) -> None:
    """Verify existing cached files only wait on any outstanding lock."""
    store = _build_filestore(tmp_path)
    host_file_path = tmp_path / "saved" / "file.txt"
    host_file_path.parent.mkdir(parents=True, exist_ok=True)
    host_file_path.write_text("data", encoding="utf-8")

    with patch.object(store, "_wait_for_lock") as wait_for_lock:
        local_path, error = store._minimega_get_data(
            str(host_file_path), "file.txt", False
        )

    assert local_path == str(host_file_path)
    assert error == ""
    wait_for_lock.assert_called_once_with(str(host_file_path))


def test_minimega_get_data_failed_download_removes_partial(tmp_path: Path) -> None:
    """Verify failed downloads remove the partial destination."""
    store = _build_filestore(tmp_path)
    host_file_path = tmp_path / "saved" / "file.txt"
    host_file_path.parent.mkdir(parents=True, exist_ok=True)

    def fake_get_file(cache_location: str, _filename: str) -> bool:
        Path(cache_location).write_text("partial", encoding="utf-8")
        return False

    with (
        patch.object(store, "file_lock") as file_lock,
        patch.object(store, "_minimega_get_file", side_effect=fake_get_file),
    ):
        file_lock.return_value.__enter__.return_value = True
        file_lock.return_value.__exit__.return_value = False

        local_path, error = store._minimega_get_data(
            str(host_file_path), "file.txt", False
        )

    assert local_path == ""
    assert error == "failed"
    assert not host_file_path.exists()


def test_minimega_get_data_xz_decompress_error(tmp_path: Path) -> None:
    """Verify xz decompression failures return the correct error."""
    store = _build_filestore(tmp_path)
    host_file_path = tmp_path / "saved" / "file"
    host_file_path.parent.mkdir(parents=True, exist_ok=True)

    def fake_get_file(cache_location: str, filename: str) -> bool:
        Path(cache_location).write_bytes(b"not really xz")
        return True

    with (
        patch.object(store, "file_lock") as file_lock,
        patch.object(store, "_minimega_get_file", side_effect=fake_get_file),
    ):
        file_lock.return_value.__enter__.return_value = True
        file_lock.return_value.__exit__.return_value = False

        local_path, error = store._minimega_get_data(
            str(host_file_path), "file.xz", True
        )

    assert local_path == ""
    assert error == "decompress"


def test_minimega_get_data_tar_decompress_error(tmp_path: Path) -> None:
    """Verify tar decompression failures return the correct error."""
    store = _build_filestore(tmp_path)
    host_file_path = tmp_path / "saved" / "archive"
    host_file_path.parent.mkdir(parents=True, exist_ok=True)

    def fake_get_file(cache_location: str, filename: str) -> bool:
        Path(cache_location).write_bytes(b"not a tar archive")
        return True

    with (
        patch.object(store, "file_lock") as file_lock,
        patch.object(store, "_minimega_get_file", side_effect=fake_get_file),
    ):
        file_lock.return_value.__enter__.return_value = True
        file_lock.return_value.__exit__.return_value = False

        local_path, error = store._minimega_get_data(
            str(host_file_path), "archive.tar", True
        )

    assert local_path == ""
    assert error == "decompress"


def test_minimega_get_file_raises_filenotfound_on_file_get(tmp_path: Path) -> None:
    """Verify file_get no-such-file errors are mapped to FileNotFoundError."""
    store = _build_filestore(tmp_path)

    class FakeError(Exception):
        """Simple stand-in minimega error."""

    cache_location = str(tmp_path / "saved" / "file.txt")

    with patch("firewheel.lib.minimega.file_store.MinimegaError", FakeError):
        store.mm_api.mm.file_get.side_effect = FakeError("no such file")
        with pytest.raises(FileNotFoundError):
            store._minimega_get_file(cache_location, "file.txt")


def test_minimega_get_file_allows_already_in_flight(tmp_path: Path) -> None:
    """Verify already-in-flight download errors are tolerated."""
    store = _build_filestore(tmp_path)
    cache_location = str(tmp_path / "saved" / "file.txt")

    class FakeError(Exception):
        """Simple stand-in minimega error."""

    with (
        patch("firewheel.lib.minimega.file_store.MinimegaError", FakeError),
        patch("firewheel.lib.minimega.file_store.time.sleep"),
    ):
        store.mm_api.mm.file_get.side_effect = FakeError("already in flight")
        store.mm_api.mm.file_status.return_value = [{"Tabular": []}]
        store.mm_api.mm.disk_info.return_value = [
            {"Header": ["backingfile"], "Tabular": [[""]], "Host": "host1"}
        ]
        store.mm_api.mmr_map.return_value = {"backingfile": ""}
        assert store._minimega_get_file(cache_location, "file.txt") is True


def test_minimega_get_file_raises_generic_minimega_error(tmp_path: Path) -> None:
    """Verify unexpected file_get errors are re-raised as MinimegaError."""
    store = _build_filestore(tmp_path)
    cache_location = str(tmp_path / "saved" / "file.txt")

    class FakeError(Exception):
        """Simple stand-in minimega error."""

    with patch("firewheel.lib.minimega.file_store.MinimegaError", FakeError):
        store.mm_api.mm.file_get.side_effect = FakeError("other failure")
        with pytest.raises(FakeError):
            store._minimega_get_file(cache_location, "file.txt")


def test_minimega_get_file_raises_filenotfound_on_disk_info(tmp_path: Path) -> None:
    """Verify disk_info no-such-file errors are mapped to FileNotFoundError."""
    store = _build_filestore(tmp_path)
    cache_location = str(tmp_path / "saved" / "file.txt")
    Path(cache_location).parent.mkdir(parents=True, exist_ok=True)
    Path(cache_location).write_text("data", encoding="utf-8")

    class FakeError(Exception):
        """Simple stand-in minimega error."""

    with (
        patch("firewheel.lib.minimega.file_store.MinimegaError", FakeError),
        patch("firewheel.lib.minimega.file_store.time.sleep"),
    ):
        store.mm_api.mm.file_status.return_value = [{"Tabular": []}]
        store.mm_api.mm.disk_info.side_effect = FakeError("file not found")
        with pytest.raises(FileNotFoundError):
            store._minimega_get_file(cache_location, "file.txt")


def test_add_image_file(monkeypatch, tmp_path: Path) -> None:
    """Verify add_image_file uploads, decompresses, and broadcasts."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"
    store.add_file = Mock()
    store.remove_file = Mock()
    store.get_path = Mock(return_value=str(tmp_path / "saved" / "image.qcow2"))
    store.broadcast_get_file = Mock(return_value=True)

    assert store.add_image_file("/tmp/image.qcow2.xz", force=True) is True
    store.add_file.assert_called_once()
    store.remove_file.assert_called_once_with("image.qcow2")
    store.broadcast_get_file.assert_called_once_with("saved/image.qcow2")


def test_check_mesh_file_consistency_inconsistent_mesh_size() -> None:
    """Verify mesh size mismatch marks a file inconsistent."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.get_mesh_size.return_value = 3
    store.mm_api.mm.file_list.return_value = [{"Tabular": []}]
    store.mm_api.mm.mesh_send.return_value = [{"Tabular": []}]

    result = store._check_mesh_file_consistency("saved/file")
    assert result["consistent"] is False
    assert result["exists"] is False


def test_check_mesh_transfer_returns_false_when_not_consistent() -> None:
    """Verify mesh transfer returns False when final consistency fails."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.mm.mesh_send.return_value = [
        {"Host": "host1", "Header": ["filename"], "Tabular": []}
    ]
    store.mm_api.mmr_map.return_value = {"host1": []}
    store._check_mesh_file_consistency = Mock(
        return_value={"consistent": False, "exists": True}
    )

    assert store._check_mesh_transfer("saved/file") is False


def test_broadcast_get_file_breaks_on_already_in_flight() -> None:
    """Verify broadcast tolerates already-in-flight mesh transfer errors."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.get_mesh_size.return_value = 2
    store.mm_api.mm.mesh_send.side_effect = Exception("already in flight")
    store._check_mesh_transfer = Mock(return_value=True)

    assert store.broadcast_get_file("saved/file") is True


def test_add_file_raises_on_copy_failure(tmp_path: Path, monkeypatch) -> None:
    """Verify add_file propagates copy failures."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    (tmp_path / "saved").mkdir(parents=True, exist_ok=True)

    with patch(
        "firewheel.lib.minimega.file_store.shutil.copy2",
        side_effect=OSError("copy fail"),
    ):
        with pytest.raises(OSError):
            store.add_file(str(source), force=False)


def test_add_file_raises_on_mesh_send_failure(tmp_path: Path, monkeypatch) -> None:
    """Verify add_file wraps mesh broadcast failures as OSError."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    (tmp_path / "saved").mkdir(parents=True, exist_ok=True)
    store.mm_api.mm.mesh_send.side_effect = Exception("mesh fail")

    with pytest.raises(OSError):
        store.add_file(str(source), force=False)


def test_remove_file_raises_oserror() -> None:
    """Verify remove_file wraps backend failures as OSError."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.mm.file_delete.side_effect = Exception("delete fail")

    with pytest.raises(OSError):
        store.remove_file("file.txt")


def test_strip_extension_removes_only_tar_suffix() -> None:
    """Verify .tar suffix stripping removes only the exact suffix."""
    store = _build_filestore(Path("/tmp"))

    assert store._strip_extension("foobar.tar") == "foobar"


def test_strip_extension_removes_only_tgz_suffix() -> None:
    """Verify .tgz suffix stripping removes only the exact suffix."""
    store = _build_filestore(Path("/tmp"))

    assert store._strip_extension("pizza.tgz") == "pizza"


def test_strip_extension_removes_only_xz_suffix() -> None:
    """Verify .xz suffix stripping removes only the exact suffix."""
    store = _build_filestore(Path("/tmp"))

    assert store._strip_extension("buzz.xz") == "buzz"


def test_get_path_decompress_strips_suffix_after_success() -> None:
    """Verify get_path strips compression suffix on successful decompression."""
    store = _build_filestore(Path("/tmp"))
    store.decompress = True

    with (
        patch.object(store, "get_file_path", return_value="/tmp/saved/file"),
        patch.object(
            store, "_minimega_get_data", return_value=("/tmp/saved/file.xz", "")
        ),
    ):
        assert store.get_path("file.xz") == "/tmp/saved/file"


def test_add_image_file_no_remove_if_suffix_not_changed(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify add_image_file does not delete an expected basename when unchanged."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "files_dir", str(tmp_path))
    store = _build_filestore(tmp_path)
    store.store = "saved"
    store.add_file = Mock()
    store.remove_file = Mock()
    store.get_path = Mock(return_value=str(tmp_path / "saved" / "image.qcow2"))
    store.broadcast_get_file = Mock(return_value=True)

    assert store.add_image_file("/tmp/image.qcow2", force=True) is True
    store.remove_file.assert_not_called()


def test_check_mesh_transfer_breaks_on_empty_host_response() -> None:
    """Verify mesh transfer returns False when consistency never becomes valid."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.mm.mesh_send.return_value = [
        {"Host": "host1", "Header": ["filename"], "Tabular": []}
    ]
    store.mm_api.mmr_map.return_value = {"host1": []}
    store._check_mesh_file_consistency = Mock(
        return_value={"consistent": False, "exists": False}
    )

    assert store._check_mesh_transfer("saved/file") is False


def test_broadcast_get_file_raises_non_inflight_exception() -> None:
    """Verify broadcast_get_file re-raises unexpected mesh_send exceptions."""
    store = _build_filestore(Path("/tmp"))
    store.mm_api.get_mesh_size.return_value = 2
    store.mm_api.mm.mesh_send.side_effect = Exception("hard failure")

    with pytest.raises(Exception, match="hard failure"):
        store.broadcast_get_file("saved/file")
