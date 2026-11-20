import json
from types import SimpleNamespace
from unittest.mock import ANY, Mock

import pytest

import firewheel.cli.experiment as experiment
from firewheel.control.model_component_spec import ModelComponentSpecError


def test_get_mc_list_delegates_to_core_model_component_builder(monkeypatch):
    builder = Mock(return_value=["mc"])
    monkeypatch.setattr(experiment, "build_model_components", builder)

    result = experiment.get_mc_list(["tests.vm_gen:3"], install_mcs=False)

    assert result == ["mc"]
    builder.assert_called_once_with(["tests.vm_gen:3"], install_mcs=False)


def test_get_mc_list_rejects_malformed_keyword_arguments(monkeypatch):
    monkeypatch.setattr(
        experiment,
        "build_model_components",
        Mock(side_effect=ModelComponentSpecError("bad args")),
    )

    with pytest.raises(experiment.ExperimentHelperError) as excinfo:
        experiment.get_mc_list(["tests.vm_gen:a=b=c"], install_mcs=False)

    assert excinfo.value.error_type == "malformed_model_component_argument"
    assert excinfo.value.phase == "model_component_resolution"


def test_create_cli_parser_accepts_expected_arguments():
    parser = experiment.create_cli_parser()

    args = parser.parse_args(
        ["--format", "json", "--no-install", "tests.vm_gen:3"]
    )

    assert args.format == "json"
    assert args.no_install is False
    assert args.model_component == ["tests.vm_gen:3"]


def test_create_cli_parser_sets_expected_defaults():
    parser = experiment.create_cli_parser()

    args = parser.parse_args(["tests.vm_gen:3"])

    assert args.format == "table"
    assert args.profile is False
    assert args.dry_run is False
    assert args.force is False
    assert args.restart is False
    assert args.no_install is None
    assert args.model_component == ["tests.vm_gen:3"]


def test_build_table_result_returns_failure_count():
    _table, exit_code = experiment.build_table_result(
        dependency_graph_time=1.0,
        total_time=2.0,
        exp_result=[
            {"model_component": "ok.mc", "errors": False, "time": 0.1},
            {"model_component": "bad.mc", "errors": True, "time": 0.2},
        ],
    )

    assert exit_code == 1


def test_render_table_prints_and_returns_exit_code():
    console = Mock()

    exit_code = experiment.render_table(
        console,
        dependency_graph_time=1.0,
        total_time=2.0,
        exp_result=[{"model_component": "bad.mc", "errors": True, "time": 0.2}],
    )

    assert exit_code == 1
    console.print.assert_called_once()


def test_build_json_success_result_records_model_component_statuses():
    cmd_args = SimpleNamespace(
        dry_run=True,
        profile=False,
        force=False,
        restart=True,
        no_install=False,
    )

    result = experiment.build_json_success_result(
        cmd_args=cmd_args,
        active_exp_present=True,
        dependency_graph_time=1.25,
        total_time=2.5,
        exp_result=[
            {"model_component": "ok.mc", "errors": False, "time": 0.1},
            {"model_component": "bad.mc", "errors": True, "time": 0.2},
        ],
        captured_output={"execution": {"stdout": "out", "stderr": "err"}},
    )

    assert result["success"] is False
    assert result["dry_run"] is True
    assert result["active_experiment_detected"] is True
    assert result["dependency_graph_time"] == 1.25
    assert result["total_time"] == 2.5
    assert result["model_components"] == [
        {"name": "ok.mc", "success": True, "errors": False, "time": 0.1},
        {"name": "bad.mc", "success": False, "errors": True, "time": 0.2},
    ]
    assert result["captured_output"] == {
        "execution": {"stdout": "out", "stderr": "err"}
    }
    assert result["message"] == "Experiment completed with model component failures."
    assert "generated_at" in result


def test_build_json_error_result_records_error_phase_and_type():
    cmd_args = SimpleNamespace(
        dry_run=False,
        profile=True,
        force=True,
        restart=False,
        no_install=False,
    )
    error = experiment.ExperimentHelperError("boom", "test_error", "execution")

    result = experiment.build_json_error_result(
        cmd_args=cmd_args,
        active_exp_present=False,
        error=error,
        captured_output={"execution": {"stdout": "", "stderr": "trace"}},
        dependency_graph_time=1.0,
        total_time=2.0,
    )

    assert result["success"] is False
    assert result["profile_enabled"] is True
    assert result["force"] is True
    assert result["phase"] == "execution"
    assert result["error"] == {"type": "test_error", "detail": "boom"}
    assert result["message"] == "boom"


def test_initialize_and_append_phase_capture():
    captured_output = experiment.initialize_captured_output()

    experiment.append_phase_capture(captured_output, "execution", "out", "err")
    experiment.append_phase_capture(captured_output, "execution", "2", "3")

    assert captured_output["execution"] == {"stdout": "out2", "stderr": "err3"}
    assert set(captured_output) == {
        "environment_prepare",
        "model_component_resolution",
        "dependency_graph",
        "execution",
    }


