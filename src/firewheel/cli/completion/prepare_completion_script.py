"""
Prepare the tab completion script using the template and configuration values.

This script uses values from the current FIREWHEEEL configuration to
populate the tab completion template script. This generator script is
always run on installation to prepare a new completion script for the
current configuration, and it may be run again at any point to generate
a new completion script that is is up-to-date with the current FIREWHEEL
configuration. Tab completion for Bash and Zsh is explicitly supported,
though the script may work with other shells permitting tab completion.

Examples:
    .. code-block:: bash

        $ python -m firewheel.cli.completion.prepare_completion_script
"""

from __future__ import annotations

import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from firewheel import FIREWHEEL_PACKAGE_DIR
from firewheel.config import config
from firewheel.cli.utils import cli_output_theme
from firewheel.cli.completion import COMPLETION_DIR, COMPLETION_SCRIPT_PATH


def populate_template(script_path: Path) -> None:
    """
    Substitute template placeholders to produce the completion script.

    Args:
        script_path (Path): The location where the completion
            script should be written.
    """
    # Define a templating environment
    template_environment = Environment(
        loader=FileSystemLoader(COMPLETION_DIR),
        autoescape=True,
        # Use an alternate style for comments since the normal Jinja2 comment
        # syntax ('{#') conflicts with Bash syntax
        comment_start_string="{##",
        comment_end_string="##}",
    )
    # Replace placeholders in the template with the provided values
    template = template_environment.get_template("completion-template.sh")
    script_content = template.render(
        fw_package_dir=FIREWHEEL_PACKAGE_DIR,
        fw_venv=config["python"]["venv"],
        python_bin=config["python"]["bin"],
    )
    # Write the script content to the completion script
    with script_path.open("w", encoding="utf-8") as script_file:
        script_file.write(script_content)


def display_instructions(script_path: Path) -> None:
    """
    Display instructions for using the script to set autocompletion.

    Args:
        script_path (Path): The location where the completion
            script should be written.
    """
    console = Console(theme=cli_output_theme)
    # Define the options for Bash and Zsh
    bash_command = (
        f"sudo cp {script_path} /usr/share/bash-completion/completions/firewheel"
    )
    zsh_command = f"sudo su -c 'echo \"source {script_path}\" >> /etc/zsh/zlogin'"
    instructions = (
        "\nTo enable tab-completion for the FIREWHEEL CLI, we recommend "
        "[bold]ONE[/bold] of the following:\n\n"
        "\t1. Add the completion script to the system default location\n"
        f"\t\tBash: [inline_code]{bash_command}[/inline_code]\n"
        f"\t\tZsh:  [inline_code]{zsh_command}[/inline_code]\n"
        "\t2. Source the tab completion script in your preferred `*rc` file\n"
        f"\t\t[inline_code]source {script_path}[/inline_code]\n"
    )
    console.print(instructions)


def print_completion_script_path() -> None:
    """Print the path to the tab-completion script."""
    print(COMPLETION_SCRIPT_PATH)


def main() -> None:
    """Prepare the completion script, provide setup instructions, and print its path."""

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Prepare the tab completion script.")
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="Print the path to the tab-completion script.",
    )

    args = parser.parse_args()

    if args.print_path:
        print_completion_script_path()
    else:
        populate_template(COMPLETION_SCRIPT_PATH)
        display_instructions(COMPLETION_SCRIPT_PATH)


if __name__ == "__main__":
    main()
