"""Utilities for FIREWHEEL save/load archive layout handling."""

from __future__ import annotations

import json
import tarfile
from typing import Any
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from importlib.metadata import version
import sys
import math
import pickle

from firewheel.vm_resource_manager.schedule_entry import ScheduleEntry

from firewheel.lib.utilities import get_safe_tarfile_members

MANIFEST_FILENAME = "manifest.json"
VM_MAPPING_FILENAME = "vm_mapping.json"
EXPERIMENT_TIME_FILENAME = "experiment_time.json"
LAUNCH_CMDS_FILENAME = "launch_cmds.mm"
SCHEDULES_DIRNAME = "schedules"
IMAGESTORE_DIRNAME = "imagestore_cache"
VMRESOURCESTORE_DIRNAME = "vm_resource_cache"
FORMAT_VERSION = 1


@dataclass(frozen=True)
class BackupLayout:
    """Represents a validated FIREWHEEL backup directory layout.

    Attributes:
        root_dir: Root directory of the extracted or user-provided backup.
        manifest_path: Path to the manifest file.
        vm_mapping_path: Path to the VM mapping file.
        experiment_time_path: Path to the experiment time file.
        schedules_dir: Path to the schedules directory.
        experiment_dir: Path to the saved minimega experiment directory.
        launch_mm_path: Path to the experiment launch script.
        launch_cmds_path: Optional path to VM resource handler launch commands.
        imagestore_dir: Optional path to saved ImageStore cache.
        vm_resource_store_dir: Optional path to saved VmResourceStore cache.
        manifest: Parsed manifest content.
    """

    root_dir: Path
    manifest_path: Path
    vm_mapping_path: Path
    experiment_time_path: Path
    schedules_dir: Path
    experiment_dir: Path
    launch_mm_path: Path
    launch_cmds_path: Path | None
    imagestore_dir: Path | None
    vm_resource_store_dir: Path | None
    manifest: dict[str, Any]


def is_supported_archive(path: Path) -> bool:
    """Return whether the path appears to be a supported tar archive.

    Args:
        path: Path to test.

    Returns:
        True if the path ends with a supported tar archive suffix.
    """
    return path.name.endswith((".tar.gz", ".tgz", ".tar"))


def write_manifest(
    output_dir: Path,
    manifest: dict[str, Any],
) -> Path:
    """Write a backup manifest into the output directory.

    Args:
        output_dir: Root output directory for the saved backup.
        manifest: Manifest content.

    Returns:
        Path to the manifest file.

    Raises:
        OSError: If the manifest cannot be written.
    """
    manifest_path = output_dir / MANIFEST_FILENAME
    with manifest_path.open("w", encoding="utf-8") as f_handle:
        json.dump(manifest, f_handle, indent=2, sort_keys=True)
    return manifest_path


