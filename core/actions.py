"""Recommendation rule. Only the kill line T is tuned; the lower bands are a risk-appetite heuristic.

Mirrored in web/src/logic.js for the live slider; keep the two in step.
"""


def decide_action(p: float, cusum_fired: bool, T: float, f: float = 1.0) -> str:
    t_eff = f * T
    if p >= t_eff:
        return "kill"
    if cusum_fired:
        return "pause"
    if p >= 2 / 3 * t_eff:
        return "reduce"
    if p >= 1 / 3 * t_eff:
        return "investigate"
    return "keep"
