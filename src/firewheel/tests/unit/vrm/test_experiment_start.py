"""
Tests for :class:`ExperimentStart` against a real, in-process gRPC server.

Time is controlled by patching ``datetime`` in the module under test, so no
test sleeps and no external FIREWHEEL gRPC server is required.
"""

import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from firewheel.config import config
from firewheel.tests.unit.grpc_test_server import running_grpc_server
from firewheel.vm_resource_manager.experiment_start import ExperimentStart

pytestmark = pytest.mark.integration

START_BUFFER = timedelta(
    seconds=int(config["vm_resource_manager"]["experiment_start_buffer_sec"])
)


class FakeClock:
    """A settable stand-in for :class:`datetime.datetime` used by ExperimentStart."""

    def __init__(self, now):
        self._now = now

    def now(self, tz=None):
        assert tz is timezone.utc
        return self._now

    def advance(self, seconds):
        self._now += timedelta(seconds=seconds)


@pytest.fixture
def grpc_port():
    with running_grpc_server() as (_servicer, port):
        yield port


@pytest.fixture
def clock():
    fake = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    with patch("firewheel.vm_resource_manager.experiment_start.datetime", fake):
        yield fake


@pytest.fixture
def experiment_start(grpc_port):
    start = ExperimentStart(hostname="127.0.0.1", port=str(grpc_port), db="test")
    try:
        yield start
    finally:
        start.close()


def test_get_no_start_yet(experiment_start):
    assert experiment_start.get_start_time() is None


def test_single_start_time(experiment_start, clock):
    inserted_time = experiment_start.add_start_time()

    assert inserted_time == clock.now(timezone.utc) + START_BUFFER
    assert experiment_start.get_start_time() == inserted_time


def test_second_add_returns_first_start_time(experiment_start, clock):
    inserted_time_1 = experiment_start.add_start_time()
    clock.advance(2)

    inserted_time_2 = experiment_start.add_start_time()

    assert inserted_time_2 == inserted_time_1
    assert experiment_start.get_start_time() == inserted_time_1


def test_custom_start_times_keep_first_reported(experiment_start, clock):
    first = clock.now(timezone.utc)
    second = first + timedelta(seconds=2)

    assert experiment_start.add_start_time(first) == first
    # The server keeps the first value and add_start_time reports what was stored.
    assert experiment_start.add_start_time(second) == first

    assert experiment_start.get_start_time() == first


def test_custom_start_time_after_default_returns_stored(experiment_start, clock):
    stored = experiment_start.add_start_time()

    assert experiment_start.add_start_time(clock.now(timezone.utc)) == stored
    assert experiment_start.get_start_time() == stored


def test_concurrent_start_time_reports_agree(grpc_port):
    """Every racing reporter gets the single value the server stored."""
    reporters = 12
    barrier = threading.Barrier(reporters)
    results = [None] * reporters

    def report(index):
        start = ExperimentStart(hostname="127.0.0.1", port=str(grpc_port), db="test")
        try:
            barrier.wait()
            proposed = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=index
            )
            results[index] = start.add_start_time(proposed)
        finally:
            start.close()

    threads = [threading.Thread(target=report, args=(i,)) for i in range(reporters)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(set(results)) == 1
    with_reader = ExperimentStart(hostname="127.0.0.1", port=str(grpc_port), db="test")
    try:
        assert with_reader.get_start_time() == results[0]
    finally:
        with_reader.close()


def test_duplicate_connection_sees_same_start_time(experiment_start, grpc_port):
    inserted_time = experiment_start.add_start_time()

    second_conn = ExperimentStart(hostname="127.0.0.1", port=str(grpc_port), db="test")
    try:
        assert second_conn.get_start_time() == inserted_time
    finally:
        second_conn.close()

    assert experiment_start.get_start_time() == inserted_time


def test_clear_start_time(experiment_start):
    inserted_time = experiment_start.add_start_time()
    assert experiment_start.get_start_time() == inserted_time

    assert experiment_start.clear_start_time() == {}

    assert experiment_start.get_start_time() is None


def test_clear_start_time_also_clears_launch_time(experiment_start):
    experiment_start.set_launch_time()

    experiment_start.clear_start_time()

    assert experiment_start.get_launch_time() is None


def test_get_launch_time_before_set(experiment_start):
    assert experiment_start.get_launch_time() is None


def test_set_launch_time_is_stable(experiment_start, clock):
    inserted_time = experiment_start.set_launch_time()
    assert inserted_time == clock.now(timezone.utc)

    clock.advance(5)

    assert experiment_start.get_launch_time() == inserted_time


def test_get_time_to_start(experiment_start, clock):
    experiment_start.set_launch_time()
    assert experiment_start.get_time_to_start() is None

    clock.advance(7)
    experiment_start.add_start_time()

    expected = (timedelta(seconds=7) + START_BUFFER).total_seconds()
    assert experiment_start.get_time_to_start() == expected


def test_get_time_to_start_requires_launch_time(experiment_start):
    experiment_start.add_start_time()

    assert experiment_start.get_time_to_start() is None


def test_get_time_since_start(experiment_start, clock):
    assert experiment_start.get_time_since_start() is None

    experiment_start.add_start_time()
    clock.advance(START_BUFFER.total_seconds() + 5)

    assert experiment_start.get_time_since_start() == 5
