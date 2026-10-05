"""Loads the project CSVs with the right types."""

import ast
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FILES = {
    "posts":     DATA / "truth_posts.csv",
    "corpus":    DATA / "oil" / "clean_corpus.csv",
    "events":    DATA / "oil" / "oil_events.csv",
    "episodes":  DATA / "oil" / "episodes.csv",
    "to_review": DATA / "oil" / "to_review.csv",
}

TIME_COLUMNS = ("timestamp_utc", "start", "end")
LIST_COLUMNS = ("actors_found", "mechanisms_found")


DOWNLOAD = ROOT / "download"
FROZEN_MINUTES = 60


def load_series():
    """One-minute series from download/, merged by instrument. A bar is real if
    it is not inside a constant-price stretch of at least FROZEN_MINUTES minutes."""
    pieces = {}
    for f in sorted(DOWNLOAD.glob("*.csv")):
        if f.stat().st_size == 0:
            continue
        pieces.setdefault(f.name.split("-")[0], []).append(pd.read_csv(f))
    series = {}
    for name, parts in pieces.items():
        df = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp")
        df["t"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        stretch = (df["close"].diff() != 0).cumsum()
        df["real"] = df.groupby(stretch)["close"].transform("size") < FROZEN_MINUTES
        series[name] = df.reset_index(drop=True)
    return series


def hourly_coverage(df):
    """Share of minutes with a real bar for each (weekday, UTC hour), over the
    period covered by the file."""
    days = pd.date_range(df["t"].min().normalize(), df["t"].max().normalize(), freq="D")
    occurrences = pd.Series(days.dayofweek).value_counts()
    real = df[df["real"]]
    counts = real.groupby([real["t"].dt.dayofweek, real["t"].dt.hour]).size()
    grid = pd.MultiIndex.from_product([range(7), range(24)], names=["day", "hour"])
    possible = pd.Series([occurrences.get(d, 0) * 60 for d, _ in grid], index=grid)
    return (counts.reindex(grid, fill_value=0) / possible).fillna(0)


def load(name):
    df = pd.read_csv(FILES[name])
    for c in TIME_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601", errors="coerce")
    for c in LIST_COLUMNS:
        if c in df.columns:
            df[c] = df[c].fillna("[]").apply(ast.literal_eval)
    return df
