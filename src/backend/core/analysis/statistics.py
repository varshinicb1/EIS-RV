"""
Statistical Analysis Module

Comprehensive statistical analysis tools for RĀMAN Studio Advanced Analysis panel.
Provides descriptive statistics, hypothesis testing, correlation, and regression analysis.

OriginLab feature parity:
- Descriptive statistics (mean, std, quartiles, etc.)
- Normality tests (Shapiro-Wilk, Kolmogorov-Smirnov)
- Hypothesis testing (t-test, ANOVA, chi-square)
- Correlation analysis (Pearson, Spearman, Kendall)
- Linear and nonlinear regression
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DescriptiveStats:
    """Descriptive statistics results"""
    n: int
    mean: float
    std: float
    variance: float
    sem: float  # Standard error of mean
    median: float
    q1: float  # 25th percentile
    q3: float  # 75th percentile
    iqr: float  # Interquartile range
    min: float
    max: float
    range: float
    skewness: float
    kurtosis: float
    cv: float  # Coefficient of variation (%)
    mad: float  # Median absolute deviation
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'n': self.n,
            'mean': self.mean,
            'std': self.std,
            'variance': self.variance,
            'sem': self.sem,
            'median': self.median,
            'q1': self.q1,
            'q3': self.q3,
            'iqr': self.iqr,
            'min': self.min,
            'max': self.max,
            'range': self.range,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
            'cv': self.cv,
            'mad': self.mad,
        }


def descriptive_statistics(data: List[float]) -> DescriptiveStats:
    """
    Calculate comprehensive descriptive statistics.
    
    Args:
        data: List of numeric values
    
    Returns:
        DescriptiveStats object with all statistics
    """
    arr = np.array(data)
    n = len(arr)
    
    if n == 0:
        raise ValueError("Cannot compute statistics on empty data")
    
    # Basic statistics
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)  # Sample standard deviation
    variance = np.var(arr, ddof=1)
    sem = std / np.sqrt(n)
    
    # Percentiles
    median = np.median(arr)
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1
    
    # Range
    min_val = np.min(arr)
    max_val = np.max(arr)
    range_val = max_val - min_val
    
    # Shape statistics
    skewness = stats.skew(arr)
    kurtosis = stats.kurtosis(arr)
    
    # Coefficient of variation
    cv = (std / mean * 100) if mean != 0 else 0
    
    # Median absolute deviation
    mad = np.median(np.abs(arr - median))
    
    return DescriptiveStats(
        n=n,
        mean=mean,
        std=std,
        variance=variance,
        sem=sem,
        median=median,
        q1=q1,
        q3=q3,
        iqr=iqr,
        min=min_val,
        max=max_val,
        range=range_val,
        skewness=skewness,
        kurtosis=kurtosis,
        cv=cv,
        mad=mad,
    )


def normality_test(data: List[float]) -> Dict[str, Any]:
    """
    Test for normality using multiple methods.
    
    Args:
        data: List of numeric values
    
    Returns:
        Dictionary with test results
    """
    arr = np.array(data)
    
    # Shapiro-Wilk test (best for n < 5000)
    shapiro_stat, shapiro_p = stats.shapiro(arr)
    
    # Kolmogorov-Smirnov test
    ks_stat, ks_p = stats.kstest(arr, 'norm', args=(np.mean(arr), np.std(arr)))
    
    # Anderson-Darling test
    anderson_result = stats.anderson(arr, dist='norm')
    
    # D'Agostino-Pearson test
    dagostino_stat, dagostino_p = stats.normaltest(arr)
    
    return {
        'shapiro_wilk': {
            'statistic': float(shapiro_stat),
            'p_value': float(shapiro_p),
            'is_normal': shapiro_p > 0.05,
        },
        'kolmogorov_smirnov': {
            'statistic': float(ks_stat),
            'p_value': float(ks_p),
            'is_normal': ks_p > 0.05,
        },
        'anderson_darling': {
            'statistic': float(anderson_result.statistic),
            'critical_values': anderson_result.critical_values.tolist(),
            'significance_levels': anderson_result.significance_level.tolist(),
        },
        'dagostino_pearson': {
            'statistic': float(dagostino_stat),
            'p_value': float(dagostino_p),
            'is_normal': dagostino_p > 0.05,
        },
        'recommendation': 'Data appears normally distributed' if shapiro_p > 0.05 else 'Data may not be normally distributed',
    }


def t_test(
    group1: List[float],
    group2: Optional[List[float]] = None,
    mu: float = 0.0,
    alternative: str = 'two-sided',
) -> Dict[str, Any]:
    """
    Perform t-test (one-sample, two-sample, or paired).
    
    Args:
        group1: First group of data
        group2: Second group of data (None for one-sample test)
        mu: Population mean for one-sample test
        alternative: 'two-sided', 'less', or 'greater'
    
    Returns:
        Dictionary with test results
    """
    arr1 = np.array(group1)
    
    if group2 is None:
        # One-sample t-test
        t_stat, p_value = stats.ttest_1samp(arr1, mu, alternative=alternative)
        test_type = 'one-sample'
        df = len(arr1) - 1
    else:
        arr2 = np.array(group2)
        # Two-sample t-test (independent)
        t_stat, p_value = stats.ttest_ind(arr1, arr2, alternative=alternative)
        test_type = 'two-sample'
        df = len(arr1) + len(arr2) - 2
    
    # Effect size (Cohen's d)
    if group2 is not None:
        pooled_std = np.sqrt(((len(arr1) - 1) * np.var(arr1, ddof=1) + 
                              (len(arr2) - 1) * np.var(arr2, ddof=1)) / df)
        cohens_d = (np.mean(arr1) - np.mean(arr2)) / pooled_std
    else:
        cohens_d = (np.mean(arr1) - mu) / np.std(arr1, ddof=1)
    
    return {
        'test_type': test_type,
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'degrees_of_freedom': int(df),
        'cohens_d': float(cohens_d),
        'significant': p_value < 0.05,
        'alternative': alternative,
        'interpretation': _interpret_t_test(p_value, cohens_d),
    }


def anova_one_way(*groups: List[float]) -> Dict[str, Any]:
    """
    Perform one-way ANOVA.
    
    Args:
        *groups: Variable number of groups to compare
    
    Returns:
        Dictionary with ANOVA results
    """
    if len(groups) < 2:
        raise ValueError("ANOVA requires at least 2 groups")
    
    # Convert to numpy arrays
    arrays = [np.array(g) for g in groups]
    
    # One-way ANOVA
    f_stat, p_value = stats.f_oneway(*arrays)
    
    # Calculate effect size (eta-squared)
    grand_mean = np.mean(np.concatenate(arrays))
    ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in arrays)
    ss_total = sum(np.sum((g - grand_mean)**2) for g in arrays)
    eta_squared = ss_between / ss_total if ss_total > 0 else 0
    
    # Degrees of freedom
    df_between = len(groups) - 1
    df_within = sum(len(g) for g in arrays) - len(groups)
    
    return {
        'f_statistic': float(f_stat),
        'p_value': float(p_value),
        'df_between': int(df_between),
        'df_within': int(df_within),
        'eta_squared': float(eta_squared),
        'significant': p_value < 0.05,
        'num_groups': len(groups),
        'interpretation': _interpret_anova(p_value, eta_squared),
    }


def correlation_analysis(
    x: List[float],
    y: List[float],
    method: str = 'pearson',
) -> Dict[str, Any]:
    """
    Calculate correlation between two variables.
    
    Args:
        x: First variable
        y: Second variable
        method: 'pearson', 'spearman', or 'kendall'
    
    Returns:
        Dictionary with correlation results
    """
    arr_x = np.array(x)
    arr_y = np.array(y)
    
    if len(arr_x) != len(arr_y):
        raise ValueError("x and y must have the same length")
    
    if method == 'pearson':
        corr, p_value = stats.pearsonr(arr_x, arr_y)
    elif method == 'spearman':
        corr, p_value = stats.spearmanr(arr_x, arr_y)
    elif method == 'kendall':
        corr, p_value = stats.kendalltau(arr_x, arr_y)
    else:
        raise ValueError(f"Unknown correlation method: {method}")
    
    # Coefficient of determination
    r_squared = corr ** 2
    
    return {
        'method': method,
        'correlation': float(corr),
        'p_value': float(p_value),
        'r_squared': float(r_squared),
        'significant': p_value < 0.05,
        'n': len(arr_x),
        'interpretation': _interpret_correlation(corr, p_value),
    }


def linear_regression(
    x: List[float],
    y: List[float],
) -> Dict[str, Any]:
    """
    Perform linear regression analysis.
    
    Args:
        x: Independent variable
        y: Dependent variable
    
    Returns:
        Dictionary with regression results
    """
    arr_x = np.array(x)
    arr_y = np.array(y)
    
    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(arr_x, arr_y)
    
    # Predictions
    y_pred = slope * arr_x + intercept
    
    # Residuals
    residuals = arr_y - y_pred
    
    # Sum of squares
    ss_total = np.sum((arr_y - np.mean(arr_y))**2)
    ss_residual = np.sum(residuals**2)
    ss_regression = ss_total - ss_residual
    
    # Mean squared error
    mse = ss_residual / (len(arr_y) - 2)
    rmse = np.sqrt(mse)
    
    # F-statistic
    f_stat = (ss_regression / 1) / (ss_residual / (len(arr_y) - 2))
    
    return {
        'slope': float(slope),
        'intercept': float(intercept),
        'r_value': float(r_value),
        'r_squared': float(r_value**2),
        'p_value': float(p_value),
        'std_err': float(std_err),
        'rmse': float(rmse),
        'f_statistic': float(f_stat),
        'equation': f'y = {slope:.4f}x + {intercept:.4f}',
        'predictions': y_pred.tolist(),
        'residuals': residuals.tolist(),
        'significant': p_value < 0.05,
        'interpretation': _interpret_regression(r_value**2, p_value),
    }


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _interpret_t_test(p_value: float, cohens_d: float) -> str:
    """Generate interpretation for t-test results"""
    if p_value >= 0.05:
        return "No significant difference detected (p ≥ 0.05)"
    
    effect_size = abs(cohens_d)
    if effect_size < 0.2:
        effect = "negligible"
    elif effect_size < 0.5:
        effect = "small"
    elif effect_size < 0.8:
        effect = "medium"
    else:
        effect = "large"
    
    return f"Significant difference detected (p < 0.05) with {effect} effect size (d = {cohens_d:.3f})"


def _interpret_anova(p_value: float, eta_squared: float) -> str:
    """Generate interpretation for ANOVA results"""
    if p_value >= 0.05:
        return "No significant difference between groups (p ≥ 0.05)"
    
    if eta_squared < 0.01:
        effect = "negligible"
    elif eta_squared < 0.06:
        effect = "small"
    elif eta_squared < 0.14:
        effect = "medium"
    else:
        effect = "large"
    
    return f"Significant difference between groups (p < 0.05) with {effect} effect size (η² = {eta_squared:.3f})"


def _interpret_correlation(corr: float, p_value: float) -> str:
    """Generate interpretation for correlation results"""
    if p_value >= 0.05:
        return "No significant correlation detected (p ≥ 0.05)"
    
    abs_corr = abs(corr)
    if abs_corr < 0.3:
        strength = "weak"
    elif abs_corr < 0.7:
        strength = "moderate"
    else:
        strength = "strong"
    
    direction = "positive" if corr > 0 else "negative"
    
    return f"Significant {strength} {direction} correlation (r = {corr:.3f}, p < 0.05)"


def _interpret_regression(r_squared: float, p_value: float) -> str:
    """Generate interpretation for regression results"""
    if p_value >= 0.05:
        return "Model is not statistically significant (p ≥ 0.05)"
    
    variance_explained = r_squared * 100
    
    if r_squared < 0.3:
        fit = "weak"
    elif r_squared < 0.7:
        fit = "moderate"
    else:
        fit = "strong"
    
    return f"Model shows {fit} fit (R² = {r_squared:.3f}), explaining {variance_explained:.1f}% of variance"
