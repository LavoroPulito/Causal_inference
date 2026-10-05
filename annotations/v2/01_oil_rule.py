#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01 — Corpus cleaning, oil rule, episodes, intervals.

    STEP 1  cleaning       duplicates, placeholders, boilerplate
    STEP 2  rule           actor x mechanism
    STEP 3  sample         posts to annotate by hand
    STEP 4  episodes       collapsed bursts
    STEP 5  intervals      sizing of the event window

The reasons behind each choice are in report/project_status.typ.

    python 01_oil_rule.py

Input: data/truth_posts.csv
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURATION
# ==============================================================================

INPUT_CSV = "data/truth_posts.csv"
OUTPUT_DIR = Path("data/oil")

COL_TEXT = "text"
COL_TIMESTAMP = "timestamp_utc"
COL_ID = "post_id"

SEED = 42

# --- cleaning -----------------------------------------------------------------
MIN_WORDS = 5

# Deduplication is on post_id, not on text: a text republished with a different
# ID is a distinct event. Only close double posts are collapsed.
COLLAPSE_REPOSTS_WITHIN_MINUTES = 2   # 0 to disable

PLACEHOLDER_PATTERNS = [
    r"^\s*\[\s*response to previous truth post\s*\]\s*$",
    r"^\s*\[\s*no content\s*\]\s*$",
    r"^\s*$",
]
BOILERPLATE_PATTERNS = [
    r"complete and total endorsement",
    r"(?:he|she) (?:will|has) never let you down",
]

# --- manual review sample -----------------------------------------------------
N_SAMPLE_INSIDE = 100
N_SAMPLE_BOUNDARY = 50

# --- episodes -----------------------------------------------------------------
BURST_THRESHOLD_MINUTES = 30

# --- intervals ----------------------------------------------------------------
WINDOWS_MINUTES = [1, 2, 5, 10, 15, 30, 60, 120]
ACCEPTABLE_OVERLAP_SHARE = 0.15


# ==============================================================================
# THE RULE
# ==============================================================================

ACTORS = [
    # Iran
    "iran", "iranian", "iranians", "tehran", "khamenei", "irgc",
    "revolutionary guard", "hormuz", "persian gulf",
    # Venezuela
    "venezuela", "venezuelan", "maduro", "caracas", "pdvsa",
    # Russia / Ukraine
    "russia", "russian", "russians", "putin", "moscow", "kremlin",
    "rosneft", "lukoil", "gazprom", "nord stream", "urals",
    "ukraine", "ukrainian", "zelensky", "zelenskyy", "kyiv",
    # crude producers and institutions
    "opec", "saudi", "saudi arabia", "aramco",
    "strategic petroleum reserve", "spr",
    # routes and shipping
    "red sea", "houthi", "houthis", "suez", "bab el mandeb",
    # explicit oil
    "oil", "crude", "barrel", "barrels", "petroleum", "gasoline", "fuel",
    # market
    "market", "markets"
    ]

MECHANISMS = [
    # physical supply disruption
    "blockade", "blockading", "mine", "mines", "interdict", "interdiction",
    "tanker", "tankers", "shipping", "strait", "waterway", "vessel", "vessels",
    "convoy", "port", "ports", "pipeline", "refinery", "refineries",
    "shadow fleet", "dark fleet",
    # military action
    "strike", "strikes", "military", "navy", "naval", "bomber", "bombers",
    "attack", "attacked", "destroy", "destroyed", "drone", "drones", 
    "obliterate", "obliterated", "obliterating", "obliteration",
    # sanctions and embargo
    "sanction", "sanctions", "sanctioned", "embargo", "price cap",
    "secondary tariff", "secondary tariffs",
    # nuclear negotiation
    "nuclear", "enrichment", "jcpoa",
    # price
    "boom", "down", "plummet", "dropping"
    # regime change in a producer country
    "regime change",
]

