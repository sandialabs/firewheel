"""Utilities for FIREWHEEL save/load archive layout handling."""

from __future__ import annotations

import sys
import json
import math
import pickle
import shutil
import tarfile
from typing import Any, Optional
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from importlib.metadata import version

from rich.table import Table
from rich.console import Console

from firewheel.lib.utilities import (
    print_error,
    print_reused,
    print_success,
    get_safe_tarfile_members,
)
from firewheel.lib.minimega.file_store import FileStore
from firewheel.vm_resource_manager.schedule_entry import ScheduleEntry

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
    launch_mm_path: Path
    launch_cmds_path: Path | None
    imagestore_dir: Path | None
    vm_resource_store_dir: Path | None
    manifest: dict[str, Any]


@dataclass(frozen=True)
class SavedExperimentInfo:
    """Represents one saved experiment in the minimega saved FileStore.

    Attributes:
        name: Saved experiment directory name.
        path: Full path to the saved experiment directory.
        created_at: Backup creation time from the manifest, if available.
        seconds_since_start: Elapsed experiment time at save, if available.
        schedule_count: Number of saved schedule files, if available.
        complete: Whether the backup included optional caches, if known.
    """

    name: str
    path: Path
    created_at: Optional[datetime]
    seconds_since_start: Optional[int]
    schedule_count: Optional[int]
    complete: Optional[bool]


def list_saved_experiments() -> list[SavedExperimentInfo]:
    """List saved experiments from the minimega saved FileStore.

    Returns:
        list[SavedExperimentInfo]: Saved experiment directories sorted by name.
    """
    saved_exp = FileStore("saved")
    saved_root = Path(saved_exp.cache)

    results: list[SavedExperimentInfo] = []
    if not saved_root.exists():
        return results

    for entry in sorted(saved_root.iterdir(), key=lambda path: path.name):
        if not entry.is_dir():
            continue

        created_at = None
        seconds_since_start = None
        schedule_count = None
        complete = None

        manifest_path = entry / MANIFEST_FILENAME
        if manifest_path.is_file():
            try:
                with manifest_path.open("r", encoding="utf-8") as f_handle:
                    manifest = json.load(f_handle)

                if isinstance(manifest, dict):
                    raw_created_at = manifest.get("created_at")
                    if isinstance(raw_created_at, str):
                        try:
                            created_at = datetime.fromisoformat(raw_created_at)
                        except ValueError:
                            created_at = None

                    raw_schedule_count = manifest.get("schedule_count")
                    if isinstance(raw_schedule_count, int):
                        schedule_count = raw_schedule_count

                    raw_complete = manifest.get("complete")
                    if isinstance(raw_complete, bool):
                        complete = raw_complete
            except (OSError, json.JSONDecodeError):
                pass

        experiment_time_path = entry / EXPERIMENT_TIME_FILENAME
        if experiment_time_path.is_file():
            try:
                with experiment_time_path.open("r", encoding="utf-8") as f_handle:
                    experiment_time = json.load(f_handle)

                if isinstance(experiment_time, dict):
                    raw_seconds = experiment_time.get("seconds_since_start")
                    if isinstance(raw_seconds, int):
                        seconds_since_start = raw_seconds
            except (OSError, json.JSONDecodeError):
                pass

        results.append(
            SavedExperimentInfo(
                name=entry.name,
                path=entry,
                created_at=created_at,
                seconds_since_start=seconds_since_start,
                schedule_count=schedule_count,
                complete=complete,
            )
        )

    return results


def print_saved_experiments(console: Console) -> int:
    """Print available saved experiments.

    Args:
        console (Console): Console used for output.

    Returns:
        ``0`` on success and ``1`` on failure.
    """
    try:
        saved_experiments = list_saved_experiments()
    except OSError as exc:
        print_error(console, f"Failed to list saved experiments: {exc}")
        return 1

    if not saved_experiments:
        print_reused(console, "No saved experiments found")
        return 0

    table = Table(title="Saved Experiments", row_styles=["none", "dim"])
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Created Time")
    table.add_column("Sec Into Experiment", justify="right")
    table.add_column("Num Schedules", justify="right")
    table.add_column("All Exp Data")

    for exp in saved_experiments:
        created_text = "-"
        if exp.created_at is not None:
            created_text = exp.created_at.replace(microsecond=0).isoformat()

        table.add_row(
            exp.name,
            created_text,
            (
                str(exp.seconds_since_start)
                if exp.seconds_since_start is not None
                else "-"
            ),
            str(exp.schedule_count) if exp.schedule_count is not None else "-",
            ("Yes" if exp.complete is True else "No" if exp.complete is False else "-"),
        )

    console.print(table)
    return 0


