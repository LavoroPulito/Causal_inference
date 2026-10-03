#!/usr/bin/env python3
"""Ricalcola dai file del progetto i numeri citati in stato_progetto.typ e li
scrive in numeri.json.

    python report/typst/numeri.py
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

QUI = Path(__file__).resolve().parent
RADICE = QUI.parents[1]
sys.path.insert(0, str(RADICE / "query"))
from _comune import carica, carica_serie, copertura_oraria  # noqa: E402


def modulo(percorso):
    spec = importlib.util.spec_from_file_location("regola", percorso)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    s = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return round(c - s, 3), round(c + s, 3)


regola = modulo(RADICE / "01_regola_petrolio.py")
posts = carica("posts")
corpus = carica("corpus")
episodi = carica("episodi")
feat = pd.read_parquet(RADICE / "dati" / "features" / "episodi_features.parquet")

# pulizia: i conteggi sono quelli stampati da 01
grezzi = pd.read_csv(RADICE / "dati" / "truth_posts.csv")
grezzi["timestamp_utc"] = pd.to_datetime(grezzi["timestamp_utc"], utc=True, format="ISO8601")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    regola.pulisci(grezzi.sort_values("timestamp_utc"))
log = buf.getvalue()
def conta(etichetta):
    return int(re.search(rf"{etichetta}[^:]*:\s*(\d+)", log).group(1))

attore, mecc = corpus["ha_attore"].astype(bool), corpus["ha_meccanismo"].astype(bool)
gap = episodi["inizio"].sort_values().diff().dt.total_seconds().div(60).dropna()

# storia delle versioni della regola
versioni, prec = [], None
for v in sorted((RADICE / "annotazioni").glob("v*"), key=lambda p: int(p.name[1:])):
    r = modulo(v / "01_regola_petrolio.py")
    termini = set(r.ATTORI) | set(r.MECCANISMI)
    a = pd.read_csv(v / "da_leggere.csv", dtype=str)
    g = pd.to_numeric(a["giudizio"].str.replace("*", "", regex=False), errors="coerce")
    den, con = g[a["gruppo"] == "dentro"], g[a["gruppo"] == "confine"]
    versioni.append({
        "versione": v.name,
        "aggiunti": sorted(termini - prec) if prec else [],
        "tolti": sorted(prec - termini) if prec else [],
        "precisione": round((den == 1).mean(), 3),
        "precisione_ic": wilson(int((den == 1).sum()), len(den)),
        "confine": round((con == 1).mean(), 3),
        "confine_ic": wilson(int((con == 1).sum()), len(con)),
    })
    prec = termini

ultima = versioni[-1]
n_conf = int((attore ^ mecc).sum())
presi = ultima["precisione"] * corpus["evento_petrolio"].sum()
persi = ultima["confine"] * n_conf

wti = carica_serie()["lightcmdusd"]
cop = copertura_oraria(wti)
t = episodi["inizio"]

numeri = {
    "data": pd.Timestamp.today().strftime("%d/%m/%Y"),
    "post": len(posts),
    "post_ucsb": int((posts["fonte"] == "ucsb").sum()),
    "post_cnn": int((posts["fonte"] == "cnn").sum()),
    "periodo_fine": f"{posts['timestamp_utc'].max():%d/%m/%Y}",
    "verificati_ucsb": round(posts.loc[posts["fonte"] == "ucsb", "verificato"].astype(bool).mean(), 3),
    "pulizia": {
        "segnaposto": conta("Segnaposto"),
        "doppi": conta("Doppi invii"),
        "boilerplate": conta("Boilerplate"),
        "corti": conta("Sotto le"),
    },
    "corpus_pulito": len(corpus),
    "con_attore": int(attore.sum()),
    "con_meccanismo": int(mecc.sum()),
    "eventi": int(corpus["evento_petrolio"].sum()),
    "deboli": int(corpus["solo_meccanismi_deboli"].sum()),
    "confine": n_conf,
    "richiamo": round(presi / (presi + persi), 2),
    "episodi": len(episodi),
    "episodi_multipost": int((episodi["n_post"] > 1).sum()),
    "contaminati_60": round((gap < 60).mean(), 3),
    "contaminati_120": round((gap < 120).mean(), 3),
    "mercato_usa": round(feat["mercato_usa_aperto"].mean(), 3),
    "weekend": round(feat["weekend"].mean(), 3),
    "copertura_wti": round(cop.reindex(list(zip(t.dt.dayofweek, t.dt.hour))).mean(), 3),
    "mde": round(2.8016 / math.sqrt(len(episodi)), 3),
    "novita": {k: round(float(feat["novita"].quantile(q)), 3)
               for k, q in [("p10", .1), ("mediana", .5), ("p90", .9)]},
    "novita_basse": int((feat["novita"] < 0.15).sum()),
    "novita_basse_rt": int(((feat["novita"] < 0.15) & feat["testo_unito"].str.startswith("RT")).sum()),
    "gold": len(pd.read_csv(RADICE / "dati" / "features" / "gold_da_annotare.csv")),
    "feature_colonne": feat.shape[1],
    "versioni": versioni,
}

(QUI / "numeri.json").write_text(json.dumps(numeri, indent=2, ensure_ascii=False))
print(f"scritto {QUI / 'numeri.json'}")
