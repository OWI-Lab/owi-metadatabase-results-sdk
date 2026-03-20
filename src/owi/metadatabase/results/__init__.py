"""Results extension for OWI Metadatabase SDK."""

from .analyses import BaseAnalysis, LifetimeDesignFrequencies, LifetimeDesignVerification, WindSpeedHistogram
from .ceit import CeitMeasurement, CeitResultsService, load_ceit_measurements, plot_ceit_analyses
from .endpoints import DEFAULT_RESULTS_ENDPOINTS, ResultsEndpoints
from .frequency_plots import (
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_geo,
)
from .io import ResultsAPI
from .models import (
    AnalysisDefinition,
    AnalysisKind,
    PlotRequest,
    PlotResponse,
    RelatedObject,
    ResultQuery,
    ResultScope,
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
    "AnalysisKind",
    "AnalysisProtocol",
    "AnalysisRegistry",
    "BaseAnalysis",
    "CeitMeasurement",
    "CeitResultsService",
    "HistogramPlotStrategy",
    "LifetimeDesignFrequencies",
    "LifetimeDesignVerification",
    "PlotRequest",
    "PlotResponse",
    "PlotStrategyProtocol",
    "RelatedObject",
    "ResultProtocol",
    "ResultQuery",
    "ResultScope",
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
    "load_ceit_measurements",
    "plot_results",
    "plot_ceit_analyses",
    "plot_lifetime_design_frequencies_by_location",
    "plot_lifetime_design_frequencies_geo",
    "register_analysis",
]
