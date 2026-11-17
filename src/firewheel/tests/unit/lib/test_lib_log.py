# test_lib_log.py
"""Unit tests for :mod:`firewheel.lib.log`."""

from __future__ import annotations

from typing import Iterator
import logging
from unittest.mock import patch

import pytest

from firewheel.lib.log import Log, UTCLog


@pytest.fixture
def mock_config(tmp_path, monkeypatch) -> Iterator[dict]:
    """Configure logging-related settings for tests and yield the config."""
    from firewheel.config import config

    monkeypatch.setitem(config["logging"], "root_dir", str(tmp_path))
    monkeypatch.setitem(config["logging"], "firewheel_log", "firewheel.log")
    monkeypatch.setitem(config["logging"], "level", "INFO")
    monkeypatch.setitem(config["system"], "default_group", "")
    yield config


def test_log_creates_handler(mock_config) -> None:
    """Verify a file handler is created for a new logger."""
    logger = Log("test_log_handler").log
    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.FileHandler)


def test_log_uses_null_handler_on_bad_root_dir(mock_config, monkeypatch) -> None:
    """Verify a null handler is used when log path construction fails."""
    monkeypatch.setitem(mock_config["logging"], "root_dir", 1234)

    logger = Log("test_bad_root_dir").log
    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.NullHandler)


def test_log_falls_back_to_second_try_file(mock_config) -> None:
    """Verify logger falls back to a username-suffixed file on IOError."""
    original_file_handler = logging.FileHandler

    call_count = {"count": 0}

    def fake_file_handler(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise IOError("first attempt fails")
        return original_file_handler(*args, **kwargs)

    with patch("firewheel.lib.log.logging.FileHandler", side_effect=fake_file_handler):
        logger = Log("test_second_try_file").log

    assert logger.handlers
    assert call_count["count"] == 2


def test_utclog_uses_gmtime(mock_config, monkeypatch) -> None:
    """Verify UTCLog configures its formatter for UTC conversion."""
    monkeypatch.setitem(mock_config["logging"], "firewheel_log", "utc.log")

    logger = UTCLog("test_utc_log").log
    formatter = logger.handlers[0].formatter
    assert formatter.converter is not None


def test_log_warns_on_missing_group(mock_config, monkeypatch) -> None:
    """Verify missing configured group emits a warning path."""
    monkeypatch.setitem(mock_config["logging"], "firewheel_log", "group_missing.log")
    monkeypatch.setitem(mock_config["system"], "default_group", "definitely_missing_group")

    logger = Log("test_log_missing_group").log
    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.FileHandler)


def test_log_warning_on_chown_failure(mock_config, monkeypatch) -> None:
    """Verify chown failures are tolerated and logger still initializes."""
    monkeypatch.setitem(mock_config["logging"], "firewheel_log", "chown_failure.log")
    monkeypatch.setitem(mock_config["system"], "default_group", "root")

    class FakeGroup:
        """Simple group record."""

        gr_gid = 99999

    class FakeStat:
        """Simple stat record."""

        st_gid = 12345

    with (
        patch("firewheel.lib.log.grp.getgrnam", return_value=FakeGroup()),
        patch("firewheel.lib.log.os.stat", return_value=FakeStat()),
        patch("firewheel.lib.log.os.getgid", return_value=1),
        patch("firewheel.lib.log.os.chown", side_effect=OSError("bad chown")),
    ):
        logger = Log("test_log_chown_failure").log

    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.FileHandler)


def test_log_second_try_also_fails_uses_nullhandler(mock_config, monkeypatch) -> None:
    """Verify logger falls back to NullHandler if both file opens fail."""
    monkeypatch.setitem(mock_config["logging"], "firewheel_log", "double_fail.log")

    with patch("firewheel.lib.log.logging.FileHandler", side_effect=IOError("fail")):
        logger = Log("test_log_double_fail").log

    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.NullHandler)
