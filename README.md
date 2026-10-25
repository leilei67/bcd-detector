# Broken, or just a bad run?

A kill-switch adviser for a solo trader whose strategy is losing money. It reads daily returns and recommends **keep / investigate / reduce / pause / kill**, weighing two ways of being wrong: killing a strategy that was fine, and riding a broken one too long.

Tuning is honest. Every threshold is tuned on 300 simulated strategies (seed 1) and scored on 300 fresh ones (seed 2) that the tuning never saw. For a real series, those strategies are simulated from a Student-t fitted to its first 250 days, so its later returns never touch the tuning.

The page has three ways in:
- a simulated demo strategy;
- a real one, Kenneth French's momentum factor through its 2009 crash;
- your own CSV, analysed in the browser.

## Run it

Needs [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
uv sync                      # numpy, scipy, pytest
uv run pytest -q             # maths tests
uv run python -m core.run    # analyse both bundled datasets, write web/public/datasets/ (~4 s)

cd web
npm install
npm test                     # browser-side decision rule tests
npm run dev                  # open the printed URL
```

- **Committed outputs.** `web/public/datasets/*.json` and `data/umd_2007_2009.csv` are committed, so the bundled examples work offline without running Python first.
- **Re-downloading the real data.** Run `uv run python scripts/fetch_umd.py`.
- **Uploads.** An upload runs `core/pipeline.py` itself in a web worker via [Pyodide](https://pyodide.org). The first upload downloads Python, numpy and scipy from the jsdelivr CDN (about 30 MB, so it needs internet). After that, an analysis takes a few seconds. The file never leaves the browser.

### CSV format

```
date,return
2021-01-04,0.0042
2021-01-05,-0.0017
```

The rules:
- One row per trading day.
- Dates are ISO `YYYY-MM-DD` and increase down the file.
- Returns are decimals: 1 % is `0.01`.
- At least 310 rows: 250 for the warm-up, plus 60 to judge.

The page lists every problem it finds at once:
- unreadable rows, with the line number;
- too few days;
- returns that look like percentages;
- duplicate or out-of-order dates.

## Simulated demo: test-set scoreboard

| Rule | Tuned on train | Mean regret (% capital) | Gap vs best (paired) | False kills /300 | Missed /200 | Mean delay |
|---|---|---|---|---|---|---|
| Bayesian, hazard 1y | T = 0.78 | 15.08 ± 0.91 | – | 102 | 16 | 58 d |
| Bayesian, hazard 2y | T = 0.62 | 15.18 ± 0.91 | +0.10 ± 0.14 | 100 | 16 | 60 d |
| Bayesian, hazard 5y | T = 0.38 | 15.21 ± 0.92 | +0.13 ± 0.15 | 99 | 20 | 58 d |
| Drawdown depth | d = 16.5 σ | 15.66 ± 0.86 | +0.58 ± 0.69 | 102 | 21 | 63 d |
| CUSUM | c = 4 | 15.86 ± 0.91 | +0.78 ± 0.44 | 93 | 28 | 68 d |
| Never kill | – | 22.16 ± 1.45 | +7.08 ± 0.99 | 0 | 200 | – |

- **Never kill.** Every tuned rule clearly beats never killing.
- **Between the tuned rules.** The gaps are within noise.
- **The default rule.** The default 2-year Bayesian rule did not win. The 1-year variant edged it by 0.10 ± 0.14 points, and the page says so.
- **What Bayesian adds.** It does not beat the fairly tuned baselines on regret. It adds a calibrated probability, which feeds the cost card and the risk bands.

About a third of strategies get a "false kill" under every tuned rule. Most of these are broken strategies killed shortly before their break, including decay strategies whose mean was already sliding. Regret tuning accepts them, because a false kill only costs the 60-day sit-out.

## Real data: momentum factor (UMD), 2007–2009

**Source.** [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), "Momentum Factor (Mom)", daily. The factor is long the past year's winners and short the past year's losers. The source file is in percent; `scripts/fetch_umd.py` converts it to decimals.

**Licence.** The file says "Copyright Eugene F. Fama and Kenneth R. French". The library is free to download and states no explicit licence. This repo redistributes a 750-row excerpt for a non-commercial demo, with attribution. Check the terms before any other use.

**Window.** The 750 trading days ending 2009-12-31 (2007-01-11 to 2009-12-31). This is the same shape as the simulated strategies, so 2007 is the warm-up. We picked it because the 2009 momentum crash is the textbook "broken or bad run?" case, and the page caption says so.

**Tuning.** The 2007 fit (μ = 0.12 % a day, σ = 0.40 %, ν = 3.5) seeds the simulated train and test sets. The crash itself is never used.

| Rule (tuned on simulations of the 2007 fit) | Threshold | Test regret | Gap vs best | First fires on the real series |
|---|---|---|---|---|
| Bayesian, hazard 2y | T = 0.76 | 9.09 ± 0.52 | – | 2009-01-02 |
| CUSUM | c = 5.5 | 9.11 ± 0.54 | +0.02 ± 0.22 | 2009-01-05 |
| Bayesian, hazard 5y | T = 0.54 | 9.19 ± 0.52 | +0.10 ± 0.07 | 2009-01-02 |
| Bayesian, hazard 1y | T = 0.90 | 9.32 ± 0.55 | +0.23 ± 0.14 | 2009-01-05 |
| Drawdown depth | d = 16.5 σ | 10.47 ± 0.55 | +1.37 ± 0.35 | 2008-01-23 |
| Never kill | – | 18.21 ± 1.14 | +9.11 ± 0.76 | – |

What happens on the real series:
- **Bayesian and CUSUM** both fire in the first days of January 2009, ahead of the March–May 2009 crash. The Bayesian probability then falls back in February and pins at 1 from April.
- **Drawdown** fires in January 2008. Volatility roughly tripled in 2008, and depth is measured in 2007's calm σ.
- **Volatility is outside the model.** The model only knows mean shifts. A volatility regime change shows up only through drawdown depth and the "volatility is N× normal" evidence text.

## How it works

- **Baseline.** A Student-t (μ, σ, ν) fitted to the first 250 days, which are assumed healthy.
- **Broken model.** Same σ and ν, mean −k·|μ| with k = 1.
- **Bayesian detector.** Daily hazard h = 1/(252·years). Each day: p_prior = p + (1−p)·h, then a Bayes update with the likelihood ratio L = pdf_broken(r) / pdf_healthy(r). Done in log-odds for stability.
- **CUSUM.** S = max(0, S + log L), fires when S > c.
- **Drawdown depth.** Drawdown of cumulative PnL in units of σ, fires when depth > d.
- **Actions.** With T_eff = f·T: p ≥ T_eff kills. Below that, a CUSUM alarm pauses. Otherwise the bands at ⅔·T_eff and ⅓·T_eff give reduce / investigate / keep. Only T is tuned; the bands are a risk-appetite heuristic.
- **Regret.** The oracle trades until the true break. A rule trades until it fires, sits out 60 days, then restarts with its detector reset. Regret = oracle PnL − rule PnL, counted from day 250.
- **Pipeline.** `core/pipeline.py` `analyse()` takes one series and produces everything the page shows: fit, re-simulate, tune, score, run the detectors. The CLI and the browser upload both call it.

All three detectors share one vectorised one-day step (`core/detectors.py`). The display series and the tuning simulator therefore run the same code.

## Choices the spec left open

- **Simulated strategy.** Healthy daily mean 0.15 %, Student-t scale 0.8 %, ν = 4, an annual Sharpe of about 2.1. At Sharpe 1.4, 250 days often could not pin μ (some fits came out μ ≤ 0, which makes "broken" identical to "healthy"), and p drifted up on healthy strategies.
- **Break days.** Sudden breaks land uniformly in days 260–739. Decay starts uniformly in days 260–629. A decay's "true break" is the day its mean crosses zero (start + 60), the first day continuing loses money in expectation.
- **Demo strategy.** Sudden break at day 450. It uses the first random seed whose warm-up sample mean is within 20 % of the true μ. The rule never looks past the warm-up, so it cannot pick a seed where the detectors look good. Its simulations use the true generating parameters. Real and uploaded series re-simulate from their warm-up fit.
- **Student-t fit.**
  - Method: EM for μ and σ at each of 25 values of ν (geometric grid, 2.05 to 50), then the ν with the highest likelihood. All strategies are fitted at once.
  - Why: scipy's generic fit took 11 of the 12 seconds per run. That was too slow for the browser, where a full analysis now takes a few seconds.
  - Check: a test confirms the fit's likelihood is at least scipy's MLE on every test series.
  - Effect: the simulated scoreboard moved by at most 0.4 points.
- **Simulation horizon.** The simulated strategies are as long as the series being judged, with a minimum of 380 days, which leaves room for a 120-day decay after the warm-up. That way the thresholds suit how long the strategy has been live. A long upload (say 10 years) therefore takes proportionally longer to analyse.
- **Real-data window.** As above: 750 days ending at the end of the crash year, the same shape as the simulations.
- **Default "as of" day.** Day 540 for the simulated demo, so the risk slider visibly flips the recommendation. The last day for real and uploaded data.
- **CSV rules.**
  - Dates must be ISO.
  - "Looks like percentages" means the median absolute daily return is above 5 %.
  - Every problem is reported, not just the first.
- **Pyodide.** Version 0.27.7 from the jsdelivr CDN. The worker reads `core/*.py` as text at build time, so there is no second copy of the maths to keep in step. On the bundled UMD file, an end-to-end check in Chrome reproduced the native thresholds and scoreboard exactly.
- **Grids.** T: 0.02–0.90 in steps of 0.02, plus 0.92–0.995. c: 0.5–15 (59 points). d: 2–40 σ (77 points).
- **Metrics.**
  - False kills: strategies killed at least once while healthy or before their break.
  - Missed breaks: broken strategies never killed on or after the break.
  - Delay: days from the break to the first kill on or after it, detected strategies only.
  - Slow-kill cost: money lost from the break to that kill, averaged over broken strategies.
- **Scoreboard extras.** Standard errors, plus a paired gap against the winner on the same 300 strategies, so a 0.1-point lead is not presented as a win.
- **Bayesian rows.** One per hazard (1, 2, 5 years), each with its own tuned T. The verdict judges the default 2-year rule.
- **Calibration.** Uses the p series with no restarts, from day 250, over all test strategy-days.
- **Cost card.** Uses the fitted μ. "Average return" in the evidence text is the plain sample mean.
- **"CUSUM fired" in the UI** means S > c on the day being judged, not "fired at any point".
- **Equity and drawdown** are additive (sum of returns), not compounded.
- **Styling.** Light theme only, for projector contrast. Chart colours are the validated categorical palette from the dataviz skill.

## Not built yet

- **Edge gate.** There is no "was the edge ever real?" test. The tool only refuses outright when the warm-up's fitted mean is zero or negative; a lucky positive warm-up passes.
- **Real data.** There is one real episode (UMD 2009), not a library of real strategies with known break dates. All tuning is on simulations.
- **Volatility.** The model has no volatility-change detector. "Broken" means the mean flipped.
- **Decision journal.** Nothing records what was recommended and what the trader did.
- **Bands.** The keep / investigate / reduce bands are a heuristic. Only the kill line T is tuned.
- **Offline uploads.** Uploading needs internet the first time, to download Pyodide. Vendoring Pyodide into the build would fix this, at about 30 MB.
- **Other upload formats.** There is no upload of prices, equity curves or trade logs. Only daily returns are accepted.

## Review notes

Two two-axis reviews (standards and spec) ran:
- the first against the `start` commit;
- the second against the end of the simulated-only build (`19ec1b6`).

**Fixed, because they made a shown number wrong or broke the demo:**
- **Calibration.** The calibration p series ran through the warm-up instead of starting at 0 on day 250. Regression test in `tests/test_evaluate.py`.
- **Trade-off marker.** With hazard 1y and f > 1.28, T_eff goes above 1 and the rule can never kill. The marker now says so instead of claiming T_eff ≈ 0.995.
- **Verdict.** The scoreboard verdict asks whether the *default* tuned Bayesian rule won, not whether any Bayesian row did.
- **Simulation horizon.** Uploads of any length were tuned on 750-day simulations, so a long series got thresholds for the wrong horizon. Simulations now match the series length. Regression test in `tests/test_pipeline.py`.
- **Second upload.** Uploading a shorter file after a longer one kept the old "as of" day and crashed the page. Each upload now resets the page state.
- **Date errors.** A file with both duplicate and unsorted dates now reports both problems.
- **Worker retry.** The Pyodide worker now retries loading Python only when loading itself failed. Previously, any later JavaScript error forced a fresh 30 MB download.

**Deferred, because nothing is wrong today but a later edit could make it wrong:**
- **Simulation parameters.** These travel as a positional `(mu, sigma, nu)` tuple through `pipeline.py`, `run.py` and `Results.jsx`. A named object would be safer.
- **Library versions.** Pyodide 0.27.7 ships older numpy and scipy than `uv.lock`. On the bundled UMD file the upload reproduced the native thresholds and scoreboard exactly. Other files could differ in the last decimal. There is no automated test of the Pyodide path; it was checked in Chrome with Playwright.
- **Fire comparison.** The `>=` / `>` rules are written in `core/detectors.py`, `core/pipeline.py` and `web/src/App.jsx`. `demo.fire_day` in the JSON is unused by the page.
- **Cost card.** `logic.js` `costs()` hard-codes k = 1. The slider label repeats the band edges from `decideAction`.
- **Rule keys.** String rule keys like `bayes_2y` are built in several places.
- **Argument clumps.** `(returns, llr, break_day)` travels together everywhere.
- **Page components.** `Demo` and `Live` in `App.jsx` share a render function rather than a component. Captions are built in both `run.py` and `analyse_csv`.
- **Python decision rule.** `core/actions.py` is only exercised by tests; the browser copy in `logic.js` is what runs, with the same test cases.
- **Percent check.** It is one heuristic (median |r| > 5 %). A very volatile decimal series would be rejected, and a calm series in percent would pass. Gaps between trading days are not flagged.
- **Multiple comparison.** The three Bayesian hazard rows on the test board are a mild multiple comparison. The verdict uses only the default 2y row.
