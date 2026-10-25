"""Read Kenneth French Data Library daily CSVs (percent returns) into decimal series."""
from datetime import date

MISSING = (-99.99, -999.0)
MAX_GAP_DAYS = 7  # a window must end within a week of its stated end date (weekends, holidays)


def parse_french_csv(text: str, column: str):
    """First table in the file only (later tables are monthly/annual).

    Returns (ISO dates, decimal values); missing-data markers become None.
    """
    lines = text.splitlines()
    header = next((i for i, line in enumerate(lines)
                   if line.startswith(",") and column in [c.strip() for c in line.split(",")]), None)
    if header is None:
        raise ValueError(f"column {column!r} not found in a table header")
    j = [c.strip() for c in lines[header].split(",")].index(column)
    dates, values = [], []
    for line in lines[header + 1:]:
        parts = [p.strip() for p in line.split(",")]
        if not (parts[0].isdigit() and len(parts[0]) == 8):
            break
        raw = float(parts[j])
        dates.append(f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]}")
        values.append(None if raw in MISSING else raw / 100)
    return dates, values


def select_window(dates, values, end, days):
    """The `days` trading days ending on the last date <= `end` (ISO), or at the latest date if end is None."""
    if end is None:
        stop = len(dates)
    else:
        target = date.fromisoformat(end)  # rejects typos like "2020-1-5"
        stop = sum(1 for d in dates if date.fromisoformat(d) <= target)
        if stop and (target - date.fromisoformat(dates[stop - 1])).days > MAX_GAP_DAYS:
            raise ValueError(f"window was meant to end {end}, but the data stops at {dates[stop - 1]}")
    if stop < days:
        raise ValueError(f"need {days} trading days ending {end or 'latest'}, only {stop} available")
    d, v = dates[stop - days:stop], values[stop - days:stop]
    bad = [day for day, x in zip(d, v) if x is None]
    if bad:
        raise ValueError(f"missing-data marker inside the window on {', '.join(bad[:5])}")
    return d, v
