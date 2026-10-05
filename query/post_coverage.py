#!/usr/bin/env python3
"""Share of posts falling at hours when the series in download/ have data.

Each post gets the coverage of its weekday and UTC hour (share of minutes with
a real bar, see series_hours.py). The mean over posts is the expected share of
posts with a price available.

    python query/post_coverage.py
"""

from _common import load, load_series, hourly_coverage

sets = {"all posts": load("posts"), "selected by 01": load("events")}

for name, df in load_series().items():
    cov = hourly_coverage(df)
    print(f"\n=== {name} ({df['t'].min():%Y-%m-%d} -> {df['t'].max():%Y-%m-%d}) ===")
    for label, posts in sets.items():
        t = posts["timestamp_utc"].dropna()
        share = cov.reindex(list(zip(t.dt.dayofweek, t.dt.hour))).mean()
        print(f"  {label:16s} {len(t):6d} posts  ->  {share:.1%} at hours with data")
