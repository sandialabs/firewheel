import io
import os
import tempfile
import unittest
from enum import Enum
from unittest.mock import patch

from firewheel.cli.utils import (
    HelperNotFoundError,
    execution_issue_suffix,
    load_helper,
    parse_to_helper,
    process_helper_group,
    state_text,
    style_minimega_power_state,
    style_vm_resource_state,
)
from firewheel.cli.helper import Helper
from firewheel.cli.helper_group import HelperGroup


class CliUtilsTestCase(unittest.TestCase):
    def setUp(self):
        # Create a helper directory
        # pylint: disable=consider-using-with
        self.helper_root = tempfile.TemporaryDirectory()

        self.author = "Unittest"
        self.description = "Testing this case."

    def tearDown(self):
        # remove the temp directory
        self.helper_root.cleanup()

    def test_parse_to_helper_index(self):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f1 = "test1"
        run_f2 = "test2"

        # Add an index helper
        helper_index = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f1)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "index"), "w", encoding="utf8") as fhand:
            fhand.write(helper_index)

        # Add a regular helper
        helper_name = "normal"
        helper_regular = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "normal"), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create Helper dict
        index_helper_obj = Helper("index", index_path)
        helper_dict = {
            index_name: {
                helper_name: Helper(helper_name, index_path),
                "index": index_helper_obj,
            }
        }

        ret = parse_to_helper(index_name, helper_dict)
        self.assertEqual(ret[0], index_helper_obj)

    @patch("builtins.input", side_effect=["yes"])
    def test_parse_to_helper_index_args(self, _mock_input):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f1 = "test1"
        run_f2 = "test2"

        # Add an index helper
        helper_index = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f1)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "index"), "w", encoding="utf8") as fhand:
            fhand.write(helper_index)

        # Add a regular helper
        helper_name = "normal"
        helper_regular = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "normal"), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create HelperGroup dict
        helper_group = HelperGroup(index_path)
        index_helper_obj = Helper("index", index_path)
        helpers = {
            helper_name: Helper(helper_name, index_path),
            "index": index_helper_obj,
        }
        helper_group.helpers = helpers
        helper_dict = {index_name: helper_group}

        func_args = f"{index_name} invalid"
        ret = parse_to_helper(func_args, helper_dict)
        self.assertEqual(ret[0], index_helper_obj)

    @patch("builtins.input", side_effect=["no"])
    def test_parse_to_helper_index_args_no(self, _mock_input):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f1 = "test1"
        run_f2 = "test2"

        # Add an index helper
        helper_index = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f1)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "index"), "w", encoding="utf8") as fhand:
            fhand.write(helper_index)

        # Add a regular helper
        helper_name = "normal"
        helper_regular = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "normal"), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create HelperGroup dict
        helper_group = HelperGroup(index_path)
        index_helper_obj = Helper("index", index_path)
        helpers = {
            helper_name: Helper(helper_name, index_path),
            "index": index_helper_obj,
        }
        helper_group.helpers = helpers
        helper_dict = {index_name: helper_group}

        func_args = f"{index_name} invalid"
        with self.assertRaises(HelperNotFoundError):
            parse_to_helper(func_args, helper_dict)

    @patch("builtins.input", side_effect=["yes"])
    def test_parse_to_helper_no_index_args(self, _mock_input):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f2 = "test2"

        # Add a regular helper
        helper_name = "normal"
        helper_regular = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "normal"), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create Helper dict
        helper_group = HelperGroup(index_path)
        helpers = {
            helper_name: Helper(helper_name, index_path),
        }
        helper_group.helpers = helpers
        helper_dict = {index_name: helper_group}
        func_args = f"{index_name} invalid"
        with self.assertRaises(HelperNotFoundError):
            parse_to_helper(func_args, helper_dict)

    def test_parse_to_helper_args(self):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f2 = "test2"

        # Add a regular helper
        helper_name = "normal"
        helper_regular = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, helper_name), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create Helper dict
        valid_helper = Helper(helper_name, index_path)
        helper_dict = {helper_name: valid_helper}
        arg_list = ["arg1", "arg2"]
        func_args = f"{helper_name} {' '.join(arg_list)}"
        obj, args = parse_to_helper(func_args, helper_dict)
        self.assertEqual(obj, valid_helper)
        self.assertEqual(args, arg_list)

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_process_helper_group_invalid(self, mock_stdout):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f1 = "test1"
        run_f2 = "test2"

        # Add an index helper
        helper_index = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f1)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "index"), "w", encoding="utf8") as fhand:
            fhand.write(helper_index)

        # Add a regular helper
        helper_name = "normal"
        helper_regular = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "normal"), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create Helper dict
        index_helper_obj = Helper("index", index_path)
        helper_dict = {
            index_name: {
                helper_name: Helper(helper_name, index_path),
                "index": index_helper_obj,
            }
        }

        invalid_path = os.path.join(index_path, "invalid")
        process_helper_group(invalid_path, helper_dict)
        msg = "Helper path not found"
        self.assertIn(msg, mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_load_helper_invalid(self, mock_stdout):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f1 = "test1"
        run_f2 = "test2"

        # Add an index helper
        helper_index = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f1)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "index"), "w", encoding="utf8") as fhand:
            fhand.write(helper_index)

        # Add a regular helper
        helper_name = "invalid"
        helper_regular = str(
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f2)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, helper_name), "w", encoding="utf8") as fhand:
            fhand.write(helper_regular)

        # Create Helper dict
        index_helper_obj = Helper("index", index_path)
        helper_dict = {index_name: {"index": index_helper_obj}}

        load_helper(os.path.join(index_path, helper_name), helper_dict)
        msg_1 = "Malformed section encountered"
        msg_2 = "Continuing without Helper"
        self.assertIn(msg_1, mock_stdout.getvalue())
        self.assertIn(msg_2, mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_load_helper_invalid_path(self, mock_stdout):
        # Create a directory in the temp directory
        index_name = "testing"
        index_path = os.path.join(self.helper_root.name, index_name)
        os.makedirs(index_path)

        run_f1 = "test1"

        # Add an index helper
        helper_index = str(
            f"AUTHOR\n{self.author}\nDONE\n"
            f"DESCRIPTION\n{self.description}\nDONE\n"
            "RUN Shell ON control\n"
            f"touch {os.path.join(self.helper_root.name, run_f1)}\n"
            "DONE\n"
        )

        with open(os.path.join(index_path, "index"), "w", encoding="utf8") as fhand:
            fhand.write(helper_index)

        # Add a regular helper
        helper_name = "invalid"

        # Create Helper dict
        index_helper_obj = Helper("index", index_path)
        helper_dict = {index_name: {"index": index_helper_obj}}

        load_helper(os.path.join(index_path, helper_name), helper_dict)
        msg_1 = "Unexpected error while parsing Helper"
        msg_2 = "Continuing without Helper"
        self.assertIn(msg_1, mock_stdout.getvalue())
        self.assertIn(msg_2, mock_stdout.getvalue())

    def test_style_minimega_power_state_styles_expected_states(self):
        self.assertEqual(style_minimega_power_state("RUNNING"), "[green]RUNNING[/green]")
        self.assertEqual(style_minimega_power_state("running"), "[green]running[/green]")
        self.assertEqual(style_minimega_power_state("PAUSED"), "[yellow]PAUSED[/yellow]")
        self.assertEqual(style_minimega_power_state("error"), "[red]error[/red]")

    def test_style_minimega_power_state_leaves_other_values_unstyled(self):
        self.assertEqual(style_minimega_power_state("building"), "building")
        self.assertEqual(style_minimega_power_state("quit"), "quit")
        self.assertEqual(
            style_minimega_power_state("error: run failed"),
            "error: run failed",
        )

    def test_state_text_prefers_enum_values(self):
        class DemoState(Enum):
            READY = "ready"

        self.assertEqual(state_text(DemoState.READY), "ready")
        self.assertEqual(state_text("configured"), "configured")

    def test_execution_issue_suffix_handles_counts(self):
        self.assertEqual(execution_issue_suffix({}), "")
        self.assertEqual(
            execution_issue_suffix(
                {"has_execution_issues": True, "execution_issue_count": 1}
            ),
            " (execution issues)",
        )
        self.assertEqual(
            execution_issue_suffix(
                {"has_execution_issues": True, "execution_issue_count": 2}
            ),
            " (execution issues: 2)",
        )
        self.assertEqual(
            execution_issue_suffix(
                {"has_execution_issues": True, "execution_issue_count": 2},
                show_count=False,
            ),
            " (execution issues)",
        )

    def test_style_vm_resource_state_styles_expected_states(self):
        self.assertEqual(style_vm_resource_state("configured"), "[green]configured[/green]")
        self.assertEqual(style_vm_resource_state("testing"), "[cyan]testing[/cyan]")
        self.assertEqual(
            style_vm_resource_state("configuring"),
            "[yellow]configuring[/yellow]",
        )
        self.assertEqual(style_vm_resource_state("failed"), "[red]failed[/red]")
        self.assertEqual(
            style_vm_resource_state("status missing"),
            "[red]status missing[/red]",
        )
        self.assertEqual(
            style_vm_resource_state("configured (execution issues)"),
            "[yellow]configured (execution issues)[/yellow]",
        )
