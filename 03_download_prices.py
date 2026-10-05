#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03 — Downloads one-minute price history from Dukascopy.

    WTI     main variable
    GOLD    control: geopolitical risk through the safe-haven channel
    EUR/USD dollar proxy, plausible confounder
    BRENT   robustness (incomplete coverage: see the report)

Choice of instruments, data quality and limits in report/project_status.typ.

    python 03_download_prices.py --dry-run
    python 03_download_prices.py
    python 03_download_prices.py --only wti

Dependencies: pandas, numpy, pyarrow; Node.js for npx dukascopy-node.
"""

import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURATION
# ==============================================================================

START_DATE = date(2024, 12, 1)
END_DATE = date(2026, 8, 1)       # exclusive

TIMEFRAME = "m1"
PRICE = "bid"

RAW_DIR = Path("data/prices/raw")
OUTPUT_DIR = Path("data/prices")

# Dukascopy identifiers. Check them with --dry-run before a long run: they
# change between CLI versions.
INSTRUMENTS = {
    "wti":    "lightcmdusd",
    "gold":   "xauusd",
    "eurusd": "eurusd",
    "brent":  "brentcmdusd",
}

GAP_MINUTES = 15
PAUSE_BETWEEN_CALLS = 1.0


# ==============================================================================
# UTILITIES
# ==============================================================================

def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def months(start, end):
    """Bounds (first_day, first_day_of_next_month)."""
    cur = date(start.year, start.month, 1)
    while cur < end:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        yield cur, min(nxt, end)
        cur = nxt


def command(instrument_id, frm, to, outdir):
    return [
        "npx", "--yes", "dukascopy-node",
        "-i", instrument_id,
        "-from", frm.isoformat(),
        "-to", to.isoformat(),
        "-t", TIMEFRAME,
        "-p", PRICE,
        "-f", "csv",
        "-dir", str(outdir),
        "-v", "true",
    ]


# ==============================================================================
# DOWNLOAD
# ==============================================================================

def download(name, instrument_id, dry_run=False):
    """One month at a time; blocks already present are skipped."""
    outdir = RAW_DIR / name
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- {name} ({instrument_id}) ---")
    failed = []

    for frm, to in months(START_DATE, END_DATE):
        present = list(outdir.glob(f"*{frm.isoformat()}*"))
        if present and not dry_run:
            print(f"  {frm:%Y-%m}  already present, skipping")
            continue

        cmd = command(instrument_id, frm, to, outdir)

        if dry_run:
            print("  " + " ".join(cmd))
            continue

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                print(f"  {frm:%Y-%m}  ERROR\n    {r.stderr.strip()[:300]}")
                failed.append(str(frm))
            else:
                print(f"  {frm:%Y-%m}  ok")
        except subprocess.TimeoutExpired:
            print(f"  {frm:%Y-%m}  timeout")
            failed.append(str(frm))
        except FileNotFoundError:
            print("\nnpx not found: install Node.js.")
            sys.exit(1)

    return failed


# ==============================================================================
# MERGE AND NORMALIZATION
# ==============================================================================

def merge(name):
    """Merges the monthly CSVs into one sorted series in UTC. The time field
    can be epoch (ms or s) or an ISO string depending on the version."""
    outdir = RAW_DIR / name
    csv_files = sorted(outdir.glob("*.csv"))
    if not csv_files:
        print(f"{name}: no CSV found.")
        return None

    pieces = []
    for f in csv_files:
        try:
            pieces.append(pd.read_csv(f))
        except Exception as e:
            print(f"  unreadable {f.name}: {e}")

    if not pieces:
        return None

    df = pd.concat(pieces, ignore_index=True)
    df.columns = [c.strip().lower() for c in df.columns]

    col_t = next((c for c in df.columns
                  if c in ("timestamp", "time", "date", "datetime")), df.columns[0])

    if pd.api.types.is_numeric_dtype(df[col_t]):
        unit = "ms" if df[col_t].iloc[0] > 1e11 else "s"
        df["t"] = pd.to_datetime(df[col_t], unit=unit, utc=True)
    else:
        df["t"] = pd.to_datetime(df[col_t], utc=True, errors="coerce")

    df = (df.dropna(subset=["t"])
            .drop_duplicates(subset="t", keep="last")
            .sort_values("t")
            .reset_index(drop=True))

    keep = ["t"] + [c for c in ("open", "high", "low", "close", "volume")
                    if c in df.columns]
    return df[keep]


# ==============================================================================
# QUALITY CHECK
# ==============================================================================

def quality(name, df):
    """Hourly coverage and weekday gaps: they determine how many episodes will
    have a usable price."""
    print(f"\n--- {name} ---")
    print(f"Bars            : {len(df):,}")
    print(f"Period (UTC)    : {df['t'].min()} -> {df['t'].max()}")

    gap = df["t"].diff().dt.total_seconds().div(60)
    print(f"Median interval : {gap.median():.1f} min")

    prev = df["t"].shift(1)
    weekend = prev.dt.dayofweek.isin([4, 5, 6])
    gaps = gap > GAP_MINUTES
    weekday_gaps = gaps & ~weekend

    print(f"Gaps > {GAP_MINUTES} min    : {gaps.sum()} "
          f"(of which {weekday_gaps.sum()} on weekdays)")

    if weekday_gaps.sum():
        worst = (df.assign(gap=gap)[weekday_gaps]
                 .nlargest(5, "gap")[["t", "gap"]])
        print("  longest:")
        for _, r in worst.iterrows():
            print(f"    {r['t']}  {r['gap']:.0f} min")

    per_hour = df["t"].dt.hour.value_counts().sort_index()
    print(f"Hours covered   : {len(per_hour)}/24  "
          f"(min {per_hour.min():,} bars, max {per_hour.max():,})")

    if "close" in df.columns:
        odd = (df["close"] <= 0).sum()
        if odd:
            print(f"  WARNING: {odd} bars with close <= 0")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print the commands without running them")
    ap.add_argument("--only", help="download a single instrument (e.g. wti)")
    args = ap.parse_args()

    if not args.dry_run and shutil.which("npx") is None:
        print("npx not found. Install Node.js, or use --dry-run.")
        sys.exit(1)

    if args.only and args.only not in INSTRUMENTS:
        print(f"Unknown instrument. Available: {list(INSTRUMENTS)}")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    todo = ({args.only: INSTRUMENTS[args.only]} if args.only else INSTRUMENTS)

    heading("DOWNLOAD")
    failed = {}
    for name, sid in todo.items():
        f = download(name, sid, dry_run=args.dry_run)
        if f:
            failed[name] = f

    if args.dry_run:
        print("\nDry run: nothing downloaded.")
        return

    heading("MERGE AND QUALITY CHECK")
    series = {}
    for name in todo:
        df = merge(name)
        if df is None or df.empty:
            print(f"{name}: nothing to merge.")
            continue
        quality(name, df)
        df.to_parquet(OUTPUT_DIR / f"{name}_m1.parquet", index=False)
        series[name] = df

    if failed:
        print("\nFAILED BLOCKS (rerun the script: it resumes from these)")
        for n, mm in failed.items():
            print(f"  {n}: {', '.join(mm)}")

    heading("DONE")
    for name, df in series.items():
        print(f"  {name}_m1.parquet   {len(df):,} bars")


if __name__ == "__main__":
    main()
