"""Tune on the training set (seed 1), score on the test set (seed 2), write web/public/results.json."""
import json
from pathlib import Path

import numpy as np

from core.detectors import Bayes, Cusum, Drawdown, run_series
from core.evaluate import REDEPLOY, run_kill_rule, score, tune
from core.model import K_BROKEN, fit_baseline, log_likelihood_ratio
from core.sim import N_DAYS, WARMUP, demo_strategy, simulate

HAZARD_YEARS = (1, 2, 5)
DEFAULT_HAZARD = 2
T_GRID = np.round(np.concatenate([np.linspace(0.02, 0.9, 45), [0.92, 0.94, 0.96, 0.98, 0.99, 0.995]]), 3)
C_GRID = np.round(np.linspace(0.5, 15, 59), 3)
D_GRID = np.round(np.linspace(2, 40, 77), 3)
OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "results.json"


def prepare(n, seed):
    s = simulate(n, seed)
    bases = [fit_baseline(r[:WARMUP]) for r in s.returns]
    llr = np.array([log_likelihood_ratio(r, b) for r, b in zip(s.returns, bases)])
    sigma = np.array([b.sigma for b in bases])
    return s, llr, sigma


def detectors(sigma):
    rules = {f"bayes_{y}y": Bayes(y) for y in HAZARD_YEARS}
    rules["cusum"] = Cusum()
    rules["drawdown"] = Drawdown(sigma)
    return rules


GRIDS = {**{f"bayes_{y}y": T_GRID for y in HAZARD_YEARS}, "cusum": C_GRID, "drawdown": D_GRID}
LABELS = {**{f"bayes_{y}y": f"Bayesian (hazard {y}y)" for y in HAZARD_YEARS},
          "cusum": "CUSUM", "drawdown": "Drawdown depth", "never": "Never kill"}


def row(name, threshold, s, i=0):
    pick = lambda k: float(s[k][i])
    delay = pick("mean_delay")
    return {"rule": name, "label": LABELS[name], "threshold": threshold,
            "mean_regret": pick("mean_regret"), "se_regret": pick("se_regret"), "false_kills": int(s["false_kills"][i]),
            "missed_breaks": int(s["missed_breaks"][i]),
            "mean_delay": None if np.isnan(delay) else delay,
            "mean_slow_cost": pick("mean_slow_cost")}


def calibration(p, s):
    days = np.arange(N_DAYS)[WARMUP:]
    broken = (days[None, :] >= s.break_day[:, None]).ravel()
    p = p[:, WARMUP:].ravel()
    idx = np.minimum((p * 10).astype(int), 9)
    bins = []
    for b in range(10):
        m = idx == b
        bins.append({"lo": b / 10, "hi": (b + 1) / 10, "count": int(m.sum()),
                     "mean_p": float(p[m].mean()) if m.any() else None,
                     "frac_broken": float(broken[m].mean()) if m.any() else None})
    return bins


