import pytest

import firewheel.cli.experiment as experiment


def test_get_mc_list_parses_model_component_arguments(monkeypatch):
    created = []

    class FakeModelComponent:
        def __init__(self, name, arguments, install):
            self.name = name
            self.arguments = arguments
            self.install = install
            created.append(self)

    monkeypatch.setattr(experiment, "ModelComponent", FakeModelComponent)

    result = experiment.get_mc_list(
        ["tests.vm_gen:3:key=value"], install_mcs=False
    )

    assert result == created
    assert result[0].name == "tests.vm_gen"
    assert result[0].arguments == {"plugin": {"key": "value", "": ["3"]}}
    assert result[0].install is False


def test_get_mc_list_rejects_malformed_keyword_arguments():
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
