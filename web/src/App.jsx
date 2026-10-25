import React, { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { WINDOW, costs, decideAction, evidence } from "./logic.js";
import { Calibration, Scoreboard, Tradeoff } from "./Results.jsx";
import { C, pct } from "./theme.js";

const AXIS = { fontSize: 14, fill: C.ink2 };
const DAY_TICKS = [0, 100, 200, 300, 400, 500, 600, 700];

const ACTIONS = {
  keep: { color: "var(--good)", icon: "✓" },
  investigate: { color: "var(--warning)", icon: "?" },
  reduce: { color: "var(--serious)", icon: "▼" },
  pause: { color: "var(--serious)", icon: "❚❚" },
  kill: { color: "var(--critical)", icon: "✕" },
};

export default function App() {
  const [res, setRes] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetch("results.json").then((r) => r.json()).then(setRes).catch((e) => setError(String(e)));
  }, []);
  if (error) return <main><p>Could not load results.json ({error}). Run <code>uv run python -m core.run</code> first.</p></main>;
  if (!res) return <main><p>Loading…</p></main>;
  return <Demo res={res} />;
}

function Demo({ res }) {
  const { demo, tuned, config } = res;
  const warmup = demo.warmup;
  const [f, setF] = useState(1);
  const [hazard, setHazard] = useState(String(config.default_hazard));
  const [day, setDay] = useState(540);

  const T = tuned.T[hazard];
  const tEff = f * T;
  const p = demo.p[hazard];
  const i = day - warmup; // index into the post-warm-up detector series

  const series = useMemo(() => {
    let eq = 0;
    return demo.returns.map((r, d) => ({ day: d, ret: 100 * r, equity: 100 * (eq += r) }));
  }, [demo]);
  const detector = useMemo(
    () => p.map((v, k) => ({ day: k + warmup, p: v, cusum: demo.cusum[k], dd: demo.drawdown[k] })),
    [p, demo, warmup],
  );
  const firstDay = (xs, test) => {
    const k = xs.findIndex(test);
    return k < 0 ? null : k + warmup;
  };
  const fire = {
    bayes: firstDay(p, (v) => v >= tEff),
    cusum: firstDay(demo.cusum, (v) => v > tuned.c),
    dd: firstDay(demo.drawdown, (v) => v > tuned.d),
  };

  const cusumFired = demo.cusum[i] > tuned.c;
  const action = decideAction(p[i], cusumFired, T, f);
  const ev = evidence(demo.returns, day, demo.baseline, demo.drawdown[i]);
  const cost = costs(p[i], demo.baseline.mu);

  const markers = (
    <>
      <ReferenceLine x={day} stroke={C.ink2} strokeWidth={2} />
      <ReferenceLine x={demo.break_day} stroke={C.ink} strokeDasharray="6 4"
        label={{ value: "true break", position: "insideTopLeft", fontSize: 14, fill: C.ink }} />
    </>
  );

  return (
    <main>
      <h1>Broken, or just a bad run?</h1>
      <p className="sub">
        A kill-switch adviser for a solo trader's strategy. Demo strategy: simulated, healthy for 450 days, then its edge flips negative.
      </p>

      <section>
        <h2>1. The strategy</h2>
        <p className="caption">Cumulative profit and each day's return; the first {warmup} days are assumed healthy and used to learn what normal looks like.</p>
        <div className="chart-title">Cumulative PnL (% of capital)</div>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={series} syncId="t" margin={{ top: 10, right: 16, left: 4, bottom: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="day" type="number" domain={[0, 749]} ticks={DAY_TICKS} tick={AXIS} />
            <YAxis tick={AXIS} width={52} />
            <ReferenceArea x1={0} x2={warmup} fill={C.grid} fillOpacity={0.5}
              label={{ value: "warm-up (assumed healthy)", position: "insideTop", fontSize: 14, fill: C.ink2 }} />
            {markers}
            <ReferenceLine x={day} stroke="none"
              label={{ value: `as of day ${day}`, position: "insideBottomRight", fontSize: 14, fill: C.ink2 }} />
            <Tooltip formatter={(v) => `${v.toFixed(2)}%`} labelFormatter={(d) => `day ${d}`} />
            <Line dataKey="equity" name="Cumulative PnL" stroke={C.ink} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        <div className="chart-title">Daily return (%)</div>
        <ResponsiveContainer width="100%" height={150}>
          <BarChart data={series} syncId="t" margin={{ top: 6, right: 16, left: 4, bottom: 0 }} barCategoryGap={0}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="day" type="number" domain={[0, 749]} ticks={DAY_TICKS} tick={AXIS} />
            <YAxis tick={AXIS} width={52} />
            <ReferenceLine y={0} stroke={C.ink2} />
            <ReferenceLine x={demo.break_day} stroke={C.ink} strokeDasharray="6 4" />
            <Tooltip formatter={(v) => `${v.toFixed(2)}%`} labelFormatter={(d) => `day ${d}`} />
            <Bar dataKey="ret" name="Return" fill={C.ink2} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h2>2. Three detectors, one timeline</h2>
        <p className="caption">Each detector watches the same returns; the dashed horizontal line is its tuned trigger, the coloured vertical line is the day it first fires, and the grey line is the day being judged.</p>
        <DetectorChart data={detector} k="p" color={C.bayes} markers={markers} fire={fire.bayes}
          title={`Bayesian: probability the strategy is broken (hazard ${hazard}y, kill line T_eff = ${tEff.toFixed(2)})`}
          threshold={tEff} domain={[0, 1]} fmt={(v) => v.toFixed(2)} />
        <DetectorChart data={detector} k="cusum" color={C.cusum} markers={markers} fire={fire.cusum}
          title={`CUSUM: accumulated evidence for "broken" (trigger c = ${tuned.c})`}
          threshold={tuned.c} fmt={(v) => v.toFixed(1)} />
        <DetectorChart data={detector} k="dd" color={C.dd} markers={markers} fire={fire.dd}
          title={`Drawdown depth in daily sigmas (trigger d = ${tuned.d})`}
          threshold={tuned.d} fmt={(v) => v.toFixed(1)} />
      </section>

      <section>
        <h2>3. Recommendation, as of day {day}</h2>
        <p className="caption">What to do today, from the Bayesian probability, the CUSUM alarm and the kill line set by the risk slider below.</p>
        <div className="row" style={{ alignItems: "center" }}>
          <div>
            <span className="action" style={{ borderColor: ACTIONS[action].color }}>
              <span aria-hidden="true" style={{ color: ACTIONS[action].color }}>{ACTIONS[action].icon}</span>
              {action}
            </span>
          </div>
          <div className="tile" style={{ flex: "0 1 300px" }}>
            <div className="label">P(broken)</div>
            <div className="value">{p[i].toFixed(2)}</div>
          </div>
          <div className="tile" style={{ flex: "0 1 300px" }}>
            <div className="label">CUSUM alarm</div>
            <div className="value" style={{ fontSize: 28 }}>{cusumFired ? "fired" : "quiet"} ({demo.cusum[i].toFixed(1)} vs {tuned.c})</div>
          </div>
        </div>
        <p className="evidence">
          Average return {ev.recentMean < ev.baselineMean ? "fell" : "rose"} from {pct(ev.baselineMean)} to {pct(ev.recentMean)} a day
          over the last {WINDOW} days; volatility is {ev.volRatio.toFixed(1)}× normal; drawdown is {ev.depth.toFixed(1)} sigmas deep.
        </p>
      </section>

      <section>
        <h2>4. What each mistake would cost</h2>
        <p className="caption">Rough expected cost over the next {WINDOW} days: carrying on with a broken strategy versus switching off one that is still fine.</p>
        <div className="row">
          <div className="tile">
            <div className="label">Cost of continuing ≈ p · |μ| · {WINDOW}</div>
            <div className="value" style={{ color: cost.continue > cost.kill ? "var(--critical)" : C.ink }}>{pct(cost.continue)}</div>
            <div className="note">loss if it really is broken, weighted by p = {p[i].toFixed(2)}</div>
          </div>
          <div className="tile">
            <div className="label">Cost of killing ≈ (1 − p) · μ · {WINDOW}</div>
            <div className="value" style={{ color: cost.kill > cost.continue ? "var(--critical)" : C.ink }}>{pct(cost.kill)}</div>
            <div className="note">profit given up if it is still healthy (μ = {pct(demo.baseline.mu, 3)} a day)</div>
          </div>
        </div>
        <p className="note">Back-of-envelope: assumes "broken" means the mean flips to −|μ| (k = {config.k_broken}) and ignores re-deploy costs. The bigger number is the mistake to fear.</p>
      </section>

      <section>
        <h2>5. Your risk appetite</h2>
        <p className="caption">Slide to make the kill line stricter or looser, pick how often you expect strategies to break, and scrub the day being judged.</p>
        <div className="controls">
          <div>
            <label htmlFor="f">Risk factor f = {f.toFixed(2)} → kill line T_eff = {tEff.toFixed(2)}</label>
            <input id="f" type="range" min={0.5} max={1.5} step={0.05} value={f} onChange={(e) => setF(Number(e.target.value))} />
            <div className="bands">
              keep &lt; {(tEff / 3).toFixed(2)} ≤ investigate &lt; {((2 * tEff) / 3).toFixed(2)} ≤ reduce &lt; {tEff.toFixed(2)} ≤ kill
            </div>
            <div className="note">Only T = {T} is tuned (on the training set). The lower bands are a risk-appetite heuristic, not tuned. CUSUM alarm below the kill line → pause.</div>
          </div>
          <div>
            <label>Expected time between breaks (hazard)</label>
            <div className="seg">
              {config.hazard_years.map((y) => (
                <button key={y} aria-pressed={hazard === String(y)} onClick={() => setHazard(String(y))}>{y} yr</button>
              ))}
            </div>
            <div className="note">Each hazard has its own tuned T: {config.hazard_years.map((y) => `${y}y → ${tuned.T[y]}`).join(", ")}.</div>
          </div>
          <div>
            <label htmlFor="day">As of day {day}</label>
            <input id="day" type="range" min={warmup} max={config.n_days - 1} step={1} value={day} onChange={(e) => setDay(Number(e.target.value))} />
            <div className="note">True break is day {demo.break_day}.</div>
          </div>
        </div>
      </section>

      <Tradeoff res={res} hazard={hazard} tEff={tEff} />
      <Scoreboard res={res} />
      <Calibration res={res} hazard={hazard} />
    </main>
  );
}

function DetectorChart({ data, k, color, title, threshold, domain, fmt, fire, markers }) {
  return (
    <>
      <div className="chart-title">
        <span style={{ display: "inline-block", width: 18, height: 3, background: color, verticalAlign: "middle", marginRight: 8 }} />
        {title} — {fire == null ? "does not fire" : `fires day ${fire}`}
      </div>
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={data} syncId="t" margin={{ top: 10, right: 16, left: 4, bottom: 0 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="day" type="number" domain={[0, 749]} ticks={DAY_TICKS} tick={AXIS} />
          <YAxis tick={AXIS} width={52} domain={domain ?? [0, "auto"]} tickFormatter={fmt} />
          {markers}
          <ReferenceLine y={threshold} stroke={color} strokeDasharray="4 4" strokeWidth={2} ifOverflow="extendDomain" />
          {fire != null && <ReferenceLine x={fire} stroke={color} strokeWidth={3} />}
          <Tooltip formatter={(v) => fmt(v)} labelFormatter={(d) => `day ${d}`} />
          <Line dataKey={k} name={title.split(":")[0]} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}
