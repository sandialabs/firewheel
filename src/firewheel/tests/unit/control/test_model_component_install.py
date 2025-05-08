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
        result = install_component.install_mc("test_mc", Path("/mock/path/INSTALL"))
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
        result = install_component.install_mc("test_mc", Path("/mock/path/INSTALL"))
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
        result = install_component.install_mc("test_mc", Path("/mock/path/INSTALL"))
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
    Test the :py:meth:`has_shebang` method with a valid Ansible playbook.

    Args:
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the behavior of the file read to simulate invalid YAML
    mock_file = MagicMock()
    mock_file.read.return_value = "---\n- hosts: localhost\n  vars:\n    cached_files: [{'destination': 'file.txt'}]"
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


@patch("firewheel.control.model_component_install.ansible_runner.run")
@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
@patch("firewheel.control.model_component_install.Path.exists", return_value=True)
def test_run_ansible_playbook_success(
    mock_exists, mock_open, mock_run, install_component
):
    """
    Test the successful execution of a valid Ansible playbook.

    Mocks the playbook content to simulate a valid YAML structure.

    Args:
        mock_exists (MagicMock): Mock for the :py:meth:`pathlib.Path.exists` method.
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        mock_run (MagicMock): Mock for the ansible_runner.run method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the playbook content
    mock_file = MagicMock()
    mock_file.read.return_value = "---\n- hosts: localhost"
    mock_open.return_value.__enter__.return_value = mock_file

    # Mock the return value of ansible_runner.run
    mock_run.return_value = MagicMock(rc=0)

    result = install_component.run_ansible_playbook(Path("/mock/path/INSTALL"))
    assert result is True


@patch("firewheel.control.model_component_install.ansible_runner.RunnerConfig")
@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
@patch("firewheel.control.model_component_install.config", new_callable=MagicMock)
def test_run_ansible_playbook_fail(
    mock_config, mock_open, mock_runner_config, install_component
):
    """
    Test the failure of the :py:meth:`run_ansible_playbook` method when an error occurs.

    Mocks the playbook content and simulates a failure during execution.

    Args:
        mock_config (MagicMock): Mock for the FIREWHEEL configuration.
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        mock_runner_config (MagicMock): Mock for the RunnerConfig.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the playbook content
    mock_file = MagicMock()
    mock_file.read.return_value = "---\n- hosts: localhost\n  vars:\n    cached_files: [{'destination': 'file.txt'}]"
    mock_open.return_value.__enter__.return_value = mock_file

    # Set up the mock configuration
    mock_config.__getitem__.side_effect = lambda key: {
        "system": {"default_output_dir": "mock_dir"},
        "ansible": {"cache_type": "git"},
    }[key]

    # Create a mock for the RunnerConfig
    mock_runner_config_instance = MagicMock()
    mock_runner_config_instance.prepare = MagicMock()
    mock_runner_config.return_value = mock_runner_config_instance

    # Mock the return value of ansible_runner.run to simulate failure
    mock_runner = MagicMock()
    mock_runner.rc = 1

    # Patch the ansible_runner.run to return the mock runner
    with patch(
        'firewheel.control.model_component_install.ansible_runner.Runner.run',
        return_value=("success", 0),
    ):
        with patch(
            "firewheel.control.model_component_install.ansible_runner.run",
            return_value=mock_runner,
        ):
            result = install_component.run_ansible_playbook(Path("/mock/path/INSTALL"))

    assert result is False


@patch("firewheel.control.model_component_install.Path.open", new_callable=MagicMock)
@patch("firewheel.control.model_component_install.config", new_callable=MagicMock)
def test_run_ansible_playbook_invalid_cache_type(
    mock_config, mock_open, install_component
):
    """
    Test the :py:meth:`run_ansible_playbook` method when an invalid cache type is provided.

    Mocks the playbook content and simulates an invalid cache type scenario.

    Args:
        mock_config (MagicMock): Mock for the FIREWHEEL configuration.
        mock_open (MagicMock): Mock for the :py:meth:`pathlib.Path.open` method.
        install_component (ModelComponentInstall): The instance of :py:class:`ModelComponentInstall` to test.
    """
    # Mock the playbook content
    mock_file = MagicMock()
    mock_file.read.return_value = "---\n- hosts: localhost\n  vars:\n    cached_files: [{'destination': 'file.txt'}]"
    mock_open.return_value.__enter__.return_value = mock_file

    # Set up the mock configuration with an invalid cache type
    mock_config.__getitem__.side_effect = lambda key: {
        "system": {"default_output_dir": "mock_dir"},
        "ansible": {"cache_type": "invalid"},
    }[key]

    # Assert that ValueError is raised
    with pytest.raises(ValueError, match="Available `cache_type` are:"):
        install_component.run_ansible_playbook(Path("/mock/path/INSTALL"))
