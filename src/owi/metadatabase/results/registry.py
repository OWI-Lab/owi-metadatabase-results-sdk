"""Analysis registry for the results extension."""

from __future__ import annotations

from .protocols import AnalysisProtocol


class AnalysisRegistry:
    """Simple in-process registry for analysis implementations."""

    def __init__(self) -> None:
        self._registry: dict[str, type[AnalysisProtocol]] = {}

    def register(self, analysis_type: type[AnalysisProtocol]) -> type[AnalysisProtocol]:
        """Register an analysis implementation by its public name."""
        self._registry[analysis_type.analysis_name] = analysis_type
        return analysis_type

    def get(self, analysis_name: str) -> AnalysisProtocol:
        """Instantiate the registered analysis implementation."""
        try:
            return self._registry[analysis_name]()
        except KeyError as exc:
            raise KeyError(f"Unknown analysis: {analysis_name}") from exc

    def names(self) -> list[str]:
        """Return registered analysis names."""
        return sorted(self._registry)


default_registry = AnalysisRegistry()


def register_analysis(analysis_type: type[AnalysisProtocol]) -> type[AnalysisProtocol]:
    """Register a built-in analysis implementation."""
    return default_registry.register(analysis_type)
