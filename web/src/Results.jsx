import React from "react";
import {
  CartesianGrid, ReferenceDot, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import { C, pct } from "./theme.js";
import { nearestPoint } from "./logic.js";

const AXIS = { fontSize: 14, fill: C.ink2 };
const axisLabel = (value, axis) =>
  axis === "x"
    ? { value, position: "insideBottom", offset: -6, fontSize: 15, fill: C.ink2 }
    : { value, angle: -90, position: "insideLeft", offset: 10, fontSize: 15, fill: C.ink2, style: { textAnchor: "middle" } };

function Tip({ active, payload, lines }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "#fff", border: "1px solid #ccc", padding: "6px 10px", fontSize: 15 }}>
      {lines(d).map((l) => <div key={l}>{l}</div>)}
    </div>
  );
}

export function Tradeoff({ res, hazard, tEff }) {
  const curve = res.tradeoff[hazard].map((d) => ({ ...d, slow: 100 * d.slow_cost }));
  const cur = nearestPoint(curve, tEff);
  const nBroken = (2 / 3) * res.config.test.n;
  return (
    <section>
      <h2>6. The trade-off: kill too early or too late</h2>
      <p className="caption">Each point is a kill line T on the test set: a lower line kills more healthy strategies, a higher line loses more money after a real break.</p>
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 10, right: 24, left: 16, bottom: 24 }}>
          <CartesianGrid stroke={C.grid} />
          <XAxis type="number" dataKey="false_kills" name="False kills" tick={AXIS}
            label={axisLabel(`False kills (of ${res.config.test.n} strategies)`, "x")} />
          <YAxis type="number" dataKey="slow" name="Slow-kill cost" tick={AXIS} tickFormatter={(v) => `${v}%`}
            label={axisLabel("Slow-kill cost per broken strategy", "y")} width={70} />
          <Tooltip content={<Tip lines={(d) => [`T = ${d.T}`, `${d.false_kills} false kills`,
            `slow-kill cost ${d.slow.toFixed(2)}%`, `mean regret ${pct(d.mean_regret)}`]} />} />
          <Scatter data={curve} fill={C.bayes} line={{ stroke: C.bayes, strokeWidth: 2 }} isAnimationActive={false} />
          <ReferenceDot x={cur.false_kills} y={cur.slow} r={11} fill="none" stroke={C.ink} strokeWidth={3}
            label={{ value: `T_eff ≈ ${cur.T}`, position: "right", fontSize: 16, fill: C.ink, offset: 14 }} />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="note">
        At T_eff ≈ {cur.T} (hazard {hazard}y): {cur.false_kills} false kills, {cur.slow.toFixed(1)}% lost per broken strategy
        ({Math.round(nBroken)} broken) before the kill, mean regret {pct(cur.mean_regret)}. False kill = fired on a healthy strategy or before its break.
      </p>
    </section>
  );
}

export function Scoreboard({ res }) {
  const board = res.scoreboard;
  const best = board[0];
  const bayesWon = best.rule.startsWith("bayes");
  const clear = board.filter((r) => r !== best && r.gap_vs_best > 2 * r.gap_se);
  const tied = board.filter((r) => r !== best && r.gap_vs_best <= 2 * r.gap_se);
  return (
    <section>
      <h2>7. Scoreboard (test set only)</h2>
      <p className="caption">
        Every threshold was tuned on {res.config.train.n} training strategies (seed {res.config.train.seed}) and is scored here on {res.config.test.n} fresh ones
        (seed {res.config.test.seed}); regret is profit lost against an oracle that stops exactly at the true break.
      </p>
      <p className="verdict">
        {bayesWon ? <><b>{best.label}</b> has the lowest test regret.</> : <><b>The tuned Bayesian rule did not win on the test set:</b> {best.label} did.</>}{" "}
        {clear.length > 0 && <>Clearly better than {clear.map((r) => r.label).join(", ")}. </>}
        {tied.length > 0 && <>Within noise (gap under 2 standard errors) of {tied.map((r) => r.label).join(", ")}.</>}
      </p>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Rule</th><th>Tuned threshold</th><th>Mean regret</th><th>Gap vs best (paired)</th>
              <th>False kills</th><th>Missed breaks</th><th>Mean delay</th><th>Slow-kill cost</th>
            </tr>
          </thead>
          <tbody>
            {board.map((r) => (
              <tr key={r.rule} className={r === best ? "best" : ""}>
                <td>{r.label}</td>
                <td>{r.threshold ?? "–"}</td>
                <td>{pct(r.mean_regret)} ± {pct(r.se_regret)}</td>
                <td>{r === best ? "–" : `+${pct(r.gap_vs_best)} ± ${pct(r.gap_se)}`}</td>
                <td>{r.false_kills}</td>
                <td>{r.missed_breaks}</td>
                <td>{r.mean_delay == null ? "–" : `${r.mean_delay.toFixed(0)} d`}</td>
                <td>{pct(r.mean_slow_cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        Regret in % of capital per strategy (± standard error). False kills: strategies killed while healthy or before their break (of {res.config.test.n}).
        Missed: broken strategies never killed after the break (of {Math.round((2 / 3) * res.config.test.n)}). Delay: days from break to first kill, detected ones only.
        After any kill the rule sits out {res.config.redeploy_days} days, then restarts with detectors reset.
      </p>
    </section>
  );
}

export function Calibration({ res, hazard }) {
  const bins = res.calibration[hazard].filter((b) => b.count > 0);
  return (
    <section>
      <h2>8. Is the probability honest?</h2>
      <p className="caption">When the model says "30% broken", about 30% of those days should really be broken: points on the diagonal mean the probability can be taken at face value.</p>
      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 10, right: 24, left: 16, bottom: 24 }}>
          <CartesianGrid stroke={C.grid} />
          <XAxis type="number" dataKey="mean_p" domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tick={AXIS}
            label={axisLabel("Predicted P(broken), binned", "x")} />
          <YAxis type="number" dataKey="frac_broken" domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tick={AXIS}
            label={axisLabel("Fraction really broken", "y")} width={70} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={C.ink2} strokeDasharray="6 4"
            label={{ value: "perfect calibration", position: "insideTopLeft", fontSize: 14, fill: C.ink2 }} />
          <Tooltip content={<Tip lines={(d) => [`bin ${d.lo.toFixed(1)}–${d.hi.toFixed(1)}`, `predicted ${d.mean_p.toFixed(2)}`,
            `actually broken ${d.frac_broken.toFixed(2)}`, `${d.count.toLocaleString()} strategy-days`]} />} />
          <Scatter data={bins} fill={C.bayes} isAnimationActive={false} shape={(props) => (
            <circle cx={props.cx} cy={props.cy} r={8} fill={C.bayes} stroke="#fff" strokeWidth={2} />
          )} />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="note">All {res.config.test.n} test strategies × {res.config.n_days - res.config.warmup} post-warm-up days, hazard {hazard}y, no restarts. Below the line, the model is more alarmed than it should be; above it, less.</p>
    </section>
  );
}
