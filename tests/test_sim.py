import numpy as np

from core.sim import N_DAYS, WARMUP, MU, simulate


def test_three_equal_groups_and_shape():
    s = simulate(300, seed=1)
    assert s.returns.shape == (300, N_DAYS)
    assert [int((s.kind == k).sum()) for k in ("healthy", "sudden", "decay")] == [100, 100, 100]


def test_same_seed_same_data_different_seed_different_data():
    assert np.array_equal(simulate(30, seed=1).returns, simulate(30, seed=1).returns)
    assert not np.array_equal(simulate(30, seed=1).returns, simulate(30, seed=2).returns)


def test_healthy_never_breaks():
    s = simulate(60, seed=1)
    h = s.kind == "healthy"
    assert np.all(s.break_day[h] == N_DAYS)
    assert np.allclose(s.mean[h], MU)


def test_breaks_happen_after_warmup():
    s = simulate(300, seed=1)
    b = s.break_day[s.kind != "healthy"]
    assert b.min() > WARMUP and b.max() < N_DAYS
    assert np.allclose(s.mean[:, :WARMUP], MU)


def test_sudden_mean_flips_at_break():
    s = simulate(60, seed=1)
    i = np.flatnonzero(s.kind == "sudden")[0]
    b = s.break_day[i]
    assert np.allclose(s.mean[i, :b], MU) and np.allclose(s.mean[i, b:], -MU)


def test_decay_slides_over_120_days_and_break_is_zero_crossing():
    s = simulate(60, seed=1)
    i = np.flatnonzero(s.kind == "decay")[0]
    m, b = s.mean[i], s.break_day[i]
    start = b - 60
    assert np.isclose(m[start], MU) and np.allclose(m[: start + 1], MU)
    assert m[b - 1] > 0 >= m[b]
    assert np.allclose(m[start + 120 :], -MU)
    assert np.allclose(np.diff(m[start : start + 121]), -2 * MU / 120)