# Diagnostics only: they flag a possible false positive when they are the only
# mechanism present.
WEAK_MECHANISMS = ["war", "military", "attack", "strike", "strikes", "nuclear", "down"]


# ==============================================================================
# UTILITIES
# ==============================================================================

def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def pattern_for(terms):
    return r"\b(" + "|".join(re.escape(x) for x in terms) + r")\b"


def find_terms(lower_series, terms):
    """For each row, the list of terms actually found."""
    rx = re.compile(pattern_for(terms))
    return lower_series.fillna("").astype(str).apply(
        lambda t: sorted(set(m.group(0) for m in rx.finditer(t))))


def normalize(t):
    t = str(t).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ==============================================================================
# STEP 1 — CLEANING
# ==============================================================================

def clean(df):
    """Removals in order of safety, each one counted."""
    heading("STEP 1 — CLEANING")
    n0 = len(df)
    df = df.copy()

    # fillna before astype: in pandas 3 astype(str) leaves NaN missing
    df[COL_TEXT] = df[COL_TEXT].fillna("").astype(str)

    df[COL_TEXT] = (df[COL_TEXT]
                    .str.replace(r"http\S+|www\.\S+", " ", regex=True)
                    .str.replace(r"@\w+", " ", regex=True)
                    .str.replace(r"&amp;", "&", regex=True)
                    .str.replace(r"\s+", " ", regex=True)
                    .str.strip())

    dup_id = df.duplicated(subset=COL_ID, keep="first")
    print(f"Duplicate post_id          : {dup_id.sum()}  (artifacts, removed)")
    df = df[~dup_id]

    mask = pd.Series(False, index=df.index)
    for p in PLACEHOLDER_PATTERNS:
        mask |= df[COL_TEXT].str.match(p, case=False, na=False)
    print(f"Placeholders, no content   : {mask.sum()}")
    df = df[~mask]

    df["_norm"] = df[COL_TEXT].apply(normalize)
    n_repeated = int(df.duplicated(subset="_norm", keep="first").sum())
    print(f"Identical texts republished: {n_repeated}  (KEPT)")
    if n_repeated > 0:
        print("  most republished:")
        for t, c in df["_norm"].value_counts().head(3).items():
            print(f"    {c}x  {t[:60]}")

    if COLLAPSE_REPOSTS_WITHIN_MINUTES > 0:
        df = df.sort_values(["_norm", COL_TIMESTAMP])
        gap = df.groupby("_norm")[COL_TIMESTAMP].diff().dt.total_seconds().div(60)
        doubles = gap.notna() & (gap <= COLLAPSE_REPOSTS_WITHIN_MINUTES)
        print(f"Double posts within {COLLAPSE_REPOSTS_WITHIN_MINUTES} min "
              f": {doubles.sum()}  (collapsed)")
        df = df[~doubles].sort_values(COL_TIMESTAMP)

    low = df[COL_TEXT].fillna("").astype(str).str.lower()
    mb = pd.Series(False, index=df.index)
    for p in BOILERPLATE_PATTERNS:
        mb |= low.str.contains(p, regex=True, na=False)
    print(f"Endorsement boilerplate    : {mb.sum()}")
    df = df[~mb]

    df["n_words"] = df[COL_TEXT].str.split().str.len()
    short = df["n_words"] < MIN_WORDS
    print(f"Under {MIN_WORDS} words              : {short.sum()}")
    df = df[~short]

    df = df.drop(columns=["_norm"]).reset_index(drop=True)
    print(f"\nRemaining: {len(df)} of {n0} ({len(df)/n0:.1%})")
    return df


# ==============================================================================
# STEP 2 — RULE
# ==============================================================================

