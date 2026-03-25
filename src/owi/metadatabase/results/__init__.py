"""Results extension for OWI Metadatabase SDK."""

from .analyses import (
    BaseAnalysis,
    CeitMeasurement,
    LifetimeDesignFrequencies,
    LifetimeDesignVerification,
    WindSpeedHistogram,
    load_ceit_measurements,
)
from .endpoints import DEFAULT_RESULTS_ENDPOINTS, ResultsEndpoints
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
from .plotting.ceit import plot_ceit_analyses
from .plotting.frequency import (
    plot_lifetime_design_frequencies_by_location,
    plot_lifetime_design_frequencies_geo,
)
from .protocols import AnalysisProtocol, PlotStrategyProtocol, ResultProtocol
from .registry import AnalysisRegistry, default_registry, register_analysis
from .services import CeitResultsService, ResultsService, get_results, plot_results

__version__ = "0.1.1"

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
