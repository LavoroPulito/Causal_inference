#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 — Event study: price reaction in the minutes after each episode.

    STEP 1  prices          one-minute series, filler bars removed
    STEP 2  returns         cumulative abnormal return per episode and horizon,
                            and the raw return in the minutes before the post
    STEP 3  regressions     returns on the annotated variables

The time zero of an episode is its first post. The base price is the close of
the last bar ending before the post; the expected return is the mean one-minute
return of the previous hour (constant-mean model). An episode is left out of a
horizon, with the reason recorded, when a price is missing or another episode
starts inside its window.

The pre-trend is the raw return from PRE_TREND minutes before the post up to
the post (negative horizons in the output). If prices already move before the
post, in the direction the post will take, part of the reaction attributed to
the post started earlier: news may reach the market before Trump writes, or
Trump may react to prices. Such a move also enters the expected return of the
previous hour, so the post-event regressions are shown both on the abnormal
return (car) and on the raw return (ret).

The price series is not chosen yet (report, section 8). Two sources serve to
test the chain:

    python 06_event_study.py --prices download/lightcmdusd-m1-bid-2025-03-01-2025-04-01.csv
    python 06_event_study.py --prices data/prices/wti_m1.parquet
    python 06_event_study.py --synthetic --effect 0.2
    python 06_event_study.py --power

--synthetic generates a random walk with the trading hours of WTI and adds a
known effect: an episode with direction +2 lowers the price by --effect percent
over 15 minutes, one with -2 raises it by as much. The chain must find it.
--power repeats this many times for several effect sizes and reports how often
the effect is detected at the 5% level.

Input:  data/features/episode_table_*.parquet (the latest, or --table)
Output: data/event_study/<source>/
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# ==============================================================================
# CONFIGURATION
# ==============================================================================

TABLE_GLOB = "data/features/episode_table_*.parquet"
OUTPUT_DIR = Path("data/event_study")

HORIZONS = [1, 5, 15, 30, 60]          # minutes after the post
PRE_TREND = [60, 30, 15, 5]            # minutes before the post
PRE_MINUTES = 60                       # window for the expected return
MIN_PRE_RETURNS = 30
TOLERANCE_MINUTES = 2                  # largest distance of a bar from its time
FROZEN_MINUTES = 60                    # constant price this long = filler

SPECS = {
    "simple": ["direction"],
    "full": ["direction", "intensity", "specificity", "novelty"],
}

# --- synthetic series ---------------------------------------------------------
SIGMA = 0.00043                        # one-minute log-return sd, WTI March 2025
START_PRICE = 70.0
EFFECT_MINUTES = 15
POWER_EFFECTS = [0.0, 0.05, 0.1, 0.2, 0.4]
POWER_REPS = 200
POWER_HORIZON = 15
SEED = 42

MINUTE = 60 * 10**9


def ns(t):
    """Nanoseconds since epoch: pandas 3 may store times in microseconds."""
    return pd.DatetimeIndex(t).as_unit("ns").asi8


def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ==============================================================================
# STEP 1 — PRICES
# ==============================================================================