def apply_rule(df):
    """Actor x mechanism conjunction, recording the terms found."""
    heading("STEP 2 — OIL RULE")
    low = df[COL_TEXT].fillna("").astype(str).str.lower()

    df = df.copy()
    df["actors_found"] = find_terms(low, ACTORS)
    df["mechanisms_found"] = find_terms(low, MECHANISMS)
    df["has_actor"] = df["actors_found"].str.len() > 0
    df["has_mechanism"] = df["mechanisms_found"].str.len() > 0
    df["oil_event"] = df["has_actor"] & df["has_mechanism"]

    n = int(df["oil_event"].sum())
    print(f"With at least one ACTOR    : {df['has_actor'].sum()}")
    print(f"With at least one MECHANISM: {df['has_mechanism'].sum()}")
    print(f"EVENTS (both)              : {n}  ({n/len(df):.1%} of the corpus)")

    ev = df[df["oil_event"]]

    print("\nMost frequent actors in events:")
    ca = pd.Series([x for l in ev["actors_found"] for x in l]).value_counts()
    print(ca.head(12).to_string())

    print("\nMost frequent mechanisms in events:")
    cm = pd.Series([x for l in ev["mechanisms_found"] for x in l]).value_counts()
    print(cm.head(12).to_string())

    weak_only = ev["mechanisms_found"].apply(
        lambda l: len(l) > 0 and all(x in WEAK_MECHANISMS for x in l))
    print(f"\nEvents resting ONLY on weak mechanisms: {weak_only.sum()} "
          f"({weak_only.mean():.1%} of events)")

    df["weak_mechanisms_only"] = False
    df.loc[ev.index[weak_only], "weak_mechanisms_only"] = True

    print("\nEvents per month:")
    print(ev.groupby(ev[COL_TIMESTAMP].dt.to_period("M")).size().to_string())

    return df


# ==============================================================================
# STEP 3 — MANUAL REVIEW SAMPLE
# ==============================================================================

def sample(df, outdir):
    """Draws posts captured by the rule ('inside') and posts meeting only one
    criterion ('boundary'), to estimate precision and recall."""
    heading("STEP 3 — MANUAL REVIEW SAMPLE")
    rng = np.random.default_rng(SEED)

    inside = df[df["oil_event"]]
    boundary = df[df["has_actor"] ^ df["has_mechanism"]]

    def draw(sub, n, group):
        if len(sub) == 0:
            return pd.DataFrame()
        idx = rng.choice(sub.index, size=min(n, len(sub)), replace=False)
        out = sub.loc[idx, [COL_ID, COL_TIMESTAMP, COL_TEXT,
                            "actors_found", "mechanisms_found"]].copy()
        out.insert(0, "group", group)
        out["label"] = ""      # to fill in by hand: 1 relevant, 0 not
        return out

    review = pd.concat([
        draw(inside, N_SAMPLE_INSIDE, "inside"),
        draw(boundary, N_SAMPLE_BOUNDARY, "boundary"),
    ])
    review.to_csv(outdir / "to_review.csv", index=False)

    print(f"Captured by the rule : {len(inside)}  "
          f"(sampled {min(N_SAMPLE_INSIDE, len(inside))})")
    print(f"On the boundary      : {len(boundary)}  "
          f"(sampled {min(N_SAMPLE_BOUNDARY, len(boundary))})")
    print("\nSaved 'to_review.csv' with the 'label' column to fill in.")


# ==============================================================================
# STEP 4 — EPISODES
# ==============================================================================

