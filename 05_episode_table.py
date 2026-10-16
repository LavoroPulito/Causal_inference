#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05 — Final episode table: features of 04 joined with the manual annotations.

One row per episode, matched through `first_post`. The table is written with
the date in the name, so that every analysis states which version it used.
It stops if an episode lacks judgements or is marked `text_changed`.

    python 05_episode_table.py

Input:  data/features/episode_features.parquet
        data/features/manual_annotations.csv
        data/oil/oil_events.csv
Output: data/features/episode_table_YYYY-MM-DD.parquet
"""

from datetime import date
from pathlib import Path

import pandas as pd


FEATURES = Path("data/features/episode_features.parquet")
ANNOTATIONS = Path("data/features/manual_annotations.csv")
EVENTS = Path("data/oil/oil_events.csv")
OUTPUT_DIR = Path("data/features")

JUDGEMENTS = ["direction", "intensity", "specificity"]
RANGES = {"direction": (-2, 2), "intensity": (1, 3), "specificity": (0, 1)}


def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def check(ann):
    """Every problem is listed before stopping, not only the first one."""
    problems = []
    empty = ann[ann[JUDGEMENTS].isna().any(axis=1)]
    if len(empty):
        problems.append(f"{len(empty)} episodes without judgements: "
                        f"{empty['episode_id'].tolist()}")
    changed = ann[ann["text_changed"]]
    if len(changed):
        problems.append(f"{len(changed)} episodes with text_changed: "
                        f"{changed['episode_id'].tolist()}")
    for c, (lo, hi) in RANGES.items():
        out = ann[ann[c].notna() & ~ann[c].between(lo, hi)]
        if len(out):
            problems.append(f"{c} out of range in {out['episode_id'].tolist()}")
    zero = ann[(ann["direction"] == 0) &
               ((ann["intensity"] != 1) | (ann["specificity"] != 0))]
    if len(zero):
        problems.append("direction 0 with intensity != 1 or specificity != 0: "
                        f"{zero['episode_id'].tolist()}")
    if problems:
        raise SystemExit("Annotations not ready:\n  " + "\n  ".join(problems))


def main():
    heading("EPISODE TABLE")
    feat = pd.read_parquet(FEATURES)
    ann = pd.read_csv(ANNOTATIONS)
    ann["text_changed"] = ann["text_changed"].fillna(False).astype(bool)

    lost = ann[ann["episode_id"].isna()]
    if len(lost):
        print(f"{len(lost)} annotated episodes no longer pass the rule: left out.")
    ann = ann[ann["episode_id"].notna() & ann["first_post"].isin(feat["first_post"])]
    check(ann)

    missing = feat[~feat["first_post"].isin(ann["first_post"])]
    if len(missing):
        raise SystemExit(f"{len(missing)} episodes missing from the annotation "
                         "file: run update.py.")

    keep = ["first_post", "gold"] + JUDGEMENTS
    table = feat.merge(ann[keep], on="first_post", how="left", validate="1:1")
    for c in JUDGEMENTS:
        table[c] = table[c].astype("int64")

    table["direction_sign"] = table["direction"].clip(-1, 1)
    table["direction_x_intensity"] = table["direction"] * table["intensity"]
    table["decisive"] = table["direction"].abs() == 2

    events = pd.read_csv(EVENTS, usecols=["episode_id", "text"])
    events["repost"] = events["text"].fillna("").str.match(r"RT\b")
    reposts = events.groupby("episode_id")["repost"].sum()
    table["n_reposts"] = table["episode_id"].map(reposts).fillna(0).astype("int64")
    table["only_reposts"] = table["n_reposts"] == table["n_post"]

    table = table.drop(columns=["joined_text"]).sort_values("start").reset_index(drop=True)
    out = OUTPUT_DIR / f"episode_table_{date.today().isoformat()}.parquet"
    table.to_parquet(out, index=False)

    print(f"Episodes: {len(table)}  ({table['start'].min():%Y-%m-%d} -> "
          f"{table['start'].max():%Y-%m-%d})")
    print("\nDirection:")
    print(table["direction"].value_counts().sort_index().to_string())
    print(f"\nDecisive (±2)      : {table['decisive'].sum()}")
    print(f"Only reposts       : {table['only_reposts'].sum()}")
    print(f"\nSaved {out}  ({len(table.columns)} columns)")


if __name__ == "__main__":
    main()
