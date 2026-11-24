from unittest.mock import Mock, patch

import pytest

from firewheel.vm_resource_manager import utils
from firewheel.vm_resource_manager.vm_mapping import VMState


def test_vm_state_update():
    mapping = Mock()
    mapping.set_vm_state_by_uuid.return_value = {
        "server_uuid": "uuid-1",
        "state": VMState.FAILED,
    }

    utils.set_vm_state("uuid-1", VMState.FAILED, mapping=mapping)

    mapping.set_vm_state_by_uuid.assert_called_once_with("uuid-1", VMState.FAILED)
    mapping.close.assert_not_called()


def test_vm_state_update_creates_and_closes_mapping():
    mapping = Mock()
    mapping.set_vm_state_by_uuid.return_value = {
        "server_uuid": "uuid-1",
        "state": VMState.FAILED,
    }

    with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
        utils.set_vm_state("uuid-1", VMState.FAILED)

    mapping.set_vm_state_by_uuid.assert_called_once_with("uuid-1", VMState.FAILED)
    mapping.close.assert_called_once()


def test_vm_state_invalid():
    mapping = Mock()
    mapping.set_vm_state_by_uuid.return_value = None

    with pytest.raises(RuntimeError):
        utils.set_vm_state("invalid", VMState.FAILED, mapping=mapping)


def test_vm_time_update():
    mapping = Mock()
    mapping.set_vm_time_by_uuid.return_value = {
        "server_uuid": "uuid-1",
        "current_time": "100",
    }

    utils.set_vm_time("uuid-1", "100", mapping=mapping)

    mapping.set_vm_time_by_uuid.assert_called_once_with("uuid-1", "100")
    mapping.close.assert_not_called()


def test_vm_time_update_creates_and_closes_mapping():
    mapping = Mock()
    mapping.set_vm_time_by_uuid.return_value = {
        "server_uuid": "uuid-1",
        "current_time": "100",
    }

    with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
        utils.set_vm_time("uuid-1", 100)

    mapping.set_vm_time_by_uuid.assert_called_once_with("uuid-1", "100")
    mapping.close.assert_called_once()


def test_vm_time_invalid():
    mapping = Mock()
    mapping.set_vm_time_by_uuid.return_value = None

    with pytest.raises(RuntimeError):
        utils.set_vm_time("invalid", "100", mapping=mapping)


def test_add_execution_issue():
    mapping = Mock()
    mapping.add_execution_issue_by_uuid.return_value = {
        "server_uuid": "uuid-1",
        "has_execution_issues": True,
    }

    utils.add_execution_issue("uuid-1", "warning text", mapping=mapping)

    mapping.add_execution_issue_by_uuid.assert_called_once_with(
        "uuid-1", "warning text"
    )
    mapping.close.assert_not_called()


def test_add_execution_issue_creates_and_closes_mapping():
    mapping = Mock()
    mapping.add_execution_issue_by_uuid.return_value = {
        "server_uuid": "uuid-1",
        "has_execution_issues": True,
    }

    with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
        utils.add_execution_issue("uuid-1", "warning text")

    mapping.add_execution_issue_by_uuid.assert_called_once_with(
        "uuid-1", "warning text"
    )
    mapping.close.assert_called_once()


def test_add_execution_issue_invalid():
    mapping = Mock()
    mapping.add_execution_issue_by_uuid.return_value = None

    with pytest.raises(RuntimeError):
        utils.add_execution_issue("invalid", "warning text", mapping=mapping)


def test_not_ready_count_not_zero():
    mapping = Mock()
    mapping.get_count_vm_not_ready.return_value = 2

    count = utils.get_vm_count_not_ready(mapping=mapping)

    assert count == 2
    mapping.close.assert_not_called()


def test_not_ready_count_creates_and_closes_mapping():
    mapping = Mock()
    mapping.get_count_vm_not_ready.return_value = 3

    with patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping):
        count = utils.get_vm_count_not_ready()

    assert count == 3
    mapping.close.assert_called_once()


# --- Connection ownership --------------------------------------------------
#
# Each wrapper either uses a caller-supplied mapping (which it must never
# close) or creates one itself (which it must always close, even on error).

UTILS_WRAPPERS = [
    pytest.param(
        lambda **kw: utils.set_vm_state("uuid-1", VMState.FAILED, **kw),
        "set_vm_state_by_uuid",
        id="set_vm_state",
    ),
    pytest.param(
        lambda **kw: utils.set_vm_time("uuid-1", "100", **kw),
        "set_vm_time_by_uuid",
        id="set_vm_time",
    ),
    pytest.param(
        lambda **kw: utils.add_execution_issue("uuid-1", "warning", **kw),
        "add_execution_issue_by_uuid",
        id="add_execution_issue",
    ),
    pytest.param(
        lambda **kw: utils.get_vm_count_not_ready(**kw),
        "get_count_vm_not_ready",
        id="get_vm_count_not_ready",
    ),
]


@pytest.mark.parametrize(("call", "method"), UTILS_WRAPPERS)
def test_internal_mapping_closed_when_call_raises(call, method):
    mapping = Mock()
    getattr(mapping, method).side_effect = ConnectionError("lost connection")

    with (
        patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping),
        pytest.raises(ConnectionError),
    ):
        call()

    mapping.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("call", "method"),
    [p for p in UTILS_WRAPPERS if p.id != "get_vm_count_not_ready"],
)
def test_internal_mapping_closed_when_uuid_missing(call, method):
    mapping = Mock()
    getattr(mapping, method).return_value = None

    with (
        patch("firewheel.vm_resource_manager.utils.VMMapping", return_value=mapping),
        pytest.raises(RuntimeError),
    ):
        call()

    mapping.close.assert_called_once_with()


@pytest.mark.parametrize(("call", "method"), UTILS_WRAPPERS)
def test_caller_mapping_never_closed_even_on_error(call, method):
    mapping = Mock()
    getattr(mapping, method).side_effect = ConnectionError("lost connection")

    with (
        patch("firewheel.vm_resource_manager.utils.VMMapping") as mapping_cls,
        pytest.raises(ConnectionError),
    ):
        call(mapping=mapping)

    mapping_cls.assert_not_called()
    mapping.close.assert_not_called()


@pytest.mark.parametrize("bad_time", ["abc", "", None, "1.5"])
def test_vm_time_non_numeric_raises_value_error_without_connecting(bad_time):
    with (
        patch("firewheel.vm_resource_manager.utils.VMMapping") as mapping_cls,
        pytest.raises((ValueError, TypeError)),
    ):
        utils.set_vm_time("uuid-1", bad_time)

    mapping_cls.assert_not_called()


def test_managed_resource_uses_and_does_not_close_supplied_resource():
    resource = Mock()
    factory = Mock()

    with utils.managed_resource(resource, factory) as managed:
        assert managed is resource

    factory.assert_not_called()
    resource.close.assert_not_called()


def test_managed_resource_creates_and_closes_on_error():
    resource = Mock()
    factory = Mock(return_value=resource)

    with pytest.raises(KeyError):
        with utils.managed_resource(None, factory) as managed:
            assert managed is resource
            raise KeyError("boom")

    factory.assert_called_once_with()
    resource.close.assert_called_once_with()


def test_managed_resource_propagates_factory_errors():
    factory = Mock(side_effect=ConnectionError("down"))

    with pytest.raises(ConnectionError):
        utils.managed_resource(None, factory)
