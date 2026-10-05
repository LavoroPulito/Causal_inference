#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
00 — Scraping dei post Truth Social dall'American Presidency Project (UCSB).

Il timestamp e' derivato dall'ID snowflake, non dall'ora in pagina, e validato
contro di essa. Motivazioni e limiti: vedi report/stato_progetto.tex.

    python 00_scraper_ucsb.py --ispeziona 2024-12-01
    python 00_scraper_ucsb.py

Dipendenze: requests, beautifulsoup4, lxml, pandas.
"""

import re
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================

DATA_INIZIO = date(2024, 12, 1)
DATA_FINE = date(2026, 7, 31)      # estremo incluso

CACHE_DIR = Path("cache_ucsb")
OUTPUT_DIR = Path("dati")

BASE = "https://www.presidency.ucsb.edu/documents/truth-social-posts-{m}-{d}-{y}"

PAUSA_SECONDI = 0.2
TIMEOUT = 30
USER_AGENT = "Ricerca accademica - tesi magistrale (contatto: j.arma.ac@gmail.com)"

MESI = ["january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"]

FUSO_PAGINA = "America/Los_Angeles"
TOLLERANZA_MINUTI = 1


# ==============================================================================
# DECODIFICA DELL'ID
# ==============================================================================

def id_a_utc(post_id):
    """Snowflake Mastodon -> datetime UTC."""
    ms = int(post_id) >> 16
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def id_a_sequenza(post_id):
    """I 16 bit bassi: ordinano i post nello stesso millisecondo."""
    return int(post_id) & 0xFFFF


# ==============================================================================
# SCARICAMENTO
# ==============================================================================

def url_del_giorno(g):
    return BASE.format(m=MESI[g.month - 1], d=g.day, y=g.year)


def scarica(g, sessione):
    """HTML del giorno, dalla cache se presente. Un 404 e' messo in cache come
    stringa vuota; un errore di rete torna None e sara' riprovato."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{g.isoformat()}.html"

    if f.exists():
        return f.read_text(encoding="utf-8")

    url = url_del_giorno(g)
    try:
        r = sessione.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"  {g} errore di rete: {e}")
        return None

    time.sleep(PAUSA_SECONDI)

    if r.status_code == 404:
        f.write_text("", encoding="utf-8")
        return ""
    if r.status_code != 200:
        print(f"  {g} HTTP {r.status_code}")
        return None

    f.write_text(r.text, encoding="utf-8")
    return r.text


# ==============================================================================
# PARSING
# ==============================================================================

RE_ID = re.compile(r"truthsocial\.com/@[\w.]+/posts/(\d+)")

# L'archivio usa due formati: 24 ore senza suffisso ("18:11") e 12 ore con
# meridiano ("1:17 PM", "7:05 A.M."). Si cerca prima l'ora, poi il meridiano
# ancorato subito dopo di essa. Il confine di parola e il match maiuscolo
# servono a non leggere come meridiano l'inizio del testo che segue un orario
# a 24 ore ("10:08 Amazing...", "09:36 A MUST WATCH...").
RE_ORA = re.compile(r"(\d{1,2}):(\d{2})")
RE_MERIDIANO = re.compile(r"\s*([AP])\.?\s?M\b\.?")


def ora_a_24(ora, minuto, meridiano):
    """('1', '17', 'P') -> '13:17'. Senza meridiano l'ora e' gia' a 24 ore."""
    ora = int(ora)
    if meridiano == "A" and ora == 12:
        ora = 0
    elif meridiano == "P" and ora != 12:
        ora += 12
    return f"{ora:02d}:{minuto}"


def ispeziona(html):
    """Stampa la struttura della pagina, per riadattare i selettori."""
    soup = BeautifulSoup(html, "lxml")

    print("--- candidati contenitore ---")
    for cls in ["field-docs-content", "node__content", "field-item"]:
        for el in soup.select(f"div.{cls}"):
            testo = el.get_text(" ", strip=True)[:200]
            print(f"\ndiv.{cls}\n  {testo}")

    print("\n--- link a truthsocial trovati ---")
    for a in soup.find_all("a", href=RE_ID):
        print(" ", a["href"])

    print("\n--- primi 3000 caratteri del contenuto principale ---")
    main = soup.select_one("div.field-docs-content") or soup.body
    print(main.get_text("\n", strip=True)[:3000])