def build_manifest(
    experiment_name: str,
    complete: bool,
    archived: bool,
    experiment_dir_name: str,
    has_launch_cmds: bool,
    has_imagestore_cache: bool,
    has_vm_resource_cache: bool,
    schedule_count: int,
) -> dict[str, Any]:
    """Build a manifest dictionary for a FIREWHEEL backup.

    Args:
        experiment_name: Logical experiment name.
        complete: Whether the save included optional caches.
        archived: Whether the caller requested archive creation.
        experiment_dir_name: Name of the saved experiment directory.
        has_launch_cmds: Whether launch_cmds.mm is included.
        has_imagestore_cache: Whether the ImageStore cache is included.
        has_vm_resource_cache: Whether the VmResourceStore cache is included.
        schedule_count: Number of schedule files included.

    Returns:
        Manifest dictionary.
    """

    return {
        "format_version": FORMAT_VERSION,
        "fw_version": version("firewheel"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_name": experiment_name,
        "experiment_dir_name": experiment_dir_name,
        "complete": complete,
        "archived": archived,
        "files": {
            "vm_mapping": VM_MAPPING_FILENAME,
            "experiment_time": EXPERIMENT_TIME_FILENAME,
            "schedules_dir": SCHEDULES_DIRNAME,
            "launch_cmds": LAUNCH_CMDS_FILENAME if has_launch_cmds else None,
            "imagestore_cache": IMAGESTORE_DIRNAME if has_imagestore_cache else None,
            "vm_resource_cache": VMRESOURCESTORE_DIRNAME
            if has_vm_resource_cache
            else None,
        },
        "schedule_count": schedule_count,
    }


def load_manifest(root_dir: Path) -> Any:
    """Load the manifest from a candidate backup root directory.

    Args:
        root_dir: Backup root directory.

    Returns:
        Parsed manifest dictionary.

    Raises:
        FileNotFoundError: If the manifest is missing.
        json.JSONDecodeError: If the manifest is invalid JSON.
        OSError: If the manifest cannot be read.
    """
    manifest_path = root_dir / MANIFEST_FILENAME
    with manifest_path.open("r", encoding="utf-8") as f_handle:
        return json.load(f_handle)


def extract_archive_safely(archive_path: Path, destination: Path) -> None:
    """Safely extract a tar archive into a destination directory.

    Args:
        archive_path: Archive to extract.
        destination: Extraction destination.

    Raises:
        tarfile.ReadError: If the file is not a readable tar archive.
        tarfile.CompressionError: If the archive compression is invalid.
        OSError: If extraction fails.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        members = get_safe_tarfile_members(archive, destination)
        archive.extractall(path=destination, members=members)  # noqa: S202 members are pre-vetted for safety


def find_experiment_dir_by_launch_mm(root_dir: Path) -> Path:
    """Find the experiment directory by locating exactly one launch.mm file.

    Args:
        root_dir: Backup root directory.

    Returns:
        Path to the directory containing launch.mm.

    Raises:
        FileNotFoundError: If no experiment directory is found.
        ValueError: If multiple candidate experiment directories are found.
        OSError: If the directory cannot be inspected.
    """
    matches = [path.parent for path in root_dir.rglob("launch.mm") if path.is_file()]

    matches = [path for path in matches if path.parent == root_dir]

    if not matches:
        raise FileNotFoundError(
            f"Could not find an experiment directory containing launch.mm under {root_dir}"
        )

    if len(matches) > 1:
        names = ", ".join(sorted(match.name for match in matches))
        raise ValueError(
            f"Multiple experiment directories containing launch.mm found under "
            f"{root_dir}: {names}"
        )

    return matches[0]


def validate_backup_directory(root_dir: Path) -> BackupLayout:
    """Validate a FIREWHEEL backup directory.

    This validation uses the manifest when present and validates the expected
    layout and optional content.

    Args:
        root_dir: Root directory to validate.

    Returns:
        Validated backup layout.

    Raises:
        FileNotFoundError: If required files or directories are missing.
        NotADirectoryError: If a required directory is not a directory.
        ValueError: If the structure is invalid or inconsistent.
        json.JSONDecodeError: If the manifest is invalid JSON.
        OSError: If the directory cannot be inspected.
    """
    if not root_dir.exists():
        raise FileNotFoundError(f"Backup root directory does not exist: {root_dir}")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"Backup root is not a directory: {root_dir}")

    manifest = load_manifest(root_dir)

    format_version = manifest.get("format_version")
    if format_version != FORMAT_VERSION:
        raise ValueError(
            f"Unsupported backup format_version={format_version!r}; "
            f"expected {FORMAT_VERSION}"
        )

    vm_mapping_path = root_dir / VM_MAPPING_FILENAME
    if not vm_mapping_path.is_file():
        raise FileNotFoundError(f"Missing required file: {vm_mapping_path}")

    experiment_time_path = root_dir / EXPERIMENT_TIME_FILENAME
    if not experiment_time_path.is_file():
        raise FileNotFoundError(f"Missing required file: {experiment_time_path}")

    schedules_dir = root_dir / SCHEDULES_DIRNAME
    if not schedules_dir.exists():
        raise FileNotFoundError(f"Missing required directory: {schedules_dir}")
    if not schedules_dir.is_dir():
        raise NotADirectoryError(
            f"Expected directory but found otherwise: {schedules_dir}"
        )

    experiment_dir = find_experiment_dir_by_launch_mm(root_dir)
    launch_mm_path = experiment_dir / "launch.mm"
    if not launch_mm_path.is_file():
        raise FileNotFoundError(f"Missing required file: {launch_mm_path}")

    expected_dir_name = manifest.get("experiment_dir_name")
    if expected_dir_name and experiment_dir.name != expected_dir_name:
        raise ValueError(
            f"Manifest expected experiment_dir_name={expected_dir_name!r}, "
            f"but found {experiment_dir.name!r}"
        )

    launch_cmds_name = manifest.get("files", {}).get("launch_cmds")
    launch_cmds_path = root_dir / launch_cmds_name if launch_cmds_name else None
    if launch_cmds_path is not None and not launch_cmds_path.is_file():
        raise FileNotFoundError(f"Manifest references missing file: {launch_cmds_path}")

    imagestore_name = manifest.get("files", {}).get("imagestore_cache")
    imagestore_dir = root_dir / imagestore_name if imagestore_name else None
    if imagestore_dir is not None and not imagestore_dir.is_dir():
        raise FileNotFoundError(
            f"Manifest references missing directory: {imagestore_dir}"
        )

    vm_resource_name = manifest.get("files", {}).get("vm_resource_cache")
    vm_resource_store_dir = root_dir / vm_resource_name if vm_resource_name else None
    if vm_resource_store_dir is not None and not vm_resource_store_dir.is_dir():
        raise FileNotFoundError(
            f"Manifest references missing directory: {vm_resource_store_dir}"
        )

    return BackupLayout(
        root_dir=root_dir,
        manifest_path=root_dir / MANIFEST_FILENAME,
        vm_mapping_path=vm_mapping_path,
        experiment_time_path=experiment_time_path,
        schedules_dir=schedules_dir,
        experiment_dir=experiment_dir,
        launch_mm_path=launch_mm_path,
        launch_cmds_path=launch_cmds_path,
        imagestore_dir=imagestore_dir,
        vm_resource_store_dir=vm_resource_store_dir,
        manifest=manifest,
    )


def create_resume_schedule_entry(sched_db, con, vm_name):
    """
    Create a schedule entry for a RESUME event.

    Args:
        sched_db (ScheduleDb): A schedule database instance.
        con (rich.console.Console): A console instance to use.
        vm_name (str): The name of a VM for which the schedule was resumed.

    Returns:
        list: A list of :py:class:`ScheduleEntry` objects.
    """
    pickled_schedule = sched_db.get(vm_name)
    if not pickled_schedule:
        con.print(f"[b red]Unable to get schedule for VM: [cyan]{vm_name}")
        sys.exit(1)
    schedule = pickle.loads(pickled_schedule)

    # ScheduleEntry will have been loaded prior to this point automatically.
    sched_entry = ScheduleEntry(-math.inf)
    entry = {"resume": True}
    sched_entry.data.append(entry)
    schedule.append(sched_entry)
    return schedule
