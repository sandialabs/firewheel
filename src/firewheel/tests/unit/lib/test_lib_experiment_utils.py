# test_lib_experiment_utils.py
"""Unit tests for :mod:`firewheel.lib.experiment_utils`."""

from __future__ import annotations

import json
import pickle
import tarfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from firewheel.lib.experiment_utils import (
    FORMAT_VERSION,
    MANIFEST_FILENAME,
    SCHEDULES_DIRNAME,
    IMAGESTORE_DIRNAME,
    VM_MAPPING_FILENAME,
    LAUNCH_CMDS_FILENAME,
    VMRESOURCESTORE_DIRNAME,
    EXPERIMENT_TIME_FILENAME,
    BackupLayout,
    load_manifest,
    build_manifest,
    write_manifest,
    is_supported_archive,
    extract_archive_safely,
    list_saved_experiments,
    delete_saved_experiment,
    print_saved_experiments,
    get_saved_experiment_path,
    validate_backup_directory,
    create_resume_schedule_entry,
)


def _make_base_backup(root: Path) -> None:
    """Create a minimal backup directory."""
    (root / VM_MAPPING_FILENAME).write_text("{}", encoding="utf-8")
    (root / EXPERIMENT_TIME_FILENAME).write_text("{}", encoding="utf-8")
    (root / "launch.mm").write_text("launch", encoding="utf-8")
    (root / SCHEDULES_DIRNAME).mkdir()
    manifest = {
        "format_version": FORMAT_VERSION,
        "experiment_dir_name": root.name,
        "files": {
            "launch_cmds": None,
            "imagestore_cache": None,
            "vm_resource_cache": None,
        },
    }
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")


def test_is_supported_archive() -> None:
    """Verify supported tar archive suffixes are recognized."""
    assert is_supported_archive(Path("a.tar.gz")) is True
    assert is_supported_archive(Path("a.tgz")) is True
    assert is_supported_archive(Path("a.tar")) is True
    assert is_supported_archive(Path("a.zip")) is False


def test_build_manifest() -> None:
    """Verify manifest structure is built as expected."""
    manifest = build_manifest(
        experiment_name="exp",
        complete=True,
        archived=False,
        experiment_dir_name="exp_dir",
        has_launch_cmds=True,
        has_imagestore_cache=True,
        has_vm_resource_cache=False,
        schedule_count=3,
    )

    assert manifest["format_version"] == FORMAT_VERSION
    assert manifest["experiment_name"] == "exp"
    assert manifest["complete"] is True
    assert manifest["files"]["launch_cmds"] == LAUNCH_CMDS_FILENAME
    assert manifest["files"]["imagestore_cache"] == IMAGESTORE_DIRNAME
    assert manifest["files"]["vm_resource_cache"] is None
    assert manifest["schedule_count"] == 3


def test_write_and_load_manifest(tmp_path: Path) -> None:
    """Verify a manifest can be written and loaded back."""
    manifest = {"format_version": FORMAT_VERSION}
    path = write_manifest(tmp_path, manifest)
    assert path == tmp_path / MANIFEST_FILENAME
    assert load_manifest(tmp_path) == manifest


def test_load_manifest_raises_on_invalid(tmp_path: Path) -> None:
    """Verify invalid manifest content raises OSError."""
    (tmp_path / MANIFEST_FILENAME).write_text("{bad json", encoding="utf-8")
    with pytest.raises(OSError):
        load_manifest(tmp_path)


def _make_valid_backup_dir(root: Path) -> None:
    """Create a minimal valid backup layout."""
    (root / VM_MAPPING_FILENAME).write_text("{}", encoding="utf-8")
    (root / EXPERIMENT_TIME_FILENAME).write_text("{}", encoding="utf-8")
    (root / "launch.mm").write_text("vm info", encoding="utf-8")
    (root / SCHEDULES_DIRNAME).mkdir()
    manifest = {
        "format_version": FORMAT_VERSION,
        "experiment_dir_name": root.name,
        "files": {
            "launch_cmds": None,
            "imagestore_cache": None,
            "vm_resource_cache": None,
        },
    }
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")


def test_validate_backup_directory(tmp_path: Path) -> None:
    """Verify a valid backup directory is parsed into BackupLayout."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_valid_backup_dir(root)

    layout = validate_backup_directory(root)
    assert isinstance(layout, BackupLayout)
    assert layout.root_dir == root
    assert layout.vm_mapping_path == root / VM_MAPPING_FILENAME
    assert layout.schedules_dir == root / SCHEDULES_DIRNAME


def test_validate_backup_directory_with_optional_content(tmp_path: Path) -> None:
    """Verify optional manifest-referenced content is validated."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_valid_backup_dir(root)

    (root / LAUNCH_CMDS_FILENAME).write_text("cmd", encoding="utf-8")
    (root / IMAGESTORE_DIRNAME).mkdir()
    (root / VMRESOURCESTORE_DIRNAME).mkdir()

    manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["files"]["launch_cmds"] = LAUNCH_CMDS_FILENAME
    manifest["files"]["imagestore_cache"] = IMAGESTORE_DIRNAME
    manifest["files"]["vm_resource_cache"] = VMRESOURCESTORE_DIRNAME
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    layout = validate_backup_directory(root)
    assert layout.launch_cmds_path == root / LAUNCH_CMDS_FILENAME
    assert layout.imagestore_dir == root / IMAGESTORE_DIRNAME
    assert layout.vm_resource_store_dir == root / VMRESOURCESTORE_DIRNAME