def build_episodes(events, outdir):
    """Collapses close posts into one episode, dated at the first post."""
    heading("STEP 4 — EPISODES (collapsed bursts)")

    ev = events.sort_values(COL_TIMESTAMP).copy()
    gap_min = ev[COL_TIMESTAMP].diff().dt.total_seconds().div(60)
    ev["new_episode"] = (gap_min.isna()) | (gap_min > BURST_THRESHOLD_MINUTES)
    ev["episode_id"] = ev["new_episode"].cumsum()

    ep = ev.groupby("episode_id").agg(
        start=(COL_TIMESTAMP, "min"),
        end=(COL_TIMESTAMP, "max"),
        n_post=(COL_ID, "size"),
        n_words_total=("n_words", "sum"),
        first_post=(COL_ID, "first"),
        joined_text=(COL_TEXT, lambda s: " || ".join(s)),
    ).reset_index()
    ep["duration_min"] = (ep["end"] - ep["start"]).dt.total_seconds() / 60

    print(f"Events (single posts) : {len(ev)}")
    print(f"Episodes ({BURST_THRESHOLD_MINUTES} min threshold): {len(ep)}")
    print(f"Reduction             : {1 - len(ep)/len(ev):.1%}")
    print(f"\nPosts per episode: median {ep['n_post'].median():.0f}, "
          f"max {ep['n_post'].max()}")
    print("Distribution:")
    print(ep["n_post"].value_counts().sort_index().head(8).to_string())

    ep.to_csv(outdir / "episodes.csv", index=False)
    return ev, ep


# ==============================================================================
# STEP 5 — INTERVALS
# ==============================================================================

def intervals(ep):
    """Longest event window compatible with the spacing between episodes."""
    heading("STEP 5 — INTERVALS BETWEEN EPISODES")

    if len(ep) < 2:
        print("Too few episodes.")
        return

    ts = ep["start"].sort_values()
    d = ts.diff().dt.total_seconds().div(60).dropna()
    days = max((ts.max() - ts.min()).days, 1)

    print(f"Episodes: {len(ts)} over {days} days "
          f"({len(ts)/days*30.44:.1f} per month)")

    print("\nPercentiles of the interval between episodes (minutes):")
    for p in [1, 5, 10, 25, 50, 75]:
        v = np.percentile(d, p)
        extra = f"  ({v/60:.1f} hours)" if v >= 120 else ""
        print(f"  p{p:<3}: {v:>10.1f} min{extra}")

    print("\nShare of episodes preceded by another within the window:")
    ok = []
    for w in WINDOWS_MINUTES:
        q = (d < w).mean()
        status = "ok" if q < ACCEPTABLE_OVERLAP_SHARE else "contaminated"
        print(f"  {w:>4} min : {q:>6.1%}   {status}")
        if q < ACCEPTABLE_OVERLAP_SHARE:
            ok.append(w)

    if ok:
        print(f"\nLongest event window allowed by the text side: {max(ok)} minutes.")
    else:
        print("\nOverlap above threshold already at 1 minute: raise "
              "BURST_THRESHOLD_MINUTES.")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    # explicit format: timestamps falling on an exact second are written without
    # a fractional part, and pandas 3 infers the format from the first row
    df[COL_TIMESTAMP] = pd.to_datetime(df[COL_TIMESTAMP], utc=True,
                                       format="ISO8601", errors="coerce")
    df = df.dropna(subset=[COL_TIMESTAMP]).sort_values(COL_TIMESTAMP)
    print(f"Loaded {len(df)} posts from {INPUT_CSV}")
    print(f"Period (UTC): {df[COL_TIMESTAMP].min()} -> {df[COL_TIMESTAMP].max()}")

    df = clean(df)
    df = apply_rule(df)
    sample(df, OUTPUT_DIR)

    events = df[df["oil_event"]].copy()
    if len(events) < 2:
        print("\nToo few events: widen the lists and rerun.")
        return

    ev, ep = build_episodes(events, OUTPUT_DIR)
    intervals(ep)

    df.to_csv(OUTPUT_DIR / "clean_corpus.csv", index=False)
    ev.to_csv(OUTPUT_DIR / "oil_events.csv", index=False)

    heading("DONE")
    print("clean_corpus.csv     corpus with the rule columns")
    print(f"oil_events.csv       {len(ev)} captured posts, with episode_id")
    print(f"episodes.csv         {len(ep)} episodes, the unit of analysis")
    print("to_review.csv        sample to annotate by hand")


if __name__ == "__main__":
    main()
