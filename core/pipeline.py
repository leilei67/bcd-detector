"""One strategy in, everything the page shows out.

Fit the warm-up, re-simulate train (seed 1) and test (seed 2) sets of
healthy / sudden / decay strategies, tune thresholds on train, score on test,
and run the detectors over the strategy itself. The series being judged is
never used for tuning. Used by `python -m core.run` and, via Pyodide, by the
browser upload, so both run the same code.
"""
import numpy as np

from core.data import CsvError, parse_returns_csv
from core.detectors import Bayes, Cusum, Drawdown, run_series
from core.evaluate import REDEPLOY, calibration, run_kill_rule, score, tune
from core.model import K_BROKEN, Baseline, fit_baseline, fit_baselines, log_likelihood_ratio
from core.sim import MIN_SIM_DAYS, WARMUP, simulate

HAZARD_YEARS = (1, 2, 5)
DEFAULT_HAZARD = 2
TRAIN_SEED, TEST_SEED = 1, 2
T_GRID = np.round(np.concatenate([np.linspace(0.02, 0.9, 45), [0.92, 0.94, 0.96, 0.98, 0.99, 0.995]]), 3)
C_GRID = np.round(np.linspace(0.5, 15, 59), 3)
D_GRID = np.round(np.linspace(2, 40, 77), 3)
GRIDS = {**{f"bayes_{y}y": T_GRID for y in HAZARD_YEARS}, "cusum": C_GRID, "drawdown": D_GRID}
LABELS = {**{f"bayes_{y}y": f"Bayesian (hazard {y}y)" for y in HAZARD_YEARS},
          "cusum": "CUSUM", "drawdown": "Drawdown depth", "never": "Never kill"}


def prepare(n, seed, sim_params, n_days):
    mu, scale, nu = sim_params
    s = simulate(n, seed, mu=mu, scale=scale, nu=nu, n_days=n_days)
    mus, sigmas, nus = fit_baselines(s.returns[:, :WARMUP])
    llr = np.array([log_likelihood_ratio(r, Baseline(*b)) for r, b in zip(s.returns, zip(mus, sigmas, nus))])
    return s, llr, sigmas


def detectors(sigma):
    rules = {f"bayes_{y}y": Bayes(y) for y in HAZARD_YEARS}
    rules["cusum"] = Cusum()
    rules["drawdown"] = Drawdown(sigma)
    return rules


def row(name, threshold, s):
    delay = float(s["mean_delay"][0])
    return {"rule": name, "label": LABELS[name], "threshold": threshold,
            "mean_regret": float(s["mean_regret"][0]), "se_regret": float(s["se_regret"][0]),
            "false_kills": int(s["false_kills"][0]), "missed_breaks": int(s["missed_breaks"][0]),
            "mean_delay": None if np.isnan(delay) else delay, "mean_slow_cost": float(s["mean_slow_cost"][0])}


def first_day(mask):
    hits = np.flatnonzero(mask)
    return int(hits[0]) + WARMUP if len(hits) else None


