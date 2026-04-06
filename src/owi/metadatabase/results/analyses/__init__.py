"""Built-in analyses for the results extension."""

from .base import BaseAnalysis
from .ceit import CorrosionMonitoring as CeitCorrosionMonitoring
from .lifetime_design_frequencies import LifetimeDesignFrequencies
from .lifetime_design_verification import LifetimeDesignVerification
from .wind_speed_histogram import WindSpeedHistogram

__all__ = [
    "BaseAnalysis",
    "CeitCorrosionMonitoring",
    "LifetimeDesignFrequencies",
    "LifetimeDesignVerification",
    "WindSpeedHistogram",
]
