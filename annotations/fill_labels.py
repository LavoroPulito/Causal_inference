#!/usr/bin/env python3
"""Fills the label in to_review.csv for posts already labelled in the saved
versions. For the same post the most recent version wins."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "annotations"
TO_REVIEW = ROOT / "data" / "oil" / "to_review.csv"

versions = sorted((p for p in FOLDER.glob("v*") if p.is_dir()),
                  key=lambda p: int(p.name[1:]))

labels = {}
for v in versions:
    ann = pd.read_csv(v / "to_review.csv").dropna(subset=["label"])
    labels.update(zip(ann["post_id"], ann["label"]))

df = pd.read_csv(TO_REVIEW)
before = df["label"].notna().sum()
df["label"] = df["label"].fillna(df["post_id"].map(labels))
df.to_csv(TO_REVIEW, index=False)

print(f"filled {df['label'].notna().sum() - before} labels out of {len(df)} rows")
