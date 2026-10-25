"""Healthy vs broken return models: a Student-t fitted to the known-healthy warm-up."""
from dataclasses import dataclass

import numpy as np
from scipy import stats

K_BROKEN = 1.0  # broken mean = -K_BROKEN * |mu|


@dataclass(frozen=True)
class Baseline:
    mu: float
    sigma: float
    nu: float


def fit_baseline(returns) -> Baseline:
    nu, mu, sigma = stats.t.fit(np.asarray(returns, dtype=float))
    return Baseline(mu=float(mu), sigma=float(sigma), nu=float(nu))


def log_likelihood_ratio(returns, base: Baseline, k: float = K_BROKEN) -> np.ndarray:
    """Per-day log(pdf_broken(r) / pdf_healthy(r)). Same sigma and nu, so the scale term cancels."""
    r = np.asarray(returns, dtype=float)
    mu_broken = -k * abs(base.mu)
    return stats.t.logpdf((r - mu_broken) / base.sigma, base.nu) - stats.t.logpdf(
        (r - base.mu) / base.sigma, base.nu
    )
