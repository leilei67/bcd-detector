"""Download the Kenneth French daily factors and write every bundled window to data/<id>.csv.

Source files are in percent; outputs are decimal returns. Fails loudly if a
window is short or contains a missing-data marker.

    uv run python scripts/fetch_data.py
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.datasets import REAL, SOURCES, WINDOW_DAYS  # noqa: E402
from core.french import parse_french_csv, select_window  # noqa: E402


def download(url):
    raw = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url, timeout=60).read()))
    return raw.read(raw.namelist()[0]).decode("latin-1")


def main():
    texts = {key: download(url) for key, url in SOURCES.items()}
    for ds in REAL:
        dates, values = parse_french_csv(texts[ds["source"]], ds["column"])
        d, v = select_window(dates, values, ds["end"], WINDOW_DAYS)
        out = ROOT / "data" / f"{ds['id']}.csv"
        out.write_text("date,return\n" + "".join(f"{a},{b:.6f}\n" for a, b in zip(d, v)))
        print(f"wrote {out.name}: {d[0]}..{d[-1]}")


if __name__ == "__main__":
    main()
