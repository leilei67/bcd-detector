import pytest

from core.french import parse_french_csv, select_window

SAMPLE = """This file was created by using the 202608 CRSP database.
Missing data are indicated by -99.99 or -999.

,Mkt-RF,SMB,HML,RF
20200102,    0.45,   -0.34,   -0.03,    0.01
20200103,   -1.20,    0.10,    0.50,    0.01
20200106,    0.30,   -99.99,    0.25,    0.01
20200107,    0.10,    0.20,    0.05,    0.01

 Annual Factors: January-December
,Mkt-RF,SMB,HML,RF
  2020,   20.00,   10.00,   -30.00,    0.40

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""


def test_reads_one_column_of_the_first_table_as_decimals():
    dates, values = parse_french_csv(SAMPLE, "HML")
    assert dates == ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    assert values == pytest.approx([-0.0003, 0.005, 0.0025, 0.0005])


def test_unknown_column_fails_loudly():
    with pytest.raises(ValueError, match="Mom"):
        parse_french_csv(SAMPLE, "Mom")


def test_window_ends_on_last_trading_day_on_or_before_end():
    dates, values = parse_french_csv(SAMPLE, "HML")
    d, v = select_window(dates, values, end="2020-01-05", days=2)
    assert d == ["2020-01-02", "2020-01-03"]


def test_window_defaults_to_latest_date():
    dates, values = parse_french_csv(SAMPLE, "Mkt-RF")
    d, _ = select_window(dates, values, end=None, days=3)
    assert d == ["2020-01-03", "2020-01-06", "2020-01-07"]


def test_missing_marker_inside_window_fails_loudly_but_not_outside():
    dates, values = parse_french_csv(SAMPLE, "SMB")
    with pytest.raises(ValueError, match="missing"):
        select_window(dates, values, end=None, days=2)
    d, _ = select_window(dates, values, end="2020-01-03", days=2)
    assert d == ["2020-01-02", "2020-01-03"]


def test_too_little_history_fails_loudly():
    dates, values = parse_french_csv(SAMPLE, "HML")
    with pytest.raises(ValueError, match="only 4"):
        select_window(dates, values, end=None, days=10)