def read_prices(path):
    """Parquet from 03, 03b or 03c (columns t, close, and instrument_id for
    futures) or Dukascopy CSV (timestamp in ms, close); a folder is read as all
    the CSV files it contains."""
    path = Path(path)
    if path.is_dir():
        df = pd.concat([pd.read_csv(f) for f in sorted(path.glob("*.csv"))
                        if f.stat().st_size > 0])
    elif path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if "t" not in df.columns:
        df["t"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df[df["close"] > 0]          # also drops missing prices
    if "instrument_id" not in df.columns:
        df["instrument_id"] = 0
    df = (df[["t", "close", "instrument_id"]].drop_duplicates("t")
            .sort_values("t").reset_index(drop=True))

    stretch = (df["close"].diff() != 0).cumsum()
    df["real"] = df.groupby(stretch)["close"].transform("size") < FROZEN_MINUTES
    return df


def trading_minutes(start, end):
    """WTI hours: Sunday 22 UTC to Friday 21 UTC, closed daily from 21 to 22."""
    t = pd.date_range(start.floor("min"), end.ceil("min"), freq="min")
    day, hour = t.dayofweek, t.hour
    open_ = ((day <= 3) & (hour != 21)) | ((day == 4) & (hour < 21)) | ((day == 6) & (hour >= 22))
    return t[open_]


def synthetic_prices(table, effect, rng):
    """Random walk plus a known effect: -effect% x direction/2, spread over
    EFFECT_MINUTES after the first post."""
    t = trading_minutes(table["start"].min() - pd.Timedelta(days=2),
                        table["start"].max() + pd.Timedelta(days=2))
    steps = rng.normal(0.0, SIGMA, len(t))

    ends = ns(t + pd.Timedelta(minutes=1))
    t0 = ns(table["start"])
    lo = np.searchsorted(ends, t0, side="right")
    hi = np.searchsorted(ends, t0 + EFFECT_MINUTES * MINUTE, side="right")
    shift = -effect / 100 * table["direction"].to_numpy() / 2
    for a, b, s in zip(lo, hi, shift):
        if b > a:
            steps[a:b] += s / (b - a)

    close = START_PRICE * np.exp(np.cumsum(steps))
    return pd.DataFrame({"t": t, "close": close, "real": True, "instrument_id": 0})


# ==============================================================================
# STEP 2 — RETURNS
# ==============================================================================

def abnormal_returns(table, prices):
    """One row per episode and horizon. Returns are log returns in percent."""
    real = prices[prices["real"]]
    ends = ns(real["t"] + pd.Timedelta(minutes=1))
    lp = np.log(real["close"].to_numpy())

    r = np.diff(lp, prepend=lp[0])
    # a return between two contracts is the roll, not a price move
    contract = real["instrument_id"].to_numpy()
    valid = np.r_[False, (np.diff(ends) == MINUTE) & (np.diff(contract) == 0)]
    r = np.where(valid, r, 0.0)
    c1 = np.cumsum(r)
    c2 = np.cumsum(r ** 2)
    cn = np.cumsum(valid)

    t0 = ns(table["start"])
    starts = np.sort(t0)
    tol = TOLERANCE_MINUTES * MINUTE

    base = np.searchsorted(ends, t0, side="right") - 1
    has_base = (base >= 0) & (t0 - ends[np.maximum(base, 0)] <= tol)

    # returns entirely inside (t0 - PRE, t0]: indices first+1 .. base
    first = np.searchsorted(ends, t0 - PRE_MINUTES * MINUTE, side="right")
    b = np.maximum(base, 0)
    a = np.minimum(first, b)
    n = cn[b] - cn[a]
    s1 = c1[b] - c1[a]
    s2 = c2[b] - c2[a]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = s1 / n
        sd = np.sqrt((s2 - n * mu ** 2) / (n - 1))

    rows = []
    for h in HORIZONS:
        target = t0 + h * MINUTE
        k = np.searchsorted(ends, target, side="right") - 1
        has_h = (k > base) & (target - ends[np.maximum(k, 0)] <= tol)
        roll = contract[np.maximum(k, 0)] != contract[b]
        others = (np.searchsorted(starts, target, side="right")
                  - np.searchsorted(starts, t0 - PRE_MINUTES * MINUTE, side="left") - 1)

        status = np.select(
            [~has_base, n < MIN_PRE_RETURNS, ~has_h, roll, others > 0],
            ["no_price_t0", "short_pre_window", "no_price_horizon", "roll", "overlap"],
            default="ok")
        ret = np.where(has_h & has_base & ~roll, lp[np.maximum(k, 0)] - lp[b], np.nan)
        car = ret - mu * h
        rows.append(pd.DataFrame({
            "first_post": table["first_post"].to_numpy(),
            "episode_id": table["episode_id"].to_numpy(),
            "horizon": h,
            "status": status,
            "ret": 100 * ret,
            "car": 100 * car,
            "scar": car / (sd * np.sqrt(h)),
        }))
    return pd.concat(rows, ignore_index=True)


def pre_trend(table, prices):
    """Raw return from h minutes before the post to the post, one row per
    episode and h, with horizon = -h. Excluded when another episode starts in
    the stretch or in the PRE_MINUTES before it, whose reaction would still
    be under way."""
    real = prices[prices["real"]]
    ends = ns(real["t"] + pd.Timedelta(minutes=1))
    lp = np.log(real["close"].to_numpy())
    contract = real["instrument_id"].to_numpy()

    t0 = ns(table["start"])
    starts = np.sort(t0)
    tol = TOLERANCE_MINUTES * MINUTE
    base = np.searchsorted(ends, t0, side="right") - 1
    b = np.maximum(base, 0)
    has_base = (base >= 0) & (t0 - ends[b] <= tol)

    rows = []
    for h in PRE_TREND:
        target = t0 - h * MINUTE
        k = np.searchsorted(ends, target, side="right") - 1
        kk = np.maximum(k, 0)
        has_h = (k >= 0) & (k < base) & (target - ends[kk] <= tol)
        roll = contract[kk] != contract[b]
        others = (np.searchsorted(starts, t0, side="left")
                  - np.searchsorted(starts, target - PRE_MINUTES * MINUTE, side="left"))
        status = np.select(
            [~has_base, ~has_h, roll, others > 0],
            ["no_price_t0", "no_price_horizon", "roll", "overlap"], default="ok")
        ret = np.where(has_base & has_h & ~roll, lp[b] - lp[kk], np.nan)
        rows.append(pd.DataFrame({
            "first_post": table["first_post"].to_numpy(),
            "episode_id": table["episode_id"].to_numpy(),
            "horizon": -h,
            "status": status,
            "ret": 100 * ret,
            "car": 100 * ret,
            "scar": np.nan,
        }))
    return pd.concat(rows, ignore_index=True)


# ==============================================================================
# STEP 3 — REGRESSIONS
# ==============================================================================

def ols(y, X):
    """OLS with heteroskedasticity-robust standard errors (HC1)."""
    X = np.column_stack([np.ones(len(y)), X])
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    xtx = np.linalg.pinv(X.T @ X)
    cov = xtx @ (X.T * e ** 2) @ X @ xtx * n / (n - k)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), n - k)
    return beta, se, t, p, n


