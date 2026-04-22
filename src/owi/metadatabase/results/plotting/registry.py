"""Registry for custom plot definitions."""

from __future__ import annotations

from .definitions import PlotDefinition
from .frequency_verification import build_frequency_verification_plot_definition

_registry: dict[tuple[str, str], PlotDefinition] = {}


def register_plot_definition(definition: PlotDefinition) -> PlotDefinition:
    """Register a plot definition for each owner-analysis alias."""
    for owner_analysis_name in definition.owner_analysis_names:
        _registry[(owner_analysis_name, definition.plot_type)] = definition
    return definition


def get_plot_definition(analysis_name: str, plot_type: str | None) -> PlotDefinition | None:
    """Return the plot definition for the given owner and plot type."""
    if plot_type is None:
        return None
    return _registry.get((analysis_name, plot_type))


register_plot_definition(build_frequency_verification_plot_definition())
