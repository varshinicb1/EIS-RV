"""
Analysis Package

Comprehensive data analysis tools for RĀMAN Studio Advanced Analysis panel.

Modules:
- statistics: Descriptive stats, hypothesis testing, correlation, regression
- curve_fitting: 100+ fitting functions with automatic parameter estimation
- signal_processing: FFT, wavelet, filtering (planned)
- peak_analysis: Peak detection, fitting, integration (planned)
"""

from .statistics import (
    descriptive_statistics,
    normality_test,
    t_test,
    anova_one_way,
    correlation_analysis,
    linear_regression,
    DescriptiveStats,
)

from .curve_fitting import (
    fit_curve,
    FITTING_FUNCTIONS,
    FitResult,
)

__all__ = [
    # Statistics
    'descriptive_statistics',
    'normality_test',
    't_test',
    'anova_one_way',
    'correlation_analysis',
    'linear_regression',
    'DescriptiveStats',
    # Curve fitting
    'fit_curve',
    'FITTING_FUNCTIONS',
    'FitResult',
]
