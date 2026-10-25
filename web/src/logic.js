// Live-demo maths that must react to the risk slider. Mirrors core/actions.py; keep the two in step.

export const WINDOW = 60;

export function decideAction(p, cusumFired, T, f = 1) {
  const tEff = f * T;
  if (p >= tEff) return "kill";
  if (cusumFired) return "pause";
  if (p >= (2 / 3) * tEff) return "reduce";
  if (p >= (1 / 3) * tEff) return "investigate";
  return "keep";
}

// Expected cost over the next WINDOW days, as a fraction of capital.
export function costs(p, mu, days = WINDOW) {
  return { continue: p * Math.abs(mu) * days, kill: (1 - p) * mu * days };
}

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const std = (xs) => {
  const m = mean(xs);
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
};

// returns: full series; day: as-of index; baseline: warm-up sample mean/std; depth: drawdown sigmas at day.
export function evidence(returns, day, baseline, depth, days = WINDOW) {
  const recent = returns.slice(Math.max(0, day - days + 1), day + 1);
  return { baselineMean: baseline.mean, recentMean: mean(recent), volRatio: std(recent) / baseline.std, depth };
}

export function nearestPoint(curve, tEff) {
  return curve.reduce((best, pt) => (Math.abs(pt.T - tEff) < Math.abs(best.T - tEff) ? pt : best));
}
