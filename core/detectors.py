"""The three detectors, each as a vectorised one-day step.

The same step drives both the display series (one strategy, no restarts) and the
kill-rule simulator in evaluate.py (many strategies x thresholds, with restarts),
so the two can never disagree.
"""
from dataclasses import dataclass

import numpy as np
from scipy.special import expit


def hazard(years: float) -> float:
    return 1.0 / (252.0 * years)


@dataclass(frozen=True)
class Bayes:
    """Posterior probability the strategy is broken, with a constant daily break hazard."""

    hazard_years: float

    def init(self, shape):
        return np.zeros(shape)

    def step(self, p, r, llr):
        h = hazard(self.hazard_years)
        prior = p + (1 - p) * h
        with np.errstate(divide="ignore"):
            log_odds = np.log(prior) - np.log1p(-prior) + llr
        p = expit(log_odds)
        return p, p

    def fires(self, stat, threshold):
        return stat >= threshold


@dataclass(frozen=True)
class Cusum:
    """S = max(0, S + log L)."""

    def init(self, shape):
        return np.zeros(shape)

    def step(self, s, r, llr):
        s = np.maximum(0.0, s + llr)
        return s, s

    def fires(self, stat, threshold):
        return stat > threshold


@dataclass(frozen=True)
class Drawdown:
    """Current drawdown of cumulative (additive) PnL, in units of daily sigma."""

    sigma: object  # float, or array broadcast against the strategy axis

    def init(self, shape):
        return np.zeros(shape), np.zeros(shape)

    def step(self, state, r, llr):
        cum, peak = state
        cum = cum + r
        peak = np.maximum(peak, cum)
        return (cum, peak), (peak - cum) / self.sigma

    def fires(self, stat, threshold):
        return stat > threshold


def run_series(detector, returns, llr) -> np.ndarray:
    """Run a detector with no restarts. Arrays are (..., n_days); output has the same shape."""
    returns = np.asarray(returns, dtype=float)
    llr = np.asarray(llr, dtype=float)
    state = detector.init(returns.shape[:-1])
    out = np.empty(returns.shape)
    for t in range(returns.shape[-1]):
        state, out[..., t] = detector.step(state, returns[..., t], llr[..., t])
    return out


def bayes_probability(llr, hazard_years: float) -> np.ndarray:
    llr = np.asarray(llr, dtype=float)
    return run_series(Bayes(hazard_years), np.zeros_like(llr), llr)


def cusum(llr) -> np.ndarray:
    llr = np.asarray(llr, dtype=float)
    return run_series(Cusum(), np.zeros_like(llr), llr)


def drawdown_depth(returns, sigma: float) -> np.ndarray:
    returns = np.asarray(returns, dtype=float)
    return run_series(Drawdown(sigma), returns, np.zeros_like(returns))
