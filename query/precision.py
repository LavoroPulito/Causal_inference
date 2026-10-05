#!/usr/bin/env python3
"""Share of rows in a group of to_review.csv with a given label.

    python query/precision.py                       # inside, label 1
    python query/precision.py --group boundary      # same count on the boundary
"""

import argparse
import math

from _common import load


def wilson(k, n, z=1.96):
    """95% confidence interval for a proportion."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return centre - half, centre + half


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="inside")
    ap.add_argument("--value", type=float, default=1)
    args = ap.parse_args()

    df = load("to_review")
    g = df[df["group"] == args.group]
    if g.empty:
        raise SystemExit(f"No rows in group '{args.group}'. "
                         f"Groups present: {sorted(df['group'].unique())}")

    n = len(g)
    labelled = int(g["label"].notna().sum())
    print(f"group '{args.group}': {n} rows, {labelled} labelled")
    if labelled == 0:
        return

    k = int((g["label"] == args.value).sum())
    low, high = wilson(k, n)
    print(f"label = {args.value:g}: {k} of {n} = {k / n:.1%}")
    print(f"95% CI (Wilson): {low:.1%} - {high:.1%}")
    if labelled < n:
        print(f"warning: {n - labelled} unlabelled rows count in the "
              f"denominator; on labelled rows only the share is {k / labelled:.1%}")


if __name__ == "__main__":
    main()
