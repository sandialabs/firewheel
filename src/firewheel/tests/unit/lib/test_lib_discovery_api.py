# test_lib_discovery_api.py
"""Unit tests for :mod:`firewheel.lib.discovery.api`."""

from __future__ import annotations

from typing import Iterator
from unittest.mock import Mock, patch

import pytest
import requests

from firewheel.lib.discovery.api import discoveryAPI


def _mock_config() -> dict:
    """Return a minimal configuration dictionary for discovery tests."""
    return {
        "discovery": {
            "hostname": "discovery-host",
            "port": 9001,
            "install_dir": "/opt/discovery",
        },
        "logging": {
            "root_dir": "/tmp/firewheel-logs",
            "discovery_log": "discovery.log",
            "level": "INFO",
        },
    }


@pytest.fixture
def mock_config() -> Iterator[None]:
    """Patch the discovery API configuration loading with deterministic test values."""
    with patch("firewheel.lib.discovery.api.Config") as mock_config_cls:
        mock_config_cls.return_value.get_config.return_value = _mock_config()
        yield


def _build_response(
    status_code: int = 200,
    json_data=None,
    ok: bool = True,
) -> Mock:
    """Build a mocked requests response object.

    Args:
        status_code (int): HTTP status code.
        json_data (Any): Value returned by ``json()``.
        ok (bool): Value for the response ``ok`` attribute.

    Returns:
        Mock: Mocked response object.
    """
    response = Mock()
    response.status_code = status_code
    response.ok = ok
    response.json.return_value = json_data
    response.raise_for_status = Mock()
    return response


def test_init_uses_config_defaults(mock_config) -> None:
    """Verify discoveryAPI initialization uses configuration defaults."""
    api = discoveryAPI()

    assert api.bind_addr == "discovery-host:9001"
    assert api.discovery_URI == "http://discovery-host:9001"
    assert api.log_file is None


def test_init_uses_explicit_hostname_port(mock_config) -> None:
    """Verify discoveryAPI honors explicit hostname and port overrides."""
    api = discoveryAPI(hostname="custom-host", port=1234)

    assert api.bind_addr == "custom-host:1234"
    assert api.discovery_URI == "http://custom-host:1234"


@patch("firewheel.lib.discovery.api.requests.get")
def test_test_connection_success(mock_get, mock_config) -> None:
    """Verify test_connection returns True for HTTP 200."""
    mock_get.return_value = _build_response(status_code=requests.codes.ok)

    api = discoveryAPI()

    assert api.test_connection() is True
    mock_get.assert_called_once_with(f"{api.discovery_URI}/config", timeout=60)


@patch("firewheel.lib.discovery.api.requests.get")
def test_test_connection_bad_status_returns_false(mock_get, mock_config) -> None:
    """Verify test_connection returns False for unexpected status codes."""
    mock_get.return_value = _build_response(status_code=500)

    api = discoveryAPI()

    assert api.test_connection() is False


@patch("firewheel.lib.discovery.api.requests.get")
def test_test_connection_connection_error(mock_get, mock_config) -> None:
    """Verify test_connection returns False on connection failures."""
    mock_get.side_effect = requests.exceptions.ConnectionError()

    api = discoveryAPI()

    assert api.test_connection() is False


@patch("firewheel.lib.discovery.api.requests.get")
def test_test_connection_invalid_url(mock_get, mock_config) -> None:
    """Verify test_connection returns False for invalid URLs."""
    mock_get.side_effect = requests.exceptions.InvalidURL()

    api = discoveryAPI()

    assert api.test_connection() is False


def test_start_discovery_returns_true_if_already_running(mock_config) -> None:
    """Verify start_discovery returns immediately when service is already running."""
    api = discoveryAPI()

    with patch.object(api, "test_connection", return_value=True) as test_connection:
        assert api.start_discovery() is True

    test_connection.assert_called_once()


