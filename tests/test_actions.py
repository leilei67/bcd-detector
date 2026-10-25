import pytest

from core.actions import decide_action

# T = 0.6, f = 1 -> T_eff = 0.6; bands at 0.2 and 0.4


@pytest.mark.parametrize(
    "p, expected",
    [(0.0, "keep"), (0.19, "keep"), (0.2, "investigate"), (0.39, "investigate"),
     (0.4, "reduce"), (0.59, "reduce"), (0.6, "kill"), (1.0, "kill")],
)
def test_bands_without_cusum(p, expected):
    assert decide_action(p, cusum_fired=False, T=0.6, f=1.0) == expected


def test_pause_when_cusum_fired_and_p_below_kill_line():
    assert decide_action(0.1, cusum_fired=True, T=0.6, f=1.0) == "pause"
    assert decide_action(0.5, cusum_fired=True, T=0.6, f=1.0) == "pause"


def test_kill_beats_pause():
    assert decide_action(0.7, cusum_fired=True, T=0.6, f=1.0) == "kill"


def test_risk_factor_scales_kill_line():
    # f = 0.5 -> T_eff = 0.3: p = 0.35 kills; f = 1.5 -> T_eff = 0.9: p = 0.35 investigates
    assert decide_action(0.35, cusum_fired=False, T=0.6, f=0.5) == "kill"
    assert decide_action(0.35, cusum_fired=False, T=0.6, f=1.5) == "investigate"
