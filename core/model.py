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


NU_GRID = np.geomspace(2.05, 50.0, 25)
EM_STEPS = 50


def fit_baselines(returns):
    """Student-t MLE for many series at once: rows of `returns` are series.

    For each nu on NU_GRID, EM finds mu and sigma; the nu with the highest
    likelihood wins. Vectorised so 600 fits take about a second, which keeps
    re-simulation tuning usable in the browser (Pyodide). Returns (mu, sigma, nu) arrays.
    """
    x = np.atleast_2d(np.asarray(returns, dtype=float))[None]  # (1, n, m)
    nu = NU_GRID[:, None, None]  # (g, 1, 1)
    med = np.median(x, -1, keepdims=True)
    mad = 1.4826 * np.median(np.abs(x - med), -1, keepdims=True)
    floor = 1e-8
    mu = np.broadcast_to(med, (len(NU_GRID),) + med.shape[1:]).copy()
    sigma = np.broadcast_to(np.maximum(mad, floor), mu.shape).copy()
    for _ in range(EM_STEPS):
        w = (nu + 1) / (nu + ((x - mu) / sigma) ** 2)
        mu = (w * x).sum(-1, keepdims=True) / w.sum(-1, keepdims=True)
        sigma = np.maximum(np.sqrt((w * (x - mu) ** 2).mean(-1, keepdims=True)), floor)
    loglik = stats.t.logpdf(x, nu, mu, sigma).sum(-1)  # (g, n)
    best = np.argmax(loglik, 0)
    cols = np.arange(x.shape[1])
    return mu[best, cols, 0], sigma[best, cols, 0], NU_GRID[best]


def fit_baseline(returns) -> Baseline:
    mu, sigma, nu = fit_baselines(np.asarray(returns, dtype=float)[None])
    return Baseline(mu=float(mu[0]), sigma=float(sigma[0]), nu=float(nu[0]))


def log_likelihood_ratio(returns, base: Baseline, k: float = K_BROKEN) -> np.ndarray:
    """Per-day log(pdf_broken(r) / pdf_healthy(r)). Same sigma and nu, so the scale term cancels."""
    r = np.asarray(returns, dtype=float)
    mu_broken = -k * abs(base.mu)
    return stats.t.logpdf((r - mu_broken) / base.sigma, base.nu) - stats.t.logpdf(
        (r - base.mu) / base.sigma, base.nu
    )
