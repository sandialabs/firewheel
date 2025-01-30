# Typically, conftest imports are not allowed, but since the test suites
# are part of the FIREWHEEL package, the conftest file is a module and
# is importable. This allows the plugin hooks to be loaded when running
# the unit test set independently using the FIREWHEEL helper.
from firewheel.tests.conftest import pytest_configure  # noqa: F401
