"""Built-in analyses for the results extension."""

from .base import BaseAnalysis
from .ceit import (
    CEIT_ANALYSIS_PREFIX,
    CEIT_METRICS,
    CeitMeasurement,
    _sanitize_json_text,
    ceit_frame_from_measurements,
    load_ceit_measurements,
)
from .lifetime_design_frequencies import LifetimeDesignFrequencies
from .lifetime_design_verification import LifetimeDesignVerification
from .wind_speed_histogram import WindSpeedHistogram

__all__ = [
    "BaseAnalysis",
    "CEIT_ANALYSIS_PREFIX",
    "CEIT_METRICS",
    "CeitMeasurement",
    "LifetimeDesignFrequencies",
    "LifetimeDesignVerification",
    "WindSpeedHistogram",
    "_sanitize_json_text",
    "ceit_frame_from_measurements",
    "load_ceit_measurements",
]
