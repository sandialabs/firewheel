import io
import os
import copy
import argparse
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

    def test_do_set_single_string(self):
        new_log_name = "new_cli.log"
        old_setting = self.old_config["logging"]["cli_log"]
        self.assertNotEqual(old_setting, new_log_name)
        args = f"-s logging.cli_log {new_log_name}"
        self.cli.do_set(args)

        new_config = Config().get_config()

        self.assertEqual(new_config["logging"]["cli_log"], new_log_name)

    def test_do_set_single_list_one_element(self):
        new_nodes_string = "test_node"
        old_setting = self.old_config["cluster"]["compute"]
        self.assertNotEqual(old_setting, new_nodes_string)
        args = f"-s cluster.compute {new_nodes_string}"
        self.cli.do_set(args)

        new_config = Config().get_config()

        self.assertEqual(new_config["cluster"]["compute"], [new_nodes_string])

    def test_do_set_single_list_one_element_with_space(self):
        new_nodes_string = "test node"
        old_setting = self.old_config["cluster"]["compute"]
        self.assertNotEqual(old_setting, new_nodes_string)
        args = f"-s cluster.compute '{new_nodes_string}'"
        self.cli.do_set(args)

        new_config = Config().get_config()

        self.assertEqual(new_config["cluster"]["compute"], [new_nodes_string])

    def test_do_set_single_list_multiple_elements(self):
        new_nodes_string = "test_node0,test_node1"
        old_setting = self.old_config["cluster"]["compute"]
        self.assertNotEqual(old_setting, new_nodes_string)
        args = f"-s cluster.compute {new_nodes_string}"
        self.cli.do_set(args)

        new_config = Config().get_config()

        self.assertEqual(new_config["cluster"]["compute"], [new_nodes_string])

    def test_do_set_single_list_multiple_elements_space(self):
        new_nodes_string = "test_node0 test_node1"
        old_setting = self.old_config["cluster"]["compute"]
        self.assertNotEqual(old_setting, new_nodes_string)
        args = f"-s cluster.compute {new_nodes_string}"
        self.cli.do_set(args)

        new_config = Config().get_config()

        self.assertEqual(new_config["cluster"]["compute"], new_nodes_string.split(" "))

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

    @unittest.mock.patch("firewheel.cli.configure_firewheel.Config")
    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_path(self, mock_stdout, mock_config_cls):
        mock_config_path = "/path/to/config"
        mock_config_cls().config_path = mock_config_path

        args = ""
        self.cli.do_path(args)

        self.assertIn(mock_config_path, mock_stdout.getvalue())

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_do_edit_param_invalid(self, mock_stdout):
        args = "-e asdf"
        self.cli.do_edit(args)

        msg = "Error: Failed to open FIREWHEEL configuration with"
        self.assertIn(msg, mock_stdout.getvalue())

    @unittest.mock.patch.dict(os.environ, {"EDITOR": "", "VISUAL": ""})
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

    def test_valid_json(self):
        json_string = '{"key": "value", "number": 123}'
        expected = {"key": "value", "number": 123}
        result = self.cli._argparse_check_json_type(json_string)
        self.assertEqual(result, expected)

    def test_empty_json(self):
        json_string = "{}"
        expected = {}
        result = self.cli._argparse_check_json_type(json_string)
        self.assertEqual(result, expected)

    def test_invalid_json(self):
        invalid_json_cases = [
            '{"key": "value", "number": 123',  # Missing brace
            '{"key": "value", "number": "123" "extra": "value"}',  # Missing comma
            '{"key": "value", "number": [1, 2, 3,}',  # Trailing comma
            '{key: "value"}',  # Missing quotes
            '["value1", "value2",]',  # Trailing comma
            "{'key': 'value'}",  # Single quotes
        ]

        for json_string in invalid_json_cases:
            with self.subTest(json_string=json_string):
                with self.assertRaises(argparse.ArgumentTypeError) as context:
                    self.cli._argparse_check_json_type(json_string)
                self.assertIn("Invalid JSON string", str(context.exception))

    def test_json_with_nested_structure(self):
        json_string = '{"outer": {"inner": "value"}}'
        expected = {"outer": {"inner": "value"}}
        result = self.cli._argparse_check_json_type(json_string)
        self.assertEqual(result, expected)

    def test_json_with_array(self):
        json_string = '{"array": [1, 2, 3]}'
        expected = {"array": [1, 2, 3]}
        result = self.cli._argparse_check_json_type(json_string)
        self.assertEqual(result, expected)

    @unittest.mock.patch("firewheel.cli.configure_firewheel.Config")
    def test_do_set_with_json(self, mock_config_cls):
        mock_config_cls().get_config.return_value = {"key": "value"}
        mock_config_cls().set_config = unittest.mock.Mock()
        mock_config_cls().write = unittest.mock.Mock()

        json_input = '{"key": "new_value", "nested": {"inner_key": "inner_value"}}'
        args = f"--json '{json_input}'"

        self.cli.do_set(args)

        expected_config = {"key": "new_value", "nested": {"inner_key": "inner_value"}}
        mock_config_cls().set_config.assert_called_once_with(expected_config)
        mock_config_cls().write.assert_called_once()

    @unittest.mock.patch("firewheel.cli.configure_firewheel.Config")
    def test_do_set_with_invalid_json(self, mock_config_cls):
        json_input = '{"key": "value", "nested": {"inner_key": "inner_value"'
        args = f'--json "{json_input}"'

        with self.assertRaises(SystemExit):
            self.cli.do_set(args)

    @unittest.mock.patch("firewheel.cli.configure_firewheel.Config")
    def test_do_set_with_empty_json(self, mock_config_cls):
        mock_config_cls().get_config.return_value = {"key": "value"}
        mock_config_cls().set_config = unittest.mock.Mock()
        mock_config_cls().write = unittest.mock.Mock()

        json_input = "{}"
        args = f'--json "{json_input}"'  # Create a string that simulates command-line input

        self.cli.do_set(args)  # Pass the string instead of a Mock

        expected_config = {"key": "value"}  # No changes should be made
        mock_config_cls().set_config.assert_called_once_with(expected_config)
        mock_config_cls().write.assert_called_once()

    def test_update_existing_key(self):
        original = {"key": "value", "nested": {"inner_key": "inner_value"}}
        updates = {"key": "new_value"}
        expected = {"key": "new_value", "nested": {"inner_key": "inner_value"}}
        result = self.cli._update_nested_dict(original, updates)
        self.assertEqual(result, expected)

    def test_update_nested_key(self):
        original = {"nested": {"inner_key": "inner_value"}}
        updates = {"nested": {"inner_key": "new_inner_value"}}
        expected = {"nested": {"inner_key": "new_inner_value"}}
        result = self.cli._update_nested_dict(original, updates)
        self.assertEqual(result, expected)

    def test_add_new_key(self):
        original = {"key": "value"}
        updates = {"new_key": "new_value"}
        expected = {"key": "value", "new_key": "new_value"}
        result = self.cli._update_nested_dict(original, updates)
        self.assertEqual(result, expected)

    def test_update_with_non_nested_key(self):
        original = {"key": "value"}
        updates = {"key": {"sub_key": "sub_value"}}
        expected = {"key": {"sub_key": "sub_value"}}
        result = self.cli._update_nested_dict(original, updates)
        self.assertEqual(result, expected)

    def test_update_with_nested_and_non_nested_keys(self):
        original = {"key": "value", "nested": {"inner_key": "inner_value"}}
        updates = {
            "key": "new_value",
            "nested": {"inner_key": "new_inner_value"},
            "new_key": "new_value",
        }
        expected = {
            "key": "new_value",
            "nested": {"inner_key": "new_inner_value"},
            "new_key": "new_value",
        }
        result = self.cli._update_nested_dict(original, updates)
        self.assertEqual(result, expected)
