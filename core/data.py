"""Read a user's `date, return` CSV and say plainly what is wrong with it."""
import csv
import io
from datetime import date

import numpy as np

from core.sim import WARMUP

MIN_DAYS = WARMUP + 60
PERCENT_MEDIAN = 0.05  # a median daily move of 5% only makes sense if the file is in percent
MAX_LISTED = 5


class CsvError(ValueError):
    def __init__(self, messages):
        super().__init__("; ".join(messages))
        self.messages = messages


def parse_returns_csv(text: str):
    """Returns (ISO date strings, decimal returns). Raises CsvError listing every problem found."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().lower() for h in next(reader, [])]
    if "date" not in header or "return" not in header:
        raise CsvError(["Expected columns: date, return (one header row, then one row per trading day)."])
    di, ri = header.index("date"), header.index("return")

    dates, returns, bad = [], [], []
    for line, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        cells = row + [""] * (max(di, ri) + 1 - len(row))
        d, r = cells[di].strip(), cells[ri].strip()
        try:
            day = date.fromisoformat(d)
        except ValueError:
            bad.append(f"line {line}: date '{d}' is not YYYY-MM-DD")
            continue
        try:
            value = float(r)
            if not np.isfinite(value):
                raise ValueError
        except ValueError:
            bad.append(f"line {line}: return '{r}' is missing or not a number")
            continue
        dates.append(day)
        returns.append(value)

    messages = []
    if bad:
        more = f" (and {len(bad) - MAX_LISTED} more)" if len(bad) > MAX_LISTED else ""
        messages.append(f"{len(bad)} unreadable rows: " + "; ".join(bad[:MAX_LISTED]) + more)
    if len(returns) < MIN_DAYS:
        messages.append(f"Need at least {MIN_DAYS} days ({WARMUP} warm-up + 60 to judge); got {len(returns)}.")
    r = np.array(returns)
    if len(r) and np.median(np.abs(r)) > PERCENT_MEDIAN:
        messages.append(f"Returns look like percentages (median daily move {np.median(np.abs(r)):.2f}). "
                        "Divide by 100 so 1% is written 0.01.")
    seen, dupes = set(), []
    for d in dates:
        if d in seen:
            dupes.append(d.isoformat())
        seen.add(d)
    if dupes:
        messages.append(f"Duplicate dates: {', '.join(dupes[:MAX_LISTED])}" + (" …" if len(dupes) > MAX_LISTED else ""))
    if any(b < a for a, b in zip(dates, dates[1:])):
        first = next(i for i, (a, b) in enumerate(zip(dates, dates[1:])) if b < a)
        messages.append(f"Dates are not in increasing order (first at {dates[first + 1].isoformat()}). Sort the file by date.")
    if messages:
        raise CsvError(messages)
    return [d.isoformat() for d in dates], r
