"""Base helpers for protocol-conforming analyses."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from ..models import PlotRequest, PlotResponse, ResultSeries
from ..plotting import get_plot_strategy
from ..protocols import PlotStrategyProtocol


class BaseAnalysis:
    """Convenience mixin for concrete protocol-conforming analyses."""

    analysis_name = "base"
    analysis_kind = "comparison"
    result_scope = "site"
    default_plot_type = "comparison"

    def validate_inputs(self, payload: Any) -> Any:
        """Return validated analysis inputs."""
        return payload

    def compute(self, payload: Any) -> pd.DataFrame:
        """Normalize validated input data."""
        raise NotImplementedError

    def to_results(self, payload: Any) -> list[ResultSeries]:
        """Convert payloads to persisted results."""
        raise NotImplementedError

    def from_results(self, results: Sequence[ResultSeries]) -> pd.DataFrame:
        """Convert stored results back to normalized data."""
        raise NotImplementedError

    def plot(
        self,
        results: Sequence[ResultSeries],
        request: PlotRequest | None = None,
        plot_strategy: PlotStrategyProtocol | None = None,
    ) -> PlotResponse:
        """Render results using the default plot strategy."""
        plot_request = request or PlotRequest(analysis_name=self.analysis_name)
        strategy = plot_strategy or get_plot_strategy(self.default_plot_type)
        data = self.from_results(results)
        return strategy.render(data, plot_request)
