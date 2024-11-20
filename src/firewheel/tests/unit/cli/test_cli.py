import io
import os
import copy
import uuid
import tempfile
import unittest
import unittest.mock
from importlib.metadata import version

from firewheel.config import Config
from firewheel.cli.utils import HelperNotFoundError
from firewheel.cli.firewheel_cli import FirewheelCLI


class CliTestCase(unittest.TestCase):
    def setUp(self):
        # Create a helper directory
        # pylint: disable=consider-using-with
        self.tmp_dir = tempfile.TemporaryDirectory()

        # Change the CLI settings
        self.fw_config = Config(writable=True)
        self.old_config = copy.deepcopy(self.fw_config.get_config())

    def tearDown(self):
        # remove the temp directory
        self.tmp_dir.cleanup()

        # Fix the config
        self.fw_config.set_config(self.old_config)
        self.fw_config.write()

    def test_normal_setup(self):
        cli = FirewheelCLI()

        # Check that certain attributes have been created
        self.assertIsNotNone(cli.log)
        self.assertEqual(cli.session["sequence_number"], 0)
        self.assertIsInstance(cli.session["id"], uuid.UUID)
        self.assertNotEqual(cli.history_file.name, "/dev/null")

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_no_history_file(self, mock_stdout):
        self.fw_config.resolve_set("logging.root_dir", 1234)
        self.fw_config.write()

        cli = FirewheelCLI()

        # Check that certain attributes have been created
        self.assertIsNotNone(cli.log)
        self.assertEqual(cli.session["sequence_number"], 0)
        self.assertIsInstance(cli.session["id"], uuid.UUID)
        self.assertEqual(cli.history_file.name, "/dev/null")
        self.assertIn("Continuing", mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_no_exp_history_file(self, mock_stdout):
        self.fw_config.resolve_set("logging.root_dir", 1234)
        self.fw_config.write()

        cli = FirewheelCLI()

        # Check that certain attributes have been created
        self.assertIsNotNone(cli.log)
        self.assertEqual(cli.session["sequence_number"], 0)
        self.assertIsInstance(cli.session["id"], uuid.UUID)
        self.assertEqual(cli.history_file.name, "/dev/null")
        self.assertIn("experiment history", mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_invalid_umask(self, mock_stdout):
        self.fw_config.resolve_set("system.umask", None)
        self.fw_config.write()

        with self.assertRaises(SystemExit) as exp:
            FirewheelCLI()

        self.assertEqual(exp.exception.code, 1)
        self.assertIn("Invalid integer", mock_stdout.getvalue())

    def test_postcmd(self):
        cli = FirewheelCLI()

        # Check that certain attributes have been created
        self.assertIsNotNone(cli.log)
        self.assertEqual(cli.session["sequence_number"], 0)
        self.assertIsInstance(cli.session["id"], uuid.UUID)
        self.assertNotEqual(cli.history_file.name, "/dev/null")

        # Run postcmd
        line = "this is the line"
        stop = "asdf"
        ret = cli.postcmd(stop, line)

        self.assertEqual(ret, stop)
        self.assertEqual(cli.session["sequence_number"], 1)

        # Close the object to flush the write buffer
        cli.history_file.close()

        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")

        with open(hist_file, "r", encoding="utf8") as f_hand:
            last_line = f_hand.readlines()[-1]

        self.assertIn(line, last_line)

    def test_emptyline(self):
        cli = FirewheelCLI()

        # Run emptyline
        self.assertIsNone(cli.emptyline())

    # Mocking based on https://stackoverflow.com/a/46307456
    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_list(self, mock_stdout):
        cli = FirewheelCLI()

        args = ""
        cli.do_list(args)

        helper_list = mock_stdout.getvalue().strip().split("\n")
        # This verifies that the number of CLI Helpers
        # is exactly 43. This will need to be fixed if
        # Helpers are added/removed.
        self.assertEqual(len(helper_list[1:]), 43)

        heading = "FIREWHEEL Helper commands:"
        self.assertIn(heading, mock_stdout.getvalue())

        # Close the object to flush the write buffer
        cli.history_file.flush()

        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")
        with open(hist_file, "r", encoding="utf8") as f_hand:
            last_line = f_hand.readlines()[-1]

        self.assertIn("list", last_line)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_list_args(self, mock_stdout):
        cli = FirewheelCLI()

        args = "example_helpers"
        cli.do_list(args)

        helper_list = mock_stdout.getvalue().strip().split("\n")
        # This verifies that the number of `example_helpers`
        # CLI Helpers is exactly 4.
        # This will need to be fixed if Helpers are added/removed.
        self.assertEqual(len(helper_list[1:]), 4)
        heading = f"FIREWHEEL Helper commands containing '{args}':"
        self.assertIn(heading, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_list_args_partial(self, mock_stdout):
        cli = FirewheelCLI()

        args = "example"
        cli.do_list(args)

        helper_list = mock_stdout.getvalue().strip().split("\n")
        # This verifies that the number of `example_helpers`
        # CLI Helpers is exactly 4.
        # This will need to be fixed if Helpers are added/removed.
        self.assertEqual(len(helper_list[1:]), 4)
        heading = f"FIREWHEEL Helper commands containing '{args}':"
        self.assertIn(heading, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_list_args_partial_sub(self, mock_stdout):
        cli = FirewheelCLI()
        args = "example_helpers te"
        cli.do_list(args)

        helper_list = mock_stdout.getvalue().strip().split("\n")
        # This verifies that the number of `example_helpers`
        # CLI Helpers is exactly 2.
        # This will need to be fixed if Helpers are added/removed.
        self.assertEqual(len(helper_list[1:]), 2)

        heading = f"FIREWHEEL Helper commands containing '{args}':"
        self.assertIn(heading, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_list_single_helper(self, mock_stdout):
        cli = FirewheelCLI()

        args = "example_helpers test"
        cli.do_list(args)

        helper_list = mock_stdout.getvalue().strip().split("\n")
        self.assertEqual(len(helper_list[1:]), 1)

        heading = f"FIREWHEEL Helper commands containing '{args}':"
        self.assertIn(heading, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_author_no_args(self, mock_stdout):
        cli = FirewheelCLI()

        args = ""
        cli.do_author(args)

        self.assertIn("Print the AUTHOR", mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_author_invalid(self, mock_stdout):
        cli = FirewheelCLI()

        args = "invalid"
        cli.do_author(args)

        self.assertEqual(mock_stdout.getvalue().strip(), f"{cli.cmd_not_found} {args}")

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_author_normal(self, mock_stdout):
        cli = FirewheelCLI()

        args = "example_helpers test"
        cli.do_author(args)

        self.assertEqual(mock_stdout.getvalue().strip(), "FIREWHEEL Team")

        # Close the object to flush the write buffer
        cli.history_file.flush()

        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")
        with open(hist_file, "r", encoding="utf8") as f_hand:
            last_line = f_hand.readlines()[-1]

        self.assertIn("author", last_line)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_docs_normal(self, mock_stdout):
        cli = FirewheelCLI()

        cli.do_docs(self.tmp_dir.name)

        # Check to see if the files were created
        helper_path = os.path.join(self.tmp_dir.name, "helper_docs.rst")
        cmd_path = os.path.join(self.tmp_dir.name, "commands.rst")
        self.assertTrue(os.path.exists(helper_path))
        self.assertTrue(os.path.exists(cmd_path))

        # Check to see if output was printed
        helper_str = "FIREWHEEL Helper documentation placed in"
        cmd_str = "FIREWHEEL Command documentation placed in"
        self.assertIn(helper_str, mock_stdout.getvalue())
        self.assertIn(cmd_str, mock_stdout.getvalue())

        # Close the object to flush the write buffer
        cli.history_file.flush()

        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")
        with open(hist_file, "r", encoding="utf8") as f_hand:
            last_line = f_hand.readlines()[-1]

        self.assertIn("docs", last_line)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_eof(self, mock_stdout):
        cli = FirewheelCLI()

        args = ""
        self.assertTrue(cli.do_EOF(args))

        self.assertEqual(mock_stdout.getvalue().strip(), "")

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_version(self, mock_stdout):
        cli = FirewheelCLI()
        args = ""
        cli.do_version(args)

        self.assertEqual(mock_stdout.getvalue().strip(), version("firewheel"))

    def test_do_exit(self):
        cli = FirewheelCLI()
        args = ""
        self.assertTrue(cli.do_exit(args))

    def test_do_quit(self):
        cli = FirewheelCLI()
        args = ""
        self.assertTrue(cli.do_quit(args))

    def test_complete_author(self):
        cli = FirewheelCLI()
        text = "example"
        line = f"author {text}"
        ret = cli.complete_author(text, line, None, None)
        self.assertEqual(len(ret), 4)

        text = "example_helpers s"
        line = f"author {text}"
        ret = cli.complete_author(text, line, None, None)
        self.assertEqual(len(ret), 2)

    def test_complete_run(self):
        cli = FirewheelCLI()
        text = "example"
        line = f"run {text}"
        ret = cli.complete_run(text, line, None, None)
        self.assertEqual(len(ret), 4)

        text = "example_helpers s"
        line = f"run {text}"
        ret = cli.complete_run(text, line, None, None)
        self.assertEqual(len(ret), 2)

    def test_complete_help(self):
        cli = FirewheelCLI()
        text = "example"
        line = f"help {text}"
        ret = cli.complete_help(text, line, None, None)
        self.assertEqual(len(ret), 4)

        text = "example_helpers s"
        line = f"help {text}"
        ret = cli.complete_help(text, line, None, None)
        self.assertEqual(len(ret), 2)

        text = "auth"
        line = f"help {text}"
        ret = cli.complete_help(text, line, None, None)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0], "author")

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_base_do_help(self, mock_stdout):
        cli = FirewheelCLI()
        args = ""
        cli.base_do_help(args)

        self.assertIn(
            "FIREWHEEL Infrastructure Command Line Interpreter",
            mock_stdout.getvalue().strip(),
        )

        helpers = "Available CLI Helpers"
        self.assertIn(helpers, mock_stdout.getvalue().strip())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_base_do_help_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = "author"
        cli.base_do_help(args)

        self.assertIn("Print the AUTHOR", mock_stdout.getvalue())

        args = "invalid"
        with self.assertRaises(AttributeError):
            cli.base_do_help(args)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_help(self, mock_stdout):
        cli = FirewheelCLI()
        args = ""
        cli.do_help(args)

        self.assertIn(
            "FIREWHEEL Infrastructure Command Line Interpreter",
            mock_stdout.getvalue().strip(),
        )

        helpers = "Available CLI Helpers"
        self.assertIn(helpers, mock_stdout.getvalue().strip())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_help_args_cmd(self, mock_stdout):
        cli = FirewheelCLI()
        args = "author"
        cli.do_help(args)
        self.assertIn("Print the AUTHOR", mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_help_args_invalid(self, mock_stdout):
        cli = FirewheelCLI()
        args = "invalid"
        cli.do_help(args)
        self.assertEqual(mock_stdout.getvalue().strip(), f"{cli.cmd_not_found} {args}")

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_help_args_helper_group(self, mock_stdout):
        cli = FirewheelCLI()
        args = "example_helpers"
        cli.do_help(args)
        heading = f"FIREWHEEL Helper commands containing '{args}':"
        self.assertIn(heading, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_help_args_helper(self, mock_stdout):
        cli = FirewheelCLI()
        args = "example_helpers test"
        cli.do_help(args)
        description_str = "Use this file as a template for new Helpers."
        self.assertIn(description_str, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_history(self, mock_stdout):
        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")
        # Remove the current history file to ensure it is blank
        os.remove(hist_file)

        cli = FirewheelCLI()

        cli.do_history("")
        output = "<Count>: <ID>:<Sequence Number> -- <command>"
        self.assertEqual(mock_stdout.getvalue().strip(), output)

        # Close the object to flush the write buffer
        cli.history_file.flush()

        with open(hist_file, "r", encoding="utf8") as f_hand:
            last_line = f_hand.readlines()[-1]

        self.assertIn("history", last_line)

        cli.do_history("")
        output = "-- history"
        self.assertIn(output, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_history_exp(self, mock_stdout):
        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")
        exp_hist_file = os.path.join(
            config["logging"]["root_dir"], "experiment.history"
        )

        # Remove the current history file to ensure it is blank
        os.remove(hist_file)
        os.remove(exp_hist_file)

        cli = FirewheelCLI()

        experiment = "experiment tests.vm_gen:1"

        cli.do_history("experiment")
        output = "No experiments"
        self.assertIn(output, mock_stdout.getvalue().strip())

        # Now actually write an experiment
        experiment = "experiment tests.vm_gen:1"
        cli.write_history(experiment)

        cli.do_history("experiment")
        output = f"firewheel {experiment}"
        self.assertIn(output, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_exp_history(self, mock_stdout):
        config = Config().get_config()
        hist_file = os.path.join(config["logging"]["root_dir"], "cli_history.log")
        exp_hist_file = os.path.join(
            config["logging"]["root_dir"], "experiment.history"
        )

        # Remove the current history file to ensure it is blank
        os.remove(hist_file)
        os.remove(exp_hist_file)

        cli = FirewheelCLI()
        experiment = "experiment tests.vm_gen:1"
        cli.write_history(experiment)

        # Close the object to flush the write buffer
        cli.history_exp_file.flush()

        with open(exp_hist_file, "r", encoding="utf8") as f_hand:
            last_line = f_hand.readlines()[-1]

        self.assertIn(f"firewheel {experiment}", last_line)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_handle_run_no_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = ""
        self.assertEqual(-1, cli.handle_run(args))

        output = "Runs the scripts found in the specified Helper file."
        self.assertIn(output, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_handle_run_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = "example_helpers test"
        cli.handle_run(args)

        self.assertIn("Hello, World!", mock_stdout.getvalue())

        args = "invalid"
        with self.assertRaises(HelperNotFoundError):
            cli.handle_run(args)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_run_no_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = ""
        self.assertEqual(-1, cli.do_run(args))

        output = "Runs the scripts found in the specified Helper file."
        self.assertIn(output, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_run_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = "example_helpers test"
        self.assertEqual(0, cli.do_run(args))

        self.assertIn("Hello, World!", mock_stdout.getvalue())
        self.assertIn("foo", mock_stdout.getvalue())
        self.assertIn("bar", mock_stdout.getvalue())

        args = "invalid"
        self.assertEqual(1, cli.do_run(args))

        # Repository is a Helper Group without an index file
        args = "repository"
        cli.do_run(args)
        self.assertIn("Cannot run a Helper group.", mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_default_no_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = ""
        self.assertEqual(-1, cli.default(args))

        output = "Runs the scripts found in the specified Helper file."
        self.assertIn(output, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_default_args(self, mock_stdout):
        cli = FirewheelCLI()
        args = "example_helpers test"
        self.assertEqual(0, cli.default(args))

        self.assertIn("Hello, World!", mock_stdout.getvalue())
        self.assertIn("foo", mock_stdout.getvalue())
        self.assertIn("bar", mock_stdout.getvalue())

        args = "invalid"
        self.assertEqual(1, cli.default(args))

        # Repository is a Helper Group without an index file
        args = "repository"
        cli.default(args)
        self.assertIn("Cannot run a Helper group.", mock_stdout.getvalue())
