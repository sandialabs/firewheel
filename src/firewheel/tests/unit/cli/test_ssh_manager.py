import shlex
import socket
from unittest.mock import patch, mock_open

import pytest

from firewheel.cli.ssh_manager import SSHManager, ParallelSSHManager, SCPManager


class _TestSSHProtocolManager:

    # Specify the local host (defined by `minimegaAPI.cluster_head_node`)
    local_hostname = f"{socket.gethostname()}"
    # Create a flattened form of the options common among SSH protocols
    default_options = [
        "-o",
        "LogLevel=error",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "HostKeyAlgorithms=+ssh-rsa",
        "-o",
        f"ProxyCommand ssh -o BatchMode=yes {local_hostname} -W %h:%p",
    ]


@pytest.fixture
def ssh():
    ssh = SSHManager()
    # Mock the acquisition of a remote VM IP address
    with patch.object(ssh, "_get_remote_vm_ip", return_value=TestSSHManager.vm_ip):
        yield ssh


class TestSSHManager(_TestSSHProtocolManager):

    # SSH-specific case settings
    user = "test_user"
    host = "hostname.test"
    vm_ip = "ABC.DEF.GHI.JKL"
    host_based_address = f"{user}@{host}"
    ip_based_address = f"{user}@{vm_ip}"

    @patch("subprocess.run")
    def test_call_ssh(self, mock_subprocess, ssh):
        # Mock a successful SSH call
        mock_subprocess.return_value.returncode = 0

        # Test the call (no additional options or command specified)
        result = ssh(self.host_based_address)
        assert result is mock_subprocess.return_value
        # Check that the SSH command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            ["ssh", *self.default_options, self.ip_based_address],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_ssh_default_user(self, mock_subprocess, ssh):
        # Mock a successful SSH call
        mock_subprocess.return_value.returncode = 0

        # Test the call (no additional options or command specified)
        result = ssh(self.host)
        assert result is mock_subprocess.return_value
        # Check that the SSH command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            ["ssh", *self.default_options, f"{self.vm_ip}"],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_ssh_with_options(self, mock_subprocess, ssh):
        # Mock a successful SSH call
        mock_subprocess.return_value.returncode = 0

        # Test the call (with additional options)
        options = [("-L", "localhost:5000:localhost:5000")]
        result = ssh(self.host_based_address, options=options)
        assert result is mock_subprocess.return_value
        # Check that the SSH command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            ["ssh", *self.default_options, *options[0], self.ip_based_address],
            check=True,
            capture_output=False,
        )

    @pytest.mark.parametrize(
        "command",
        [
            "ls -la",
            "grep 'test string' file.txt",
            "'grep \"test string\" file.txt'",
        ]
    )
    @patch("subprocess.run")
    def test_call_ssh_with_command(self, mock_subprocess, command, ssh):
        # Mock a successful SSH call
        mock_subprocess.return_value.returncode = 0

        # Test the call (with command specified)
        command = "ls -la"
        result = ssh(self.host_based_address, command=command)
        assert result is mock_subprocess.return_value
        # Check that the SSH command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "ssh",
                *self.default_options,
                self.ip_based_address,
                *shlex.split(command),
            ],
            check=True,
            capture_output=False,
        )


@pytest.fixture
def pssh():
    pssh = ParallelSSHManager()
    # Mock the acquisition of a remote VM IP address
    with patch.object(pssh, "_get_remote_vm_ip", side_effect=TestPSSHManager.vm_ips):
        yield pssh


class TestPSSHManager(_TestSSHProtocolManager):

    # PSSH-specific case settings
    user = "test_user"
    hosts = ["hostname0.test", "hostname1.test"]
    vm_ips = ["ABC.DEF.GHI.JKL", "MNO.PQR.STU.VWX"]
    host_based_addresses = [f"{user}@{hosts[0]}", f"{user}@{hosts[1]}"]
    ip_based_addresses = [f"{user}@{vm_ips[0]}", f"{user}@{vm_ips[1]}"]

    @property
    def default_options(self):
        # SSH options passed by parallel-ssh use a "-O" instead of "-o"
        return ["-O" if arg == "-o" else arg for arg in super().default_options]

    @patch("subprocess.run")
    def test_call_pssh(self, mock_subprocess, pssh):
        # Mock a successful PSSH call
        mock_subprocess.return_value.returncode = 0

        # Test the call
        command = "ls -la"
        options = [
            ("-H", " ".join(self.host_based_addresses)),
            ("-p", "10"),
        ]
        result = pssh(command, options=options)
        assert result is mock_subprocess.return_value
        # Check that the PSSH command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "parallel-ssh",
                *self.default_options,
                "-H",
                f"{self.ip_based_addresses[0]} {self.ip_based_addresses[1]}",
                "-p",
                "10",
                command,
            ],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_pssh_multiple_options(self, mock_subprocess, pssh):
        # Mock a successful PSSH call
        mock_subprocess.return_value.returncode = 0

        # Test the call
        command = "ls -la"
        options = [("-H", address) for address in self.host_based_addresses]
        result = pssh(command, options=options)
        assert result is mock_subprocess.return_value
        # Check that the SSH command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "parallel-ssh",
                *self.default_options,
                "-H",
                f"{self.ip_based_addresses[0]}",
                "-H",
                f"{self.ip_based_addresses[1]}",
                command,
            ],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_pssh_host_file(self, mock_subprocess, pssh):
        # Mock the acquisition of remote VM IP addresses
        mocked_vm_dict = {
            host: {"control_ip": ip} for host, ip in zip(self.hosts, self.vm_ips)
        }
        # Mock a successful PSSH call
        mock_subprocess.return_value.returncode = 0

        mocked_open = mock_open(read_data="\n".join(self.host_based_addresses))
        with patch(
            "firewheel.cli.ssh_manager.Path.open", mocked_open
        ) as mock_open_method, patch(
            "firewheel.cli.ssh_manager.minimegaAPI.mm_vms"
        ) as mock_vm_method, patch(
            "firewheel.cli.ssh_manager.Path.unlink"
        ) as mock_unlink_method:
            mock_write_method = mock_open_method.return_value.write
            mock_vm_method.return_value = mocked_vm_dict
            # Test the call (with a file of hosts provided)
            command = "ls -la"
            options = [("-h", "test_file.txt")]
            result = pssh(command, options=options)
            assert result is mock_subprocess.return_value
            # Check that the SSH command executed via subprocess was correct
            mock_subprocess.assert_called_with(
                ["parallel-ssh", *self.default_options, "-h", "test_file.tmp", command],
                check=True,
                capture_output=False,
            )
            mock_write_method.assert_called_once_with(
                "\n".join(self.ip_based_addresses)
            )
            mock_unlink_method.assert_called_once()

    def test_call_pssh_no_hosts(self, pssh):
        # Test the call with no hosts specified
        with pytest.raises(ValueError):
            pssh("ls -la", options=[("-p", "10")])


