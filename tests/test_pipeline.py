import numpy as np

from core.model import fit_baseline
from core.pipeline import analyse, analyse_csv
from core.sim import demo_strategy

N = 30  # small re-simulated sets keep the test fast; the app uses 300


def test_same_input_gives_same_thresholds():
    r = demo_strategy()
    assert analyse(r, n=N)["tuned"] == analyse(r, n=N)["tuned"]


def test_real_series_is_tuned_on_simulations_from_its_own_fit():
    r = demo_strategy()
    res = analyse(r, dates=[f"d{i}" for i in range(len(r))], n=N)
    b = fit_baseline(r[:250])
    assert np.allclose(res["dataset"]["sim_params"], [b.mu, b.sigma, b.nu])
    assert res["demo"]["break_day"] is None
    assert res["demo"]["dates"][0] == "d0"


def test_series_length_need_not_match_simulations():
    res = analyse(demo_strategy()[:400], n=N)
    assert len(res["demo"]["p"]["2"]) == 400 - 250


def test_no_edge_in_warmup_gives_warning_not_recommendation():
    r = demo_strategy().copy()
    r[:250] -= 0.01  # warm-up clearly loses money
    res = analyse(r, n=N)
    assert res["warning"] and "tuned" not in res


def test_csv_errors_come_back_as_messages():
    assert "at least 310" in " ".join(analyse_csv("date,return\n2020-01-01,0.01\n")["errors"])


def test_long_series_is_tuned_on_simulations_of_the_same_length():
    r = np.concatenate([demo_strategy(), demo_strategy()[250:]])  # 1250 days
    res = analyse(r, n=N)
    assert res["config"]["sim_days"] == 1250 and res["config"]["n_days"] == 1250
