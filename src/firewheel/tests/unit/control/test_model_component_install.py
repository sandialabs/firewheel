import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from firewheel.control.model_component_install import ModelComponentInstall


@pytest.fixture
def mock_model_component():
    """
    Create a mock :py:class:`ModelComponent` instance for testing.

    Returns:
        MockModelComponent: A mock object simulating a ModelComponent with a name and path.
    """

    class MockModelComponent:
        def __init__(self, name, path):
            self.name = name
            self.path = path

    return MockModelComponent(name="test_mc", path="/mock/path")


@pytest.fixture
def install_component(mock_model_component):
    """
    Create an instance of :py:class:`ModelComponentInstall` for testing.

    Args:
        mock_model_component (MockModelComponent): A mock ModelComponent instance.

    Returns:
        ModelComponentInstall: An instance of :py:class:`ModelComponentInstall` initialized with the
        mock ModelComponent.
    """
    return ModelComponentInstall(mc=mock_model_component)


@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
@patch(
    "firewheel.control.model_component_install.Path.stat",
    return_value=MagicMock(st_mode=0),
)
@patch("firewheel.control.model_component_install.Path.chmod")
def test_install_mc_success(mock_chmod, mock_stat, mock_open, install_component):
    """
    Test the successful execution of the :py:meth:`install_mc` method.

    Mocks the INSTALL script to simulate a successful installation.

    Args:
        mock_chmod (MagicMock): Mock for the :py:meth:`pathlib.Path.chmod` method.
        mock_stat (MagicMock): Mock for the :py:meth:`pathlib.Path.stat` method.
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the behavior of the file read to simulate a valid INSTALL script
    mock_file = MagicMock()
    mock_file.read.return_value = "#!/bin/bash\necho 'Installing...'"
    mock_open.return_value.__enter__.return_value = mock_file

    with patch("firewheel.control.model_component_install.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = install_component.install_mc(Path("/mock/path/INSTALL"))
        assert result is True


@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
@patch(
    "firewheel.control.model_component_install.Path.stat",
    return_value=MagicMock(st_mode=0),
)
@patch("firewheel.control.model_component_install.Path.chmod")
def test_install_mc_failure(mock_chmod, mock_stat, mock_open, install_component):
    """
    Test the failure of the :py:meth:`install_mc` method when a subprocess error occurs.

    Mocks the INSTALL script to simulate a failure during installation.

    Args:
        mock_chmod (MagicMock): Mock for the :py:meth:`pathlib.Path.chmod` method.
        mock_stat (MagicMock): Mock for the :py:meth:`pathlib.Path.stat` method.
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the behavior of the file read to simulate a valid INSTALL script
    mock_file = MagicMock()
    mock_file.read.return_value = "#!/bin/bash\necho 'Installing...'"
    mock_open.return_value.__enter__.return_value = mock_file

    with patch("firewheel.control.model_component_install.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        result = install_component.install_mc(Path("/mock/path/INSTALL"))
        assert result is False


@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
@patch(
    "firewheel.control.model_component_install.Path.stat",
    return_value=MagicMock(st_mode=0),
)
@patch("firewheel.control.model_component_install.Path.chmod")
def test_install_mc_already_installed(
    mock_chmod, mock_stat, mock_open, install_component
):
    """
    Test the :py:meth:`install_mc` method when the component is already installed.

    Mocks the INSTALL script to simulate an already installed state.

    Args:
        mock_chmod (MagicMock): Mock for the :py:meth:`pathlib.Path.chmod` method.
        mock_stat (MagicMock): Mock for the :py:meth:`pathlib.Path.stat` method.
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the behavior of the file read to simulate a valid INSTALL script
    mock_file = MagicMock()
    mock_file.read.return_value = "#!/bin/bash\necho 'Installing...'"
    mock_open.return_value.__enter__.return_value = mock_file

    with patch("firewheel.control.model_component_install.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(117, "cmd")
        result = install_component.install_mc(Path("/mock/path/INSTALL"))
        # Expecting True since the return code 117 indicates an already installed
        # model component
        assert result is True


@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
def test_has_shebang_valid(mock_open, install_component):
    """
    Test the :py:meth:`has_shebang` method with a valid INSTALL script.

    Args:
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the behavior of the file read to simulate a valid Ansible playbook
    mock_file = MagicMock()
    mock_file.read.return_value = "#! /bin/bash"
    mock_open.return_value.__enter__.return_value = mock_file

    result = install_component.has_shebang(Path("/mock/path/INSTALL"))
    # Expecting True since the INSTALL is valid
    assert result is True


@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
def test_has_shebang_invalid(mock_open, install_component):
    """
    Test the :py:meth:`has_shebang` method with a bash script without a shebang.

    Args:
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the behavior of the file read to simulate an invalid bash script
    mock_file = MagicMock()
    mock_file.read.return_value = "echo 'testing'"
    mock_open.return_value.__enter__.return_value = mock_file

    result = install_component.has_shebang(Path("/mock/path/INSTALL"))
    # Expecting False due to lack of shebang
    assert result is False


@patch("firewheel.control.model_component_install.Path.exists", side_effect=[False])
def test_run_install_script_no_install_script(mock_exists, install_component):
    """
    Test the :py:meth:`run_install_script` method when the install script does not exist.

    Args:
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method to simulate the absence
            of the install script.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    result = install_component.run_install_script()
    # Expecting True since the install script does not exist
    assert result is True


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, True]
)
def test_run_install_script_with_existing_install_flag(mock_exists, install_component):
    """
    Test the :py:meth:`run_install_script` method when the install flag exists.

    Args:
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method.
            Simulates the presence of the ``install_script`` and the ``install_flag``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    result = install_component.run_install_script()
    # Expecting True since the install flag exists
    assert result is True


def test_model_component_install_init_raises_value_error():
    """
    Test that initializing :py:class:`ModelComponentInstall` without a :py:class:`ModelComponent`
    raises a :py:exc:`ValueError`.

    Asserts that the appropriate error message is raised when no ModelComponent is provided.
    """
    with pytest.raises(ValueError, match="Must specify a Model Component."):
        # Pass nothing to trigger a ValueError
        ModelComponentInstall()


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, False]
)
@patch("firewheel.control.model_component_install.InstallPrompt.ask", return_value="y")
@patch(
    "firewheel.control.model_component_install.ModelComponentInstall.install_mc",
    return_value=False,
)
def test_run_install_script_user_prompt(
    mock_install_mc, mock_ask, mock_exists, install_component
):
    """
    Test the :py:meth:`run_install_script` method when the user is prompted for input.

    Args:
        mock_install_mc (MagicMock): Mock for the :py:meth:`install_mc` method to return True.
        mock_ask (MagicMock): Mock for the :py:meth:`InstallPrompt.ask` method. Mocks the user input to simulate
            a positive response to the installation prompt.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method.  Mocks the existence of
            the ``install_script`` and the non-existence of the ``install_flag``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    result = install_component.run_install_script()
    assert result is False


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, False]
)
@patch(
    "firewheel.control.model_component_install.ModelComponentInstall.install_mc",
    return_value=False,
)
def test_run_install_script_insecure_fail(
    mock_install_mc, mock_exists, install_component
):
    """
    Test the :py:meth:`run_install_script` method when insecure installation fails.

    Args:
        mock_install_mc (MagicMock): Mock for the :py:meth:`install_mc` method to simulate a failure
            during insecure installation..
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the existence of
            the ``install_script`` and the non-existence of the ``install_flag``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    result = install_component.run_install_script(insecure=True)
    assert result is False


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, False]
)
@patch(
    "firewheel.control.model_component_install.ModelComponentInstall.install_mc",
    return_value=True,
)
def test_run_install_script_insecure_pass(
    mock_install_mc, mock_exists, install_component
):
    """
    Test the :py:meth:`run_install_script` method when insecure installation succeeds.

    Args:
        mock_install_mc (MagicMock): Mock for the :py:meth:`install_mc` method to simulate a successful
            installation during insecure mode.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the existence of the
            ``install_script`` and the non-existence of the ``install_flag``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    result = install_component.run_install_script(insecure=True)
    assert result is True


