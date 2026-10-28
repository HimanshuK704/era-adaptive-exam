"""Small, dependency-light Rasch/1PL model and grid-based Bayesian EAP update."""
from __future__ import annotations

import math
import numpy as np


def logistic(value: float | np.ndarray) -> float | np.ndarray:
    """Numerically stable logistic function."""
    x = np.asarray(value, dtype=float)
    out = np.empty_like(x)
    positive = x >= 0
    out[positive] = 1.0 / (1.0 + np.exp(-x[positive]))
    exp_x = np.exp(x[~positive])
    out[~positive] = exp_x / (1.0 + exp_x)
    if out.ndim == 0:
        return float(out)
    return out


def probability_correct(theta: float | np.ndarray, difficulty: float) -> float | np.ndarray:
    return logistic(np.asarray(theta) - difficulty)


def fisher_information(theta: float, difficulty: float) -> float:
    p = float(probability_correct(theta, difficulty))
    return p * (1.0 - p)


def eap_update(
    prior_theta: float,
    prior_sd: float,
    difficulty: float,
    correct: bool,
    *,
    grid_min: float = -4.0,
    grid_max: float = 4.0,
    grid_points: int = 1601,
) -> tuple[float, float]:
    """Return posterior mean (EAP) and posterior standard deviation.

    Uses a normal prior and a bounded numerical grid. This is intentionally
    transparent and suitable for a prototype, not a substitute for validation.
    """
    if prior_sd <= 0:
        raise ValueError("prior_sd must be positive")
    if grid_points < 101:
        raise ValueError("grid_points must be at least 101")
    grid = np.linspace(grid_min, grid_max, grid_points)
    prior_log = -0.5 * ((grid - prior_theta) / prior_sd) ** 2 - math.log(prior_sd)
    p = np.clip(probability_correct(grid, difficulty), 1e-12, 1.0 - 1e-12)
    likelihood_log = np.log(p) if correct else np.log1p(-p)
    log_weights = prior_log + likelihood_log
    log_weights -= np.max(log_weights)
    weights = np.exp(log_weights)
    total = float(weights.sum())
    if not math.isfinite(total) or total <= 0:
        raise ArithmeticError("posterior normalization failed")
    weights /= total
    mean = float(np.sum(grid * weights))
    variance = float(np.sum(((grid - mean) ** 2) * weights))
    return mean, math.sqrt(max(variance, 0.0))
