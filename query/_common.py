"""Caricamento dei CSV di progetto con i tipi corretti."""

import ast
from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[1]
DATI = RADICE / "dati"

FILE = {
    "posts":      DATI / "truth_posts.csv",
    "corpus":     DATI / "petrolio" / "corpus_pulito.csv",
    "eventi":     DATI / "petrolio" / "eventi_petrolio.csv",
    "episodi":    DATI / "petrolio" / "episodi.csv",
    "da_leggere": DATI / "petrolio" / "da_leggere.csv",
}

COLONNE_TEMPO = ("timestamp_utc", "inizio", "fine")
COLONNE_LISTA = ("attori_trovati", "meccanismi_trovati")


DOWNLOAD = RADICE / "download"
MINUTI_CONGELATI = 60


def carica_serie():
    """Serie al minuto di download/, unite per strumento. Una barra e' reale se
    non sta in un tratto a prezzo costante di almeno MINUTI_CONGELATI minuti."""
    pezzi = {}
    for f in sorted(DOWNLOAD.glob("*.csv")):
        if f.stat().st_size == 0:
            continue
        pezzi.setdefault(f.name.split("-")[0], []).append(pd.read_csv(f))
    serie = {}
    for nome, lista in pezzi.items():
        df = pd.concat(lista).drop_duplicates("timestamp").sort_values("timestamp")
        df["t"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        tratto = (df["close"].diff() != 0).cumsum()
        df["reale"] = df.groupby(tratto)["close"].transform("size") < MINUTI_CONGELATI
        serie[nome] = df.reset_index(drop=True)
    return serie


def copertura_oraria(df):
    """Quota di minuti con una barra reale per (giorno della settimana, ora UTC),
    sul periodo coperto dal file."""
    giorni = pd.date_range(df["t"].min().normalize(), df["t"].max().normalize(), freq="D")
    occorrenze = pd.Series(giorni.dayofweek).value_counts()
    reali = df[df["reale"]]
    conteggi = reali.groupby([reali["t"].dt.dayofweek, reali["t"].dt.hour]).size()
    griglia = pd.MultiIndex.from_product([range(7), range(24)], names=["giorno", "ora"])
    possibili = pd.Series([occorrenze.get(g, 0) * 60 for g, _ in griglia], index=griglia)
    return (conteggi.reindex(griglia, fill_value=0) / possibili).fillna(0)


def carica(nome):
    df = pd.read_csv(FILE[nome])
    for c in COLONNE_TEMPO:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601", errors="coerce")
    for c in COLONNE_LISTA:
        if c in df.columns:
            df[c] = df[c].fillna("[]").apply(ast.literal_eval)
    return df
