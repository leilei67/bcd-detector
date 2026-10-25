import numpy as np
from scipy import stats

from core.model import fit_baseline, log_likelihood_ratio
from core.detectors import bayes_probability, cusum, drawdown_depth

MU, SIGMA, NU = 0.0015, 0.008, 4.0  # annual Sharpe ~2.1, matches core.sim


def make_returns(n=750, break_day=None, seed=0):
    r = MU + SIGMA * stats.t.rvs(NU, size=n, random_state=np.random.default_rng(seed))
    if break_day is not None:
        r[break_day:] -= 2 * MU
    return r


def bayes_after_warmup(r, years=2):
    base = fit_baseline(r[:250])
    return bayes_probability(log_likelihood_ratio(r[250:], base), hazard_years=years)


def test_fit_baseline_recovers_known_parameters():
    base = fit_baseline(make_returns(n=20000))
    assert abs(base.mu - MU) < 0.0003
    assert abs(base.sigma - SIGMA) / SIGMA < 0.05
    assert 3.0 < base.nu < 5.5


def test_bayes_probability_with_uninformative_days_is_pure_hazard():
    # L = 1 every day, so p_n = 1 - (1 - h)^n
    h = 1 / (252 * 2)
    p = bayes_probability(np.zeros(100), hazard_years=2)
    assert np.allclose(p, 1 - (1 - h) ** np.arange(1, 101))


def test_bayes_probability_one_step_worked_example():
    # p0 = 0 -> p_prior = h; L = e; p = h*e / (h*e + 1 - h)
    h = 1 / 252
    p = bayes_probability(np.array([1.0]), hazard_years=1)
    assert np.isclose(p[0], h * np.e / (h * np.e + 1 - h))


def test_p_rises_after_break():
    p = bayes_after_warmup(make_returns(break_day=450, seed=3))
    before, after = p[: 450 - 250], p[-100:]
    assert before.mean() < 0.2
    assert after.mean() > 0.6


def test_p_stays_low_on_healthy_strategies():
    # One healthy path is noisy, so judge the group: low on average, rarely high.
    ps = np.array([bayes_after_warmup(make_returns(seed=seed)) for seed in range(20)])
    assert ps.mean() < 0.2
    assert (ps > 0.5).mean() < 0.1


def test_cusum_worked_example():
    assert np.allclose(cusum(np.array([1.0, -0.5, -1.0, 2.0])), [1.0, 0.5, 0.0, 2.0])


def test_cusum_never_negative():
    r = make_returns(break_day=450, seed=1)
    s = cusum(log_likelihood_ratio(r[250:], fit_baseline(r[:250])))
    assert s.min() >= 0


def test_drawdown_depth_worked_example():
    depth = drawdown_depth(np.array([0.01, -0.02, -0.01, 0.03]), sigma=0.01)
    assert np.allclose(depth, [0.0, 2.0, 3.0, 0.0])


def test_p_rises_after_break_on_demo_strategy():
    from core.sim import demo_strategy

    p = bayes_after_warmup(demo_strategy(break_day=450))
    assert p[: 450 - 250].mean() < 0.2
    assert p[-100:].mean() > 0.6
