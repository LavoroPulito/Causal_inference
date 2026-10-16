#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03c — One-minute futures prices from Databento (exchange data).

    python 03c_download_databento.py --cost      price of each series, downloads nothing
    python 03c_download_databento.py             downloads and converts
    python 03c_download_databento.py --only wti
    python 03c_download_databento.py --convert   rebuilds the parquet files from the raw data

Continuous contracts with the volume roll rule (`.v.0`): at any moment the most
traded contract. Databento does not adjust prices at the roll, so every bar
keeps the `instrument_id` of its contract: returns across a roll are not
reactions and must be excluded. Bars exist only in minutes with at least one
trade.

The API key is read from the DATABENTO_API_KEY environment variable.

Output: data/prices/raw/databento/<name>.dbn.zst   original data
        data/prices/databento/<name>.parquet         t, close, volume, instrument_id
"""

import argparse
from datetime import date
from pathlib import Path

import pandas as pd


START = "2024-11-24"                 # one week before the corpus, for the pre-event windows
SCHEMA = "ohlcv-1m"

SERIES = {
    "wti":    ("GLBX.MDP3", "CL.v.0"),
    "brent":  ("IFEU.IMPACT", "BRN.v.0"),
    "gold":   ("GLBX.MDP3", "GC.v.0"),
    "sp500":  ("GLBX.MDP3", "ES.v.0"),
    "eurusd": ("GLBX.MDP3", "6E.v.0"),
}

RAW_DIR = Path("data/prices/raw/databento")
OUTPUT_DIR = Path("data/prices/databento")


def end_of(client, dataset):
    """Last available date of the dataset, at most today."""
    available = pd.Timestamp(client.metadata.get_dataset_range(dataset=dataset)["end"])
    return min(available.date(), date.today()).isoformat()


def request(client, dataset, symbol):
    return dict(dataset=dataset, symbols=[symbol], stype_in="continuous",
                schema=SCHEMA, start=START, end=end_of(client, dataset))


def show_cost(client, todo):
    total = 0.0
    print(f"{'series':<8} {'symbol':<10} {'period':<24} {'size':>10} {'cost':>9}")
    for name, (dataset, symbol) in todo.items():
        q = request(client, dataset, symbol)
        size = client.metadata.get_billable_size(**q)
        cost = client.metadata.get_cost(**q)
        total += cost
        print(f"{name:<8} {symbol:<10} {q['start']} -> {q['end']}  "
              f"{size / 1e6:>7.1f} MB {cost:>8.2f} $")
    print(f"{'total':<56}{total:>9.2f} $")


def download(client, name, dataset, symbol):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw = RAW_DIR / f"{name}.dbn.zst"
    client.timeseries.get_range(**request(client, dataset, symbol), path=raw)
    convert(name)


def convert(name):
    """Raw DBN file to parquet. Bars without a price (some ICE trades) are
    dropped."""
    import databento as db
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = db.DBNStore.from_file(RAW_DIR / f"{name}.dbn.zst").to_df().reset_index()
    missing = int(df["close"].isna().sum())
    df = df[df["close"].notna()]
    out = pd.DataFrame({
        "t": pd.to_datetime(df["ts_event"], utc=True),
        "close": df["close"].astype(float),
        "volume": df["volume"].astype("int64"),
        "instrument_id": df["instrument_id"].astype("int64"),
    }).sort_values("t").reset_index(drop=True)
    out.to_parquet(OUTPUT_DIR / f"{name}.parquet", index=False)

    rolls = int((out["instrument_id"].diff() != 0).sum()) - 1
    print(f"  {name}: {len(out):,} bars, {out['t'].min():%Y-%m-%d} -> "
          f"{out['t'].max():%Y-%m-%d}, {rolls} contract rolls, "
          f"{missing} bars without a price dropped")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost", action="store_true", help="show the price, download nothing")
    ap.add_argument("--only", choices=list(SERIES))
    ap.add_argument("--convert", action="store_true",
                    help="rebuild the parquet files from the raw data, no download")
    args = ap.parse_args()

    todo = {args.only: SERIES[args.only]} if args.only else SERIES
    if args.convert:
        for name in todo:
            convert(name)
        return

    import databento as db
    client = db.Historical()          # key from DATABENTO_API_KEY
    if args.cost:
        show_cost(client, todo)
        return
    for name, (dataset, symbol) in todo.items():
        download(client, name, dataset, symbol)
    print(f"\nSaved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
