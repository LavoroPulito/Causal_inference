#!/usr/bin/env python3
"""Plots price series with the episodes marked by direction.

    python query/plot_series.py                         synthetic series, whole period
    python query/plot_series.py --episode 160           two hours around episode 160
    python query/plot_series.py --from 2025-06-20 --to 2025-06-25
    python query/plot_series.py --series download/lightcmdusd-m1-bid-2025-03-01-2025-04-01.csv
    python query/plot_series.py --episode 160 --save episode_160.png

A series is a parquet with columns t, close (03, 03b) or a Dukascopy CSV.
Filler bars (constant price for an hour or more) are not drawn. Episodes are
vertical lines: red toward escalation, green toward resolution, grey 0.
"""

import argparse
import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = sorted((ROOT / "data/prices/synthetic").glob("synthetic_*.parquet"))
TABLES = sorted((ROOT / "data/features").glob("episode_table_*.parquet"))
ANNOTATIONS = ROOT / "data/features/manual_annotations.csv"

AROUND_EPISODE = pd.Timedelta(hours=2)
MINUTE_BARS_UP_TO = pd.Timedelta(days=7)     # longer ranges are drawn hourly
COLORS = {-2: "#b2182b", -1: "#ef8a62", 0: "#999999", 1: "#67a9cf", 2: "#2166ac"}


def read_prices(path):
    """Same reader as the event study."""
    spec = importlib.util.spec_from_file_location("event_study", ROOT / "06_event_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_prices(path)


def episodes():
    table = pd.read_parquet(TABLES[-1])
    text = pd.read_csv(ANNOTATIONS, usecols=["first_post", "joined_text"])
    return table.merge(text, on="first_post", how="left")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="+", default=[str(p) for p in SYNTHETIC])
    ap.add_argument("--episode", type=int, help="episode_id to centre on")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--save", help="write a PNG instead of opening a window")
    args = ap.parse_args()

    ep = episodes()
    if args.episode is not None:
        row = ep.loc[ep["episode_id"] == args.episode]
        if row.empty:
            raise SystemExit(f"Episode {args.episode} not found.")
        row = row.iloc[0]
        start, end = row["start"] - AROUND_EPISODE, row["start"] + AROUND_EPISODE
        title = (f"Episode {args.episode}, {row['start']:%Y-%m-%d %H:%M} UTC — "
                 f"direction {row['direction']:+d}, intensity {row['intensity']}, "
                 f"specificity {row['specificity']}\n{str(row['joined_text'])[:140]}")
    else:
        start = pd.Timestamp(args.start, tz="UTC") if args.start else None
        end = pd.Timestamp(args.end, tz="UTC") + pd.Timedelta(days=1) if args.end else None
        title = "Prices and episodes"

    fig, axes = plt.subplots(len(args.series), 1, sharex=True, squeeze=False,
                             figsize=(13, 2.8 * len(args.series)))
    for ax, path in zip(axes[:, 0], args.series):
        df = read_prices(path)
        df = df[df["real"]].set_index("t")["close"]
        lo = start if start is not None else df.index.min()
        hi = end if end is not None else df.index.max()
        df = df[(df.index >= lo) & (df.index <= hi)]
        if df.empty:
            ax.text(0.5, 0.5, "no prices in this range (market closed?)", transform=ax.transAxes, ha="center")
        else:
            # a regular index leaves closed hours as gaps instead of joining them
            freq = "min" if hi - lo <= MINUTE_BARS_UP_TO else "h"
            df = df.resample(freq).last()
            ax.plot(df.index, df.values, lw=0.8, color="black")

        for _, e in ep[(ep["start"] >= lo) & (ep["start"] <= hi)].iterrows():
            ax.axvline(e["start"], color=COLORS[e["direction"]], lw=1.2,
                       alpha=0.9 if args.episode is not None else 0.5)
        ax.set_xlim(lo, hi)
        ax.set_ylabel(Path(path).stem.split("-")[0].replace("synthetic_", "synthetic\n"), fontsize=9)
        ax.grid(alpha=0.3)

    handles = [plt.Line2D([], [], color=c, lw=2, label=f"{d:+d}") for d, c in COLORS.items()]
    axes[0, 0].legend(handles=handles, title="direction", fontsize=8, ncol=5,
                      loc="upper left", framealpha=0.8)
    axes[0, 0].set_title(title, fontsize=10, loc="left")
    axes[-1, 0].set_xlabel("UTC")
    fig.tight_layout()

    if args.save:
        fig.savefig(args.save, dpi=130)
        print(f"Saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