@patch("firewheel.control.model_component_install.Path.is_dir", return_value=False)
def test_run_ansible_playbook_not_a_directory(mock_is_dir, install_component):
    """
    This test checks if ``install_path`` is not a directory, which should raise a :py:exc:`ValueError`.

    Args:
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method. Mocks the non-existence of the
            ``install_script``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    with pytest.raises(ValueError, match="Invalid INSTALL file."):
        install_component.run_ansible_playbook(Path("/mock/path"))


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[False, False]
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
def test_run_ansible_playbook_missing_vars_file(
    mock_is_dir, mock_exists, install_component
):
    """
    Test the behavior when the ``vars`` file is missing.

    Args:
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the non-existence of the
            ``vars.yml`` and the non-existence of the ``vars.yaml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    with pytest.raises(ValueError, match="Missing vars.yml file in directory"):
        install_component.run_ansible_playbook(Path("/mock/path"))


@patch(
    "firewheel.control.model_component_install.Path.exists",
    side_effect=[True, False, False],
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
def test_run_ansible_playbook_missing_tasks_file(
    mock_is_dir, mock_exists, install_component
):
    """
    Test the behavior when the ``tasks`` file is missing.

    Args:
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the
            existence of ``vars.yml`` and the non-existence of the ``tasks.yml`` and ``tasks.yaml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    with pytest.raises(ValueError, match="Missing tasks.yml file in directory"):
        install_component.run_ansible_playbook(Path("/mock/path"))


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, True]
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
@patch("firewheel.control.model_component_install.ansible_runner.run")
def test_run_ansible_playbook_failure(
    mock_run, mock_is_dir, mock_exists, install_component
):
    """
    Test the return value when the Ansible playbook execution fails.

    Args:
        mock_run (MagicMock): Mock for the :py:meth:`ansible_runner.run` method to simulate a failure.
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method.  Mocks the
            existence of ``vars.yml`` and the existence ``tasks.yml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    mock_runner = MagicMock()
    mock_runner.rc = 1  # Failing return code
    mock_run.return_value = mock_runner

    result = install_component.run_ansible_playbook(Path("/mock/path"))
    # Expecting False since the playbook execution fails
    assert result is False


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, True]
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
@patch("firewheel.control.model_component_install.ansible_runner.run")
def test_run_ansible_playbook_success(
    mock_run, mock_is_dir, mock_exists, install_component
):
    """
    Test the successful execution of a valid Ansible playbook.

    Args:
        mock_run (MagicMock): Mock for the result from ansible_runner.
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method.  Mocks the
            existence of ``vars.yml`` and the existence ``tasks.yml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the return value of ansible_runner.run to simulate failure
    mock_runner = MagicMock()
    mock_runner.rc = 0  # Success return code
    mock_run.return_value = mock_runner

    result = install_component.run_ansible_playbook(Path("/mock/path"))
    assert result is True  # Expecting False since the playbook execution fails


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, True]
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
@patch("firewheel.control.model_component_install.config", new_callable=MagicMock)
def test_run_ansible_playbook_git_config(
    mock_config, mock_is_dir, mock_exists, install_component
):
    """
    This test verifies that the Git configuration is correctly flattened from the ansible config.

    Args:
        mock_config (MagicMock): Mock for the configuration dictionary.
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the
            existence of ``vars.yml`` and the existence ``tasks.yml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock configuration with Git servers
    mock_config.__getitem__.side_effect = lambda key: {
        "system": {"default_output_dir": "mock_dir"},
        "ansible": {
            "git_servers": [
                {
                    "server_url": "https://git.example.com",
                    "repositories": [
                        {"path": "repo1", "branch": "main"},
                        {"path": "repo2"},
                    ],
                }
            ]
        },
    }[key]

    result = install_component.flatten_git_config()

    assert len(result) == 2
    assert result[0]["server_url"] == "https://git.example.com"
    assert result[0]["path"] == "repo1"
    assert "branch" in result[0]
    assert result[1]["path"] == "repo2"


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, True]
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
@patch("firewheel.control.model_component_install.config", new_callable=MagicMock)
def test_run_ansible_playbook_s3_config(
    mock_config, mock_is_dir, mock_exists, install_component
):
    """
    This test verifies that the S3 configuration is correctly flattened from the ansible config.

    Args:
        mock_config (MagicMock): Mock for the configuration dictionary.
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the
            existence of ``vars.yml`` and the existence ``tasks.yml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock configuration with S3 endpoints
    mock_config.__getitem__.side_effect = lambda key: {
        "system": {"default_output_dir": "mock_dir"},
        "ansible": {
            "s3_endpoints": [
                {
                    "s3_endpoint": "https://s3.example.com",
                    "aws_access_key_id": "mock_access_key",
                    "aws_secret_access_key": "mock_secret_key",
                    "buckets": ["bucket1", "bucket2"],
                }
            ]
        },
    }[key]

    result = install_component.flatten_s3_config()

    assert len(result) == 2
    assert result[0]["s3_endpoint"] == "https://s3.example.com"
    assert result[0]["bucket"] == "bucket1"


@patch(
    "firewheel.control.model_component_install.Path.exists", side_effect=[True, True]
)
@patch("firewheel.control.model_component_install.Path.is_dir", return_value=True)
@patch("firewheel.control.model_component_install.config", new_callable=MagicMock)
def test_run_ansible_playbook_file_server_config(
    mock_config, mock_is_dir, mock_exists, install_component
):
    """
    This test verifies that the file server configuration is correctly flattened from the ansible config.

    Args:
        mock_config (MagicMock): Mock for the configuration dictionary.
        mock_is_dir (MagicMock): Mock for the :py:meth:`pathlib.Path.is_dir` method.
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method. Mocks the
            existence of ``vars.yml`` and the existence ``tasks.yml``.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock configuration with file servers
    mock_config.__getitem__.side_effect = lambda key: {
        "system": {"default_output_dir": "mock_dir"},
        "ansible": {
            "file_servers": [
                {
                    "url": "https://files.example.com",
                    "use_proxy": True,
                    "validate_certs": False,
                    "cache_paths": ["cache1", "cache2"],
                }
            ]
        },
    }[key]

    result = install_component.flatten_file_server_config()

    assert len(result) == 2
    assert result[0]["url"] == "https://files.example.com"
    assert result[0]["cache_path"] == "cache1"
