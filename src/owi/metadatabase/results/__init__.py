"""Results extension for OWI Metadatabase SDK."""

from .analyses import (
    BaseAnalysis,
    LifetimeDesignFrequencies,
    LifetimeDesignVerification,
    WindSpeedHistogram,
)
from .endpoints import DEFAULT_RESULTS_ENDPOINTS, ResultsEndpoints
from .io import ResultsAPI

__version__ = "0.2.1"

__all__ = [
    "BaseAnalysis",
    "LifetimeDesignFrequencies",
    "LifetimeDesignVerification",
    "ResultsEndpoints",
    "ResultsAPI",
    "WindSpeedHistogram",
    "__version__",
    "DEFAULT_RESULTS_ENDPOINTS",
]
