"""Build the bundled datasets for the web page and print their scoreboards.

    uv run python -m core.run
"""
import json
from pathlib import Path

from core.data import parse_returns_csv
from core.pipeline import analyse
from core.datasets import FACTORS, REAL, WINDOW_DAYS
from core.sim import MU, NU, SCALE, WARMUP, demo_strategy

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "datasets"


def caption(ds, dates):
    when = "ending at the latest date in the source file" if ds["end"] is None else f"ending {ds['end']}"
    return (f"{FACTORS[ds['column']]}. Window: the {WINDOW_DAYS} trading days {when} ({dates[0]} to {dates[-1]}); "
            f"the first {WARMUP} (to {dates[WARMUP - 1]}) are the healthy warm-up. Why this window: {ds['reason']} "
            "Same rule for every real dataset. Thresholds were tuned on strategies simulated from the warm-up fit, "
            "never on these returns. Source: Kenneth R. French Data Library.")


def build():
    datasets = {"sim": analyse(
        demo_strategy(), sim_params=(MU, SCALE, NU), name="Simulated demo strategy",
        caption="A simulated strategy, healthy for 450 days, then its edge flips negative.",
        break_day=450, default_day=540)}
    groups = {"sim": "Simulated"}
    for ds in REAL:
        dates, returns = parse_returns_csv((ROOT / "data" / f"{ds['id']}.csv").read_text())
        datasets[ds["id"]] = analyse(returns, dates, name=ds["name"], caption=caption(ds, dates))
        groups[ds["id"]] = ds["group"]
    return datasets, groups


def main():
    datasets, groups = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()  # drop datasets no longer in the registry
    for key, res in datasets.items():
        (OUT / f"{key}.json").write_text(json.dumps(res, allow_nan=False))
        print_board(res)
    index = [{"id": k, "name": v["dataset"]["name"], "group": groups[k], "file": f"datasets/{k}.json"}
             for k, v in datasets.items()]
    (OUT / "index.json").write_text(json.dumps(index))
    print(f"wrote {OUT}")


def print_board(res):
    print(f"\n== {res['dataset']['name']} ==")
    if res["warning"]:
        print("WARNING:", res["warning"])
        return
    mu, sigma, nu = res["dataset"]["sim_params"]
    t = res["tuned"]
    print(f"Simulated with mu={mu:.5f} sigma={sigma:.5f} nu={nu:.2f}"
          f"{' (re-simulated from this series warm-up fit)' if res['dataset']['resimulated'] else ''}")
    print(f"Tuned on train (seed 1): T={t['T']}  c={t['c']}  d={t['d']}")
    print("Test set (seed 2, never used for tuning). PnL in % of capital.")
    print(f"{'rule':<24}{'thresh':>8}{'regret%':>9}{'±se':>6}{'gap±se':>13}{'false':>7}{'missed':>8}{'delay':>7}{'slow%':>8}")
    for r in res["scoreboard"]:
        th = "-" if r["threshold"] is None else f"{r['threshold']:.3g}"
        dl = "-" if r["mean_delay"] is None else f"{r['mean_delay']:.0f}"
        gap = f"{100 * r['gap_vs_best']:.2f}±{100 * r['gap_se']:.2f}"
        print(f"{r['label']:<24}{th:>8}{100 * r['mean_regret']:>9.2f}{100 * r['se_regret']:>6.2f}{gap:>13}"
              f"{r['false_kills']:>7}{r['missed_breaks']:>8}{dl:>7}{100 * r['mean_slow_cost']:>8.2f}")
    fd, dates = res["demo"]["fire_day"], res["demo"]["dates"]
    print("Fire days:", {k: (dates[v] if dates and v is not None else v) for k, v in fd.items()},
          f"(true break {res['demo']['break_day']})")


if __name__ == "__main__":
    main()