def test_validate_backup_directory_bad_format(tmp_path: Path) -> None:
    """Verify unsupported format versions raise ValueError."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_valid_backup_dir(root)

    manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["format_version"] = 999
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError):
        validate_backup_directory(root)


def test_validate_backup_directory_missing_required_file(tmp_path: Path) -> None:
    """Verify missing required files raise FileNotFoundError."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_valid_backup_dir(root)
    (root / VM_MAPPING_FILENAME).unlink()

    with pytest.raises(FileNotFoundError):
        validate_backup_directory(root)


def test_extract_archive_safely(tmp_path: Path) -> None:
    """Verify tar archives are extracted into destination."""
    archive = tmp_path / "backup.tar"
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("hello", encoding="utf-8")

    with tarfile.open(archive, "w") as tar_handle:
        tar_handle.add(source / "file.txt", arcname="file.txt")

    dest = tmp_path / "dest"
    extract_archive_safely(archive, dest)

    assert (dest / "file.txt").read_text(encoding="utf-8") == "hello"


def test_get_saved_experiment_path() -> None:
    """Verify saved experiment path is delegated through FileStore."""
    with patch("firewheel.lib.experiment_utils.FileStore") as mock_store_cls:
        mock_store_cls.return_value.get_file_path.return_value = "/tmp/saved/exp1"
        assert get_saved_experiment_path("exp1") == Path("/tmp/saved/exp1")


