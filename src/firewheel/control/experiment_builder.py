"""Library helpers for building FIREWHEEL experiment graphs without launch."""

from typing import Any, TypeAlias
from datetime import datetime, timezone
from dataclasses import asdict, dataclass

from firewheel.control.model_component import ModelComponent
from firewheel.control.experiment_graph import ExperimentGraph
from firewheel.control.model_component_spec import (
    ModelComponentSpec,
    ModelComponentInput,
    build_model_components,
)
from firewheel.control.model_component_manager import ModelComponentManager
from firewheel.control.model_component_dependency_graph import (
    ModelComponentDependencyGraph,
)

ModelComponentDescription: TypeAlias = dict[str, Any]
Provenance: TypeAlias = dict[str, Any]


@dataclass(frozen=True)
class ExperimentBuildRequest:
    """Request to resolve and execute a FIREWHEEL model component pipeline."""

    specs: list[ModelComponentInput]
    install_mcs: bool | None = False
    dry_run: bool = False
    upload_files: bool = False
    attribute_defaults_config: dict[str, Any] | None = None


@dataclass(frozen=True)
class ModelComponentExecutionRecord:
    """Execution metadata for one processed model component."""

    model_component: str
    errors: bool
    time: float

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "ModelComponentExecutionRecord":
        """Build a typed execution record from manager output."""
        return cls(
            model_component=record["model_component"],
            errors=record["errors"],
            time=record["time"],
        )


@dataclass
class ExperimentBuildResult:
    """Result of resolving and executing a FIREWHEEL model component pipeline."""

    request: ExperimentBuildRequest
    experiment_graph: ExperimentGraph | None
    model_components: list[ModelComponentDescription]
    ordered_model_components: list[ModelComponent]
    dependency_graph: ModelComponentDependencyGraph
    dependency_graph_json: str
    execution: list[ModelComponentExecutionRecord]
    provenance: Provenance

    @property
    def success(self) -> bool:
        """Whether all model components completed without reported errors."""
        return not any(record.errors for record in self.execution)

    def to_summary(self) -> dict[str, Any]:
        """Return a serializable summary suitable for callers and logs."""
        summary = dict(self.provenance)
        summary["success"] = self.success
        summary["request"] = _describe_request(self.request)
        summary["execution"] = [asdict(record) for record in self.execution]
        return summary


def build_experiment(
    request: ExperimentBuildRequest,
    repository_db: Any = None,
    console: Any = None,
) -> ExperimentBuildResult:
    """Resolve and execute a model component pipeline without launch ownership.

    This API intentionally does not check for active experiments, restart the
    environment, instantiate minimega, or call VM resource manager APIs. It only
    resolves FIREWHEEL model components and executes their plugins through the
    core ``ModelComponentManager``.
    """
    input_specs = list(request.specs)
    components = build_model_components(
        input_specs, repository_db=repository_db, install_mcs=request.install_mcs
    )
    manager = ModelComponentManager(
        repository_db=repository_db,
        attribute_defaults_config=request.attribute_defaults_config,
        console=console,
    )
    manager.build_dependency_graph(components, install_mcs=request.install_mcs)
    dependency_graph = manager.dg
    if dependency_graph is None:
        raise RuntimeError("Dependency graph was not generated.")

    errors, experiment_graph = manager.build_experiment_graph_result(
        dry_run=request.dry_run, upload_files=request.upload_files
    )
    execution = [ModelComponentExecutionRecord.from_record(record) for record in errors]
    ordered_components = manager.get_ordered_model_component_list()
    grouped_components = dict(dependency_graph.get_ordered_entity_list_with_grouping())
    described_components = [
        mc.describe(grouping=grouped_components.get(mc)) for mc in ordered_components
    ]
    dependency_graph_json = dependency_graph.get_graph_json()
    provenance: Provenance = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_specs": [_describe_model_component_input(spec) for spec in input_specs],
        "install_mcs": request.install_mcs,
        "dry_run": request.dry_run,
        "upload_files": request.upload_files,
        "resolved_order": [mc.name for mc in ordered_components],
        "model_components": described_components,
        "execution": [asdict(record) for record in execution],
        "dependency_graph_json": dependency_graph_json,
    }

    if experiment_graph is not None:
        provenance["graph_summary"] = {
            "vertices": len(list(experiment_graph.get_vertices())),
            "edges": len(list(experiment_graph.get_edges())),
        }

    return ExperimentBuildResult(
        request=request,
        experiment_graph=experiment_graph,
        model_components=described_components,
        ordered_model_components=ordered_components,
        dependency_graph=dependency_graph,
        dependency_graph_json=dependency_graph_json,
        execution=execution,
        provenance=provenance,
    )


def _describe_request(request: ExperimentBuildRequest) -> dict[str, Any]:
    """Return a serializable description of a build request."""
    return {
        "specs": [_describe_model_component_input(spec) for spec in request.specs],
        "install_mcs": request.install_mcs,
        "dry_run": request.dry_run,
        "upload_files": request.upload_files,
        "attribute_defaults_config": request.attribute_defaults_config,
    }


def _describe_model_component_input(spec: ModelComponentInput) -> dict[str, Any]:
    """Return a serializable description of a model component input."""
    if isinstance(spec, str):
        return ModelComponentSpec.from_args(spec).describe()
    if isinstance(spec, ModelComponentSpec):
        return spec.describe()
    if isinstance(spec, ModelComponent):
        return dict(spec.describe())
    return {"type": type(spec).__name__, "value": repr(spec)}