def regressions(car, table):
    data = car[car["status"] == "ok"].merge(
        table.drop(columns=["episode_id"]), on="first_post")
    out = []
    for h, g in data.groupby("horizon"):
        for y in ["car", "ret"]:
            for spec, cols in SPECS.items():
                g2 = g.dropna(subset=cols + [y])
                if len(g2) <= len(cols) + 1:
                    continue
                beta, se, t, p, n = ols(g2[y].to_numpy(), g2[cols].to_numpy(float))
                for name, bb, ss, tt, pp in zip(["const"] + cols, beta, se, t, p):
                    out.append({"horizon": h, "y": y, "spec": spec, "variable": name,
                                "coef": bb, "se": ss, "t": tt, "p": pp, "n": n})
    return pd.DataFrame(out)


def means_by_direction(car, table):
    data = car[car["status"] == "ok"].merge(table[["first_post", "direction"]],
                                            on="first_post")
    return data.pivot_table(index="direction", columns="horizon", values="car",
                            aggfunc=["mean", "count"])


# ==============================================================================
# POWER
# ==============================================================================

def power(table):
    """Share of synthetic runs in which the direction coefficient of the simple
    regression is significant at 5%, at POWER_HORIZON minutes."""
    heading(f"POWER — {POWER_REPS} runs per effect, horizon {POWER_HORIZON} min")
    rng = np.random.default_rng(SEED)
    rows = []
    for effect in POWER_EFFECTS:
        coefs, hits = [], 0
        for _ in range(POWER_REPS):
            car = abnormal_returns(table, synthetic_prices(table, effect, rng))
            g = car[(car["horizon"] == POWER_HORIZON) & (car["status"] == "ok")]
            g = g.merge(table[["first_post", "direction"]], on="first_post")
            beta, se, t, p, n = ols(g["car"].to_numpy(), g[["direction"]].to_numpy(float))
            coefs.append(beta[1])
            hits += p[1] < 0.05
        rows.append({"effect_pct_at_2": effect, "true_coef": -effect / 2,
                     "mean_coef": np.mean(coefs), "power": hits / POWER_REPS, "n": n})
        print(f"  effect {effect:>5.2f}%  true coef {-effect/2:>7.3f}  "
              f"estimated {np.mean(coefs):>7.3f}  power {hits/POWER_REPS:>5.1%}  (n={n})")
    return pd.DataFrame(rows)


