"""Kill-rule simulation, regret scoring and threshold tuning.

A rule trades at size 1 until its detector fires, sits out REDEPLOY days, then
restarts with the detector reset. The oracle trades at size 1 until the true
break, then stops. Regret = oracle PnL - rule PnL, counted from the end of warm-up.
"""
import warnings
from dataclasses import dataclass

import numpy as np

from core.sim import WARMUP

REDEPLOY = 60


@dataclass(frozen=True)
class KillRun:
    size: np.ndarray  # (n_thresholds, n_strategies, n_days) bool: traded that day
    fired: np.ndarray  # same shape: detector fired at the close of that day


def _reset(state, fresh, mask):
    if isinstance(state, tuple):
        return tuple(_reset(s, f, mask) for s, f in zip(state, fresh))
    return np.where(mask, fresh, state)


def run_kill_rule(detector, returns, llr, thresholds, start=WARMUP, redeploy=REDEPLOY) -> KillRun:
    returns, llr = np.asarray(returns, float), np.asarray(llr, float)
    thr = np.asarray(thresholds, float)[:, None]
    n, n_days = returns.shape
    shape = (len(thr), n)
    size = np.zeros(shape + (n_days,), bool)
    fired = np.zeros_like(size)
    state = detector.init(shape)
    fresh = detector.init(shape)
    back_on = np.full(shape, start)  # day the rule (re)starts trading
    for t in range(start, n_days):
        state = _reset(state, fresh, back_on == t)
        state, stat = detector.step(state, returns[:, t], llr[:, t])
        trading = t >= back_on
        fire = trading & detector.fires(stat, thr)
        size[..., t] = trading
        fired[..., t] = fire
        back_on = np.where(fire, t + 1 + redeploy, back_on)
    return KillRun(size=size, fired=fired)


def score(run: KillRun, returns, break_day, start=WARMUP) -> dict:
    """Per-threshold metrics. Slow-kill cost is averaged over broken strategies only."""
    returns = np.asarray(returns, float)
    n_days = returns.shape[1]
    days = np.arange(n_days)
    before_break = days < break_day[:, None]  # (n, n_days)
    oracle = (returns * (before_break & (days >= start))).sum(-1)
    rule = (returns * run.size).sum(-1)  # (n_thr, n)

    false_kill = (run.fired & before_break).any(-1)
    fired_after = run.fired & ~before_break
    detected = fired_after.any(-1)
    first = np.argmax(fired_after, -1)
    broken = break_day < n_days
    end = np.where(detected, first, n_days - 1)
    window = ~before_break & (days <= end[..., None])
    slow_cost = -(returns * run.size * window).sum(-1)

    delay = np.where(detected, first - break_day, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN row: nothing detected
        mean_delay = np.nanmean(delay, -1)
    regret = oracle - rule
    return {
        "regret": regret,  # (n_thr, n) per strategy, for paired comparisons
        "mean_regret": regret.mean(-1),
        "se_regret": regret.std(-1, ddof=1) / np.sqrt(regret.shape[-1]),
        "false_kills": false_kill.sum(-1),
        "missed_breaks": (broken & ~detected).sum(-1),
        "mean_delay": mean_delay,
        "mean_slow_cost": slow_cost[:, broken].mean(-1) if broken.any() else np.zeros(len(rule)),
    }


def tune(detector, returns, llr, break_day, grid):
    """Grid search for the threshold with the lowest mean regret. Returns (best, scores)."""
    s = score(run_kill_rule(detector, returns, llr, grid), returns, break_day)
    return float(np.asarray(grid)[np.argmin(s["mean_regret"])]), s


def calibration(p_live, break_day, start=WARMUP, n_bins=10) -> list:
    """Bin predicted p (series starting on day `start`) against whether that day was really broken."""
    p_live = np.asarray(p_live, float)
    days = start + np.arange(p_live.shape[1])
    broken = (days[None, :] >= np.asarray(break_day)[:, None]).ravel()
    p = p_live.ravel()
    idx = np.minimum((p * n_bins).astype(int), n_bins - 1)
    bins = []
    for b in range(n_bins):
        m = idx == b
        bins.append({"lo": b / n_bins, "hi": (b + 1) / n_bins, "count": int(m.sum()),
                     "mean_p": float(p[m].mean()) if m.any() else None,
                     "frac_broken": float(broken[m].mean()) if m.any() else None})
    return bins
