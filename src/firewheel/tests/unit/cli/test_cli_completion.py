import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from firewheel.config import config
from firewheel.cli.completion import COMPLETION_SCRIPT_PATH
from firewheel.cli.completion.actions import (
    _keyboard_interruptable,
    get_model_component_names,
    get_available_cli_commands,
    get_total_model_components_size,
)
from firewheel.cli.completion.prepare_completion_script import (
    main,
    populate_template,
    display_instructions,
    print_completion_script_path,
)


class CliCompletionTestCase(unittest.TestCase):
    """Test case for completion script utilities."""

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_get_available_cli_commands(self, mock_stdout):
        expected_cli_commands = [
            "init",
            "list",
            "author",
            "run",
            "docs",
            "history",
            "sync",
            "config",
            "help",
            "version",
            "exit",
            "EOF",
            "quit",
        ]
        get_available_cli_commands()
        # Parse the output (space separated string) and check validity
        printed_output = mock_stdout.getvalue()
        printed_cli_commands = printed_output.strip().split(" ")
        self.assertCountEqual(printed_cli_commands, expected_cli_commands)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("firewheel.cli.completion.actions.ModelComponentIterator")
    def test_get_model_component_names(self, mock_iterator_cls, mock_stdout):
        # Mock a subset of MCs here to preserve validity as new MCs are added
        mock_mc_names = [
            "base",
            "linux",
            "utilities",
        ]
        mock_mcs = [Mock(mc_name=name) for name in mock_mc_names]
        # Override the mock's name attribute to be the MC name
        for mock_mc in mock_mcs:
            mock_mc.name = mock_mc.mc_name
        mock_iterator_cls.return_value = mock_mcs
        get_model_component_names()
        # Parse the output (space separated string) and check validity
        printed_output = mock_stdout.getvalue()
        printed_mc_names = printed_output.strip().split(" ")
        self.assertCountEqual(printed_mc_names, mock_mc_names)

    @pytest.mark.mcs
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_get_total_model_components_size(self, mock_stdout):
        # Check that the size is nonzero (some MCs were found)
        get_total_model_components_size()
        assert int(mock_stdout.getvalue()) > 0

    def test_keyboard_interruptable(self):
        @_keyboard_interruptable
        def raise_keyboard_interrupt():
            raise KeyboardInterrupt

        # Should not actually raise the exception (due to the decorator)
        assert raise_keyboard_interrupt() is None


class CliCompletionTemplatingTestCase(unittest.TestCase):
    """Test case for completion script template functionality."""

    mock_open_function = mock_open()

    @patch.object(Path, "open", new=mock_open_function)
    def test_populate_template(self):
        mock_script_path = Path("mock_script_path")
        populate_template(mock_script_path)
        # Check that the designated file was opened in write mode
        self.mock_open_function.assert_called_once_with("w")
        # Check that the output of the `write` method is correct
        mock_handle = self.mock_open_function.return_value
        mock_handle.write.assert_called_once()
        script_content = mock_handle.write.call_args.args[0]
        filled_placeholders = [
            f"fw_venv=\"{config['python']['venv']}\"",
            f"python_bin=\"{config['python']['bin']}\"",
        ]
        assert all(_ in script_content for _ in filled_placeholders)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_templating_display_instructions(self, mock_stdout):
        mock_script_path = Mock(name="script_path")
        display_instructions(mock_script_path)
        printed_output = mock_stdout.getvalue()
        assert "To enable tab-completion" in printed_output
        assert str(mock_script_path) in printed_output

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_completion_script_path(self, mock_stdout):
        print_completion_script_path()
        # Get the output and check validity
        printed_output = mock_stdout.getvalue()
        assert printed_output.strip() == str(COMPLETION_SCRIPT_PATH)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("argparse.ArgumentParser")
    @patch("firewheel.cli.completion.prepare_completion_script.display_instructions")
    @patch("firewheel.cli.completion.prepare_completion_script.populate_template")
    def test_module_as_script(
        self, mock_populate_function, mock_display_function, mock_parser_cls, mock_stdout
    ):
        # Mock the argument parser as if `--print-path` was supplied via the CLI
        mock_args = mock_parser_cls().parse_args.return_value
        mock_args.print_path = False

        main()

        # Ensure functions are called when the script is run (without `--print-path`)
        mock_populate_function.assert_called_once()
        mock_display_function.assert_called_once()

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("argparse.ArgumentParser")
    @patch("firewheel.cli.completion.prepare_completion_script.display_instructions")
    @patch("firewheel.cli.completion.prepare_completion_script.populate_template")
    def test_module_as_script_print_path(
        self, mock_populate_function, mock_display_function, mock_parser_cls, mock_stdout
    ):
        # Mock the argument parser as if `--print-path` was supplied via the CLI
        mock_args = mock_parser_cls().parse_args.return_value
        mock_args.print_path = True

        main()

        # Ensure that the path is printed when called with `--print-path`
        printed_output = mock_stdout.getvalue()
        assert printed_output.strip() == str(COMPLETION_SCRIPT_PATH)

        # The remaining functions are not called with `--print-path`
        mock_populate_function.assert_not_called()
        mock_display_function.assert_not_called()
