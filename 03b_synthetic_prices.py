#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03b — Synthetic one-minute prices, to test the analyses until the real series
is chosen.

Three series with the trading hours of WTI (Sunday 22 UTC to Friday 21 UTC,
closed daily from 21 to 22), built from one-minute log returns:

    eurusd   pure noise
    wti      noise + dollar effect + effect of the episodes
    gold     noise + effect of the episodes, opposite sign and smaller

The effect of an episode depends only on its direction: an episode with
direction +2 (toward resolution) lowers WTI by WTI_EFFECT percent, spread
evenly over the EFFECT_MINUTES after the first post; -2 raises it by as much;
±1 moves it by half. During the crisis periods the effect on WTI is
CRISIS_MULTIPLIER times larger: this is the change of mechanism that CD-NOD
should detect. The effect on gold does not change, so that gold does not carry
the same information about the crisis. After
each episode volatility is VOLATILITY_MULTIPLIER times higher for an hour, as
happens around real news.

The true values are written to truth.json, next to the series, so that every
test can be compared with what was put in.

    python 03b_synthetic_prices.py

Input:  data/features/episode_table_*.parquet (the latest)
Output: data/prices/synthetic/synthetic_{wti,gold,eurusd}.parquet  (t, close)
        data/prices/synthetic/truth.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURATION
# ==============================================================================

TABLE_GLOB = "data/features/episode_table_*.parquet"
OUTPUT_DIR = Path("data/prices/synthetic")
SEED = 42

# one-minute standard deviation of log returns
SIGMA = {"wti": 0.00043, "gold": 0.00025, "eurusd": 0.00012}
START_PRICE = {"wti": 70.0, "gold": 2900.0, "eurusd": 1.08}

DOLLAR_BETA = 0.5            # EUR/USD up = weaker dollar: WTI rises by half as much
WTI_EFFECT = 0.2             # percent, effect of a +2 episode on WTI
GOLD_EFFECT = 0.1            # percent, effect of a -2 episode on gold
EFFECT_MINUTES = 15

CRISIS_PERIODS = [("2025-06-01", "2025-06-30"), ("2026-03-01", "2026-06-30")]
CRISIS_MULTIPLIER = 2.0

VOLATILITY_MINUTES = 60
VOLATILITY_MULTIPLIER = 2.0


# ==============================================================================
# BUILDING BLOCKS
# ==============================================================================

def trading_minutes(start, end):
    """Minutes in which WTI trades."""
    t = pd.date_range(start.floor("D"), end.ceil("D"), freq="min", tz="UTC")
    day, hour = t.dayofweek, t.hour
    weekday = (day <= 3) & (hour != 21)
    friday = (day == 4) & (hour < 21)
    sunday = (day == 6) & (hour >= 22)
    return t[weekday | friday | sunday]


def in_crisis(times):
    crisis = np.zeros(len(times), dtype=bool)
    for a, b in CRISIS_PERIODS:
        crisis |= (times >= pd.Timestamp(a, tz="UTC")) & (times < pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1))
    return crisis


def episode_paths(t, table, crisis_multiplier):
    """Two per-minute series: the push of the episodes (direction / 2, spread
    over EFFECT_MINUTES, times crisis_multiplier in crisis) and the volatility
    multiplier."""
    push = np.zeros(len(t))
    volatility = np.ones(len(t))
    multiplier = np.where(in_crisis(table["start"]), crisis_multiplier, 1.0)

    for start, direction, m in zip(table["start"], table["direction"], multiplier):
        # first minute that starts after the post
        i = t.searchsorted(start.ceil("min"))
        effect_end = t.searchsorted(start + pd.Timedelta(minutes=EFFECT_MINUTES))
        if effect_end > i:
            push[i:effect_end] += m * direction / 2 / (effect_end - i)
        vol_end = t.searchsorted(start + pd.Timedelta(minutes=VOLATILITY_MINUTES))
        volatility[i:vol_end] = VOLATILITY_MULTIPLIER
    return push, volatility


def to_prices(t, returns, start_price):
    return pd.DataFrame({"t": t, "close": start_price * np.exp(np.cumsum(returns))})


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    table_path = sorted(Path().glob(TABLE_GLOB))[-1]
    table = pd.read_parquet(table_path)
    print(f"Episode table: {table_path} ({len(table)} episodes)")

    rng = np.random.default_rng(SEED)
    t = trading_minutes(table["start"].min() - pd.Timedelta(days=2),
                        table["start"].max() + pd.Timedelta(days=2))
    push_wti, volatility = episode_paths(t, table, CRISIS_MULTIPLIER)
    push_gold, _ = episode_paths(t, table, 1.0)

    noise = {k: rng.normal(0.0, s, len(t)) * volatility for k, s in SIGMA.items()}

    r_usd = noise["eurusd"]
    # a +2 episode pushes WTI down by WTI_EFFECT% and gold down by GOLD_EFFECT%:
    # resolution lowers oil and the demand for a safe haven
    r_wti = noise["wti"] + DOLLAR_BETA * r_usd - WTI_EFFECT / 100 * push_wti
    r_gold = noise["gold"] - GOLD_EFFECT / 100 * push_gold

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, r in [("wti", r_wti), ("gold", r_gold), ("eurusd", r_usd)]:
        to_prices(t, r, START_PRICE[name]).to_parquet(
            OUTPUT_DIR / f"synthetic_{name}.parquet", index=False)

    truth = {
        "episode_table": str(table_path),
        "seed": SEED,
        "sigma_per_minute": SIGMA,
        "dollar_beta": DOLLAR_BETA,
        "effect_minutes": EFFECT_MINUTES,
        # WTI: outside the crisis periods; inside, times crisis_multiplier
        "wti_car_per_direction_point_pct": -WTI_EFFECT / 2,
        "gold_car_per_direction_point_pct": -GOLD_EFFECT / 2,
        "crisis_periods": CRISIS_PERIODS,
        "crisis_multiplier": CRISIS_MULTIPLIER,
        "volatility_minutes": VOLATILITY_MINUTES,
        "volatility_multiplier": VOLATILITY_MULTIPLIER,
        "variables_without_effect": ["intensity", "specificity", "novelty"],
    }
    (OUTPUT_DIR / "truth.json").write_text(json.dumps(truth, indent=2))

    crisis = in_crisis(table["start"]).sum()
    print(f"Minutes: {len(t):,}  ({t[0]:%Y-%m-%d} -> {t[-1]:%Y-%m-%d})")
    print(f"Episodes in crisis periods: {crisis} of {len(table)}")
    print(f"True effect at {EFFECT_MINUTES}+ min, per direction point: "
          f"WTI {-WTI_EFFECT/2:+.2f}% (x{CRISIS_MULTIPLIER:g} in crisis), "
          f"gold {-GOLD_EFFECT/2:+.2f}%")
    print(f"Saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
