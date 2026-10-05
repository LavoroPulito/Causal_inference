#!/usr/bin/env python3
"""
00b — Adds to data/truth_posts.csv the posts that are in the CNN archive and
missing from the corpus. The timestamp is derived from the ID as in 00.

    python 00b_update_cnn.py
"""

import html
import json
from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
CACHE_DIR = Path("cache_cnn")
CORPUS = Path("data/truth_posts.csv")
START_DATE = pd.Timestamp("2024-12-01", tz="UTC")
USER_AGENT = "Academic research - master's thesis"


def repair(text):
    text = html.unescape(text or "")
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


CACHE_DIR.mkdir(exist_ok=True)
raw = CACHE_DIR / f"truth_archive_{date.today().isoformat()}.json"
r = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=120)
r.raise_for_status()
raw.write_bytes(r.content)

cnn = pd.DataFrame(json.loads(r.content))
cnn["post_id"] = cnn["url"].str.extract(r"truthsocial\.com/@[\w.]+/(?:posts/)?(\d+)$")[0].astype("int64")
cnn["url"] = "https://truthsocial.com/@realDonaldTrump/posts/" + cnn["post_id"].astype(str)
ms = cnn["post_id"].apply(lambda x: x >> 16)
cnn["timestamp_utc"] = pd.to_datetime(ms, unit="ms", utc=True)
cnn["sequence"] = cnn["post_id"].apply(lambda x: x & 0xFFFF)
cnn["text"] = cnn["content"].apply(repair)
declared = pd.to_datetime(cnn["created_at"], utc=True, format="ISO8601")
cnn["offset_minutes"] = (declared - cnn["timestamp_utc"]).abs().dt.total_seconds() / 60
cnn["verified"] = cnn["offset_minutes"] <= 1
cnn["source"] = "cnn"

corpus = pd.read_csv(CORPUS)
if "source" not in corpus.columns:
    corpus["source"] = "ucsb"

new = cnn[~cnn["post_id"].isin(corpus["post_id"]) & (cnn["timestamp_utc"] >= START_DATE)]
columns = ["post_id", "text", "url", "timestamp_utc", "sequence",
           "offset_minutes", "verified", "source"]
corpus["timestamp_utc"] = pd.to_datetime(corpus["timestamp_utc"], utc=True, format="ISO8601")
merged = (pd.concat([corpus, new[columns]], ignore_index=True)
            .sort_values("timestamp_utc").reset_index(drop=True))
merged.to_csv(CORPUS, index=False)

print(f"CNN archive: {len(cnn)} posts, saved to {raw}")
print(f"added: {len(new)} | corpus: {len(corpus)} -> {len(merged)}")
print(f"period: {merged['timestamp_utc'].min()} -> {merged['timestamp_utc'].max()}")
