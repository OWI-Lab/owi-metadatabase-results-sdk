"""Generic plot definition types for custom plotting workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from ..models import PlotRequest, PlotResponse, ResultQuery, ResultSeries


@dataclass(frozen=True)
class PlotSourceSpec:
    """Declarative definition of one named source used by a plot."""

    key: str
    analysis_name: str
    build_query: Callable[[ResultQuery, str], ResultQuery]


@dataclass(frozen=True)
class PlotSourceData:
    """Fetched and normalized data for one named plot source."""

    key: str
    analysis_name: str
    query: ResultQuery
    records: Sequence[ResultSeries]
    frame: pd.DataFrame


@dataclass(frozen=True)
class PlotDefinition:
    """Declarative definition of a registered custom plot."""

    owner_analysis_names: tuple[str, ...]
    plot_type: str
    build_sources: Callable[[ResultQuery, str], Sequence[PlotSourceSpec]]
    render: Callable[[Mapping[str, PlotSourceData], PlotRequest], PlotResponse]