@pytest.fixture
def scp():
    scp = SCPManager()
    # Mock the acquisition of a remote VM IP address
    with patch.object(scp, "_get_remote_vm_ip", return_value=TestSCPManager.vm_ip):
        yield scp


class TestSCPManager(_TestSSHProtocolManager):

    # SCP-specific case settings
    user = "test_user"
    host = "hostname.test"
    vm_ip = "ABC.DEF.GHI.JKL"
    host_based_address = f"{user}@{host}"
    ip_based_address = f"{user}@{vm_ip}"

    @property
    def default_options(self):
        return [*super().default_options, "-r"]

    @patch("subprocess.run")
    def test_call_scp_push(self, mock_subprocess, scp):
        # Mock a successful SSH call (raises `SystemExit` with exit code 0)
        mock_subprocess.return_value.returncode = 0

        # Test pushing a file (no additional options specified)
        local_source = "/test/local/location/file.test"
        remote_file = "/test/remote/location"
        remote_target = f"{self.host_based_address}:{remote_file}"
        result = scp(remote_target, local_source)
        assert result is mock_subprocess.return_value
        # Check that the SCP command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "scp",
                *self.default_options,
                local_source,
                f"{self.ip_based_address}:{remote_file}",
            ],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_scp_push_multiple(self, mock_subprocess, scp):
        # Mock a successful SSH call (raises `SystemExit` with exit code 0)
        mock_subprocess.return_value.returncode = 0

        # Test pushing multiple files (no additional options specified)
        local_sources = [
            "/test/local/location/file1.test",
            "/test/local/location/file2.test",
        ]
        remote_file = "/test/remote/location"
        remote_target = f"{self.host_based_address}:{remote_file}"
        result = scp(remote_target, *local_sources)
        assert result is mock_subprocess.return_value
        # Check that the SCP command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "scp",
                *self.default_options,
                *local_sources,
                f"{self.ip_based_address}:{remote_file}",
            ],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_scp_pull(self, mock_subprocess, scp):
        # Mock a successful SSH call (raises `SystemExit` with exit code 0)
        mock_subprocess.return_value.returncode = 0

        # Test pulling a file (no additional options specified)
        local_target = "/test/local/location/"
        remote_file = "/test/remote/location/file.test"
        remote_source = f"{self.host_based_address}:{remote_file}"
        result = scp(local_target, remote_source)
        assert result is mock_subprocess.return_value
        # Check that the SCP command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "scp",
                *self.default_options,
                f"{self.ip_based_address}:{remote_file}",
                local_target,
            ],
            check=True,
            capture_output=False,
        )

    @patch("subprocess.run")
    def test_call_scp_pull_multiple(self, mock_subprocess, scp):
        # Mock a successful SSH call (raises `SystemExit` with exit code 0)
        mock_subprocess.return_value.returncode = 0

        # Test pulling multiple files (no additional options specified)
        local_target = "/test/local/location/"
        remote_files = [
            "/test/remote/location/file1.test",
            "/test/remote/location/file2.test",
        ]
        remote_sources = [f"{self.ip_based_address}:{_}" for _ in remote_files]
        result = scp(local_target, *remote_sources)
        assert result is mock_subprocess.return_value
        # Check that the SCP command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            ["scp", *self.default_options, *remote_sources, local_target],
            check=True,
            capture_output=False,
        )

    def test_scp_invalid_no_source_files(self, scp):
        # Test the call with no source files specified
        with pytest.raises(ValueError):
            scp("test_target")

    def test_scp_invalid_no_remote(self, scp):
        # Test the call with no remote system specified
        with pytest.raises(SystemExit) as context:
            scp("test_target", "test_source")
            assert context.exception.code == 1

    @patch("subprocess.run")
    def test_scp_pull_with_options(self, mock_subprocess, scp):
        # Mock a successful SSH call (raises `SystemExit` with exit code 0)
        mock_subprocess.return_value.returncode = 0

        # Test pulling a file (with additional options)
        local_target = "/test/local/location/"
        remote_file = "/test/remote/location/file.test"
        remote_source = f"{self.host_based_address}:{remote_file}"
        options = [("-f", "alt_ssh_config")]
        result = scp(local_target, remote_source, options=options)
        assert result is mock_subprocess.return_value
        # Check that the SCP command executed via subprocess was correct
        mock_subprocess.assert_called_with(
            [
                "scp",
                *self.default_options,
                *options[0],
                f"{self.ip_based_address}:{remote_file}",
                local_target,
            ],
            check=True,
            capture_output=False,
        )