def test_list_saved_experiments(tmp_path: Path) -> None:
    """Verify saved experiment metadata is read from manifests."""
    saved_root = tmp_path / "saved"
    saved_root.mkdir()
    exp_dir = saved_root / "exp1"
    exp_dir.mkdir()

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schedule_count": 2,
        "complete": True,
    }
    (exp_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    (exp_dir / EXPERIMENT_TIME_FILENAME).write_text(
        json.dumps({"seconds_since_start": 12}), encoding="utf-8"
    )

    with patch("firewheel.lib.experiment_utils.FileStore") as mock_store_cls:
        mock_store_cls.return_value.cache = str(saved_root)
        result = list_saved_experiments()

    assert len(result) == 1
    assert result[0].name == "exp1"
    assert result[0].schedule_count == 2
    assert result[0].seconds_since_start == 12
    assert result[0].complete is True


def test_print_saved_experiments_none() -> None:
    """Verify printing handles an empty saved experiment list."""
    console = Console(record=True)
    with patch(
        "firewheel.lib.experiment_utils.list_saved_experiments", return_value=[]
    ):
        ret = print_saved_experiments(console)

    assert ret == 0
    assert "No saved experiments found" in console.export_text()


def test_print_saved_experiments_table() -> None:
    """Verify printing emits a table for discovered experiments."""
    console = Console(record=True)
    fake_exp = Mock()
    fake_exp.name = "exp1"
    fake_exp.created_at = datetime.now(timezone.utc)
    fake_exp.seconds_since_start = 5
    fake_exp.schedule_count = 1
    fake_exp.complete = True

    with patch(
        "firewheel.lib.experiment_utils.list_saved_experiments",
        return_value=[fake_exp],
    ):
        ret = print_saved_experiments(console)

    assert ret == 0
    text = console.export_text()
    assert "Saved Experiments" in text
    assert "exp1" in text


def test_delete_saved_experiment_success(tmp_path: Path) -> None:
    """Verify saved experiment directories can be deleted."""
    console = Console(record=True)
    exp_dir = tmp_path / "exp1"
    exp_dir.mkdir()

    with patch(
        "firewheel.lib.experiment_utils.get_saved_experiment_path",
        return_value=exp_dir,
    ):
        ret = delete_saved_experiment(console, "exp1")

    assert ret == 0
    assert not exp_dir.exists()


def test_delete_saved_experiment_missing() -> None:
    """Verify deleting a missing experiment reports an error."""
    console = Console(record=True)

    with patch(
        "firewheel.lib.experiment_utils.get_saved_experiment_path",
        return_value=Path("/does/not/exist"),
    ):
        ret = delete_saved_experiment(console, "exp1")

    assert ret == 1
    assert "does not exist" in console.export_text()


def test_create_resume_schedule_entry() -> None:
    """Verify a RESUME schedule entry is appended to an existing schedule."""
    sched_db = Mock()
    original_schedule = []
    sched_db.get.return_value = pickle.dumps(original_schedule)
    console = Console(record=True)

    result = create_resume_schedule_entry(sched_db, console, "vm1")

    assert result[-1].data == [{"resume": True}]


def test_list_saved_experiments_no_root() -> None:
    """Verify missing saved root returns an empty list."""
    with patch("firewheel.lib.experiment_utils.FileStore") as mock_store_cls:
        mock_store_cls.return_value.cache = "/path/that/does/not/exist"
        assert list_saved_experiments() == []


def test_list_saved_experiments_skips_non_dirs(tmp_path: Path) -> None:
    """Verify non-directory entries are ignored."""
    saved_root = tmp_path / "saved"
    saved_root.mkdir()
    (saved_root / "note.txt").write_text("ignore", encoding="utf-8")

    with patch("firewheel.lib.experiment_utils.FileStore") as mock_store_cls:
        mock_store_cls.return_value.cache = str(saved_root)
        assert list_saved_experiments() == []


def test_print_saved_experiments_handles_oserror() -> None:
    """Verify listing errors are reported."""
    console = Console(record=True)
    with patch(
        "firewheel.lib.experiment_utils.list_saved_experiments",
        side_effect=OSError("boom"),
    ):
        ret = print_saved_experiments(console)

    assert ret == 1
    assert "Failed to list saved experiments" in console.export_text()


def test_delete_saved_experiment_not_directory(tmp_path: Path) -> None:
    """Verify deleting a non-directory saved path fails."""
    console = Console(record=True)
    target = tmp_path / "exp1"
    target.write_text("not dir", encoding="utf-8")

    with (
        patch(
            "firewheel.lib.experiment_utils.get_saved_experiment_path",
            return_value=target,
        ),
        patch("firewheel.lib.experiment_utils.print_error") as mock_print_error,
    ):
        ret = delete_saved_experiment(console, "exp1")

    assert ret == 1
    mock_print_error.assert_called_once()
    called_console, message = mock_print_error.call_args.args
    assert called_console is console
    assert str(target) in message
    assert "is not a directory" in message


def test_delete_saved_experiment_access_error() -> None:
    """Verify path access errors are reported."""
    console = Console(record=True)
    with patch(
        "firewheel.lib.experiment_utils.get_saved_experiment_path",
        side_effect=OSError("access fail"),
    ):
        ret = delete_saved_experiment(console, "exp1")

    assert ret == 1
    assert "Failed to access saved experiments" in console.export_text()


def test_extract_archive_safely_raises_oserror(tmp_path: Path) -> None:
    """Verify unreadable archives raise OSError."""
    archive = tmp_path / "bad.tar"
    archive.write_bytes(b"not a tar")

    with pytest.raises(OSError):
        extract_archive_safely(archive, tmp_path / "dest")


def test_validate_backup_directory_missing_root(tmp_path: Path) -> None:
    """Verify missing backup roots raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        validate_backup_directory(tmp_path / "missing")


def test_validate_backup_directory_not_directory(tmp_path: Path) -> None:
    """Verify non-directory roots raise NotADirectoryError."""
    root = tmp_path / "backup"
    root.write_text("nope", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        validate_backup_directory(root)


def test_validate_backup_directory_dir_name_mismatch(tmp_path: Path) -> None:
    """Verify manifest/root name mismatches raise ValueError."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_base_backup(root)

    manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["experiment_dir_name"] = "other_name"
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError):
        validate_backup_directory(root)


def test_validate_backup_directory_schedule_not_dir(tmp_path: Path) -> None:
    """Verify schedules path must be a directory."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_base_backup(root)
    (root / SCHEDULES_DIRNAME).rmdir()
    (root / SCHEDULES_DIRNAME).write_text("bad", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        validate_backup_directory(root)


def test_validate_backup_directory_missing_optional_launch_cmds(tmp_path: Path) -> None:
    """Verify missing manifest-referenced launch_cmds raises FileNotFoundError."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_base_backup(root)

    manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["files"]["launch_cmds"] = "launch_cmds.mm"
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        validate_backup_directory(root)


def test_validate_backup_directory_missing_optional_cache_dir(tmp_path: Path) -> None:
    """Verify missing manifest-referenced cache dir raises FileNotFoundError."""
    root = tmp_path / "backup"
    root.mkdir()
    _make_base_backup(root)

    manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["files"]["imagestore_cache"] = "imagestore_cache"
    (root / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        validate_backup_directory(root)


def test_create_resume_schedule_entry_missing_schedule_exits() -> None:
    """Verify missing schedules terminate with an error."""
    from firewheel.lib.experiment_utils import create_resume_schedule_entry

    sched_db = Mock()
    sched_db.get.return_value = None
    console = Console(record=True)

    with pytest.raises(SystemExit):
        create_resume_schedule_entry(sched_db, console, "vm1")
