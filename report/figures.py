#!/usr/bin/env python3
"""Recomputes from the project files the figures quoted in project_status.typ
and writes them to figures.json.

    python report/figures.py
"""

import contextlib
import importlib.util
import io
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "query"))
from _common import load, load_series, hourly_coverage  # noqa: E402


def module(path):
    spec = importlib.util.spec_from_file_location("rule", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    s = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return round(c - s, 3), round(c + s, 3)


rule = module(ROOT / "01_oil_rule.py")
posts = load("posts")
corpus = load("corpus")
episodes = load("episodes")
feat = pd.read_parquet(ROOT / "data" / "features" / "episode_features.parquet")

# cleaning: the counts are the ones printed by 01
raw = pd.read_csv(ROOT / "data" / "truth_posts.csv")
raw["timestamp_utc"] = pd.to_datetime(raw["timestamp_utc"], utc=True, format="ISO8601")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rule.clean(raw.sort_values("timestamp_utc"))
log = buf.getvalue()
def count(label):
    return int(re.search(rf"{label}[^:]*:\s*(\d+)", log).group(1))

actor, mech = corpus["has_actor"].astype(bool), corpus["has_mechanism"].astype(bool)
gap = episodes["start"].sort_values().diff().dt.total_seconds().div(60).dropna()

# history of the rule versions
versions, prev = [], None
for v in sorted((ROOT / "annotations").glob("v*"), key=lambda p: int(p.name[1:])):
    r = module(v / "01_oil_rule.py")
    terms = set(r.ACTORS) | set(r.MECHANISMS)
    a = pd.read_csv(v / "to_review.csv", dtype=str)
    g = pd.to_numeric(a["label"].str.replace("*", "", regex=False), errors="coerce")
    ins, bnd = g[a["group"] == "inside"], g[a["group"] == "boundary"]
    versions.append({
        "version": v.name,
        "added": sorted(terms - prev) if prev else [],
        "removed": sorted(prev - terms) if prev else [],
        "precision": round((ins == 1).mean(), 3),
        "precision_ci": wilson(int((ins == 1).sum()), len(ins)),
        "boundary": round((bnd == 1).mean(), 3),
        "boundary_ci": wilson(int((bnd == 1).sum()), len(bnd)),
    })
    prev = terms

last = versions[-1]
n_boundary = int((actor ^ mech).sum())
caught = last["precision"] * corpus["oil_event"].sum()
missed = last["boundary"] * n_boundary

# audit
audit_dir = ROOT / "data" / "oil" / "audit"
audited = pd.read_csv(audit_dir / "corpus_with_audit.csv", usecols=["topic"])
clusters = pd.read_csv(audit_dir / "coverage_by_cluster.csv")
suspicious = pd.read_csv(audit_dir / "suspicious_clusters.csv")
suspicious = clusters[clusters["topic"].isin(suspicious["topic"])]
top = clusters.sort_values("captured", ascending=False).head(2)

wti = load_series()["lightcmdusd"]
cov = hourly_coverage(wti)
t = episodes["start"]

figures = {
    "date": pd.Timestamp.today().strftime("%d/%m/%Y"),
    "posts": len(posts),
    "posts_ucsb": int((posts["source"] == "ucsb").sum()),
    "posts_cnn": int((posts["source"] == "cnn").sum()),
    "period_end": f"{posts['timestamp_utc'].max():%d/%m/%Y}",
    "verified_ucsb": round(posts.loc[posts["source"] == "ucsb", "verified"].astype(bool).mean(), 3),
    "cleaning": {
        "placeholders": count("Placeholders"),
        "doubles": count("Double posts"),
        "boilerplate": count("Endorsement boilerplate"),
        "short": count("Under"),
    },
    "clean_corpus": len(corpus),
    "with_actor": int(actor.sum()),
    "with_mechanism": int(mech.sum()),
    "events": int(corpus["oil_event"].sum()),
    "weak": int(corpus["weak_mechanisms_only"].sum()),
    "boundary": n_boundary,
    "recall": round(caught / (caught + missed), 2),
    "audit": {
        "corpus": len(audited),
        "topics": int(clusters["topic"].nunique()),
        "outliers": round((audited["topic"] == -1).mean(), 3),
        "top": [{"terms": r.terms, "n": int(r.n), "captured": int(r.captured),
                 "coverage": round(r.coverage, 2)} for r in top.itertuples()],
        "suspicious": [{"terms": r.terms, "n": int(r.n), "captured": int(r.captured),
                        "coverage": round(r.coverage, 2)} for r in suspicious.itertuples()],
        "false_negatives": len(pd.read_csv(audit_dir / "candidate_false_negatives.csv")),
    },
    "episodes": len(episodes),
    "episodes_multipost": int((episodes["n_post"] > 1).sum()),
    "contaminated_60": round((gap < 60).mean(), 3),
    "contaminated_120": round((gap < 120).mean(), 3),
    "us_market": round(feat["us_market_open"].mean(), 3),
    "weekend": round(feat["weekend"].mean(), 3),
    "wti_coverage": round(cov.reindex(list(zip(t.dt.dayofweek, t.dt.hour))).mean(), 3),
    "mde": round(2.8016 / math.sqrt(len(episodes)), 3),
    "novelty": {k: round(float(feat["novelty"].quantile(q)), 3)
                for k, q in [("p10", .1), ("median", .5), ("p90", .9)]},
    "novelty_low": int((feat["novelty"] < 0.15).sum()),
    "novelty_low_rt": int(((feat["novelty"] < 0.15) & feat["joined_text"].str.startswith("RT")).sum()),
    "gold": len(pd.read_csv(ROOT / "data" / "features" / "gold_to_annotate.csv")),
    "feature_columns": feat.shape[1],
    "versions": versions,
}

(HERE / "figures.json").write_text(json.dumps(figures, indent=2, ensure_ascii=False))
print(f"written {HERE / 'figures.json'}")
