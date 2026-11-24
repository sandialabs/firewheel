"""
Resource-ownership tests for the ``load`` and ``save`` CLI Helpers.

These Helpers are not importable modules, so the ``RUN LocalPython`` section is
loaded into a fresh namespace (without triggering ``__main__``) and individual
functions are exercised with their backing stores patched out.
"""

from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from firewheel.cli.utils import helpers_path
from firewheel.cli.helper import Helper


def _load_helper_namespace(helper_name):
    helper = Helper(helper_name, str(helpers_path))
    (run_section,) = [
        section for section in helper["RUN"] if section.executor_name == "LocalPython"
    ]
    namespace = {"__name__": f"firewheel_helper_{helper_name}"}
    source = "\n".join(run_section.content)
    exec(compile(source, f"<helper {helper_name}>", "exec"), namespace)  # noqa: S102
    return SimpleNamespace(**namespace), namespace


def _context_mock():
    """A Mock usable in a ``with`` block whose exit closes it like the real class."""
    resource = MagicMock()
    resource.__enter__.return_value = resource

    def _exit(*_):
        resource.close()
        return False  # Never suppress exceptions, matching the real classes.

    resource.__exit__.side_effect = _exit
    return resource


@pytest.fixture
def load_helper():
    return _load_helper_namespace("load")


def test_check_no_existing_experiment_closes_experiment_start(load_helper):
    helper, namespace = load_helper
    start = _context_mock()
    start.get_launch_time.return_value = None
    namespace["minimegaAPI"] = Mock(return_value=Mock(mm_vms=Mock(return_value={})))
    namespace["ExperimentStart"] = Mock(return_value=start)

    helper._check_no_existing_experiment()

    start.close.assert_called_once_with()


def test_check_no_existing_experiment_closes_start_when_running(load_helper):
    helper, namespace = load_helper
    start = _context_mock()
    start.get_launch_time.return_value = object()
    namespace["minimegaAPI"] = Mock(return_value=Mock(mm_vms=Mock(return_value={})))
    namespace["ExperimentStart"] = Mock(return_value=start)

    with pytest.raises(RuntimeError, match="already a FIREWHEEL experiment"):
        helper._check_no_existing_experiment()

    start.close.assert_called_once_with()


def test_restore_experiment_time_closes_experiment_start(load_helper, tmp_path):
    helper, namespace = load_helper
    start = _context_mock()
    namespace["ExperimentStart"] = Mock(return_value=start)
    time_file = tmp_path / "experiment_time.json"
    time_file.write_text('{"seconds_since_start": 5}', encoding="utf-8")

    helper._restore_experiment_time(time_file)

    start.add_start_time.assert_called_once()
    start.close.assert_called_once_with()


def _patch_restore_dependencies(namespace, vm_mapping):
    namespace["_check_no_existing_experiment"] = Mock()
    namespace["_print_validation_summary"] = Mock()
    namespace["FileStore"] = Mock(
        return_value=Mock(get_file_path=Mock(return_value="/tmp/saved"))
    )
    namespace["VMMapping"] = Mock(return_value=vm_mapping)
    namespace["ScheduleDb"] = Mock()
    namespace["ImageStore"] = Mock(return_value=Mock(cache="/tmp/images"))
    namespace["VmResourceStore"] = Mock(return_value=Mock(cache="/tmp/vmr"))


def _layout():
    return SimpleNamespace(
        root_dir=Path("/tmp/backup"),
        manifest={"experiment_name": "exp"},
        vm_mapping_path=Path("/tmp/backup/vm_mapping.json"),
        schedules_dir=Path("/tmp/backup/schedules"),
        launch_mm_path=Path("/tmp/backup/launch.mm"),
        launch_cmds_path=None,
        imagestore_dir=None,
        vm_resource_store_dir=None,
    )


def test_restore_from_layout_dry_run_closes_vm_mapping(load_helper):
    helper, namespace = load_helper
    vm_mapping = _context_mock()
    _patch_restore_dependencies(namespace, vm_mapping)
    namespace["_validate_destination_paths"] = Mock()

    assert helper._restore_from_layout(_layout(), True, False, False) == 0

    vm_mapping.close.assert_called_once_with()


def test_restore_from_layout_closes_vm_mapping_on_validation_failure(load_helper):
    helper, namespace = load_helper
    vm_mapping = _context_mock()
    _patch_restore_dependencies(namespace, vm_mapping)
    namespace["_validate_destination_paths"] = Mock(
        side_effect=FileExistsError("conflict")
    )

    assert helper._restore_from_layout(_layout(), False, False, False) == 1

    vm_mapping.close.assert_called_once_with()


def test_restore_from_layout_closes_vm_mapping_on_unexpected_error(load_helper):
    helper, namespace = load_helper
    vm_mapping = _context_mock()
    _patch_restore_dependencies(namespace, vm_mapping)
    namespace["_validate_destination_paths"] = Mock(side_effect=KeyError("boom"))

    with pytest.raises(KeyError):
        helper._restore_from_layout(_layout(), False, False, False)

    vm_mapping.close.assert_called_once_with()


def test_save_helper_reads_vm_mapping_inside_with_block():
    # ``save_vm_state`` does too much I/O to drive end to end here, so assert
    # structurally that the mapping is only used via a ``with`` block.
    helper = Helper("save", str(helpers_path))
    source = "\n".join(
        "\n".join(section.content)
        for section in helper["RUN"]
        if section.executor_name == "LocalPython"
    )

    assert "with VMMapping() as vm_mapping:" in source
    assert "vm_mapping = VMMapping()" not in source
