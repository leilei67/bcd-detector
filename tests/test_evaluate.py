import numpy as np

from core.detectors import Cusum, Drawdown
from core.evaluate import run_kill_rule, score

# Hand-worked case: start trading on day 2, 3-day redeploy, break on day 8.
# Returns are +1 before the break and -1 after it. CUSUM with c=1 fires on the
# day its log L spike lands; c=5 never fires (never-kill).
RETURNS = np.array([[1.0] * 8 + [-1.0] * 2] * 2)
LLR = np.zeros((2, 10))
LLR[0, 3] = 2.0  # strategy A: false alarm on day 3
LLR[1, 8] = 2.0  # strategy B: catches the break on day 8
BREAK = np.array([8, 8])


def run():
    return run_kill_rule(Cusum(), RETURNS, LLR, thresholds=[1.0, 5.0], start=2, redeploy=3)


def test_rule_sits_out_redeploy_then_restarts_with_reset_detectors():
    r = run()
    # A: trades 2-3, fires day 3, out 4-6, restarts day 7 with S reset (no refire)
    assert r.size[0, 0].astype(int).tolist() == [0, 0, 1, 1, 0, 0, 0, 1, 1, 1]
    # B: trades 2-8, fires day 8, out day 9
    assert r.size[0, 1].astype(int).tolist() == [0, 0, 1, 1, 1, 1, 1, 1, 1, 0]
    assert np.flatnonzero(r.fired[0, 0]).tolist() == [3]
    assert np.flatnonzero(r.fired[0, 1]).tolist() == [8]
    assert not r.fired[1].any()


def test_score_worked_example():
    s = score(run(), RETURNS, BREAK, start=2)
    # oracle PnL = 6 (days 2-7). c=1: A PnL 1, B PnL 5. c=5: both PnL 4.
    assert np.allclose(s["mean_regret"], [(5 + 1) / 2, 2.0])
    assert s["false_kills"].tolist() == [1, 0]
    assert s["missed_breaks"].tolist() == [1, 2]
    assert s["mean_delay"][0] == 0.0 and np.isnan(s["mean_delay"][1])
    assert np.allclose(s["mean_slow_cost"], [(2 + 1) / 2, 2.0])


def test_drawdown_rule_uses_each_strategys_sigma():
    # same -3 loss on day 1; sigma 1 -> depth 3 fires at d=2; sigma 2 -> depth 1.5 does not
    returns = np.array([[0.0, -3.0, 0.0]] * 2)
    r = run_kill_rule(Drawdown(np.array([1.0, 2.0])), returns, np.zeros((2, 3)),
                      thresholds=[2.0], start=0, redeploy=5)
    assert r.fired[0, :, 1].tolist() == [True, False]


def test_calibration_aligns_live_p_with_true_break_days():
    from core.evaluate import calibration

    # p covers days 2-3 only (start=2). Strategy 0 breaks on day 3, strategy 1 never (break=4).
    p = np.array([[0.05, 0.95], [0.05, 0.15]])
    bins = calibration(p, break_day=np.array([3, 4]), start=2)
    assert bins[0]["count"] == 2 and bins[0]["frac_broken"] == 0.0
    assert bins[1]["count"] == 1 and bins[1]["frac_broken"] == 0.0
    assert bins[9]["count"] == 1 and bins[9]["frac_broken"] == 1.0
    assert bins[5]["count"] == 0 and bins[5]["mean_p"] is None
