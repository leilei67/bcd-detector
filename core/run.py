"""Build the bundled datasets for the web page and print their scoreboards.

    uv run python -m core.run
"""
import json
from pathlib import Path

from core.data import parse_returns_csv
from core.pipeline import analyse
from core.sim import MU, NU, SCALE, demo_strategy

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "datasets"
UMD_CSV = ROOT / "data" / "umd_2007_2009.csv"
UMD_CAPTION = (
    "Kenneth French's daily momentum factor (long last year's winners, short last year's losers): the 750 trading days "
    "ending 31 Dec 2009, the same shape as the simulated strategies, so 2007 is the healthy warm-up. We picked this "
    "window because the 2009 momentum crash is the textbook 'broken or bad run?' case. Thresholds were tuned on "
    "strategies simulated from the 2007 fit, never on these returns."
)


def build():
    sim = analyse(demo_strategy(), sim_params=(MU, SCALE, NU), name="Simulated demo strategy",
                  caption="A simulated strategy, healthy for 450 days, then its edge flips negative.",
                  break_day=450, default_day=540)
    dates, returns = parse_returns_csv(UMD_CSV.read_text())
    umd = analyse(returns, dates, name="Momentum factor (UMD), 2007–2009", caption=UMD_CAPTION)
    return {"sim": sim, "umd": umd}


def main():
    datasets = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for key, res in datasets.items():
        (OUT / f"{key}.json").write_text(json.dumps(res, allow_nan=False))
        print_board(res)
    index = [{"id": k, "name": v["dataset"]["name"], "file": f"datasets/{k}.json"} for k, v in datasets.items()]
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