def main():
    train, train_llr, train_sigma = prepare(300, seed=1)
    test, test_llr, test_sigma = prepare(300, seed=2)

    tuned, train_regret = {}, {}
    for name, det in detectors(train_sigma).items():
        tuned[name], s = tune(det, train.returns, train_llr, train.break_day, GRIDS[name])
        train_regret[name] = float(s["mean_regret"].min())

    board, per_strategy = [], {}
    for name, det in detectors(test_sigma).items():
        s = score(run_kill_rule(det, test.returns, test_llr, [tuned[name]]), test.returns, test.break_day)
        board.append(row(name, tuned[name], s))
        per_strategy[name] = s["regret"][0]
    s = score(run_kill_rule(Cusum(), test.returns, test_llr, [np.inf]), test.returns, test.break_day)
    board.append(row("never", None, s))
    per_strategy["never"] = s["regret"][0]
    board.sort(key=lambda r: r["mean_regret"])
    # Same 300 strategies for every rule, so compare each rule to the winner pairwise.
    best = per_strategy[board[0]["rule"]]
    for r in board:
        d = per_strategy[r["rule"]] - best
        r["gap_vs_best"] = float(d.mean())
        r["gap_se"] = float(d.std(ddof=1) / np.sqrt(len(d)))

    tradeoff, calib = {}, {}
    for y in HAZARD_YEARS:
        s = score(run_kill_rule(Bayes(y), test.returns, test_llr, T_GRID), test.returns, test.break_day)
        tradeoff[str(y)] = [{"T": float(t), "false_kills": int(s["false_kills"][i]),
                             "slow_cost": float(s["mean_slow_cost"][i]),
                             "mean_regret": float(s["mean_regret"][i])} for i, t in enumerate(T_GRID)]
        calib[str(y)] = calibration(run_series(Bayes(y), test.returns, test_llr), test)

    r = demo_strategy()
    base = fit_baseline(r[:WARMUP])
    llr = log_likelihood_ratio(r, base)
    live = slice(WARMUP, None)
    p = {str(y): run_series(Bayes(y), r[live], llr[live]) for y in HAZARD_YEARS}
    cus = run_series(Cusum(), r[live], llr[live])
    dd = run_series(Drawdown(base.sigma), r[live], llr[live])

    def first(mask):
        hits = np.flatnonzero(mask)
        return int(hits[0]) + WARMUP if len(hits) else None

    demo = {
        "break_day": 450, "warmup": WARMUP, "returns": r.tolist(),
        "baseline": {"mu": base.mu, "sigma": base.sigma, "nu": base.nu,
                     "std": float(r[:WARMUP].std(ddof=1)), "mean": float(r[:WARMUP].mean())},
        "p": {k: v.tolist() for k, v in p.items()}, "cusum": cus.tolist(), "drawdown": dd.tolist(),
        "fire_day": {**{y: first(p[y] >= tuned[f"bayes_{y}y"]) for y in p},
                     "cusum": first(cus > tuned["cusum"]), "drawdown": first(dd > tuned["drawdown"])},
    }

    results = {
        "config": {"k_broken": K_BROKEN, "redeploy_days": REDEPLOY, "warmup": WARMUP, "n_days": N_DAYS,
                   "hazard_years": list(HAZARD_YEARS), "default_hazard": DEFAULT_HAZARD,
                   "train": {"n": 300, "seed": 1}, "test": {"n": 300, "seed": 2}},
        "tuned": {"T": {str(y): tuned[f"bayes_{y}y"] for y in HAZARD_YEARS},
                  "c": tuned["cusum"], "d": tuned["drawdown"], "train_regret": train_regret},
        "scoreboard": board, "tradeoff": tradeoff, "calibration": calib, "demo": demo,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, allow_nan=False))
    print_board(results)


def print_board(res):
    t = res["tuned"]
    print(f"Tuned on train (seed 1): T={t['T']}  c={t['c']}  d={t['d']}")
    print("Test set (seed 2, 300 strategies, never used for tuning). PnL in % of capital.")
    print(f"{'rule':<24}{'thresh':>8}{'regret%':>9}{'±se':>6}{'gap±se':>13}{'false':>7}{'missed':>8}{'delay':>7}{'slow%':>8}")
    for r in res["scoreboard"]:
        th = "-" if r["threshold"] is None else f"{r['threshold']:.3g}"
        dl = "-" if r["mean_delay"] is None else f"{r['mean_delay']:.0f}"
        print(f"{r['label']:<24}{th:>8}{100*r['mean_regret']:>9.2f}{100*r['se_regret']:>6.2f}{f"{100*r['gap_vs_best']:.2f}±{100*r['gap_se']:.2f}":>13}{r['false_kills']:>7}"
              f"{r['missed_breaks']:>8}{dl:>7}{100*r['mean_slow_cost']:>8.2f}")
    print(f"Demo fire days: {res['demo']['fire_day']}  (true break 450)")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
