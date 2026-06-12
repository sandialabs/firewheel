# test_lib_grpc_resources.py
"""Unit tests for :mod:`firewheel.lib.grpc.firewheel_grpc_resources`."""

from __future__ import annotations

from unittest.mock import patch

from firewheel.lib.grpc.firewheel_grpc_resources import msg_to_dict


def test_msg_to_dict_replaces_none_string() -> None:
    """Verify literal 'None' values are converted to Python None."""
    with patch(
        "firewheel.lib.grpc.firewheel_grpc_resources.MessageToDict",
        return_value={"a": "None", "b": "value"},
    ):
        result = msg_to_dict(object())

    assert result == {"a": None, "b": "value"}