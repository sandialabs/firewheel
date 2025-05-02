import io
import uuid
import socket
from unittest.mock import patch
from pathlib import Path
from importlib.metadata import version

import pytest

from firewheel.config import Config
from firewheel.cli.utils import HelperNotFoundError
from firewheel.cli.firewheel_cli import FirewheelCLI


@pytest.fixture
def config(tmp_path):
    # Set the configuration (and save a copy of the original)
    test_config_path = tmp_path / "firewheel.yaml"
    config = Config(config_path=test_config_path, writable=True)
    config.config["logging"]["root_dir"] = str(tmp_path)
    config.config["cluster"]["compute"] = [socket.gethostname()]
    config.config["cluster"]["control"] = [socket.gethostname()]
    return config


@pytest.fixture
def cli(config):
    with patch("firewheel.config.Config.get_config", return_value=config.get_config()):
        yield FirewheelCLI()


def build_custom_config_cli(config):
    with patch("firewheel.config.Config.get_config", return_value=config.get_config()):
        return FirewheelCLI()


class TestCLI:

    @staticmethod
    def assert_standard_cli_attributes(cli):
        assert cli.log is not None
        assert cli.session["sequence_number"] == 0
        assert isinstance(cli.session["id"], uuid.UUID)

    @staticmethod
    def assert_substring_in_file_last_line(substring, path):
        with path.open("r") as f_hand:
            assert substring in f_hand.readlines()[-1]

    def test_normal_setup(self, cli):
        self.assert_standard_cli_attributes(cli)
        assert cli.history_file.name != "/dev/null"

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_no_history_file(self, mock_stdout, config):
        config.resolve_set("logging.root_dir", 1234)
        cli = build_custom_config_cli(config)
        # Check that certain attributes have been created
        self.assert_standard_cli_attributes(cli)
        assert cli.history_file.name == "/dev/null"
        assert "Continuing" in mock_stdout.getvalue()

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_no_exp_history_file(self, mock_stdout, config):
        config.resolve_set("logging.root_dir", 1234)
        cli = build_custom_config_cli(config)
        # Check that certain attributes have been created
        self.assert_standard_cli_attributes(cli)
        assert cli.history_file.name == "/dev/null"
        assert "experiment history" in mock_stdout.getvalue()

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_invalid_umask(self, mock_stdout, config):
        config.resolve_set("system.umask", None)
        with pytest.raises(SystemExit) as exc_info:
            cli = build_custom_config_cli(config)
        # Check that the error matches expectations
        assert exc_info.value.code == 1
        assert "Invalid integer" in mock_stdout.getvalue()

    def test_postcmd(self, config, cli):
        self.assert_standard_cli_attributes(cli)
        assert cli.history_file.name != "/dev/null"
        # Run postcmd
        line, stop = "this is the line", "asdf"
        assert cli.postcmd(stop, line) == stop
        assert cli.session["sequence_number"] == 1
        # Close the object to flush the write buffer
        cli.history_file.close()
        history_path = Path(config.config["logging"]["root_dir"], "cli_history.log")
        self.assert_substring_in_file_last_line(line, history_path)

    def test_empty_line(self, cli):
        assert cli.emptyline() is None

    @patch("sys.stdout", new_callable=io.StringIO)
    @pytest.mark.parametrize(
        # CLI Helper counts for each category are hardcode; update as necessary
        ["args", "helper_count"],
        [
            ["", 43],
            ["example_helpers", 4],
            ["example", 4],
            ["example_helpers te", 2],
            ["example_helpers test", 1],
        ],
    )
    def test_do_list(self, mock_stdout, args, helper_count, config, cli):
        cli.do_list(args)
        # Check the helpers
        helper_list = mock_stdout.getvalue().strip().split("\n")
        assert len(helper_list[1:]) == helper_count
        heading_modifier = f" containing '{args}'" if args else ""
        heading = f"FIREWHEEL Helper commands{heading_modifier}:"
        assert heading in mock_stdout.getvalue()
        # Close the object to flush the write buffer
        cli.history_file.close()
        history_path = Path(config.config["logging"]["root_dir"], "cli_history.log")
        self.assert_substring_in_file_last_line("list", history_path)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_author_no_args(self, mock_stdout, cli):
        args = ""
        cli.do_author(args)
        assert "Print the AUTHOR" in mock_stdout.getvalue()

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_author_normal(self, mock_stdout, config, cli):
        args = "example_helpers test"
        cli.do_author(args)
        assert mock_stdout.getvalue().strip() == "FIREWHEEL Team"

        # Close the object to flush the write buffer
        cli.history_file.close()
        history_path = Path(config.config["logging"]["root_dir"], "cli_history.log")
        self.assert_substring_in_file_last_line("author", history_path)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_author_invalid(self, mock_stdout, cli):
        args = "invalid"
        cli.do_author(args)
        assert mock_stdout.getvalue().strip() == f"{cli.cmd_not_found} {args}"

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_docs_normal(self, mock_stdout, config, cli, tmp_path):
        cli.do_docs(tmp_path)

        # Check to see if the files were created
        docs_paths = [
            tmp_path / "helper_docs.rst",
            tmp_path / "commands.rst",
        ]
        assert all(path.exists() for path in docs_paths)
        # Check to see if output was printed
        docs_strings = [
            "FIREWHEEL Helper documentation placed in",
            "FIREWHEEL Command documentation placed in",
        ]
        assert all(string in mock_stdout.getvalue() for string in docs_strings)

        # Close the object to flush the write buffer
        cli.history_file.close()
        history_path = Path(config.config["logging"]["root_dir"], "cli_history.log")
        self.assert_substring_in_file_last_line("docs", history_path)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_eof(self, mock_stdout, cli):
        assert cli.do_EOF("")
        assert mock_stdout.getvalue().strip() == ""

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_version(self, mock_stdout, cli):
        cli.do_version("")
        assert mock_stdout.getvalue().strip() == version("firewheel")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_exit(self, mock_stdout, cli):
        assert cli.do_exit("")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_quit(self, mock_stdout, cli):
        assert cli.do_quit("")

    @pytest.mark.parametrize(
        ["text", "count"],
        [
            ["example", 4],
            ["example_helpers s", 2],
        ],
    )
    def test_complete_author(self, text, cli, count):
        assert len(cli.complete_author(text, f"author {text}", None, None)) == count

    @pytest.mark.parametrize(
        ["text", "count", "values"],
        [
            ["example", 4, None],
            ["example_helpers s", 2, None],
            ["auth", 1, ["author"]],
        ],
    )
    def test_complete_help(self, text, count, values, cli):
        completion = cli.complete_help(text, f"help {text}", None, None)
        assert len(completion) == count
        if values:
            assert completion == values

    @patch("sys.stdout", new_callable=io.StringIO)
    @pytest.mark.parametrize(
        ["args", "outputs"],
        [
            [
                "",
                [
                    "FIREWHEEL Infrastructure Command Line Interpreter",
                    "Available CLI Helpers",
                ],
            ],
            ["author", ["Print the AUTHOR"]],
        ],
    )
    def test_base_do_help(self, mock_stdout, cli, args, outputs):
        cli.base_do_help(args)
        assert all(string in mock_stdout.getvalue().strip() for string in outputs)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_base_do_help_invalid(self, mock_stdout, cli):
        with pytest.raises(AttributeError):
            cli.base_do_help("invalid")

    @patch("sys.stdout", new_callable=io.StringIO)
    @pytest.mark.parametrize(
        ["args", "outputs"],
        [
            [
                "",
                [
                    "FIREWHEEL Infrastructure Command Line Interpreter",
                    "Available CLI Helpers",
                ],
            ],
            ["author", ["Print the AUTHOR"]],
            [
                "example_helpers",
                ["FIREWHEEL Helper commands containing 'example_helpers':"],
            ],
            [
                "example_helpers test",
                ["Use this file as a template for new Helpers."],
            ],
        ],
    )
    def test_do_help(self, mock_stdout, cli, args, outputs):
        cli.do_help(args)
        assert all(string in mock_stdout.getvalue().strip() for string in outputs)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_help_invalid(self, mock_stdout, cli):
        args = "invalid"
        cli.do_help(args)
        assert mock_stdout.getvalue().strip() == f"{cli.cmd_not_found} {args}"

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_history(self, mock_stdout, config, cli):
        cli.do_history("")
        output = "<Count>: <ID>:<Sequence Number> -- <command>"
        assert mock_stdout.getvalue().strip() == output

        # Close the object to flush the write buffer
        cli.history_file.close()
        history_path = Path(config.config["logging"]["root_dir"], "cli_history.log")
        self.assert_substring_in_file_last_line("history", history_path)

        cli.do_history("")
        output = "-- history"
        assert output in mock_stdout.getvalue()

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_history_experiment(self, mock_stdout, config, cli):
        cli.do_history("experiment")
        assert "No experiments" in mock_stdout.getvalue().strip()

        # Now actually write an experiment
        experiment = "experiment tests.vm_gen:1"
        cli.write_history(experiment)
        cli.do_history("experiment")
        assert f"firewheel {experiment}" in mock_stdout.getvalue()
        experiment_history_path = Path(
            config.config["logging"]["root_dir"], "experiment.history"
        )
        self.assert_substring_in_file_last_line(experiment, experiment_history_path)

    @patch("sys.stdout", new_callable=io.StringIO)
    @pytest.mark.parametrize(
        ["args", "return_code", "outputs"],
        [
            ["", -1, ["Runs the scripts found in the specified Helper file."]],
            ["example_helpers test", 0, ["Hello, World!"]],
        ],
    )
    def test_handle_run(self, mock_stdout, args, return_code, outputs, cli):
        assert cli.handle_run(args) == return_code
        assert all(output in mock_stdout.getvalue() for output in outputs)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_handle_run_invalid(self, mock_stdout, cli):
        with pytest.raises(HelperNotFoundError):
            cli.handle_run("invalid")

    @patch("sys.stdout", new_callable=io.StringIO)
    @pytest.mark.parametrize(
        ["args", "return_code", "outputs"],
        [
            ["", -1, ["Runs the scripts found in the specified Helper file."]],
            ["example_helpers test", 0, ["Hello, World!", "foo", "bar"]],
        ],
    )
    def test_do_run(slef, mock_stdout, args, return_code, outputs, cli):
        assert cli.do_run(args) == return_code
        assert all(output in mock_stdout.getvalue() for output in outputs)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_do_run_invalid(slef, mock_stdout, cli):
        assert cli.do_run("invalid") == 1

    @patch("sys.stdout", new_callable=io.StringIO)
    @pytest.mark.parametrize(
        ["args", "return_code", "outputs"],
        [
            ["", -1, ["Runs the scripts found in the specified Helper file."]],
            ["example_helpers test", 0, ["Hello, World!", "foo", "bar"]],
            # A repository is a Helper Group without an index file
            ["repository", 0, "Cannot run a Helper group."],
        ],
    )
    def test_default(self, mock_stdout, args, return_code, outputs, cli):
        assert cli.default(args) == return_code
        assert all(output in mock_stdout.getvalue() for output in outputs)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_default_invalid(self, mock_stdout, cli):
        assert cli.default("invalid") == 1
