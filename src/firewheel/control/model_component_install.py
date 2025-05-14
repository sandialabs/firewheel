import sys
import stat
import subprocess
from pathlib import Path

import ansible_runner
from rich.prompt import PromptBase
from rich.syntax import Syntax
from rich.console import Console

from firewheel.config import config
from firewheel.lib.log import Log


class InstallPrompt(PromptBase[str]):
    """A prompt that has a custom error message."""

    response_type = str
    msg = (
        "[prompt.invalid.choice]Please select one of the available options:\n"
        "y - yes, install execute this script\n"
        "n - no, do not execute this script\n"
        "v - view, see the script text\n"
        "vc - view color, see the script text with color support, must use "
        "a system pager which supports this behavior (e.g. PAGER='less -R')\n"
        "q - quit, exit immediately\n"
    )
    illegal_choice_message = msg
    validate_error_message = msg


class ModelComponentInstall:
    """
    Some Model Components may provide an additional installation details
    which can be executed to perform other setup steps (e.g. installing an extra python package
    or downloading an external VM resource).
    This takes the form of either a ``INSTALL`` directory with a ``vars.yml`` and a ``tasks.yml``
    that are Ansible tasks which can be executed.
    Alternatively, it can be a single ``INSTALL`` script that can be can be any executable file
    type as defined by a `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_ line.

    .. warning::

        The execution of Model Component ``INSTALL`` scripts can be a **DANGEROUS** operation.
        Please ensure that you **fully trust** the repository developer prior to executing
        these scripts.

    .. seealso::

        See :ref:`mc_install` for more information on ``INSTALL`` scripts.

    When installing a Model Component, users will have a variety of choices to select:

        - ``y`` - yes, install execute this script
        - ``n`` - no, do not execute this script
        - ``v`` - view, see the script text
        - ``vc`` - view color, see the script text with color support, must use a system pager
          which supports this behavior (e.g. ``PAGER='less -R'``)
        - ``q`` - quit, exit immediately

    """

    def __init__(self, mc=None):
        """
        Initialize the object.

        Args:
            mc (ModelComponent): The :py:class:`ModelComponent` to install.

        Raises:
            ValueError: Caused if a user didn't specify ``mc``.
        """
        if mc is None:
            raise ValueError("Must specify a Model Component.")

        self.mc = mc
        self.log = Log(name="ModelComponentInstall").log

    def install_mc(self, name, install_path):
        """
        Execute a given Model Component's ``INSTALL`` script.

        Args:
            name (str): The name of the Model Component.
            install_path (pathlib.Path): The path of the ``INSTALL`` file.

        Returns:
            bool: True if the MC was installed successfully (or it was already
            installed), False otherwise
        """
        console = Console()
        console.print(f"[b green]Starting to install [cyan]{name}[/cyan]!")

        # Check if the install script has a shebang line
        # if it does not, we should execute it with "ansible-runner"
        if not self.has_shebang(install_path):
            return self.run_ansible_playbook(name, install_path)

        console.print(
            "[b yellow]Warning: Use of non-ansible-based INSTALL scripts is deprecated. "
            "Please contact the model component developer to transition this file."
        )

        # Make the install file executable
        # We assume that it can be run with a "shebang" line
        install_path.chmod(
            install_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )

        try:
            # We have already checked with the user to ensure that they want to run
            # this script.
            subprocess.run(  # nosec
                [str(install_path)], cwd=install_path.parent, check=True
            )
            console.print(f"[b green]Installed [cyan]{name}[/cyan]!")
            return True
        except subprocess.CalledProcessError as exp:
            if exp.returncode == 117:  # Structure needs cleaning
                console.print(f"[b yellow][cyan]{name}[/cyan] is already installed!")
                return True

            console.print(f"[b red]Failed to install [cyan]{name}[/cyan]!")
            return False

    def has_shebang(self, install_path):
        """
        Check if the given INSTALL file has a
        `shebang <https://en.wikipedia.org/wiki/Shebang_(Unix)>`_
        line and should be treated as an executable file.

        Args:
            install_path (pathlib.Path): The path of the ``INSTALL`` file.

        Returns:
            bool: :py:data:`True` if the script starts with ``#!``, :py:data:`False` otherwise.
        """
        if install_path.is_dir():
            return False

        script = ""
        with install_path.open("r", encoding="utf-8") as file:
            script = file.read()
        return script.startswith("#!")

    def flatten_git_config(self):
        git_servers = []
        for server in config["ansible"].get("git_servers", []):
            server_url = server["server_url"]
            for repo in server["repositories"]:
                repo_info = {"server_url": server_url, "path": repo["path"]}

                if "branch" in repo:
                    repo_info["branch"] = repo["branch"]

                git_servers.append(repo_info)

        return git_servers

    def flatten_s3_config(self):
        # Flatten S3 config
        s3_endpoints = []
        for endpoint in config["ansible"].get("s3_endpoints", []):
            s3_endpoint = endpoint["s3_endpoint"]
            aws_access_key_id = endpoint["aws_access_key_id"]
            aws_secret_access_key = endpoint["aws_secret_access_key"]

            for bucket in endpoint["buckets"]:
                bucket_info = {
                    "s3_endpoint": s3_endpoint,
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                    "bucket": bucket,
                }

                s3_endpoints.append(bucket_info)

        return s3_endpoints

    def flatten_file_server_config(self):
        # Flatten file server config
        file_servers = []
        for server in config["ansible"].get("file_servers", []):
            url = server["url"]
            use_proxy = server["use_proxy"]
            validate_certs = server["validate_certs"]

            for cache_path in server["cache_paths"]:
                cache_info = {
                    "url": url,
                    "use_proxy": use_proxy,
                    "validate_certs": validate_certs,
                    "cache_path": cache_path,
                }

                file_servers.append(cache_info)

        return file_servers

    def run_ansible_playbook(self, name, install_path):
        """
        Run the provided Ansible playbook using ansible-runner.

        Args:
            name (str): The name of the Model Component.
            install_path (pathlib.Path): The path of the Ansible playbook directory.

        Returns:
            bool: :py:data:`True` if the playbook executed successfully,
            :py:data:`False` otherwise.

        Raises:
            ValueError: If an invalid ``ansible.cache_type`` is provided in the FIREWHEEL config.
        """
        console = Console()

        wrong_structure_msg = str(
            f"[b red][cyan]{install_path}[/cyan] must either be a directory with tasks.yml "
            "and vars.yml or a file with a shebang line."
        )
        if not install_path.is_dir():
            console.print(wrong_structure_msg)
            raise ValueError("Invalid INSTALL file.")

        # Check for vars file.
        vars_path = None
        if Path(install_path / "vars.yml").exists():
            vars_path = Path(install_path / "vars.yml")
        elif Path(install_path / "vars.yaml").exists():
            vars_path = Path(install_path / "vars.yaml")
        else:
            console.print(wrong_structure_msg)
            raise ValueError(f"Missing vars.yml file in directory {install_path}.")

        # Check for tasks file.
        tasks_path = None
        if Path(install_path / "tasks.yml").exists():
            tasks_path = Path(install_path / "tasks.yml")
        elif Path(install_path / "tasks.yaml").exists():
            tasks_path = Path(install_path / "tasks.yaml")
        else:
            console.print(wrong_structure_msg)
            raise ValueError(f"Missing tasks.yml file in directory {install_path}.")

        ansible_config = {
            "ansible_remote_tmp": config["system"]["default_output_dir"],
            "vars_path": str(vars_path),
            "tasks_path": str(tasks_path),
            "mc_dir": str(install_path.parent),
            "install_flag": str(install_path.parent / f".{name}.installed"),
            "mc_name": str(name),
        }

        git_servers = self.flatten_git_config()
        if git_servers:
            ansible_config.update({"git_servers": git_servers})

        s3_endpoints = self.flatten_s3_config()
        if s3_endpoints:
            ansible_config.update({"s3_endpoints": s3_endpoints})

        file_servers = self.flatten_file_server_config()
        if file_servers:
            ansible_config.update({"file_servers": file_servers})

        playbook_path = Path(__file__).resolve().parent / Path(
            "ansible_playbooks/main.yml"
        )

        # Run the Ansible playbooks
        ret = ansible_runner.run(
            private_data_dir=str(install_path.parent),
            playbook=str(playbook_path),
            extravars=ansible_config,
            roles_path=(str(playbook_path.parent / "roles")),
        )

        if ret.rc == 0:
            console.print(
                f"[b green]Successfully executed Ansible playbook [cyan]{install_path}[/cyan]!"
            )
            return True
        else:
            console.print(
                f"[b red]Ansible playbook [cyan]{install_path}[/cyan] failed: {ret}."
            )
            return False

    def run_install_script(self, insecure=False):
        """
        Ask the user to run the install script for the given Model Component.

        Args:
            insecure (bool): Whether to automatically install the Model Component without asking.
                Default is ``False``.

        Returns:
            bool: ``True`` if all MCs were installed successfully, ``False`` otherwise.
        """
        console = Console()

        install_script = Path(self.mc.path) / "INSTALL"
        install_flag = Path(self.mc.path) / f".{self.mc.name}.installed"

        if not install_script.exists():
            return True

        if install_flag.exists():
            return True

        if insecure is True:
            success = self.install_mc(self.mc.name, install_script)
            if not success:
                console.print(f"[b red]Failed to install [cyan]{self.mc.name}[/cyan].")
                return False
            return True

        choices = ["y", "n", "v", "vc", "q"]
        ask = f"[yellow]Do you want to execute [cyan]{install_script}"
        while True:
            value = InstallPrompt.ask(ask, choices=choices)
            if value == "y":
                success = self.install_mc(self.mc.name, install_script)
                if not success:
                    console.print(
                        f"[b red]Failed to install [cyan]{self.mc.name}[/cyan]"
                        " this may cause downstream issues!"
                    )
                    return False

                # If the install script didn't create the "installed" flag
                # we should do it here.
                if not install_flag.exists():
                    install_flag.touch()
                break
            if value == "n":
                console.print(
                    f"[b red]Continuing WITHOUT running [cyan]{install_script}[/cyan]"
                    " this may cause downstream issues!"
                )
                break
            if value.startswith("v"):
                contents = ""
                style = False
                if value == "vc":
                    style = True
                if install_script.is_dir():
                    file_contents = []
                    for file_path in install_script.iterdir():
                        if file_path.is_file():
                            with file_path.open("r") as file:
                                content = file.read()
                                file_contents.append((file_path.name, content))
                    with console.pager(styles=style):
                        for filename, contents in file_contents:
                            console.print(f"[bold underline]Contents of {filename}:[/]")
                            console.print(Syntax(contents, lexer="bash"))
                            console.print("\n" + "-" * 40 + "\n")
                else:
                    with open(install_script, "r", encoding="utf-8") as fhand:
                        contents = fhand.read()
                    with console.pager(styles=style):
                        console.print(Syntax(contents, lexer="bash"))
            elif value.startswith("q"):
                sys.exit(0)
        return True