def estrai_post(html, giorno):
    """Estrae i post partendo dai link a truthsocial, che portano l'ID. Ogni
    link chiude il blocco di testo che lo precede."""
    soup = BeautifulSoup(html, "lxml")
    contenuto = soup.select_one("div.field-docs-content") or soup.body
    if contenuto is None:
        return []

    testo_completo = contenuto.get_text("\n", strip=True)

    link = [a for a in contenuto.find_all("a", href=RE_ID)]
    if not link:
        return []

    posts = []
    pezzi = re.split(r"https?://truthsocial\.com/@[\w.]+/posts/\d+", testo_completo)
    ids = [RE_ID.search(a["href"]).group(1) for a in link]

    for i, pid in enumerate(ids):
        blocco = pezzi[i] if i < len(pezzi) else ""

        m = RE_ORA.search(blocco[:200])
        ora_pagina, testo = None, blocco
        if m:
            mer = RE_MERIDIANO.match(blocco, m.end())
            ora_pagina = ora_a_24(m.group(1), m.group(2),
                                  mer.group(1) if mer else None)
            testo = blocco[mer.end() if mer else m.end():]
        testo = re.sub(r"^\s*[\-\*•]\s*", "", testo)
        testo = re.sub(r"\s+", " ", testo).strip()

        posts.append({
            "post_id": pid,
            "data_pagina": giorno.isoformat(),
            "ora_pagina_pacific": ora_pagina,
            "testo": testo,
            "url": f"https://truthsocial.com/@realDonaldTrump/posts/{pid}",
        })

    return posts


# ==============================================================================
# VALIDAZIONE
# ==============================================================================

def valida(df):
    """Confronta il timestamp derivato dall'ID con l'ora Pacific in pagina."""
    df = df.copy()
    df["timestamp_utc"] = df["post_id"].apply(id_a_utc)
    df["sequenza"] = df["post_id"].apply(id_a_sequenza)

    locale = df["timestamp_utc"].dt.tz_convert(FUSO_PAGINA)
    df["ora_da_id_pacific"] = locale.dt.strftime("%H:%M")
    df["data_da_id_pacific"] = locale.dt.date.astype(str)

    atteso = pd.to_datetime(df["data_da_id_pacific"] + " " + df["ora_da_id_pacific"],
                            errors="coerce")
    osservato = pd.to_datetime(df["data_pagina"] + " " + df["ora_pagina_pacific"],
                               errors="coerce")
    scarto = (atteso - osservato).dt.total_seconds().abs().div(60)

    df["scarto_minuti"] = scarto
    df["verificato"] = scarto <= TOLLERANZA_MINUTI

    return df


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ispeziona", metavar="AAAA-MM-GG",
                    help="scarica un solo giorno e stampa la struttura HTML")
    args = ap.parse_args()

    sessione = requests.Session()
    sessione.headers.update({"User-Agent": USER_AGENT})

    if args.ispeziona:
        g = date.fromisoformat(args.ispeziona)
        html = scarica(g, sessione)
        if not html:
            print("Pagina vuota o non trovata.")
            return
        ispeziona(html)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tutti, vuoti, falliti = [], 0, []
    g = DATA_INIZIO
    while g <= DATA_FINE:
        html = scarica(g, sessione)

        if html is None:
            falliti.append(g.isoformat())
        elif html == "":
            vuoti += 1
        else:
            p = estrai_post(html, g)
            if not p:
                falliti.append(g.isoformat())
            tutti.extend(p)

        if g.day == 1:
            print(f"{g.strftime('%Y-%m')}  ...  {len(tutti)} post finora")

        g += timedelta(days=1)

    if not tutti:
        print("\nNessun post estratto. Lancia --ispeziona e adatta i selettori.")
        return

    df = pd.DataFrame(tutti).drop_duplicates(subset="post_id")
    df = valida(df).sort_values("timestamp_utc").reset_index(drop=True)

    print("\n" + "=" * 78)
    print(f"Post estratti          : {len(df)}")
    print(f"Giorni senza pagina    : {vuoti}")
    print(f"Giorni problematici    : {len(falliti)}")
    print(f"Periodo (UTC)          : {df['timestamp_utc'].min()} -> "
          f"{df['timestamp_utc'].max()}")

    n_ver = int(df["verificato"].sum())
    print(f"\nRighe verificate (ID == ora in pagina): {n_ver} ({n_ver/len(df):.1%})")
    if n_ver / len(df) < 0.95:
        print("  Scarti piu' frequenti (minuti):")
        print(df.loc[~df["verificato"], "scarto_minuti"]
              .round().value_counts().head(5).to_string())

    per_giorno = df.groupby(df["timestamp_utc"].dt.date).size()
    print(f"\nPost per giorno: mediana {per_giorno.median():.0f}, "
          f"max {per_giorno.max()}, giorni coperti {len(per_giorno)}")
    print(f"Secondi diversi da zero: "
          f"{(df['timestamp_utc'].dt.second != 0).mean():.1%}")

    df.to_csv(OUTPUT_DIR / "truth_posts.csv", index=False)
    df[~df["verificato"]].to_csv(OUTPUT_DIR / "anomalie.csv", index=False)
    if falliti:
        (OUTPUT_DIR / "giorni_falliti.txt").write_text("\n".join(falliti))

    print(f"\nSalvato in {OUTPUT_DIR}/truth_posts.csv")


if __name__ == "__main__":
    main()
