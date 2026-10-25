# Broken, or just a bad run?

A kill-switch adviser for a solo trader whose strategy is losing money. It reads daily returns and recommends **keep / investigate / reduce / pause / kill**, weighing two ways of being wrong: killing a strategy that was fine, and riding a broken one too long.

Tuning is honest. Every threshold is tuned on 300 simulated strategies (seed 1) and scored on 300 fresh ones (seed 2) that the tuning never saw.

## Run it

Needs [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
uv sync                      # numpy, scipy, pytest
uv run pytest -q             # maths tests
uv run python -m core.run    # tune on train, score on test, write web/public/results.json (~8 s)

cd web
npm install
npm test                     # browser-side decision rule tests
npm run dev                  # open the printed URL
```

`web/public/results.json` is committed, so the page works without running Python first.

## Test-set scoreboard

| Rule | Tuned on train | Mean regret (% capital) | Gap vs best (paired) | False kills /300 | Missed /200 | Mean delay |
|---|---|---|---|---|---|---|
| Bayesian, hazard 2y | T = 0.62 | 15.18 ± 0.91 | – | 102 | 16 | 60 d |
| Bayesian, hazard 1y | T = 0.78 | 15.23 ± 0.90 | +0.05 ± 0.13 | 104 | 16 | 58 d |
| Bayesian, hazard 5y | T = 0.38 | 15.31 ± 0.92 | +0.13 ± 0.11 | 101 | 20 | 58 d |
| Drawdown depth | d = 17 σ | 15.31 ± 0.85 | +0.14 ± 0.68 | 93 | 20 | 66 d |
| CUSUM | c = 4 | 15.94 ± 0.92 | +0.76 ± 0.47 | 91 | 28 | 68 d |
| Never kill | – | 22.16 ± 1.45 | +6.99 ± 0.99 | 0 | 200 | – |

The tuned Bayesian rule has the lowest test regret and clearly beats never killing. Its lead over drawdown and CUSUM is within two standard errors, so on this simulation it ties the fairly tuned baselines. What it adds over them is a calibrated probability, which feeds the cost card and the risk bands.

About a third of strategies get a "false kill" under every tuned rule. For the 2-year Bayesian rule the 102 break down as follows:
- 40 healthy strategies.
- 26 sudden-break strategies killed before their break.
- 36 decay strategies. 21 of these were killed during the slide, when the mean was already falling but not yet below zero.

Regret tuning accepts these, because a false kill only costs the 60-day sit-out.

## How it works

- **Baseline.** A Student-t (μ, σ, ν) fitted to the first 250 days, which are assumed healthy.
- **Broken model.** Same σ and ν, mean −k·|μ| with k = 1.
- **Bayesian detector.** Daily hazard h = 1/(252·years). Each day: p_prior = p + (1−p)·h, then a Bayes update with the likelihood ratio L = pdf_broken(r) / pdf_healthy(r). Done in log-odds for stability.
- **CUSUM.** S = max(0, S + log L), fires when S > c.
- **Drawdown depth.** Drawdown of cumulative PnL in units of σ, fires when depth > d.
- **Actions.** With T_eff = f·T: p ≥ T_eff kills. Below that, a CUSUM alarm pauses. Otherwise the bands at ⅔·T_eff and ⅓·T_eff give reduce / investigate / keep. Only T is tuned; the bands are a risk-appetite heuristic.
- **Regret.** The oracle trades until the true break. A rule trades until it fires, sits out 60 days, then restarts with its detector reset. Regret = oracle PnL − rule PnL, counted from day 250.

All three detectors share one vectorised one-day step (`core/detectors.py`). The display series and the tuning simulator therefore run the same code.

## Choices the spec left open

- **Simulated strategy.** Healthy daily mean 0.15 %, Student-t scale 0.8 %, ν = 4, an annual Sharpe of about 2.1. At Sharpe 1.4, 250 days often could not pin μ (some fits came out μ ≤ 0, which makes "broken" identical to "healthy"), and p drifted up on healthy strategies.
- **Break days.** Sudden breaks land uniformly in days 260–739. Decay starts uniformly in days 260–629. A decay's "true break" is the day its mean crosses zero (start + 60), the first day continuing loses money in expectation.
- **Demo strategy.** Sudden break at day 450. It uses the first random seed whose warm-up sample mean is within 20 % of the true μ. The rule never looks past the warm-up, so it cannot pick a seed where the detectors look good. The first draw tried had a losing warm-up that made "normal" meaningless.
- **Grids.** T: 0.02–0.90 in steps of 0.02, plus 0.92–0.995. c: 0.5–15 (59 points). d: 2–40 σ (77 points).
- **Metrics.** False kills count strategies killed at least once while healthy or before their break. Missed breaks count broken strategies never killed on or after the break. Delay runs from the break to the first kill on or after it, for detected strategies only. Slow-kill cost is the money lost from the break to that kill, averaged over broken strategies.
- **Scoreboard extras.** Standard errors, plus a paired gap against the winner on the same 300 strategies, so a 0.1-point lead is not presented as a win.
- **Bayesian rows.** One per hazard (1, 2, 5 years), each with its own tuned T. The default hazard in the UI is 2 years.
- **Calibration.** Uses the p series with no restarts, from day 250, over all test strategy-days.
- **Cost card.** Uses the fitted μ. "Average return" in the evidence text is the plain sample mean.
- **"CUSUM fired" in the UI** means S > c on the day being judged, not "fired at any point".
- **Extra control.** An "as of day" slider, default day 540, so the risk slider can visibly move the recommendation. On the last day, p ≈ 1 and every setting says kill.
- **Equity and drawdown** are additive (sum of returns), not compounded.
- **Styling.** Light theme only, for projector contrast. Chart colours are the validated categorical palette from the dataviz skill.

## Not built yet

- No "was the edge ever real?" gate. The tool assumes the first 250 days were genuinely profitable.
- No real historical episodes. Everything is simulated.
- No decision journal recording what was recommended and what the trader did.
- The keep / investigate / reduce bands are a heuristic. Only the kill line T is tuned.
- No CSV upload. It would need the Student-t fit and detectors ported to the browser, or a backend.

## Review notes

A two-axis review (standards and spec) ran against the `start` commit.

**Fixed, because they made a shown number wrong:**
- **Calibration.** The calibration p series ran through the warm-up instead of starting at 0 on day 250. That moved some bins by up to 0.13. There is now a regression test in `tests/test_evaluate.py`.
- **Trade-off marker.** With hazard 1y and f > 1.28, T_eff goes above 1 and the rule can never kill. The marker used to claim T_eff ≈ 0.995. It now says the rule never kills.
- **Verdict.** The scoreboard verdict now asks whether the *default* tuned Bayesian rule (2y) won, not whether any Bayesian row did.

**Deferred, because nothing is wrong today but a later edit could make it wrong:**
- **Fire comparison.** The `>=` / `>` rules are written in `core/detectors.py`, `core/run.py` and `web/src/App.jsx`. `demo.fire_day` in the JSON is unused by the page.
- **k = 1 in the cost card.** `logic.js` `costs()` hard-codes k = 1. Pass `config.k_broken` in if k ever changes.
- **Hard-coded constants in the page.** These include the 2/3 broken share, break day 450, `domain={[0, 749]}` and the band edges in the slider label. They should come from `config` / `logic.js`.
- **String rule keys.** Keys like `bayes_2y` are built in several places.
- **Repeated argument triple.** `(returns, llr, break_day)` travels together, and `core/run.py` `main` does too many jobs.
- **Python decision rule.** `core/actions.py` is only exercised by tests. The browser copy in `logic.js` is what runs, with the same test cases.
- **Unused detector inputs.** The detector `step(state, r, llr)` ignores `r` (Bayes, CUSUM) or `llr` (drawdown).
- **Multiple comparison.** Three Bayesian hazard rows on the test board are a mild multiple comparison. The headline verdict uses only the default 2y row.
