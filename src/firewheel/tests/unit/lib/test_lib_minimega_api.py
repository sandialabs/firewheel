# test_lib_minimega_api.py
"""Unit tests for :mod:`firewheel.lib.minimega.api`."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from firewheel.lib.minimega.api import minimegaAPI


def _build_api_without_init() -> minimegaAPI:
    """Create a minimegaAPI instance without running __init__."""
    api = object.__new__(minimegaAPI)
    api.log = Mock()
    api.mm = Mock()
    api.mm_base = "/tmp/mm"
    api.mm_socket = "/tmp/mm/minimega"
    return api


def test_get_head_node(monkeypatch) -> None:
    """Verify the head node is read from configuration."""
    from firewheel.config import config

    monkeypatch.setitem(config["cluster"], "control", ["headnode"])
    assert minimegaAPI.get_head_node() == "headnode"


def test_get_head_node_raises_when_missing(monkeypatch) -> None:
    """Verify missing cluster control nodes raise RuntimeError."""
    from firewheel.config import config

    monkeypatch.setitem(config["cluster"], "control", [])
    with pytest.raises(RuntimeError):
        minimegaAPI.get_head_node()


def test_get_am_head_node(monkeypatch) -> None:
    """Verify current node/head node comparison works."""
    with patch.object(minimegaAPI, "get_head_node", return_value=platform.node()):
        assert minimegaAPI.get_am_head_node() is True


def test_check_version_success() -> None:
    """Verify version check returns queue result when child finishes."""
    api = _build_api_without_init()

    queue = Mock()
    queue.get.return_value = True

    proc = Mock()
    proc.is_alive.return_value = False

    with patch("firewheel.lib.minimega.api.multiprocessing.Queue", return_value=queue), patch(
        "firewheel.lib.minimega.api.multiprocessing.Process", return_value=proc
    ):
        assert api._check_version(timeout=1, skip_retry=False) is True


def test_check_version_timeout_raises_runtimeerror_when_skip_retry() -> None:
    """Verify version check raises RuntimeError when skip_retry is enabled."""
    api = _build_api_without_init()

    queue = Mock()
    proc = Mock()
    proc.is_alive.return_value = True

    with patch("firewheel.lib.minimega.api.multiprocessing.Queue", return_value=queue), patch(
        "firewheel.lib.minimega.api.multiprocessing.Process", return_value=proc
    ):
        with pytest.raises(RuntimeError):
            api._check_version(timeout=1, skip_retry=True)


def test_set_group_perms_success() -> None:
    """Verify recursive chmod succeeds on clean minimega response."""
    api = _build_api_without_init()
    api.mm.shell.return_value = [{"Error": ""}]

    assert api.set_group_perms("/tmp/mm/subdir") is True
    api.mm.shell.assert_called_once()


def test_set_group_perms_failure() -> None:
    """Verify recursive chmod failure returns False."""
    api = _build_api_without_init()
    api.mm.shell.return_value = [{"Error": "bad"}]

    assert api.set_group_perms("/tmp/mm/subdir") is False


def test_ns_kill_processes_success() -> None:
    """Verify namespace kill returns True when command succeeds."""
    api = _build_api_without_init()
    assert api.ns_kill_processes("script.py") is True


def test_ns_kill_processes_status_1_returns_false() -> None:
    """Verify namespace kill treats status 1 as no processes killed."""
    api = _build_api_without_init()

    class FakeError(Exception):
        """Simple stand-in error."""

    with patch("firewheel.lib.minimega.api.minimega.Error", FakeError):
        api.mm.ns_run.side_effect = FakeError("status 1")
        assert api.ns_kill_processes("script.py") is False


def test_get_mesh_size() -> None:
    """Verify mesh size is parsed from mesh_status output."""
    api = _build_api_without_init()
    api.mm.mesh_status.return_value = [
        {
            "Header": ["size"],
            "Tabular": [["3"]],
            "Host": "host",
        }
    ]
    assert api.get_mesh_size() == 3


def test_mmr_map() -> None:
    """Verify tabular responses are mapped by host."""
    raw = [
        {
            "Header": ["name", "value"],
            "Tabular": [["a", "1"], ["b", "2"]],
            "Host": "host1",
        }
    ]
    assert minimegaAPI.mmr_map(raw) == {
        "host1": [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]
    }


def test_mmr_map_first_value_only() -> None:
    """Verify first_value_only returns the first parsed row."""
    raw = [{"Header": ["name"], "Tabular": [["a"]], "Host": "host1"}]
    assert minimegaAPI.mmr_map(raw, first_value_only=True) == {"name": "a"}


@pytest.mark.parametrize(
    ("filter_dict", "elem", "expected"),
    [
        ({"state": ("=", "running")}, {"state": "running"}, True),
        ({"state": ("!=", "stopped")}, {"state": "running"}, True),
        ({"name": ("~", "vm")}, {"name": "vm1"}, True),
        ({"name": ("!~", "bad")}, {"name": "vm1"}, True),
        ({"state": ("=", "running")}, {"state": "stopped"}, False),
    ],
)
def test_check_host_filter(filter_dict, elem, expected) -> None:
    """Verify supported host filters evaluate correctly."""
    assert minimegaAPI.check_host_filter(filter_dict, elem) is expected


def test_check_host_filter_unsupported() -> None:
    """Verify unsupported filter operators raise RuntimeError."""
    with pytest.raises(RuntimeError):
        minimegaAPI.check_host_filter({"state": (">", "running")}, {"state": "running"})


def test_mm_vms() -> None:
    """Verify VM info is normalized into the expected structure."""
    api = _build_api_without_init()
    api.mm.vm_info.return_value = [
        {
            "Header": ["uuid", "name", "state", "id", "vnc_port", "tags", "pid"],
            "Tabular": [
                [
                    "uuid1",
                    "vm1",
                    "running",
                    "1",
                    "5900",
                    '{"image": "img", "control_ip": "10.0.0.1"}',
                    "1234",
                ]
            ],
            "Host": "host1",
        }
    ]

    result = api.mm_vms()
    assert result["vm1"]["uuid"] == "uuid1"
    assert result["vm1"]["vnc"] == "5900"
    assert result["vm1"]["image"] == "img"
    assert result["vm1"]["control_ip"] == "10.0.0.1"
    assert result["vm1"]["hostname"] == "host1"
    assert result["vm1"]["pid"] == "1234"


def test_parse_output() -> None:
    """Verify raw shell output is split into pipe-delimited columns."""
    parsed = minimegaAPI._parse_output(b"a|b\nc|d\n")
    assert parsed == [["a", "b"], ["c", "d"], [""]]


def test_parse_table() -> None:
    """Verify table parsing converts rows to dictionaries."""
    table = [["h1", "h2"], ["v1", "v2"], [""]]
    assert minimegaAPI._parse_table(table) == [{"h1": "v1", "h2": "v2"}]


def test_cmd_to_dict() -> None:
    """Verify command helper composes parsing helpers."""
    api = _build_api_without_init()
    api._run_cmd = Mock(return_value=b"a|b\n1|2\n")
    result = api._cmd_to_dict(["vm", "info"])
    assert result == [{"a": "1", "b": "2"}]


def test_run_cmd(monkeypatch) -> None:
    """Verify raw command execution invokes minimega binary."""
    from firewheel.config import config

    monkeypatch.setitem(config["minimega"], "install_dir", "/opt/minimega")
    mocked = Mock()
    mocked.stdout = b""
    mocked.stderr = b""

    with patch("firewheel.lib.minimega.api.subprocess.run", return_value=mocked) as run:
        ret = minimegaAPI._run_cmd(["vm", "info"])

    assert ret is mocked
    run.assert_called_once_with(
        ["/opt/minimega/bin/minimega", "-e", "vm", "info"],
        capture_output=True,
        check=True,
    )


def test_parse_host() -> None:
    """Verify host rows are converted to typed host dictionaries."""
    api = _build_api_without_init()
    host = api._parse_host(
        (
            "host1",
            [
                {
                    "cpus": "8",
                    "cpucommit": "4",
                    "memtotal": "1024",
                    "memcommit": "512",
                }
            ],
        )
    )
    assert host == {
        "control_hostname": "host1",
        "hostname": "host1",
        "cpus": 8,
        "cpucommit": 4,
        "memtotal": 1024,
        "memcommit": 512,
    }


def test_get_hosts_all() -> None:
    """Verify host list retrieval parses all hosts."""
    api = _build_api_without_init()
    api.mm.host.return_value = [
        {
            "Header": ["cpus", "cpucommit", "memtotal", "memcommit"],
            "Tabular": [["8", "4", "1024", "512"]],
            "Host": "host1",
        }
    ]

    hosts = api.get_hosts()
    assert "host1" in hosts
    assert hosts["host1"]["cpus"] == 8


def test_get_hosts_single_missing() -> None:
    """Verify specific host lookup returns None when absent."""
    api = _build_api_without_init()
    api.mm.host.return_value = []
    assert api.get_hosts(host_key="missing") is None


def test_get_cpu_commit_ratio() -> None:
    """Verify CPU commit ratio is computed from current host info."""
    api = _build_api_without_init()
    with patch.object(api, "get_hosts", return_value={"cpus": 8, "cpucommit": 4}):
        assert api.get_cpu_commit_ratio() == 0.5