def test_run_phase_with_capture_returns_result_and_output():
    def func():
        print("hello")
        return "result"

    result, stdout_text, stderr_text = experiment.run_phase_with_capture(func)

    assert result == "result"
    assert "hello" in stdout_text
    assert stderr_text == ""


def test_determine_active_experiment_skips_checks_without_restart(monkeypatch):
    monkeypatch.setattr(
        experiment.vrm_api,
        "get_experiment_launch_time",
        Mock(side_effect=AssertionError),
    )
    monkeypatch.setattr(experiment, "minimegaAPI", Mock(side_effect=AssertionError))

    result = experiment.determine_active_experiment(SimpleNamespace(restart=False))

    assert result is False


def test_determine_active_experiment_detects_launch_time(monkeypatch):
    monkeypatch.setattr(
        experiment.vrm_api,
        "get_experiment_launch_time",
        Mock(return_value="time"),
    )
    monkeypatch.setattr(experiment, "minimegaAPI", Mock())

    result = experiment.determine_active_experiment(SimpleNamespace(restart=True))

    assert result is True


def test_determine_active_experiment_detects_minimega_vms(monkeypatch):
    mm_api = Mock()
    mm_api.mm_vms.return_value = ["vm"]
    monkeypatch.setattr(
        experiment.vrm_api,
        "get_experiment_launch_time",
        Mock(return_value=None),
    )
    monkeypatch.setattr(experiment, "minimegaAPI", Mock(return_value=mm_api))

    result = experiment.determine_active_experiment(SimpleNamespace(restart=True))

    assert result is True


def test_determine_active_experiment_returns_false_without_launch_or_vms(monkeypatch):
    mm_api = Mock()
    mm_api.mm_vms.return_value = []
    monkeypatch.setattr(
        experiment.vrm_api,
        "get_experiment_launch_time",
        Mock(return_value=None),
    )
    monkeypatch.setattr(experiment, "minimegaAPI", Mock(return_value=mm_api))

    result = experiment.determine_active_experiment(SimpleNamespace(restart=True))

    assert result is False


def test_maybe_restart_environment_skips_when_not_requested(monkeypatch):
    monkeypatch.setattr(experiment, "FirewheelCLI", Mock(side_effect=AssertionError))

    experiment.maybe_restart_environment(
        SimpleNamespace(force=False, restart=False), Mock(), active_exp_present=False
    )


def test_maybe_restart_environment_runs_restart_when_forced(monkeypatch):
    firewheel_cli = Mock()
    monkeypatch.setattr(experiment, "FirewheelCLI", Mock(return_value=firewheel_cli))
    console = Mock()

    experiment.maybe_restart_environment(
        SimpleNamespace(force=True, restart=False), console, active_exp_present=False
    )

    firewheel_cli.onecmd.assert_called_once_with("restart")
    assert console.print.call_count == 2


def test_maybe_restart_environment_runs_restart_when_active_restart_requested(
    monkeypatch,
):
    firewheel_cli = Mock()
    monkeypatch.setattr(experiment, "FirewheelCLI", Mock(return_value=firewheel_cli))

    experiment.maybe_restart_environment(
        SimpleNamespace(force=False, restart=True), Mock(), active_exp_present=True
    )

    firewheel_cli.onecmd.assert_called_once_with("restart")


def test_maybe_restart_environment_translates_restart_errors(monkeypatch):
    firewheel_cli = Mock()
    firewheel_cli.onecmd.side_effect = OSError("nope")
    monkeypatch.setattr(experiment, "FirewheelCLI", Mock(return_value=firewheel_cli))

    with pytest.raises(experiment.ExperimentHelperError) as excinfo:
        experiment.maybe_restart_environment(
            SimpleNamespace(force=True, restart=False), Mock(), active_exp_present=False
        )

    assert excinfo.value.error_type == "environment_restart_failed"
    assert excinfo.value.phase == "environment_prepare"


def test_run_experiment_calls_model_component_manager():
    mcm = Mock()
    mcm.build_experiment_graph_result.return_value = (["result"], None)

    result = experiment.run_experiment(mcm, Mock(), dry_run=True, is_profile=False)

    assert result == ["result"]
    mcm.build_experiment_graph_result.assert_called_once_with(dry_run=True)


def test_run_experiment_translates_plugin_argument_type_error():
    mcm = Mock()
    mcm.build_experiment_graph_result.side_effect = TypeError("bad args")
    console = Mock()

    with pytest.raises(experiment.ExperimentHelperError) as excinfo:
        experiment.run_experiment(mcm, console, dry_run=False, is_profile=False)

    assert excinfo.value.error_type == "invalid_plugin_arguments"
    assert excinfo.value.phase == "execution"
    assert console.print.call_count == 2