@patch("firewheel.lib.discovery.api.minimegaAPI")
def test_start_discovery_runtime_error_returns_false(
    mock_minimega_api_cls, mock_config
) -> None:
    """Verify start_discovery returns False on minimega runtime errors."""
    mock_minimega_api_cls.side_effect = RuntimeError("boom")

    api = discoveryAPI()

    with patch.object(api, "test_connection", return_value=False):
        assert api.start_discovery() is False


@patch("firewheel.lib.discovery.api.minimegaAPI")
def test_start_discovery_timeout_error_returns_false(
    mock_minimega_api_cls, mock_config
) -> None:
    """Verify start_discovery returns False on minimega timeout errors."""
    mock_minimega_api_cls.side_effect = TimeoutError("boom")

    api = discoveryAPI()

    with patch.object(api, "test_connection", return_value=False):
        assert api.start_discovery() is False


@patch("firewheel.lib.discovery.api.time.sleep")
@patch("firewheel.lib.discovery.api.minimegaAPI")
def test_start_discovery_success_after_polling(
    mock_minimega_api_cls, mock_sleep, mock_config
) -> None:
    """Verify start_discovery launches discovery and detects startup."""
    mock_mm = Mock()
    mock_minimega_api_cls.return_value = mock_mm

    api = discoveryAPI()

    with patch.object(
        api, "test_connection", side_effect=[False, False, True]
    ) as test_connection:
        assert api.start_discovery() is True

    mock_mm.mm.background.assert_called_once()
    assert test_connection.call_count == 3
    assert mock_sleep.call_count == 2
    assert api.log_file == "/tmp/firewheel-logs/discovery.log"


@patch("firewheel.lib.discovery.api.time.sleep")
@patch("firewheel.lib.discovery.api.minimegaAPI")
def test_start_discovery_returns_false_after_all_attempts(
    mock_minimega_api_cls, mock_sleep, mock_config
) -> None:
    """Verify start_discovery returns False if service never responds."""
    mock_minimega_api_cls.return_value = Mock()

    api = discoveryAPI()

    with patch.object(
        api, "test_connection", side_effect=[False] * 13
    ) as test_connection:
        assert api.start_discovery() is False

    assert test_connection.call_count == 13
    assert mock_sleep.call_count == 12


@patch("firewheel.lib.discovery.api.requests.get")
def test_get_config(mock_get, mock_config) -> None:
    """Verify get_config returns JSON data from discovery."""
    mock_get.return_value = _build_response(json_data={"a": 1})

    api = discoveryAPI()

    assert api.get_config("foo") == {"a": 1}
    mock_get.assert_called_once_with(f"{api.discovery_URI}/config/foo", timeout=60)
    mock_get.return_value.raise_for_status.assert_called_once()


@patch("firewheel.lib.discovery.api.requests.post")
def test_set_config(mock_post, mock_config) -> None:
    """Verify set_config posts data and returns response.ok."""
    mock_post.return_value = _build_response(ok=True)

    api = discoveryAPI()

    assert api.set_config("foo", {"bar": "baz"}) is True
    mock_post.assert_called_once_with(
        f"{api.discovery_URI}/config/foo", data={"bar": "baz"}, timeout=60
    )
    mock_post.return_value.raise_for_status.assert_called_once()


@patch("firewheel.lib.discovery.api.requests.post")
def test_insert_network(mock_post, mock_config) -> None:
    """Verify insert_network posts the expected payload."""
    mock_post.return_value = _build_response(json_data=[{"NID": "n1"}])

    api = discoveryAPI()

    assert api.insert_network() == [{"NID": "n1"}]
    mock_post.assert_called_once_with(
        f"{api.discovery_URI}/networks/", json=[{}], timeout=60
    )


@patch("firewheel.lib.discovery.api.requests.get")
def test_get_networks_returns_list(mock_get, mock_config) -> None:
    """Verify get_networks returns network data."""
    mock_get.return_value = _build_response(json_data=[{"NID": "n1"}])

    api = discoveryAPI()

    assert api.get_networks() == [{"NID": "n1"}]


