"""Bundled real datasets: one fixed rule (WINDOW_DAYS trading days ending on a stated date), one reason each.

`scripts/fetch_data.py` downloads and writes data/<id>.csv; `python -m core.run` analyses them.
"""
WINDOW_DAYS = 750
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
SOURCES = {
    "ff3": FRENCH + "F-F_Research_Data_Factors_daily_CSV.zip",
    "mom": FRENCH + "F-F_Momentum_Factor_daily_CSV.zip",
}
FACTORS = {
    "Mom": "Kenneth French's daily momentum factor (long last year's winners, short last year's losers)",
    "HML": "Kenneth French's daily value factor (long cheap stocks by book-to-market, short expensive ones)",
    "Mkt-RF": "Kenneth French's daily US stock market return above the one-month T-bill rate",
}
NOW_REASON = f"the latest {WINDOW_DAYS} trading days in the source file, so no hindsight went into choosing it."

REAL = [
    {"id": "umd_2009", "strategy": "Momentum", "note": "2009 crash",
     "source": "mom", "column": "Mom", "end": "2009-12-31",
     "reason": "the 2009 momentum crash is the textbook 'broken or bad run?' case."},
    {"id": "umd_2020", "strategy": "Momentum", "note": "2020 vaccine-news day",
     "source": "mom", "column": "Mom", "end": "2020-12-31",
     "reason": "it contains 9 Nov 2020, when vaccine news hit momentum for -14.4%, its worst day of 2020."},
    {"id": "hml_2020", "strategy": "Value", "note": "value slump",
     "source": "ff3", "column": "HML", "end": "2020-12-31",
     "reason": "value's long slump, which deepened sharply in 2020."},
    {"id": "umd_now", "strategy": "Momentum", "note": "latest", "source": "mom", "column": "Mom",
     "end": None, "reason": NOW_REASON},
    {"id": "hml_now", "strategy": "Value", "note": "latest", "source": "ff3", "column": "HML",
     "end": None, "reason": NOW_REASON},
    {"id": "mkt_now", "strategy": "US market", "note": "latest", "source": "ff3", "column": "Mkt-RF",
     "end": None, "reason": NOW_REASON},
]
