"""
Configuration file for pytest

This file establishes shared pytest functionality, including some command
line options for testing.

Notes:
    For more information on adding command line options (such as those
    added here to skip long-running tests), see `the pytest documentation
    <https://docs.pytest.org/en/7.1.x/example/simple.html#control-skipping-of-tests-according-to-command-line-option>`.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """
    Enable this conftest file to perform initial configuration.

    This is an `initialization hook
    <https://docs.pytest.org/en/7.4.x/reference/reference.html#pytest.hookspec.pytest_configure>`
    provided by :py:mod`pytest`. It allows plugins and conftest files to
    perform initial configuration. The hook is called for every plugin
    and initial conftest file after command line options have been
    parsed. After that, the hook is called for other conftest files as
    they are imported.

    This specific hook adds custom markers to the test suite, such as a
    ``long`` marker to indicate long-running tests (more than 10 seconds
    duration) and the ``mcs`` marker to indicate tests that require
    model components beyond the base FIREWHEEL package.

    Args:
        config (pytest.Config): The pytest config object.
    """
    markers = [
        "long: mark test as long running",
        "mcs: mark test as dependent on model components",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)
