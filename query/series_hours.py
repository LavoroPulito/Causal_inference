#!/usr/bin/env python3
"""At which hours the series in download/ have data.

    python query/series_hours.py
"""

import pandas as pd

from _common import load_series, hourly_coverage

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

for name, df in load_series().items():
    print(f"\n=== {name}: {df['t'].min():%Y-%m-%d} -> {df['t'].max():%Y-%m-%d} | "
          f"bars {len(df)}, real {int(df['real'].sum())}, "
          f"days with real bars {df.loc[df['real'], 't'].dt.date.nunique()} ===")

    hour = df["t"].dt.hour
    per_hour = pd.DataFrame({"bars": df.groupby(hour).size(),
                             "real": df[df["real"]].groupby(hour[df["real"]]).size()})
    print("\nbars per UTC hour")
    print(per_hour.reindex(range(24), fill_value=0).fillna(0).astype(int).T.to_string())

    cov = hourly_coverage(df).unstack()
    cov.index = DAYS
    print("\n% of minutes with a real bar, by day and UTC hour")
    print((cov * 100).round().astype(int).to_string())
