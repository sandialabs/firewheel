# test_lib_minimega_api.py
"""Unit tests for :mod:`firewheel.lib.minimega.api`."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from firewheel.lib.minimega.api import minimegaAPI


@pytest.fixture
def config() -> dict:
    """Return the mutable FIREWHEEL configuration used by minimega tests."""
    from firewheel.config import config

    return config


def _build_api_without_init() -> minimegaAPI:
    """Create a minimegaAPI instance without running __init__."""
    api = object.__new__(minimegaAPI)
    api.log = Mock()
    api.mm = Mock()
    api.mm_base = "/tmp/mm"
    api.mm_socket = "/tmp/mm/minimega"
    api.mm_namespace = "firewheel"
    return api


@pytest.fixture
def mock_mm_api() -> minimegaAPI:
    """A mocked ``minimegaAPI`` object."""
    return _build_api_without_init()


def test_get_head_node(config, monkeypatch) -> None:
    """Verify the head node is read from configuration."""
    monkeypatch.setitem(config["cluster"], "control", ["headnode"])
    assert minimegaAPI.get_head_node() == "headnode"


def test_get_head_node_raises_when_missing(config, monkeypatch) -> None:
    """Verify missing cluster control nodes raise RuntimeError."""
    monkeypatch.setitem(config["cluster"], "control", [])
    with pytest.raises(RuntimeError):
        minimegaAPI.get_head_node()


def test_get_am_head_node(monkeypatch) -> None:
    """Verify current node/head node comparison works."""
    with patch.object(minimegaAPI, "get_head_node", return_value=platform.node()):
        assert minimegaAPI.get_am_head_node() is True


def test_check_version_success(mock_mm_api) -> None:
    """Verify version check returns queue result when child finishes."""
    queue = Mock()
    queue.get.return_value = True

    proc = Mock()
    proc.is_alive.return_value = False

    with (
        patch("firewheel.lib.minimega.api.multiprocessing.Queue", return_value=queue),
        patch("firewheel.lib.minimega.api.multiprocessing.Process", return_value=proc),
    ):
        assert mock_mm_api._check_version(timeout=1, skip_retry=False) is True


def test_check_version_timeout_raises_runtimeerror_when_skip_retry(mock_mm_api) -> None:
    """Verify version check raises RuntimeError when skip_retry is enabled."""
    queue = Mock()
    proc = Mock()
    proc.is_alive.return_value = True

    with (
        patch("firewheel.lib.minimega.api.multiprocessing.Queue", return_value=queue),
        patch("firewheel.lib.minimega.api.multiprocessing.Process", return_value=proc),
    ):
        with pytest.raises(RuntimeError):
            mock_mm_api._check_version(timeout=1, skip_retry=True)


def test_set_group_perms_success(mock_mm_api) -> None:
    """Verify recursive chmod succeeds on clean minimega response."""
    mock_mm_api.mm.shell.return_value = [{"Error": ""}]

    assert mock_mm_api.set_group_perms("/tmp/mm/subdir") is True
    mock_mm_api.mm.shell.assert_called_once()


def test_set_group_perms_failure(mock_mm_api) -> None:
    """Verify recursive chmod failure returns False."""
    mock_mm_api.mm.shell.return_value = [{"Error": "bad"}]

    assert mock_mm_api.set_group_perms("/tmp/mm/subdir") is False


def test_ns_kill_processes_success(mock_mm_api) -> None:
    """Verify namespace kill returns True when command succeeds."""
    assert mock_mm_api.ns_kill_processes("script.py") is True


def test_ns_kill_processes_status_1_returns_false(mock_mm_api) -> None:
    """Verify namespace kill treats status 1 as no processes killed."""

    class FakeError(Exception):
        """Simple stand-in error."""

    with patch("firewheel.lib.minimega.api.minimega.Error", FakeError):
        mock_mm_api.mm.ns_run.side_effect = FakeError("status 1")
        assert mock_mm_api.ns_kill_processes("script.py") is False


def test_get_mesh_size(mock_mm_api) -> None:
    """Verify mesh size is parsed from mesh_status output."""
    mock_mm_api.mm.mesh_status.return_value = [
        {
            "Header": ["size"],
            "Tabular": [["3"]],
            "Host": "host",
        }
    ]
    assert mock_mm_api.get_mesh_size() == 3


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


def test_mm_vms(mock_mm_api) -> None:
    """Verify VM info is normalized into the expected structure."""
    mock_mm_api.mm.vm_info.return_value = [
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

    result = mock_mm_api.mm_vms()
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


def test_cmd_to_dict(mock_mm_api) -> None:
    """Verify command helper composes parsing helpers."""
    mock_mm_api._run_cmd = Mock(return_value=b"a|b\n1|2\n")
    result = mock_mm_api._cmd_to_dict(["vm", "info"])
    assert result == [{"a": "1", "b": "2"}]


def test_run_cmd(config, monkeypatch) -> None:
    """Verify raw command execution invokes minimega binary."""
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


def test_parse_host(mock_mm_api) -> None:
    """Verify host rows are converted to typed host dictionaries."""
    host = mock_mm_api._parse_host(
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


def test_get_hosts_all(mock_mm_api) -> None:
    """Verify host list retrieval parses all hosts."""
    mock_mm_api.mm.host.return_value = [
        {
            "Header": ["cpus", "cpucommit", "memtotal", "memcommit"],
            "Tabular": [["8", "4", "1024", "512"]],
            "Host": "host1",
        }
    ]

    hosts = mock_mm_api.get_hosts()
    assert "host1" in hosts
    assert hosts["host1"]["cpus"] == 8


def test_get_hosts_single_missing(mock_mm_api) -> None:
    """Verify specific host lookup returns None when absent."""
    mock_mm_api.mm.host.return_value = []
    assert mock_mm_api.get_hosts(host_key="missing") is None


def test_get_cpu_commit_ratio(mock_mm_api) -> None:
    """Verify CPU commit ratio is computed from current host info."""
    with patch.object(
        mock_mm_api,
        "get_hosts",
        return_value={"cpus": 8, "cpucommit": 4},
    ):
        assert mock_mm_api.get_cpu_commit_ratio() == 0.5


def test_init_raises_when_socket_missing(config, monkeypatch) -> None:
    """Verify constructor raises when minimega socket is absent."""
    monkeypatch.setitem(config["minimega"], "base_dir", "/tmp/mm")
    monkeypatch.setitem(config["minimega"], "namespace", None)
    monkeypatch.setitem(config["cluster"], "control", ["headnode"])

    with patch("firewheel.lib.minimega.api.os.path.exists", return_value=False):
        with pytest.raises(RuntimeError):
            minimegaAPI()


def test_init_raises_on_minimega_connection_failure(config, monkeypatch) -> None:
    """Verify constructor wraps connection failures as RuntimeError."""
    monkeypatch.setitem(config["minimega"], "base_dir", "/tmp/mm")
    monkeypatch.setitem(config["minimega"], "namespace", None)
    monkeypatch.setitem(config["cluster"], "control", ["headnode"])

    with (
        patch("firewheel.lib.minimega.api.os.path.exists", return_value=True),
        patch(
            "firewheel.lib.minimega.api.minimega.minimega",
            side_effect=Exception("connect fail"),
        ),
    ):
        with pytest.raises(RuntimeError):
            minimegaAPI()


def test_init_raises_timeout_from_check_version(config, monkeypatch) -> None:
    """Verify constructor propagates TimeoutError from version check."""
    monkeypatch.setitem(config["minimega"], "base_dir", "/tmp/mm")
    monkeypatch.setitem(config["minimega"], "namespace", None)
    monkeypatch.setitem(config["cluster"], "control", ["headnode"])

    mm_obj = Mock()

    with (
        patch("firewheel.lib.minimega.api.os.path.exists", return_value=True),
        patch("firewheel.lib.minimega.api.minimega.minimega", return_value=mm_obj),
        patch.object(
            minimegaAPI, "_check_version", side_effect=TimeoutError("timeout")
        ),
    ):
        with pytest.raises(TimeoutError):
            minimegaAPI()


def test_mmr_map_ignores_empty_tabular() -> None:
    """Verify empty tabular responses are skipped."""
    raw = [{"Header": ["a"], "Tabular": [], "Host": "host1"}]
    assert minimegaAPI.mmr_map(raw) == {}


def test_parse_host_none_returns_none(mock_mm_api) -> None:
    """Verify parsing a falsey host item returns None."""
    assert mock_mm_api._parse_host(None) is None


def test_get_hosts_single_hit(mock_mm_api) -> None:
    """Verify specific host lookup returns parsed host."""
    mock_mm_api.mm.host.return_value = [
        {
            "Header": ["cpus", "cpucommit", "memtotal", "memcommit"],
            "Tabular": [["8", "4", "1024", "512"]],
            "Host": "host1",
        }
    ]

    host = mock_mm_api.get_hosts(host_key="host1")
    assert host["hostname"] == "host1"
    assert host["cpus"] == 8


def test_run_minimega_script_raises_calledprocesserror(
    config, monkeypatch, tmp_path: Path, mock_mm_api
) -> None:
    """Verify subprocess failures are re-raised by run_minimega_script."""
    monkeypatch.setitem(config["minimega"], "install_dir", "/opt/minimega")

    script = tmp_path / "launch.mm"
    script.write_text("vm info", encoding="utf-8")

    with patch(
        "firewheel.lib.minimega.api.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["minimega"]),
    ):
        with pytest.raises(subprocess.CalledProcessError):
            mock_mm_api.run_minimega_script(script)


def test_run_minimega_script_raises_oserror(
    config, monkeypatch, tmp_path: Path, mock_mm_api
) -> None:
    """Verify launch failures are re-raised by run_minimega_script."""
    monkeypatch.setitem(config["minimega"], "install_dir", "/opt/minimega")

    script = tmp_path / "launch.mm"
    script.write_text("vm info", encoding="utf-8")

    with patch(
        "firewheel.lib.minimega.api.subprocess.run",
        side_effect=OSError("cannot launch"),
    ):
        with pytest.raises(OSError):
            mock_mm_api.run_minimega_script(script)


def test_mmr_map_first_value_only_empty_returns_empty_dict() -> None:
    """Verify first_value_only with empty input returns an empty mapping."""
    assert minimegaAPI.mmr_map([], first_value_only=True) == {}


def test_mmr_map_missing_host_key_raises() -> None:
    """Verify malformed minimega responses without Host raise KeyError."""
    raw = [{"Header": ["a"], "Tabular": [["1"]]}]
    with pytest.raises(KeyError):
        minimegaAPI.mmr_map(raw)


def test_mmr_map_missing_header_key_raises() -> None:
    """Verify malformed minimega responses without Header raise KeyError."""
    raw = [{"Host": "host1", "Tabular": [["1"]]}]
    with pytest.raises(KeyError):
        minimegaAPI.mmr_map(raw)


def test_get_mesh_size_bad_shape_raises_keyerror(mock_mm_api) -> None:
    """Verify malformed mesh_status output raises on missing expected keys."""
    mock_mm_api.mm.mesh_status.return_value = [{"Tabular": []}]

    with pytest.raises(KeyError):
        mock_mm_api.get_mesh_size()


def test_mm_vms_bad_tags_json_raises(mock_mm_api) -> None:
    """Verify malformed VM tag JSON propagates."""
    mock_mm_api.mm.vm_info.return_value = [
        {
            "Header": ["uuid", "name", "state", "id", "vnc_port", "tags", "pid"],
            "Tabular": [["uuid1", "vm1", "running", "1", "5900", "{bad json", "123"]],
            "Host": "host1",
        }
    ]

    with pytest.raises(Exception):
        mock_mm_api.mm_vms()


def test_parse_table_with_only_header_returns_empty() -> None:
    """Verify parse_table returns an empty list when only a header is present."""
    assert minimegaAPI._parse_table([["h1", "h2"]]) == []
