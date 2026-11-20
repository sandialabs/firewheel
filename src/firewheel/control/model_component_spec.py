"""Helpers for turning user model component specs into objects."""

from typing import Any, TypeAlias
from dataclasses import field, dataclass
from collections.abc import Mapping, Iterable

from firewheel.control.model_component import ModelComponent

PluginArguments: TypeAlias = dict[str, Any]


class ModelComponentSpecError(ValueError):
    """Raised when a model component specification string is malformed."""


@dataclass(frozen=True)
class ModelComponentSpec:
    """A model component request with plugin arguments."""

    name: str
    plugin_args: PluginArguments = field(default_factory=dict)

    @classmethod
    def from_args(
        cls,
        name: str,
        positional: Iterable[str] | None = None,
        keyword: Mapping[str, Any] | None = None,
    ) -> "ModelComponentSpec":
        """Build a model component request from app-style argument blocks.

        Args:
            name (str): Model component name.
            positional (Iterable[str] | None): Positional plugin arguments.
            keyword (Mapping[str, Any] | None): Keyword plugin arguments.

        Returns:
            ModelComponentSpec: Model component request using FIREWHEEL's plugin
            argument convention.
        """
        plugin_args: PluginArguments = dict(keyword or {})
        if positional:
            plugin_args[""] = list(positional)
        return cls(name=name, plugin_args=plugin_args)

    def describe(self) -> dict[str, Any]:
        """Return a serializable description of this model component request."""
        return {"name": self.name, "plugin_args": dict(self.plugin_args)}


ModelComponentInput: TypeAlias = str | ModelComponentSpec | ModelComponent


def parse_model_component_spec(spec: str) -> ModelComponentSpec:
    """Parse a CLI-style model component specification.

    Args:
        spec (str): Model component spec, such as ``mc``, ``mc:arg``, or
            ``mc:key=value``.

    Returns:
        ModelComponentSpec: Parsed name and plugin arguments.

    Raises:
        ModelComponentSpecError: If a keyword argument is malformed.
    """
    parts = spec.split(":")
    name = parts[0]
    plugin_args: PluginArguments = {}
    positional_args: list[str] = []

    for arg in parts[1:]:
        arg_parts = arg.split("=")
        if len(arg_parts) == 1:
            positional_args.append(arg)
        elif len(arg_parts) == 2:
            plugin_args[arg_parts[0]] = arg_parts[1]
        else:
            raise ModelComponentSpecError(
                f"Malformed argument {arg!r} in model component spec {spec!r}."
            )

    if positional_args:
        plugin_args[""] = positional_args

    return ModelComponentSpec(name=name, plugin_args=plugin_args)


def build_model_components(
    specs: Iterable[ModelComponentInput],
    repository_db: Any = None,
    install_mcs: bool | None = False,
) -> list[ModelComponent]:
    """Build ``ModelComponent`` objects from specs or existing components."""
    components: list[ModelComponent] = []

    for spec in specs:
        if isinstance(spec, ModelComponent):
            components.append(spec)
            continue

        if isinstance(spec, str):
            parsed = parse_model_component_spec(spec)
        elif isinstance(spec, ModelComponentSpec):
            parsed = spec
        else:
            raise TypeError(
                "model component specs must be strings, ModelComponentSpec, "
                "or ModelComponent instances"
            )

        components.append(
            ModelComponent(
                name=parsed.name,
                repository_db=repository_db,
                arguments={"plugin": parsed.plugin_args},
                install=install_mcs,
            )
        )

    return components