def get_saved_experiment_path(experiment_name: str) -> Path:
    """Get the path to a saved experiment by name.

    Args:
        experiment_name (str): Saved experiment directory name.

    Returns:
        Path to the saved experiment directory.
    """
    saved_exp = FileStore("saved")
    return Path(saved_exp.get_file_path(experiment_name))


def delete_saved_experiment(console: Console, experiment_name: str) -> int:
    """Delete a saved experiment from the minimega saved FileStore.

    Args:
        console (Console): Console used for output.
        experiment_name (str): Name of the saved experiment to delete.

    Returns:
        ``0`` on success and ``1`` on failure.
    """
    try:
        saved_path = get_saved_experiment_path(experiment_name)
    except OSError as exc:
        print_error(console, f"Failed to access saved experiments: {exc}")
        return 1

    if not saved_path.exists():
        print_error(
            console,
            f"Saved experiment [cyan]{experiment_name}[/cyan] does not exist.",
        )
        return 1

    if not saved_path.is_dir():
        print_error(
            console,
            f"Saved experiment path [cyan]{saved_path}[/cyan] is not a directory.",
        )
        return 1

    try:
        shutil.rmtree(saved_path)
    except OSError as exc:
        print_error(
            console,
            f"Failed to delete saved experiment [cyan]{experiment_name}[/cyan]: {exc}",
        )
        return 1

    print_success(
        console,
        f"Deleted saved experiment [cyan]{experiment_name}[/cyan]",
    )
    return 0


def is_supported_archive(path: Path) -> bool:
    """Return whether the path appears to be a supported tar archive.

    Args:
        path (Path): Path to test.

    Returns:
        bool: True if the path ends with a supported tar archive suffix.
    """
    return path.name.endswith((".tar.gz", ".tgz", ".tar"))


def write_manifest(
    output_dir: Path,
    manifest: dict[str, Any],
) -> Path:
    """Write a backup manifest into the output directory.

    Args:
        output_dir (Path): Root output directory for the saved backup.
        manifest (dict[str, Any]): Manifest content.

    Returns:
        Path: A path to the manifest file.
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
        experiment_name (str): Logical experiment name.
        complete (bool): Whether the save included optional caches.
        archived (bool): Whether the caller requested archive creation.
        experiment_dir_name (str): Name of the saved experiment directory.
        has_launch_cmds (bool): Whether launch_cmds.mm is included.
        has_imagestore_cache (bool): Whether the ImageStore cache is included.
        has_vm_resource_cache (bool): Whether the VmResourceStore cache is included.
        schedule_count (int): Number of schedule files included.

    Returns:
        dict[str, Any]: Manifest dictionary.
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


def load_manifest(root_dir: Path) -> dict[str, Any]:
    """Load the manifest from a candidate backup root directory.

    Args:
        root_dir (Path): Backup root directory.

    Returns:
        dict[str, Any]: Parsed manifest dictionary.

    Raises:
        OSError: If the manifest cannot be read.
    """
    manifest_path = root_dir / MANIFEST_FILENAME
    try:
        with manifest_path.open("r", encoding="utf-8") as f_handle:
            return json.load(f_handle)  # type: ignore[no-any-return]
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise OSError from exc


def extract_archive_safely(archive_path: Path, destination: Path) -> None:
    """Safely extract a tar archive into a destination directory.

    Args:
        archive_path (Path): Archive to extract.
        destination (Path): Extraction destination.

    Raises:
        OSError: If extraction fails.
    """
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            # members are pre-vetted for safety
            members = get_safe_tarfile_members(archive, destination)
            archive.extractall(path=destination, members=members)  # noqa: S202
    except (tarfile.ReadError, tarfile.CompressionError, OSError) as exp:
        raise OSError from exp


def validate_backup_directory(root_dir: Path) -> BackupLayout:
    """Validate a FIREWHEEL backup directory.

    This validation uses the manifest when present and validates the expected
    layout and optional content.

    Args:
        root_dir (Path): Root directory to validate.

    Returns:
        BackupLayout: Validated backup layout.

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

    launch_mm_path = root_dir / "launch.mm"
    if not launch_mm_path.is_file():
        raise FileNotFoundError(f"Missing required file: {launch_mm_path}")

    expected_dir_name = manifest.get("experiment_dir_name")
    if expected_dir_name and root_dir.name != expected_dir_name:
        raise ValueError(
            f"Manifest expected experiment_dir_name={expected_dir_name!r}, "
            f"but found {root_dir.name!r}"
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
