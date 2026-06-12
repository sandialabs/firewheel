# test_lib_file_store.py
"""Unit tests for :mod:`firewheel.lib.minimega.file_store`."""

from __future__ import annotations

import json
import os
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
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
    with patch.object(store, "get_file_path", return_value="/tmp/file"), patch.object(
        store, "_minimega_get_data", return_value=("/tmp/file", "")
    ):
        assert store.get_path("file") == "/tmp/file"


def test_get_path_failed_raises() -> None:
    """Verify get_path raises FileNotFoundError on failed fetch."""
    store = _build_filestore(Path("/tmp"))
    with patch.object(store, "get_file_path", return_value="/tmp/file"), patch.object(
        store, "_minimega_get_data", return_value=("", "failed")
    ):
        with pytest.raises(FileNotFoundError):
            store.get_path("file")


def test_get_path_decompress_raises() -> None:
    """Verify get_path raises RuntimeError on decompression failure."""
    store = _build_filestore(Path("/tmp"))
    with patch.object(store, "get_file_path", return_value="/tmp/file"), patch.object(
        store, "_minimega_get_data", return_value=("", "decompress")
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
    store.mm_api.mm.mesh_send.assert_called_once_with("all", "file delete saved/file.txt")