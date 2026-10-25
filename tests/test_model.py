import numpy as np
from scipy import stats

from core.model import fit_baseline, fit_baselines


def t_samples(n, m, seed, mu=0.0015, scale=0.008, nu=4.0):
    return mu + scale * np.random.default_rng(seed).standard_t(nu, size=(n, m))


def test_batch_fit_is_at_least_as_likely_as_scipy_mle():
    # Independent truth: scipy's own MLE. Ours may land on a nu grid point, so allow a hair of slack.
    x = t_samples(20, 250, seed=5)
    mu, sigma, nu = fit_baselines(x)
    for i in range(20):
        ours = stats.t.logpdf(x[i], nu[i], mu[i], sigma[i]).sum()
        nu_s, mu_s, sc_s = stats.t.fit(x[i])
        assert ours >= stats.t.logpdf(x[i], nu_s, mu_s, sc_s).sum() - 0.5


def test_single_fit_matches_batch_row():
    x = t_samples(3, 250, seed=6)
    mu, sigma, nu = fit_baselines(x)
    b = fit_baseline(x[1])
    assert np.isclose(b.mu, mu[1]) and np.isclose(b.sigma, sigma[1]) and np.isclose(b.nu, nu[1])


def test_constant_series_does_not_crash():
    mu, sigma, nu = fit_baselines(np.zeros((1, 250)))
    assert np.all(np.isfinite([mu, sigma, nu])) and sigma[0] > 0