@patch("firewheel.lib.discovery.api.requests.get")
def test_get_networks_returns_empty_list_on_none(mock_get, mock_config) -> None:
    """Verify get_networks normalizes None responses to an empty list."""
    mock_get.return_value = _build_response(json_data=None)

    api = discoveryAPI()

    assert api.get_networks() == []


@patch("firewheel.lib.discovery.api.requests.delete")
def test_delete_networks_with_key_and_value(mock_delete, mock_config) -> None:
    """Verify delete_networks uses the key/value endpoint when both are provided."""
    mock_delete.return_value = _build_response(json_data=[{"NID": "n1"}])

    api = discoveryAPI()

    assert api.delete_networks(key="NID", value="n1") == [{"NID": "n1"}]
    mock_delete.assert_called_once_with(
        f"{api.discovery_URI}/networks/NID/n1", timeout=60
    )


@patch("firewheel.lib.discovery.api.requests.delete")
def test_delete_networks_with_value_only(mock_delete, mock_config) -> None:
    """Verify delete_networks uses the value-only endpoint when key is omitted."""
    mock_delete.return_value = _build_response(json_data=[{"NID": "n1"}])

    api = discoveryAPI()

    assert api.delete_networks(value="n1") == [{"NID": "n1"}]
    mock_delete.assert_called_once_with(f"{api.discovery_URI}/networks/n1", timeout=60)


@patch("firewheel.lib.discovery.api.requests.delete")
def test_delete_networks_returns_empty_list_on_none(
    mock_delete, mock_config
) -> None:
    """Verify delete_networks normalizes None responses to an empty list."""
    mock_delete.return_value = _build_response(json_data=None)

    api = discoveryAPI()

    assert api.delete_networks(value="n1") == []


@patch("firewheel.lib.discovery.api.requests.get")
def test_get_endpoints_returns_list(mock_get, mock_config) -> None:
    """Verify get_endpoints returns endpoint data."""
    mock_get.return_value = _build_response(json_data=[{"NID": "e1"}])

    api = discoveryAPI()

    assert api.get_endpoints() == [{"NID": "e1"}]


@patch("firewheel.lib.discovery.api.requests.get")
def test_get_endpoints_returns_empty_list_on_none(mock_get, mock_config) -> None:
    """Verify get_endpoints normalizes None responses to an empty list."""
    mock_get.return_value = _build_response(json_data=None)

    api = discoveryAPI()

    assert api.get_endpoints() == []


@patch("firewheel.lib.discovery.api.requests.delete")
def test_delete_endpoints_with_key_and_value(mock_delete, mock_config) -> None:
    """Verify delete_endpoints uses the key/value endpoint when both are provided."""
    mock_delete.return_value = _build_response(json_data=[{"NID": "e1"}])

    api = discoveryAPI()

    assert api.delete_endpoints(key="NID", value="e1") == [{"NID": "e1"}]
    mock_delete.assert_called_once_with(
        f"{api.discovery_URI}/endpoints/NID/e1", timeout=60
    )


@patch("firewheel.lib.discovery.api.requests.delete")
def test_delete_endpoints_with_value_only(mock_delete, mock_config) -> None:
    """Verify delete_endpoints uses the value-only endpoint when key is omitted."""
    mock_delete.return_value = _build_response(json_data=[{"NID": "e1"}])

    api = discoveryAPI()

    assert api.delete_endpoints(value="qemu") == [{"NID": "e1"}]
    mock_delete.assert_called_once_with(
        f"{api.discovery_URI}/endpoints/qemu", timeout=60
    )


@patch("firewheel.lib.discovery.api.requests.delete")
def test_delete_endpoints_returns_empty_list_on_none(
    mock_delete, mock_config
) -> None:
    """Verify delete_endpoints normalizes None responses to an empty list."""
    mock_delete.return_value = _build_response(json_data=None)

    api = discoveryAPI()

    assert api.delete_endpoints(value="qemu") == []


