# test_lib_log.py
"""Unit tests for :mod:`firewheel.lib.log`."""

from __future__ import annotations

import logging
from unittest.mock import patch

from firewheel.lib.log import Log, UTCLog


def test_log_creates_handler(tmp_path, monkeypatch) -> None:
    """Verify a file handler is created for a new logger."""
    from firewheel.config import config

    monkeypatch.setitem(config["logging"], "root_dir", str(tmp_path))
    monkeypatch.setitem(config["logging"], "firewheel_log", "firewheel.log")
    monkeypatch.setitem(config["logging"], "level", "INFO")
    monkeypatch.setitem(config["system"], "default_group", "")

    logger = Log("test_log_handler").log
    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.FileHandler)


def test_log_uses_null_handler_on_bad_root_dir(monkeypatch) -> None:
    """Verify a null handler is used when log path construction fails."""
    from firewheel.config import config

    monkeypatch.setitem(config["logging"], "root_dir", 1234)
    monkeypatch.setitem(config["logging"], "firewheel_log", "firewheel.log")
    monkeypatch.setitem(config["logging"], "level", "INFO")
    monkeypatch.setitem(config["system"], "default_group", "")

    logger = Log("test_bad_root_dir").log
    assert logger.handlers
    assert isinstance(logger.handlers[0], logging.NullHandler)


def test_log_falls_back_to_second_try_file(tmp_path, monkeypatch) -> None:
    """Verify logger falls back to a username-suffixed file on IOError."""
    from firewheel.config import config

    monkeypatch.setitem(config["logging"], "root_dir", str(tmp_path))
    monkeypatch.setitem(config["logging"], "firewheel_log", "firewheel.log")
    monkeypatch.setitem(config["logging"], "level", "INFO")
    monkeypatch.setitem(config["system"], "default_group", "")

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


def test_utclog_uses_gmtime(tmp_path, monkeypatch) -> None:
    """Verify UTCLog configures its formatter for UTC conversion."""
    from firewheel.config import config

    monkeypatch.setitem(config["logging"], "root_dir", str(tmp_path))
    monkeypatch.setitem(config["logging"], "firewheel_log", "utc.log")
    monkeypatch.setitem(config["logging"], "level", "INFO")
    monkeypatch.setitem(config["system"], "default_group", "")

    logger = UTCLog("test_utc_log").log
    formatter = logger.handlers[0].formatter
    assert formatter.converter is not None