"""Registry for custom plot definitions."""

from __future__ import annotations

from .definitions import PlotDefinition
from .frequency_verification import build_frequency_verification_plot_definition

_registry: dict[str, PlotDefinition] = {}


def register_plot_definition(definition: PlotDefinition) -> PlotDefinition:
    """Register a plot definition by its public plot type."""
    _registry[definition.plot_type] = definition
    return definition


def get_plot_definition(plot_type: str | None, analysis_name: str | None = None) -> PlotDefinition | None:
    """Return the plot definition for the given plot type."""
    if plot_type is None:
        return None
    definition = _registry.get(plot_type)
    if definition is None:
        return None
    if analysis_name is not None and analysis_name not in definition.supported_analysis_names:
        supported = ", ".join(sorted(definition.supported_analysis_names))
        raise ValueError(
            f"Plot type {plot_type!r} does not support analysis {analysis_name!r}. "
            f"Supported analyses: {supported}."
        )
    return definition


register_plot_definition(build_frequency_verification_plot_definition())
