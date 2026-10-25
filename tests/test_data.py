import numpy as np
import pytest

from core.data import CsvError, parse_returns_csv


def csv(rows, header="date,return"):
    return "\n".join([header, *rows]) + "\n"


def days(n, value="0.001", start=0):
    base = np.datetime64("2010-01-01", "D")
    return [f"{base + i},{value}" for i in np.arange(start, start + n).astype("timedelta64[D]")]


def errors_for(text):
    with pytest.raises(CsvError) as e:
        parse_returns_csv(text)
    return " | ".join(e.value.messages)


def test_valid_file_parses_dates_and_decimal_returns():
    dates, r = parse_returns_csv(csv(days(310)))
    assert len(dates) == 310 and dates[0] == "2010-01-01" and np.allclose(r, 0.001)


def test_header_is_case_insensitive_and_order_free():
    dates, r = parse_returns_csv(csv([f"0.002,{d.split(',')[0]}" for d in days(310)], header="Return,Date"))
    assert np.allclose(r, 0.002)


def test_missing_columns():
    assert "date, return" in errors_for(csv(days(310), header="day,pnl"))


def test_unparseable_and_missing_rows_name_the_line():
    rows = days(310)
    rows[4] = "2010-01-05,abc"
    rows[9] = "2010-01-10,"
    rows[14] = "not-a-date,0.001"
    msg = errors_for(csv(rows))
    assert "line 6" in msg and "line 11" in msg and "line 16" in msg


def test_too_short():
    assert "at least 310" in errors_for(csv(days(200)))


def test_percentages_detected():
    assert "percent" in errors_for(csv(days(310, value="1.2")))


def test_duplicate_and_unsorted_dates():
    rows = days(310)
    rows[20] = rows[19]
    assert "Duplicate" in errors_for(csv(rows))
    rows = days(310)
    rows[30], rows[31] = rows[31], rows[30]
    assert "increasing order" in errors_for(csv(rows))


def test_all_problems_reported_together():
    rows = days(100, value="2.0")
    rows[3] = "2010-01-04,x"
    msg = errors_for(csv(rows))
    assert "line 5" in msg and "at least 310" in msg and "percent" in msg
