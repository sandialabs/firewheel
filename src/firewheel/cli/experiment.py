"""Implementation for the ``firewheel experiment`` helper."""

import os
import sys
import json
import argparse
import cProfile
import tempfile
import traceback
from datetime import datetime, timezone

from rich.align import Align
from rich.console import Console

import firewheel.vm_resource_manager.api as vrm_api
from firewheel.cli.utils import RichDefaultTable, cli_output_theme
from firewheel.lib.minimega.api import minimegaAPI
from firewheel.cli.firewheel_cli import FirewheelCLI
from firewheel.control.model_component import ModelComponent
from firewheel.control.dependency_graph import UnsatisfiableDependenciesError
from firewheel.control.model_component_manager import ModelComponentManager


class ExperimentHelperError(Exception):
    """Expected operational error for the experiment helper.

    Args:
        message (str): Human-readable error message.
        error_type (str): Stable machine-readable error type.
        phase (str): Phase in which the error occurred.
    """

    def __init__(self, message, error_type, phase):
        """Initialize the exception.

        Args:
            message (str): Human-readable error message.
            error_type (str): Stable machine-readable error type.
            phase (str): Phase in which the error occurred.
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.phase = phase


class OutputCapture:
    """Capture both Python-level and file-descriptor-level stdout/stderr.

    This context manager redirects:
      - Python ``sys.stdout`` / ``sys.stderr``
      - OS file descriptors 1 and 2

    into temporary files so that normal prints, Rich console output, and many
    subprocess writes inherited from this process can be captured safely.

    After the context exits, the original stdout/stderr streams and file
    descriptors are restored, even if an exception occurs.
    """

    def __init__(self):
        """Initialize the output capture state."""
        self.stdout = ""
        self.stderr = ""

        self._stdout_tmp = None
        self._stderr_tmp = None

        self._old_stdout = None
        self._old_stderr = None

        self._old_stdout_fd = None
        self._old_stderr_fd = None

        self._capture_stdout = None
        self._capture_stderr = None

    def __enter__(self):
        """Enter the capture context.

        Returns:
            OutputCapture: This output capture instance.
        """
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr

        self._old_stdout_fd = os.dup(1)
        self._old_stderr_fd = os.dup(2)

        self._stdout_tmp = tempfile.TemporaryFile(mode="w+b")
        self._stderr_tmp = tempfile.TemporaryFile(mode="w+b")

        os.dup2(self._stdout_tmp.fileno(), 1)
        os.dup2(self._stderr_tmp.fileno(), 2)

        self._capture_stdout = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
        self._capture_stderr = os.fdopen(os.dup(2), "w", encoding="utf-8", buffering=1)

        sys.stdout = self._capture_stdout
        sys.stderr = self._capture_stderr

        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """Exit the capture context and restore stdout/stderr.

        Args:
            exc_type (type | None): Exception type if an exception occurred.
            exc (BaseException | None): Exception instance if an exception occurred.
            exc_tb (types.TracebackType | None): Traceback if an exception occurred.

        Returns:
            bool: Always returns ``False`` so exceptions propagate normally.
        """
        try:
            try:
                if sys.stdout is not None:
                    sys.stdout.flush()
            except (OSError, ValueError):
                pass

            try:
                if sys.stderr is not None:
                    sys.stderr.flush()
            except (OSError, ValueError):
                pass

            try:
                if self._stdout_tmp is not None:
                    self._stdout_tmp.flush()
            except OSError:
                pass

            try:
                if self._stderr_tmp is not None:
                    self._stderr_tmp.flush()
            except OSError:
                pass

            try:
                if self._stdout_tmp is not None:
                    self._stdout_tmp.seek(0)
                    self.stdout = self._stdout_tmp.read().decode(
                        "utf-8", errors="replace"
                    )
            except OSError:
                self.stdout = ""

            try:
                if self._stderr_tmp is not None:
                    self._stderr_tmp.seek(0)
                    self.stderr = self._stderr_tmp.read().decode(
                        "utf-8", errors="replace"
                    )
            except OSError:
                self.stderr = ""

        finally:
            try:
                if self._capture_stdout is not None:
                    self._capture_stdout.close()
            except OSError:
                pass

            try:
                if self._capture_stderr is not None:
                    self._capture_stderr.close()
            except OSError:
                pass

            if self._old_stdout_fd is not None:
                os.dup2(self._old_stdout_fd, 1)
                os.close(self._old_stdout_fd)

            if self._old_stderr_fd is not None:
                os.dup2(self._old_stderr_fd, 2)
                os.close(self._old_stderr_fd)

            sys.stdout = self._old_stdout
            sys.stderr = self._old_stderr

            try:
                if self._stdout_tmp is not None:
                    self._stdout_tmp.close()
            except OSError:
                pass

            try:
                if self._stderr_tmp is not None:
                    self._stderr_tmp.close()
            except OSError:
                pass

        return False


def run_phase_with_capture(func, *args, **kwargs):
    """Execute a function while capturing stdout and stderr.

    Args:
        func (callable): Function to execute.
        *args: Positional arguments for ``func``.
        **kwargs: Keyword arguments for ``func``.

    Returns:
        tuple: A tuple containing:
            - result (Any): The return value of ``func``.
            - stdout_text (str): Captured stdout text.
            - stderr_text (str): Captured stderr text.
    """
    with OutputCapture() as capture:
        result = func(*args, **kwargs)
    return result, capture.stdout, capture.stderr


def get_mc_list(cli_args, install_mcs=None):
    """Get the list of model components and their arguments from the command line.

    Args:
        cli_args (list): List of command-line input model components.
        install_mcs (bool | None): Whether to install model components automatically.
            By default, this method will defer to the default defined by the model component
            object's constructor. If set to :py:data:`False`, model components will not
            be installed.

    Returns:
        list: A list of model component objects.

    Raises:
        ExperimentHelperError: If a model component argument is malformed.
    """
    initial_mc_list = []
    for init_mc in cli_args:
        sp = init_mc.split(":")
        init_mc_name = sp[0]

        args = {"plugin": {}}
        anon_args = []
        for arg in sp[1:]:
            arg_sp = arg.split("=")
            if len(arg_sp) == 2:
                args["plugin"][arg_sp[0]] = arg_sp[1]
            elif len(arg_sp) == 1:
                anon_args.append(arg_sp[0])
            else:
                raise ExperimentHelperError(
                    f"Malformed argument for ModelComponent {init_mc_name}.",
                    "malformed_model_component_argument",
                    "model_component_resolution",
                )
        if len(anon_args) > 0:
            args["plugin"][""] = anon_args

        mc = ModelComponent(name=init_mc_name, arguments=args, install=install_mcs)
        initial_mc_list.append(mc)
    return initial_mc_list


def create_cli_parser():
    """Create an argparse parser for the experiment helper.

    Returns:
        argparse.ArgumentParser: The configured parser.
    """
    parser = argparse.ArgumentParser(
        description="Start a FIREWHEEL experiment.",
        prog="firewheel experiment",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format. Defaults to table.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        default=False,
        required=False,
        help=(
            "Output profiling information for experiment graph construction. "
            "It creates a firewheel_profile.prof file in the current working directory."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        required=False,
        help=(
            "Output the ModelComponent sequence that would be evaluated, "
            "but don't actually evaluate the components."
        ),
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        required=False,
        help=(
            "Force the experiment to launch even if there is an existing experiment. "
            "This essentially clears the testbed by running `firewheel restart`."
        ),
    )
    parser.add_argument(
        "-r",
        "--restart",
        action="store_true",
        default=False,
        required=False,
        help=(
            "Similar to -f or --force, but only restarts if an active experiment is detected. "
            "If an experiment is detected, runs `firewheel restart` before starting the experiment."
        ),
    )
    parser.add_argument(
        "-ni",
        "--no-install",
        action="store_false",
        default=None,
        required=False,
        help=(
            "Continue regardless of if Model Components within the experiment have been "
            "'installed' (i.e., the INSTALL file executed). Defaults to None."
        ),
    )
    parser.add_argument(
        "model_component",
        nargs="+",
        help=(
            "The model component to use in the experiment. More than one of these may be "
            "specified. If the given Model Component's Plugin requires a parameter, "
            "the value can be passed to the MC by using a colon separated list "
            "(e.g. `<model_component>:[value1]:[value2]`). Keyword parameters can be "
            "specified as well, using the traditional keyword format of `name=value`. "
            "If no name is provided, these arguments are treated as positional. "
            "No spaces are allowed when providing MC parameters."
        ),
    )

    return parser


def build_table_result(dependency_graph_time=0.0, total_time=0.0, exp_result=None):
    """Build a Rich table for experiment execution results.

    Args:
        dependency_graph_time (float): Time to generate the dependency graph.
        total_time (float): Total helper runtime.
        exp_result (list | None): Results from each MC execution.

    Returns:
        tuple: A tuple containing:
            - table (RichDefaultTable): The rendered results table.
            - exit_code (int): Exit code based on model component failures.
    """
    caption = f"Dependency graph resolution took [cyan]{dependency_graph_time:.3f}[/ cyan] seconds"

    table = RichDefaultTable(
        title="Model Components Executed",
        show_lines=False,
        show_footer=True,
        caption=caption,
    )
    table.add_column(Align("Model Component Name", "center"))
    table.add_column(
        Align("Result", "center"), justify="right", footer="[b magenta]Total Time"
    )
    table.add_column(
        Align("Timing", "center"),
        justify="right",
        footer=f"[b cyan]{total_time:.3f}[/] seconds",
    )

    exit_code = 0

    for res in exp_result:
        if res["errors"]:
            exit_code += 1
            result_str = "[red]FAILED"
        else:
            result_str = "[green]OK"
        table.add_row(
            f"[yellow]{res['model_component']}",
            result_str,
            f"[cyan]{res['time']:.3f}[/] seconds",
        )

    return table, exit_code


def render_table(console, dependency_graph_time=0.0, total_time=0.0, exp_result=None):
    """Print table output for human-readable mode.

    Args:
        console (rich.console.Console): Console for rendering.
        dependency_graph_time (float): Dependency graph resolution time.
        total_time (float): Total helper runtime.
        exp_result (list | None): Experiment execution results.

    Returns:
        int: Exit code.
    """
    table, exit_code = build_table_result(dependency_graph_time, total_time, exp_result)
    console.print("\n", table, "\n")
    return exit_code


def build_json_success_result(
    cmd_args,
    active_exp_present,
    dependency_graph_time,
    total_time,
    exp_result,
    captured_output,
):
    """Build the final JSON success payload.

    Args:
        cmd_args (argparse.Namespace): Parsed command-line arguments.
        active_exp_present (bool): Whether an active experiment was detected.
        dependency_graph_time (float): Time to build the dependency graph.
        total_time (float): Total helper runtime.
        exp_result (list): Results from experiment execution.
        captured_output (dict): Captured stdout/stderr grouped by phase.

    Returns:
        dict: Structured JSON success payload.
    """
    exit_code = sum(1 for res in exp_result if res["errors"])

    return {
        "success": exit_code == 0,
        "dry_run": cmd_args.dry_run,
        "profile_enabled": cmd_args.profile,
        "force": cmd_args.force,
        "restart": cmd_args.restart,
        "no_install": cmd_args.no_install,
        "active_experiment_detected": active_exp_present,
        "dependency_graph_time": dependency_graph_time,
        "total_time": total_time,
        "model_components": [
            {
                "name": res["model_component"],
                "success": not res["errors"],
                "errors": res["errors"],
                "time": res["time"],
            }
            for res in exp_result
        ],
        "captured_output": captured_output,
        "message": (
            "Experiment completed successfully."
            if exit_code == 0
            else "Experiment completed with model component failures."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_json_error_result(
    cmd_args,
    active_exp_present,
    error,
    captured_output,
    dependency_graph_time=None,
    total_time=None,
):
    """Build the final JSON error payload.

    Args:
        cmd_args (argparse.Namespace): Parsed command-line arguments.
        active_exp_present (bool): Whether an active experiment was detected.
        error (ExperimentHelperError): Structured helper error.
        captured_output (dict): Captured stdout/stderr grouped by phase.
        dependency_graph_time (float | None): Time to build dependency graph, if known.
        total_time (float | None): Total helper runtime, if known.

    Returns:
        dict: Structured JSON error payload.
    """
    return {
        "success": False,
        "dry_run": cmd_args.dry_run,
        "profile_enabled": cmd_args.profile,
        "force": cmd_args.force,
        "restart": cmd_args.restart,
        "no_install": cmd_args.no_install,
        "active_experiment_detected": active_exp_present,
        "dependency_graph_time": dependency_graph_time,
        "total_time": total_time,
        "phase": error.phase,
        "error": {
            "type": error.error_type,
            "detail": error.message,
        },
        "captured_output": captured_output,
        "message": error.message,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_experiment(mcm, console, dry_run=False, is_profile=False):
    """Execute all model components included within the dependency graph.

    Args:
        mcm (ModelComponentManager): The manager used to execute the graph.
        console (rich.console.Console): Console for displaying output.
        dry_run (bool): Whether this is a dry run.
        is_profile (bool): Whether execution should be profiled.

    Returns:
        list: Experimental results.

    Raises:
        ExperimentHelperError: If plugin arguments are invalid.
    """
    exp_result = []
    try:
        if is_profile:
            profile = cProfile.Profile()
            profile.enable()

        exp_result = mcm.build_experiment_graph(dry_run=dry_run)

        if is_profile:
            profile.disable()
            profile.dump_stats("firewheel_profile.prof")
    except TypeError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # It turns out the traceback only gives infrastructure functions here,
        # not any indication of which plugin class was the root of the error.
        exc_str = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        console.print(
            "\nAborting experiment graph processing!"
            "\n[error]ERROR:[/error] Invalid arguments to experiment graph plugin."
        )
        console.print(f"\nDetails: {exc_str}")
        raise ExperimentHelperError(
            "Invalid arguments to experiment graph plugin.",
            "invalid_plugin_arguments",
            "execution",
        ) from None

    return exp_result


def determine_active_experiment(cmd_args):
    """Determine whether an active experiment is present.

    Args:
        cmd_args (argparse.Namespace): Parsed arguments.

    Returns:
        bool: Whether an active experiment is present.
    """
    active_exp_present = False
    if cmd_args.restart:
        mm_api = minimegaAPI()
        if vrm_api.get_experiment_launch_time() is not None or mm_api.mm_vms():
            active_exp_present = True
    return active_exp_present


def maybe_restart_environment(cmd_args, console, active_exp_present):
    """Restart the environment if requested.

    Args:
        cmd_args (argparse.Namespace): Parsed arguments.
        console (rich.console.Console): Console for text output.
        active_exp_present (bool): Whether an active experiment is present.

    Raises:
        ExperimentHelperError: If environment restart fails.
    """
    if cmd_args.force is True or (cmd_args.restart and active_exp_present is True):
        try:
            console.print("Cleaning up any running experiments.")
            FirewheelCLI().onecmd("restart")
            console.print("All running experiments have been cleared.")
        except OSError as exc:
            raise ExperimentHelperError(
                f"Failed to restart the environment: {exc}",
                "environment_restart_failed",
                "environment_prepare",
            ) from exc


def initialize_captured_output():
    """Initialize the phase-based captured output structure.

    Returns:
        dict: Empty stdout/stderr buckets for each phase.
    """
    return {
        "environment_prepare": {"stdout": "", "stderr": ""},
        "model_component_resolution": {"stdout": "", "stderr": ""},
        "dependency_graph": {"stdout": "", "stderr": ""},
        "execution": {"stdout": "", "stderr": ""},
    }


def append_phase_capture(captured_output, phase, stdout_text, stderr_text):
    """Append captured output for a phase.

    Args:
        captured_output (dict): The aggregate captured output structure.
        phase (str): Phase name.
        stdout_text (str): Captured stdout text.
        stderr_text (str): Captured stderr text.
    """
    captured_output[phase]["stdout"] += stdout_text
    captured_output[phase]["stderr"] += stderr_text


def main():
    """Execute the main logic of the experiment helper."""
    console = Console(theme=cli_output_theme)

    total_start = datetime.now()
    parser = create_cli_parser()
    cmd_args = parser.parse_args()

    json_mode = cmd_args.format == "json"

    if json_mode and cmd_args.no_install is not False:
        error = ExperimentHelperError(
            "JSON output requires non-interactive execution. Re-run with --no-install.",
            "interactive_install_possible",
            "argument_validation",
        )
        result = build_json_error_result(
            cmd_args=cmd_args,
            active_exp_present=False,
            error=error,
            captured_output={},
        )
        print(json.dumps(result, indent=2))
        sys.exit(1)

    captured_output = initialize_captured_output()

    active_exp_present = False
    dependency_graph_time = None

    try:
        active_exp_present = determine_active_experiment(cmd_args)

        if json_mode:
            _, stdout_text, stderr_text = run_phase_with_capture(
                maybe_restart_environment,
                cmd_args,
                console,
                active_exp_present,
            )
            append_phase_capture(
                captured_output, "environment_prepare", stdout_text, stderr_text
            )
        else:
            maybe_restart_environment(cmd_args, console, active_exp_present)

        if json_mode:
            initial_mc_list, stdout_text, stderr_text = run_phase_with_capture(
                get_mc_list,
                cmd_args.model_component,
                install_mcs=cmd_args.no_install,
            )
            append_phase_capture(
                captured_output, "model_component_resolution", stdout_text, stderr_text
            )
        else:
            initial_mc_list = get_mc_list(
                cmd_args.model_component,
                install_mcs=cmd_args.no_install,
            )

        ds = datetime.now()
        mcm = ModelComponentManager(console=console)

        try:
            if json_mode:
                _, stdout_text, stderr_text = run_phase_with_capture(
                    mcm.build_dependency_graph,
                    initial_mc_list,
                    install_mcs=cmd_args.no_install,
                )
                append_phase_capture(
                    captured_output, "dependency_graph", stdout_text, stderr_text
                )
            else:
                mcm.build_dependency_graph(
                    initial_mc_list,
                    install_mcs=cmd_args.no_install,
                )
        except UnsatisfiableDependenciesError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            exc_str = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
            if json_mode:
                raise ExperimentHelperError(
                    exc_str,
                    "unsatisfiable_dependencies",
                    "dependency_graph",
                ) from None

            console.print(
                "[error]ERROR:[/error] Unable to build model component dependency graph due to the "
                f"following error:\n\n{exc_str}\n\nNo Model Components were evaluated and no restart is "
                "required. "
            )
            sys.exit(1)

        de = datetime.now()
        dependency_graph_time = (de - ds).total_seconds()

        if json_mode:
            exp_result, stdout_text, stderr_text = run_phase_with_capture(
                run_experiment,
                mcm,
                console,
                cmd_args.dry_run,
                cmd_args.profile,
            )
            append_phase_capture(captured_output, "execution", stdout_text, stderr_text)
        else:
            exp_result = run_experiment(
                mcm, console, cmd_args.dry_run, cmd_args.profile
            )

        total_end = datetime.now()
        total_time = (total_end - total_start).total_seconds()

        if json_mode:
            result = build_json_success_result(
                cmd_args=cmd_args,
                active_exp_present=active_exp_present,
                dependency_graph_time=dependency_graph_time,
                total_time=total_time,
                exp_result=exp_result,
                captured_output=captured_output,
            )
            print(json.dumps(result, indent=2))
            exit_code = sum(1 for res in exp_result if res["errors"])
            sys.exit(exit_code)

        exit_code = render_table(
            console,
            dependency_graph_time,
            total_time,
            exp_result,
        )
        sys.exit(exit_code)

    except ExperimentHelperError as exc:
        total_end = datetime.now()
        total_time = (total_end - total_start).total_seconds()

        if json_mode:
            result = build_json_error_result(
                cmd_args=cmd_args,
                active_exp_present=active_exp_present,
                error=exc,
                captured_output=captured_output,
                dependency_graph_time=dependency_graph_time,
                total_time=total_time,
            )
            print(json.dumps(result, indent=2))
            sys.exit(1)

        console.print(f"[error]ERROR:[/error] {exc.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