def test_delete_all_endpoints_empty(mock_config) -> None:
    """Verify delete_all_endpoints returns empty when no endpoints exist."""
    api = discoveryAPI()

    with patch.object(api, "get_endpoints", return_value=[]):
        assert api.delete_all_endpoints() == []


def test_delete_all_endpoints_only_qemu_needed(mock_config) -> None:
    """Verify delete_all_endpoints stops after qemu deletion if no endpoints remain."""
    api = discoveryAPI()

    with (
        patch.object(api, "get_endpoints", side_effect=[[{"NID": "e1"}], []]),
        patch.object(
            api, "delete_endpoints", return_value=[{"NID": "e1"}]
        ) as delete_endpoints,
    ):
        assert api.delete_all_endpoints() == [{"NID": "e1"}]

    delete_endpoints.assert_called_once_with(value="qemu")


def test_delete_all_endpoints_deletes_remaining_by_nid(mock_config) -> None:
    """Verify delete_all_endpoints deletes remaining endpoints by NID."""
    api = discoveryAPI()

    remaining = [{"NID": "e2"}, {"NID": "e3"}]

    with (
        patch.object(api, "get_endpoints", side_effect=[[{"NID": "e1"}], remaining]),
        patch.object(
            api,
            "delete_endpoints",
            side_effect=[[{"NID": "e1"}], [{"NID": "e2"}], [{"NID": "e3"}]],
        ) as delete_endpoints,
    ):
        result = api.delete_all_endpoints()

    assert result == [{"NID": "e1"}, {"NID": "e2"}, {"NID": "e3"}]
    assert delete_endpoints.call_args_list[0].kwargs == {"value": "qemu"}
    assert delete_endpoints.call_args_list[1].kwargs == {"key": "NID", "value": "e2"}
    assert delete_endpoints.call_args_list[2].kwargs == {"key": "NID", "value": "e3"}


def test_delete_all_networks_empty(mock_config) -> None:
    """Verify delete_all_networks returns empty when no networks exist."""
    api = discoveryAPI()

    with patch.object(api, "get_networks", return_value=[]):
        assert api.delete_all_networks() == []


def test_delete_all_networks(mock_config) -> None:
    """Verify delete_all_networks deletes each network by NID."""
    api = discoveryAPI()

    with (
        patch.object(api, "get_networks", return_value=[{"NID": "n1"}, {"NID": "n2"}]),
        patch.object(
            api,
            "delete_networks",
            side_effect=[[{"NID": "n1"}], [{"NID": "n2"}]],
        ) as delete_networks,
    ):
        result = api.delete_all_networks()

    assert result == [{"NID": "n1"}, {"NID": "n2"}]
    assert delete_networks.call_args_list[0].kwargs == {"key": "NID", "value": "n1"}
    assert delete_networks.call_args_list[1].kwargs == {"key": "NID", "value": "n2"}


def test_delete_all_success(mock_config) -> None:
    """Verify delete_all returns True when endpoints and networks are cleared."""
    api = discoveryAPI()

    with (
        patch.object(api, "delete_all_endpoints"),
        patch.object(api, "get_endpoints", return_value=[]),
        patch.object(api, "delete_all_networks"),
        patch.object(api, "get_networks", return_value=[]),
    ):
        assert api.delete_all() is True


def test_delete_all_raises_for_remaining_endpoints(mock_config) -> None:
    """Verify delete_all raises if endpoints remain after deletion."""
    api = discoveryAPI()

    with (
        patch.object(api, "delete_all_endpoints"),
        patch.object(api, "get_endpoints", return_value=[{"NID": "e1"}]),
    ):
        with pytest.raises(RuntimeError, match="discovery endpoints"):
            api.delete_all()


def test_delete_all_raises_for_remaining_networks(mock_config) -> None:
    """Verify delete_all raises if networks remain after deletion."""
    api = discoveryAPI()

    with (
        patch.object(api, "delete_all_endpoints"),
        patch.object(api, "get_endpoints", return_value=[]),
        patch.object(api, "delete_all_networks"),
        patch.object(api, "get_networks", return_value=[{"NID": "n1"}]),
    ):
        with pytest.raises(RuntimeError, match="Networks not successfully deleted"):
            api.delete_all()


