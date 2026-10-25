"""Download Kenneth French's daily momentum factor and write the bundled demo window.

Window rule: the 750 trading days ending 2009-12-31, the same shape as the
simulated strategies (250-day warm-up, then 500 days to judge). The source
file is in percent; the output is decimal returns.

    uv run python scripts/fetch_umd.py
"""
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"
END, DAYS = "20091231", 750
OUT = Path(__file__).resolve().parent.parent / "data" / "umd_2007_2009.csv"


def main():
    raw = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(URL, timeout=60).read()))
    text = raw.read(raw.namelist()[0]).decode("latin-1")
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 8:
            rows.append((parts[0], float(parts[1])))
    rows = [r for r in rows if r[0] <= END][-DAYS:]
    assert len(rows) == DAYS and rows[-1][0] == END
    assert all(v > -99 for _, v in rows), "missing-data marker inside the window"
    lines = ["date,return"] + [f"{d[:4]}-{d[4:6]}-{d[6:]},{v / 100:.6f}" for d, v in rows]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} ({rows[0][0]}..{rows[-1][0]})")


if __name__ == "__main__":
    main()