def test_main_json_requires_no_install(monkeypatch, capsys):
    monkeypatch.setattr(
        experiment.sys,
        "argv",
        ["firewheel experiment", "--format", "json", "tests.vm_gen:3"],
    )

    with pytest.raises(SystemExit) as excinfo:
        experiment.main()

    result = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert result["success"] is False
    assert result["error"]["type"] == "interactive_install_possible"
    assert result["phase"] == "argument_validation"


def test_main_json_success_path_uses_importable_helpers(monkeypatch, capsys):
    mcm = Mock()
    model_component = object()
    monkeypatch.setattr(
        experiment.sys,
        "argv",
        ["firewheel experiment", "--format", "json", "--no-install", "tests.vm_gen:3"],
    )
    monkeypatch.setattr(
        experiment,
        "determine_active_experiment",
        Mock(return_value=False),
    )
    monkeypatch.setattr(experiment, "maybe_restart_environment", Mock())
    monkeypatch.setattr(experiment, "get_mc_list", Mock(return_value=[model_component]))
    monkeypatch.setattr(experiment, "ModelComponentManager", Mock(return_value=mcm))
    monkeypatch.setattr(
        experiment,
        "run_experiment",
        Mock(
            return_value=[
                {"model_component": "tests.vm_gen", "errors": False, "time": 0.1}
            ]
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        experiment.main()

    result = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 0
    assert result["success"] is True
    assert result["model_components"] == [
        {"name": "tests.vm_gen", "success": True, "errors": False, "time": 0.1}
    ]
    experiment.get_mc_list.assert_called_once_with(
        ["tests.vm_gen:3"], install_mcs=False
    )
    mcm.build_dependency_graph.assert_called_once_with(
        [model_component], install_mcs=False
    )
    experiment.run_experiment.assert_called_once_with(mcm, ANY, False, False)


def test_main_table_success_path_uses_render_table(monkeypatch):
    mcm = Mock()
    model_component = object()
    exp_result = [{"model_component": "tests.vm_gen", "errors": False, "time": 0.1}]
    monkeypatch.setattr(
        experiment.sys,
        "argv",
        ["firewheel experiment", "--no-install", "tests.vm_gen:3"],
    )
    monkeypatch.setattr(experiment, "determine_active_experiment", Mock(return_value=False))
    monkeypatch.setattr(experiment, "maybe_restart_environment", Mock())
    monkeypatch.setattr(experiment, "get_mc_list", Mock(return_value=[model_component]))
    monkeypatch.setattr(experiment, "ModelComponentManager", Mock(return_value=mcm))
    monkeypatch.setattr(experiment, "run_experiment", Mock(return_value=exp_result))
    monkeypatch.setattr(experiment, "render_table", Mock(return_value=0))

    with pytest.raises(SystemExit) as excinfo:
        experiment.main()

    assert excinfo.value.code == 0
    experiment.render_table.assert_called_once_with(ANY, ANY, ANY, exp_result)


def test_main_json_dependency_errors_are_reported(monkeypatch, capsys):
    mcm = Mock()
    mcm.build_dependency_graph.side_effect = experiment.UnsatisfiableDependenciesError(
        "cycle"
    )
    monkeypatch.setattr(
        experiment.sys,
        "argv",
        ["firewheel experiment", "--format", "json", "--no-install", "tests.vm_gen:3"],
    )
    monkeypatch.setattr(experiment, "determine_active_experiment", Mock(return_value=False))
    monkeypatch.setattr(experiment, "maybe_restart_environment", Mock())
    monkeypatch.setattr(experiment, "get_mc_list", Mock(return_value=[object()]))
    monkeypatch.setattr(experiment, "ModelComponentManager", Mock(return_value=mcm))

    with pytest.raises(SystemExit) as excinfo:
        experiment.main()

    result = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert result["success"] is False
    assert result["phase"] == "dependency_graph"
    assert result["error"]["type"] == "unsatisfiable_dependencies"


def test_main_table_experiment_helper_errors_are_printed(monkeypatch):
    console = Mock()
    monkeypatch.setattr(experiment, "Console", Mock(return_value=console))
    monkeypatch.setattr(
        experiment.sys,
        "argv",
        ["firewheel experiment", "tests.vm_gen:a=b=c"],
    )
    monkeypatch.setattr(experiment, "determine_active_experiment", Mock(return_value=False))
    monkeypatch.setattr(experiment, "maybe_restart_environment", Mock())
    monkeypatch.setattr(
        experiment,
        "get_mc_list",
        Mock(
            side_effect=experiment.ExperimentHelperError(
                "bad args", "malformed_model_component_argument", "model_component_resolution"
            )
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        experiment.main()

    assert excinfo.value.code == 1
    console.print.assert_called_once_with("[error]ERROR:[/error] bad args")