@patch("firewheel.lib.discovery.api.requests.post")
def test_insert_endpoint(mock_post, mock_config) -> None:
    """Verify insert_endpoint posts wrapped node properties."""
    mock_post.return_value = _build_response(json_data=[{"NID": "e1"}])

    api = discoveryAPI()
    props = {"name": "vm1"}

    assert api.insert_endpoint(props) == [{"NID": "e1"}]
    mock_post.assert_called_once_with(
        f"{api.discovery_URI}/endpoints/",
        json=[{"D": props}],
        timeout=60,
    )


@patch("firewheel.lib.discovery.api.requests.put")
def test_update_endpoint(mock_put, mock_config) -> None:
    """Verify update_endpoint sends the given node properties."""
    mock_put.return_value = _build_response(json_data=[{"NID": "e1"}])

    api = discoveryAPI()
    props = {"NID": "e1", "name": "vm1"}

    assert api.update_endpoint(props) == [{"NID": "e1"}]
    mock_put.assert_called_once_with(
        f"{api.discovery_URI}/endpoints/",
        json=[props],
        timeout=60,
    )


@patch("firewheel.lib.discovery.api.requests.post")
def test_connect_endpoint(mock_post, mock_config) -> None:
    """Verify connect_endpoint posts to the correct connect URI."""
    mock_post.return_value = _build_response(json_data={"NID": "e1", "network": "n1"})

    api = discoveryAPI()

    assert api.connect_endpoint("node1", "net1") == {"NID": "e1", "network": "n1"}
    mock_post.assert_called_once_with(
        f"{api.discovery_URI}/connect/net1/node1", timeout=60
    )


@patch("firewheel.lib.discovery.api.requests.get")
def test_get_config_propagates_json_error(mock_get, mock_config) -> None:
    """Verify malformed JSON from discovery propagates."""
    response = _build_response()
    response.json.side_effect = ValueError("bad json")
    mock_get.return_value = response

    api = discoveryAPI()

    with pytest.raises(ValueError):
        api.get_config("foo")


@patch("firewheel.lib.discovery.api.requests.post")
def test_set_config_propagates_http_error(mock_post, mock_config) -> None:
    """Verify HTTP errors from set_config are propagated."""
    response = _build_response()
    response.raise_for_status.side_effect = requests.HTTPError("boom")
    mock_post.return_value = response

    api = discoveryAPI()

    with pytest.raises(requests.HTTPError):
        api.set_config("foo", {"bar": 1})


def test_delete_all_endpoints_raises_on_missing_nid(mock_config) -> None:
    """Verify delete_all_endpoints fails clearly on malformed endpoint data."""
    api = discoveryAPI()

    with (
        patch.object(api, "get_endpoints", side_effect=[[{"NID": "e1"}], [{"bad": 1}]]),
        patch.object(api, "delete_endpoints", return_value=[{"NID": "e1"}]),
    ):
        with pytest.raises(KeyError):
            api.delete_all_endpoints()


def test_delete_all_networks_raises_on_missing_nid(mock_config) -> None:
    """Verify delete_all_networks fails clearly on malformed network data."""
    api = discoveryAPI()

    with patch.object(api, "get_networks", return_value=[{"bad": 1}]):
        with pytest.raises(KeyError):
            api.delete_all_networks()


@patch("firewheel.lib.discovery.api.requests.post")
def test_insert_endpoint_accepts_none_properties(mock_post, mock_config) -> None:
    """Verify insert_endpoint wraps None in the expected payload shape."""
    mock_post.return_value = _build_response(json_data=[{"NID": "e1"}])

    api = discoveryAPI()

    assert api.insert_endpoint(None) == [{"NID": "e1"}]
    mock_post.assert_called_once_with(
        f"{api.discovery_URI}/endpoints/",
        json=[{"D": None}],
        timeout=60,
    )