def analyse(returns, dates=None, *, sim_params=None, name="Uploaded strategy", caption="",
            break_day=None, default_day=None, n=300) -> dict:
    """sim_params=None re-simulates from the strategy's own warm-up fit (what real data uses)."""
    r = np.asarray(returns, dtype=float)
    base = fit_baseline(r[:WARMUP])
    resimulated = sim_params is None
    sim_params = (base.mu, base.sigma, base.nu) if resimulated else tuple(sim_params)
    # Simulate the same horizon as the series, so thresholds suit how long it has been live.
    sim_days = max(len(r), MIN_SIM_DAYS)
    results = {
        "dataset": {"name": name, "caption": caption, "resimulated": resimulated,
                    "sim_params": [float(v) for v in sim_params]},
        "config": {"k_broken": K_BROKEN, "redeploy_days": REDEPLOY, "warmup": WARMUP, "n_days": len(r),
                   "sim_days": sim_days, "hazard_years": list(HAZARD_YEARS), "default_hazard": DEFAULT_HAZARD,
                   "train": {"n": n, "seed": TRAIN_SEED}, "test": {"n": n, "seed": TEST_SEED},
                   "default_day": default_day if default_day is not None else len(r) - 1},
        "demo": {"break_day": break_day, "warmup": WARMUP, "returns": r.tolist(), "dates": dates,
                 "baseline": {"mu": base.mu, "sigma": base.sigma, "nu": base.nu,
                              "std": float(r[:WARMUP].std(ddof=1)), "mean": float(r[:WARMUP].mean())}},
        "warning": None,
    }
    if base.mu <= 0:
        results["warning"] = (
            f"The warm-up ({WARMUP} days) has no positive edge (fitted mean {100 * base.mu:.3f}% a day). "
            "'Broken' would look the same as 'healthy', so the detectors cannot judge this strategy.")
        return results

    train, train_llr, train_sigma = prepare(n, TRAIN_SEED, sim_params, sim_days)
    test, test_llr, test_sigma = prepare(n, TEST_SEED, sim_params, sim_days)

    tuned, train_regret = {}, {}
    for key, det in detectors(train_sigma).items():
        tuned[key], s = tune(det, train.returns, train_llr, train.break_day, GRIDS[key])
        train_regret[key] = float(s["mean_regret"].min())

    board, per_strategy = [], {}
    for key, det in detectors(test_sigma).items():
        s = score(run_kill_rule(det, test.returns, test_llr, [tuned[key]]), test.returns, test.break_day)
        board.append(row(key, tuned[key], s))
        per_strategy[key] = s["regret"][0]
    s = score(run_kill_rule(Cusum(), test.returns, test_llr, [np.inf]), test.returns, test.break_day)
    board.append(row("never", None, s))
    per_strategy["never"] = s["regret"][0]
    board.sort(key=lambda x: x["mean_regret"])
    # Same strategies for every rule, so compare each rule to the winner pairwise.
    best = per_strategy[board[0]["rule"]]
    for x in board:
        d = per_strategy[x["rule"]] - best
        x["gap_vs_best"] = float(d.mean())
        x["gap_se"] = float(d.std(ddof=1) / np.sqrt(len(d)))

    tradeoff, calib = {}, {}
    for y in HAZARD_YEARS:
        s = score(run_kill_rule(Bayes(y), test.returns, test_llr, T_GRID), test.returns, test.break_day)
        tradeoff[str(y)] = [{"T": float(t), "false_kills": int(s["false_kills"][i]),
                             "slow_cost": float(s["mean_slow_cost"][i]),
                             "mean_regret": float(s["mean_regret"][i])} for i, t in enumerate(T_GRID)]
        # p starts at 0 on the first live day, exactly as the kill rule and the demo see it
        live_p = run_series(Bayes(y), test.returns[:, WARMUP:], test_llr[:, WARMUP:])
        calib[str(y)] = calibration(live_p, test.break_day)

    llr = log_likelihood_ratio(r, base)
    live = slice(WARMUP, None)
    p = {str(y): run_series(Bayes(y), r[live], llr[live]) for y in HAZARD_YEARS}
    cus = run_series(Cusum(), r[live], llr[live])
    dd = run_series(Drawdown(base.sigma), r[live], llr[live])
    results["demo"].update({
        "p": {k: v.tolist() for k, v in p.items()}, "cusum": cus.tolist(), "drawdown": dd.tolist(),
        "fire_day": {**{y: first_day(p[y] >= tuned[f"bayes_{y}y"]) for y in p},
                     "cusum": first_day(cus > tuned["cusum"]), "drawdown": first_day(dd > tuned["drawdown"])},
    })
    results.update({
        "tuned": {"T": {str(y): tuned[f"bayes_{y}y"] for y in HAZARD_YEARS},
                  "c": tuned["cusum"], "d": tuned["drawdown"], "train_regret": train_regret},
        "scoreboard": board, "tradeoff": tradeoff, "calibration": calib,
    })
    return results


def analyse_csv(text: str, name: str = "Uploaded strategy") -> dict:
    """Browser entry point: CSV text in, results (or {'errors': [...]}) out."""
    try:
        dates, returns = parse_returns_csv(text)
    except CsvError as e:
        return {"errors": e.messages}
    caption = (f"Your upload ({name}): {dates[0]} to {dates[-1]}, {len(dates)} trading days; "
               f"the first {WARMUP} are the warm-up the tool learns 'normal' from.")
    return analyse(returns, dates, name=f"{name}: {dates[0][:4]}–{dates[-1][:4]}", caption=caption)