# ==============================================================================
# MAIN
# ==============================================================================

def latest_table():
    files = sorted(Path().glob(TABLE_GLOB))
    if not files:
        raise SystemExit("No episode table: run 05_episode_table.py")
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--prices", help="price file or folder")
    src.add_argument("--synthetic", action="store_true")
    src.add_argument("--power", action="store_true")
    ap.add_argument("--effect", type=float, default=0.2,
                    help="synthetic effect of a +2 episode, in percent")
    ap.add_argument("--table", help="episode table (default: the latest)")
    args = ap.parse_args()

    table_path = Path(args.table) if args.table else latest_table()
    table = pd.read_parquet(table_path)
    print(f"Episode table: {table_path} ({len(table)} episodes)")

    if args.power:
        outdir = OUTPUT_DIR / "power"
        outdir.mkdir(parents=True, exist_ok=True)
        power(table).to_csv(outdir / "power.csv", index=False)
        print(f"\nSaved {outdir}/power.csv")
        return

    heading("STEP 1 — PRICES")
    if args.synthetic:
        prices = synthetic_prices(table, args.effect, np.random.default_rng(SEED))
        label = f"synthetic_effect{args.effect:g}"
        print(f"Synthetic series, effect of a +2 episode: -{args.effect}% "
              f"over {EFFECT_MINUTES} min (true coefficient {-args.effect/2:g})")
    else:
        prices = read_prices(args.prices)
        label = Path(args.prices).stem
    print(f"Bars: {len(prices):,}, real {prices['real'].mean():.1%}  "
          f"({prices['t'].min()} -> {prices['t'].max()})")

    inside = table["start"].between(prices["t"].min(), prices["t"].max())
    table = table[inside].reset_index(drop=True)
    print(f"Episodes inside the series: {len(table)}")
    if table.empty:
        raise SystemExit("No episode falls inside the price series.")

    heading("STEP 2 — RETURNS (negative horizons: before the post)")
    car = pd.concat([pre_trend(table, prices), abnormal_returns(table, prices)],
                    ignore_index=True)
    print(car.pivot_table(index="status", columns="horizon", values="first_post",
                          aggfunc="size", fill_value=0).to_string())

    heading("STEP 3 — REGRESSIONS (returns in percent)")
    print("Mean car by direction (before the post: raw return):")
    print(means_by_direction(car, table).round(4).to_string())
    reg = regressions(car, table)
    if reg.empty:
        print("\nToo few usable episodes for the regressions.")
    else:
        d = reg[(reg["variable"] == "direction") & (reg["spec"] == "simple")]
        d = d.pivot_table(index="horizon", columns="y", values=["coef", "se", "p", "n"])
        print("\nDirection coefficient, simple specification "
              "(car: abnormal return, ret: raw return):")
        print(d.round(4).to_string())

    outdir = OUTPUT_DIR / label
    outdir.mkdir(parents=True, exist_ok=True)
    car.to_parquet(outdir / "car.parquet", index=False)
    reg.to_csv(outdir / "regressions.csv", index=False)
    print(f"\nSaved {outdir}/car.parquet, regressions.csv")


if __name__ == "__main__":
    main()
