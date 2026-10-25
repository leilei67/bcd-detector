"""Simulated strategies: healthy, sudden break, slow decay. Student-t noise around a known mean path."""
from dataclasses import dataclass

import numpy as np

N_DAYS = 750
WARMUP = 250
MU = 0.0015  # healthy daily mean; with SCALE/NU below, annual Sharpe ~2.1
SCALE = 0.008  # Student-t scale (daily std = SCALE * sqrt(NU / (NU - 2)))
NU = 4.0
DECAY_DAYS = 120
KINDS = ("healthy", "sudden", "decay")


@dataclass(frozen=True)
class StrategySet:
    returns: np.ndarray  # (n, N_DAYS)
    mean: np.ndarray  # (n, N_DAYS) true daily mean
    kind: np.ndarray  # (n,) one of KINDS
    break_day: np.ndarray  # (n,) first day the true mean is <= 0; N_DAYS if never


def simulate(n: int, seed: int) -> StrategySet:
    rng = np.random.default_rng(seed)
    kind = np.array([KINDS[i * 3 // n] for i in range(n)])
    mean = np.full((n, N_DAYS), MU)
    break_day = np.full(n, N_DAYS)
    days = np.arange(N_DAYS)
    for i in range(n):
        if kind[i] == "sudden":
            b = rng.integers(WARMUP + 10, N_DAYS - 10)
            mean[i, b:] = -MU
            break_day[i] = b
        elif kind[i] == "decay":
            start = rng.integers(WARMUP + 10, N_DAYS - DECAY_DAYS)
            frac = np.clip((days - start) / DECAY_DAYS, 0.0, 1.0)
            mean[i] = MU - 2 * MU * frac
            break_day[i] = start + DECAY_DAYS // 2  # mean crosses zero halfway
    returns = mean + SCALE * rng.standard_t(NU, size=(n, N_DAYS))
    return StrategySet(returns=returns, mean=mean, kind=kind, break_day=break_day)


def demo_strategy(break_day: int = 450) -> np.ndarray:
    """The bundled demo: one strategy with a sudden break.

    Uses the first seed whose warm-up looks like a typical healthy run (sample mean
    within 20% of MU). The rule never looks at what happens after the warm-up, so
    it does not pick a seed where the detectors happen to look good.
    """
    mean = np.where(np.arange(N_DAYS) < break_day, MU, -MU)
    for seed in range(1000):
        r = mean + SCALE * np.random.default_rng(seed).standard_t(NU, size=N_DAYS)
        if abs(r[:WARMUP].mean() - MU) <= 0.2 * MU:
            return r
    raise RuntimeError("no typical warm-up found")
