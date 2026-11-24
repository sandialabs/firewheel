import os
import sys
import shutil
import tempfile
from unittest.mock import Mock

import yaml
import pytest

from firewheel.control.experiment_builder import (
    build_experiment,
    ExperimentBuildRequest,
)
from firewheel.tests.unit.test_utils import cleanup_repo_db, initalize_repo_db
from firewheel.control.model_component_spec import (
    ModelComponentSpec,
    ModelComponentSpecError,
    build_model_components,
    parse_model_component_spec,
)


@pytest.fixture
def experiment_build_repo():
    base_dir = tempfile.mkdtemp()
    repo_dir = "repo"
    mc_dir = os.path.join(base_dir, repo_dir, "mc")
    os.makedirs(mc_dir)

    manifest = {
        "name": "test.build",
        "attributes": {"depends": [], "provides": ["test.build"]},
        "model_components": {"depends": []},
        "plugin": "plugin.py",
    }
    with open(os.path.join(mc_dir, "MANIFEST"), "w", encoding="utf8") as f:
        f.write(yaml.safe_dump(manifest))

    plugin = """
from firewheel.control.experiment_graph import AbstractPlugin, ExperimentGraph, Vertex

class BuildPlugin(AbstractPlugin):
    def run(self, *args, **kwargs):
        if self.g is None:
            self.g = ExperimentGraph()
        vertex = Vertex(self.g, name="built")
        vertex.args = list(args)
        vertex.kwargs = dict(kwargs)
"""
    with open(os.path.join(mc_dir, "plugin.py"), "w", encoding="utf8") as f:
        f.write(plugin)

    repository_db = initalize_repo_db()
    repository_db.add_repository({"path": os.path.join(base_dir, repo_dir)})

    try:
        yield repository_db
    finally:
        shutil.rmtree(base_dir)
        cleanup_repo_db(repository_db)
        sys.modules.pop("test.build", None)


def test_parse_model_component_spec_keyword_and_positional_args():
    spec = parse_model_component_spec("mc:arg1:arg2:key=value")

    assert spec.name == "mc"
    assert spec.plugin_args == {"": ["arg1", "arg2"], "key": "value"}


def test_parse_model_component_spec_rejects_malformed_keyword_arg():
    with pytest.raises(ModelComponentSpecError):
        parse_model_component_spec("mc:a=b=c")


def test_build_model_components_accepts_strings_and_structured_specs(
    experiment_build_repo,
):
    components = build_model_components(
        [
            "test.build:pos:key=value",
            ModelComponentSpec("test.build", {"other": "value"}),
        ],
        repository_db=experiment_build_repo,
        install_mcs=False,
    )

    assert [component.name for component in components] == [
        "test.build",
        "test.build",
    ]
    assert components[0].arguments == {"plugin": {"": ["pos"], "key": "value"}}
    assert components[1].arguments == {"plugin": {"other": "value"}}


def test_model_component_spec_from_app_style_args():
    spec = ModelComponentSpec.from_args(
        "test.build",
        positional=["pos1", "pos2"],
        keyword={"key": "value"},
    )

    assert spec.name == "test.build"
    assert spec.plugin_args == {"key": "value", "": ["pos1", "pos2"]}
    assert spec.describe() == {
        "name": "test.build",
        "plugin_args": {"key": "value", "": ["pos1", "pos2"]},
    }


def test_build_model_components_preserves_existing_components(experiment_build_repo):
    component = build_model_components(
        ["test.build"], repository_db=experiment_build_repo, install_mcs=False
    )[0]

    components = build_model_components([component], repository_db=experiment_build_repo)

    assert components == [component]


def test_build_experiment_returns_graph_and_provenance(experiment_build_repo):
    request = ExperimentBuildRequest(
        specs=[
            ModelComponentSpec.from_args(
                "test.build",
                positional=["pos"],
                keyword={"key": "value"},
            )
        ],
        upload_files=False,
    )

    result = build_experiment(
        request,
        repository_db=experiment_build_repo,
    )

    assert result.request == request
    assert result.success is True
    assert result.experiment_graph is not None
    vertex = result.experiment_graph.find_vertex("built")
    assert vertex.args == ["pos"]
    assert vertex.kwargs == {"key": "value"}
    assert result.provenance["resolved_order"] == ["test.build"]
    assert result.provenance["upload_files"] is False
    assert result.execution[0].model_component == "test.build"
    assert result.execution[0].errors is False
    assert result.provenance["execution"][0]["model_component"] == "test.build"
    assert result.provenance["input_specs"] == [
        {"name": "test.build", "plugin_args": {"key": "value", "": ["pos"]}}
    ]
    assert result.provenance["graph_summary"] == {"vertices": 1, "edges": 0}
    assert "dependency_graph_json" in result.provenance

    summary = result.to_summary()
    assert summary["success"] is True
    assert summary["request"] == {
        "specs": [
            {"name": "test.build", "plugin_args": {"key": "value", "": ["pos"]}}
        ],
        "install_mcs": False,
        "dry_run": False,
        "upload_files": False,
        "attribute_defaults_config": None,
    }
    assert summary["execution"][0]["model_component"] == "test.build"


def test_build_experiment_does_not_upload_when_disabled(experiment_build_repo):
    component = build_experiment(
        ExperimentBuildRequest(specs=["test.build"], upload_files=False),
        repository_db=experiment_build_repo,
    ).ordered_model_components[0]
    component.upload_files = Mock()

    result = build_experiment(
        ExperimentBuildRequest(specs=[component], upload_files=False),
        repository_db=experiment_build_repo,
    )

    assert result.experiment_graph is not None
    component.upload_files.assert_not_called()


def test_build_experiment_rejects_unknown_spec_type():
    with pytest.raises(TypeError):
        build_experiment(ExperimentBuildRequest(specs=[object()]))
