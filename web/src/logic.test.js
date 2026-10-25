import { test } from "node:test";
import assert from "node:assert/strict";
import { decideAction, costs, evidence, nearestPoint } from "./logic.js";

// Same cases as tests/test_actions.py: T = 0.6, f = 1 -> bands at 0.2, 0.4, 0.6
test("bands without CUSUM", () => {
  const cases = [[0, "keep"], [0.19, "keep"], [0.2, "investigate"], [0.39, "investigate"],
    [0.4, "reduce"], [0.59, "reduce"], [0.6, "kill"], [1, "kill"]];
  for (const [p, want] of cases) assert.equal(decideAction(p, false, 0.6, 1), want, `p=${p}`);
});

test("pause when CUSUM fired and p below kill line; kill beats pause", () => {
  assert.equal(decideAction(0.1, true, 0.6, 1), "pause");
  assert.equal(decideAction(0.5, true, 0.6, 1), "pause");
  assert.equal(decideAction(0.7, true, 0.6, 1), "kill");
});

test("risk factor scales the kill line", () => {
  assert.equal(decideAction(0.35, false, 0.6, 0.5), "kill");
  assert.equal(decideAction(0.35, false, 0.6, 1.5), "investigate");
});

test("costs: continue = p|mu|60, kill = (1-p)mu60", () => {
  const c = costs(0.25, 0.002);
  assert.ok(Math.abs(c.continue - 0.25 * 0.002 * 60) < 1e-12);
  assert.ok(Math.abs(c.kill - 0.75 * 0.002 * 60) < 1e-12);
});

test("evidence over the last 60 days", () => {
  // 60 days alternating +-0.02 around mean -0.01 -> mean -0.01, sample std ~0.02017
  const recent = Array.from({ length: 60 }, (_, i) => -0.01 + (i % 2 ? 0.02 : -0.02));
  const returns = [...Array(10).fill(0.5), ...recent];
  const e = evidence(returns, 69, { mean: 0.001, std: 0.01 }, 4.2);
  assert.ok(Math.abs(e.recentMean - -0.01) < 1e-12);
  assert.ok(Math.abs(e.volRatio - 2.0169) < 1e-3);
  assert.equal(e.baselineMean, 0.001);
  assert.equal(e.depth, 4.2);
});

test("nearestPoint picks the grid T closest to T_eff", () => {
  const curve = [{ T: 0.1 }, { T: 0.3 }, { T: 0.6 }];
  assert.equal(nearestPoint(curve, 0.42).T, 0.3);
  assert.equal(nearestPoint(curve, 0.9).T, 0.6);
});
