import os
import sys
import shlex
from pathlib import Path

from rich.table import Table
from rich.theme import Theme

from firewheel.cli.helper import Helper
from firewheel.cli.section import MalformedSectionError
from firewheel.cli.helper_group import HelperGroup

helpers_path = Path(__file__).parent / "helpers"

# Add theme for consistent CLI output formatting
cli_theme_styles = {
    "error": "bold red",
    "inline_code": "bold",
}
cli_output_theme = Theme(cli_theme_styles)


class RichDefaultTable(Table):
    """
    A the default table format for FIREWHEEL outputs.

    This is the specification for a default FIREWHEEL table displayed
    via the CLI. It is a subclass of the :py:class:`rich.table.Table`
    with specific attributes set to default values for FIREWHEEL.
    """

    def __init__(self, *args, **kwargs):
        """
        Build a default table for FIREWHEEL CLI output.

        Args:
            *args: Arguments passed to the :py:class:`rich.table.Table`
                constructor.
            **kwargs: Keyword arguments passed to the :py:class:`rich.table.Table`
                constructor.
        """
        # Specify table defaults (only used unless otherwise specified)
        default_kwargs = {
            "header_style": "bold magenta",
            "caption_style": "dim",
            "show_lines": True,
        }
        for key, value in default_kwargs.items():
            kwargs.setdefault(key, value)
        super().__init__(*args, **kwargs)


class HelperNotFoundError(Exception):
    """
    Error thrown when we cannot locate a referenced Helper.
    """


class InvalidHelperTypeError(Exception):
    """
    Error thrown when we find a Helper group instead of a Helper.
    """


def parse_to_helper(args, helpers_dict):
    """
    Retrieve a Helper object for the given command-line args.

    Args:
        args (str): Command-line args specifying a Helper and its arguments.
        helpers_dict (dict): A dictionary listing all the available Helpers.

    Returns:
        tuple: Containing the Helper object that was found and the list of
        arguments for the Helper.

    Raises:
        HelperNotFoundError: If the Helper cannot be located.
        InvalidHelperTypeError: If a Helper group was specified rather than a Helper.
    """
    # Check for the Helper name in the Helpers dict.
    args = shlex.split(args)
    if args[0] not in helpers_dict:
        raise HelperNotFoundError("Unable to find Helper")
    # Check the type of the Helper entry.
    # It may be a string (direct Helper) or dictionary (Helper group)
    # If it's a dict, keep resolving down our split args string until we
    # get a direct Helper.
    args_index = 0
    helper_obj = helpers_dict[args[args_index]]
    while not isinstance(helper_obj, Helper):
        args_index += 1
        if args_index >= len(args):
            # Also try to run the index Helper here.
            if "index" in helper_obj:
                helper_obj = helper_obj["index"]
                break

            raise InvalidHelperTypeError("Specified a Helper group.")

        try:
            # If we've found the end of the valid Helper chain,
            # we may actually want an "index" Helper--try that.
            # This may result in the same key error as if we didn't
            # try index, which gives Helper not found and is the desired
            # behavior.
            if args[args_index] not in helper_obj:
                question = str(
                    f"Cannot find Helper `{' '.join(args)}`. "
                    f"Did you want to run `{helper_obj.name.replace('/', ' ')} index`"
                    f" and use`{' '.join(args[args_index:])}` as an argument? (y/n): "
                )
                reply = input(question).lower()
                if reply[:1] == "y":
                    helper_obj = helper_obj["index"]
                else:
                    raise HelperNotFoundError("Unable to find Helper")
            else:
                helper_obj = helper_obj[args[args_index]]
        except KeyError as exp:
            # Make sure we treat an invalid Helper here the same as we
            # would elsewhere.
            raise HelperNotFoundError(exp) from exp

    arg_list = None
    if len(args) > (args_index + 1):
        arg_list = args[(args_index + 1) :]

    return (helper_obj, arg_list)


def load_helper(filename, helper_dict):
    """
    Identify the Helper path, create Helper object, and add it to the `working_dict`.

    Args:
        filename (str): The filename of the Helper to load.
        helper_dict (dict): A dictionary listing all the existing Helpers.
    """
    try:
        if not os.path.basename(filename).startswith("."):
            # We found a Helper we want to add to our inventory.
            # We need to make sure we understand any groups it may
            # belong to.
            helper_name = os.path.basename(filename)
            rel_path = os.path.relpath(filename, helpers_path)

            # If there's any groups in the path to our Helper.
            if rel_path != helper_name:
                groups = os.path.dirname(rel_path).split(os.sep)
            else:
                groups = []
            # Descend the dictionary-of-dictionaries for the groups
            # we found.
            working_dict = helper_dict
            # Start at 1 so the range works right.
            index = 1
            for group in groups:
                if group not in working_dict:
                    working_dict[group] = HelperGroup(os.path.join(*groups[0:index]))
                working_dict = working_dict[group]
                index += 1
            # Add the Helper at the correct depth.
            working_dict[helper_name] = Helper(rel_path, helpers_path)
    except MalformedSectionError as exp:
        print(f"Warning: Malformed section encountered in Helper {filename}: {exp}")
        print(f"Continuing without Helper {filename}.")
    except Exception as exp:  # noqa: BLE001
        print(f"Warning: Unexpected error while parsing Helper {filename}: {exp}")
        print(f"Continuing without Helper {filename}.")


def process_helper_group(directory_name, helper_dict):
    """
    Identify the path of a Helper group recursively.

    This method then calls `load_helper` to load the Helper with the correct path.
    The Helpers are added to the helper_dict.

    Args:
        directory_name (str): The name of the directory in which the actual Helper files
            are located.
        helper_dict (dict): A dictionary listing all the existing Helpers.
    """
    try:
        for filename in os.listdir(directory_name):
            real_path = os.path.join(os.path.abspath(directory_name), filename)
            if os.path.isdir(real_path):
                process_helper_group(real_path, helper_dict)
            else:
                load_helper(real_path, helper_dict)
    except FileNotFoundError:
        print(
            "Warning: Helper path not found, continuing without loading",
            file=sys.stderr,
        )


def build_helper_dict():
    """
    Builds a dictionary of Helper objects.

    This method uses :py:meth:`process_helper_group` and passes in the directory
    of the CLI Helpers.

    Returns:
        dictionary: A dictionary of Helper and HelperGroup objects.
    """
    helpers = {}
    process_helper_group(helpers_path, helpers)
    return helpers


def strip_markup_chrs(message):
    """
    Strips some of the RST-specific markup from the message before returning it.

    This helps with documentation readability when calling `firewheel help <Helper>`.

    Args:
        message (str): The string from which to strip characters.

    Returns:
        str: The updated message.
    """
    return message.translate(str.maketrans("", "", "*`"))
