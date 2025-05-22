import io
import os
import copy
import tempfile
import unittest
import unittest.mock

import yaml

from firewheel.config import Config
from firewheel.cli.configure_firewheel import ConfigureFirewheel


class CliConfigureTestCase(unittest.TestCase):
    def setUp(self):
        # Create a helper directory
        # pylint: disable=consider-using-with
        self.tmp_dir = tempfile.TemporaryDirectory()

        # Change the CLI settings
        self.fw_config = Config(writable=True)
        self.old_config = copy.deepcopy(self.fw_config.get_config())

        # Build a CLI command interface
        self.cli = ConfigureFirewheel()

    def tearDown(self):
        # remove the temp directory
        self.tmp_dir.cleanup()

        # Fix the config
        self.fw_config.set_config(self.old_config)
        self.fw_config.write()

    def test_do_reset(self):
        # Set the log name and check that it is not the default value
        new_log_name = "new_cli.log"
        default_setting = self.old_config["logging"]["cli_log"]
        args = f"-s logging.cli_lgo {new_log_name}"
        self.cli.do_set(args)
        self.assertNotEqual(new_log_name, default_setting)
        # Reset the config file and check that the new value is the default
        self.cli.do_reset()

        new_config = Config().get_config()
        self.assertEqual(new_config["logging"]["cli_log"], default_setting)

    def test_do_set_single(self):
        new_log_name = "new_cli.log"
        old_setting = self.old_config["logging"]["cli_log"]
        self.assertNotEqual(old_setting, new_log_name)
        args = f"-s logging.cli_log {new_log_name}"
        self.cli.do_set(args)

        new_config = Config().get_config()

        self.assertEqual(new_config["logging"]["cli_log"], new_log_name)

    @unittest.mock.patch("sys.stderr", new_callable=io.StringIO)
    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_set_incorrect(self, mock_stdout, mock_stderr):
        args = "--bad-argument asdf"

        with self.assertRaises(SystemExit):
            self.cli.do_set(args)

        msg = "Set a FIREWHEEL configuration."
        self.assertIn(msg, mock_stdout.getvalue())
        self.assertIn("is required", mock_stderr.getvalue())

    def test_do_set_file(self):
        new_log_name = "new_cli.log"

        old_setting = self.old_config["logging"]["cli_log"]

        tmp_config = copy.deepcopy(self.fw_config.get_config())
        tmp_config["logging"]["cli_log"] = new_log_name

        self.assertNotEqual(old_setting, new_log_name)

        # Dump new config
        config_path = os.path.join(self.tmp_dir.name, "new_config.yaml")
        with open(config_path, "w", encoding="utf8") as fhand:
            yaml.safe_dump(tmp_config, fhand)

        args = f"-f {config_path}"
        self.cli.do_set(args)

        new_config = Config().get_config()
        self.assertEqual(new_config["logging"]["cli_log"], new_log_name)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_get_single(self, mock_stdout):
        setting = self.old_config["logging"]["cli_log"]
        args = "logging.cli_log"
        self.cli.do_get(args)

        self.assertEqual(setting, mock_stdout.getvalue().strip())

    @unittest.mock.patch("sys.stderr", new_callable=io.StringIO)
    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_get_incorrect(self, mock_stdout, mock_stderr):
        args = "--bad-argument asdf"

        with self.assertRaises(SystemExit):
            self.cli.do_get(args)

        msg = "Get a FIREWHEEL configuration."
        self.assertIn(msg, mock_stdout.getvalue())
        self.assertIn("unrecognized arguments", mock_stderr.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_get_no_setting(self, mock_stdout):
        args = ""

        self.cli.do_get(args)

        msg = "Get a FIREWHEEL configuration."
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_get_all(self, mock_stdout):
        args = "-a"
        self.cli.do_get(args)

        test_config = yaml.safe_load(mock_stdout.getvalue())

        self.assertEqual(self.old_config, test_config)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_edit_param_invalid(self, mock_stdout):
        args = "-e asdf"
        self.cli.do_edit(args)

        msg = "Error: Failed to open FIREWHEEL configuration with"
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch.dict(os.environ, {'EDITOR': '', 'VISUAL': ''})
    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_edit_none(self, mock_stdout):
        args = ""
        self.cli.do_edit(args)

        msg = "Edit the FIREWHEEL configuration"
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_emptyline(self, mock_stdout):
        # Test the configuration from initialization
        cli = ConfigureFirewheel()
        cli.emptyline()

        msg = "Get or set the FIREWHEEL configuration"
        self.assertIn(msg, mock_stdout.getvalue())

        msg = "A sub-command is required"
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help_reset(self, mock_stdout):
        self.cli.help_reset()

        msg = "Reset the FIREWHEEL configuration to the default values."
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help_get(self, mock_stdout):
        self.cli.help_get()

        msg = "Get a FIREWHEEL configuration."
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help_set(self, mock_stdout):
        self.cli.help_set()

        msg = "Set a FIREWHEEL configuration."
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help_edit(self, mock_stdout):
        self.cli.help_edit()

        msg = "Edit the FIREWHEEL configuration"
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help_help(self, mock_stdout):
        self.cli.help_help()

        msg = "Prints help for the different sub-commands"
        self.assertIn(msg, mock_stdout.getvalue())
