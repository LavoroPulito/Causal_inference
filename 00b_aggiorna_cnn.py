#!/usr/bin/env python3
"""
00b — Aggiunge a dati/truth_posts.csv i post presenti nell'archivio CNN e
assenti dal corpus. Il timestamp e' derivato dall'ID come in 00.

    python 00b_aggiorna_cnn.py
"""

import html
import json
from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
CACHE_DIR = Path("cache_cnn")
CORPUS = Path("dati/truth_posts.csv")
DATA_INIZIO = pd.Timestamp("2024-12-01", tz="UTC")
USER_AGENT = "Ricerca accademica - tesi magistrale"


def ripara(testo):
    testo = html.unescape(testo or "")
    try:
        return testo.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return testo


CACHE_DIR.mkdir(exist_ok=True)
grezzo = CACHE_DIR / f"truth_archive_{date.today().isoformat()}.json"
r = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=120)
r.raise_for_status()
grezzo.write_bytes(r.content)

cnn = pd.DataFrame(json.loads(r.content))
cnn["post_id"] = cnn["url"].str.extract(r"truthsocial\.com/@[\w.]+/(?:posts/)?(\d+)$")[0].astype("int64")
cnn["url"] = "https://truthsocial.com/@realDonaldTrump/posts/" + cnn["post_id"].astype(str)
ms = cnn["post_id"].apply(lambda x: x >> 16)
cnn["timestamp_utc"] = pd.to_datetime(ms, unit="ms", utc=True)
cnn["sequenza"] = cnn["post_id"].apply(lambda x: x & 0xFFFF)
cnn["testo"] = cnn["content"].apply(ripara)
dichiarato = pd.to_datetime(cnn["created_at"], utc=True, format="ISO8601")
cnn["scarto_minuti"] = (dichiarato - cnn["timestamp_utc"]).abs().dt.total_seconds() / 60
cnn["verificato"] = cnn["scarto_minuti"] <= 1
cnn["fonte"] = "cnn"

corpus = pd.read_csv(CORPUS)
if "fonte" not in corpus.columns:
    corpus["fonte"] = "ucsb"

nuovi = cnn[~cnn["post_id"].isin(corpus["post_id"]) & (cnn["timestamp_utc"] >= DATA_INIZIO)]
colonne = ["post_id", "testo", "url", "timestamp_utc", "sequenza",
           "scarto_minuti", "verificato", "fonte"]
corpus["timestamp_utc"] = pd.to_datetime(corpus["timestamp_utc"], utc=True, format="ISO8601")
uniti = (pd.concat([corpus, nuovi[colonne]], ignore_index=True)
           .sort_values("timestamp_utc").reset_index(drop=True))
uniti.to_csv(CORPUS, index=False)

print(f"archivio CNN: {len(cnn)} post, salvato in {grezzo}")
print(f"aggiunti: {len(nuovi)} | corpus: {len(corpus)} -> {len(uniti)}")
print(f"periodo: {uniti['timestamp_utc'].min()} -> {uniti['timestamp_utc'].max()}")
