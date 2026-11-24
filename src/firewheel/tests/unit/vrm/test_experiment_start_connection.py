"""
Connection-ownership tests for :class:`ExperimentStart`.

These run against a real, in-process gRPC server and need no external
FIREWHEEL infrastructure.
"""

from unittest.mock import patch

import pytest

from firewheel.tests.unit.grpc_test_server import running_grpc_server
from firewheel.vm_resource_manager.experiment_start import ExperimentStart

pytestmark = pytest.mark.integration


@pytest.fixture
def grpc_port():
    with running_grpc_server() as (_servicer, port):
        yield port


def _connect(port):
    return ExperimentStart(hostname="127.0.0.1", port=str(port), db="test")


def test_close_is_idempotent(grpc_port):
    start = _connect(grpc_port)
    client = start.grpc_client

    with patch.object(client, "close") as close:
        start.close()
        start.close()

    close.assert_called_once_with()
    assert start.grpc_client is None


def test_context_manager_returns_self_and_closes_on_exit(grpc_port):
    with _connect(grpc_port) as start:
        assert isinstance(start, ExperimentStart)
        assert start.get_start_time() is None
        client = start.grpc_client

    assert start.grpc_client is None
    # The underlying channel was really closed, so further RPCs fail.
    with pytest.raises(ValueError):
        client.get_experiment_start_time()


def test_context_manager_closes_on_error(grpc_port):
    with pytest.raises(KeyError):
        with _connect(grpc_port) as start:
            raise KeyError("boom")

    assert start.grpc_client is None
