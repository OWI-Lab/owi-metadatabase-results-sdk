"""Results extension for OWI Metadatabase SDK."""

from .analyses import BaseAnalysis, LifetimeDesignFrequencies, LifetimeDesignVerification, WindSpeedHistogram
from .endpoints import DEFAULT_RESULTS_ENDPOINTS, ResultsEndpoints
from .io import ResultsAPI
from .models import (
    AnalysisDefinition,
    PlotRequest,
    PlotResponse,
    RelatedObject,
    ResultQuery,
    ResultSeries,
    ResultVector,
)
from .plotting import HistogramPlotStrategy, TimeSeriesPlotStrategy
from .protocols import AnalysisProtocol, PlotStrategyProtocol, ResultProtocol
from .registry import AnalysisRegistry, default_registry, register_analysis
from .services import ResultsService, get_results, plot_results

__version__ = "0.1.0"

__all__ = [
    "AnalysisDefinition",
    "AnalysisProtocol",
    "AnalysisRegistry",
    "BaseAnalysis",
    "HistogramPlotStrategy",
    "LifetimeDesignFrequencies",
    "LifetimeDesignVerification",
    "PlotRequest",
    "PlotResponse",
    "PlotStrategyProtocol",
    "RelatedObject",
    "ResultProtocol",
    "ResultQuery",
    "ResultsEndpoints",
    "ResultSeries",
    "ResultVector",
    "ResultsAPI",
    "ResultsService",
    "TimeSeriesPlotStrategy",
    "WindSpeedHistogram",
    "__version__",
    "DEFAULT_RESULTS_ENDPOINTS",
    "default_registry",
    "get_results",
    "plot_results",
    "register_analysis",
]
