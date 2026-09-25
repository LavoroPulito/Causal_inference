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


def carica(nome):
    df = pd.read_csv(FILE[nome])
    for c in COLONNE_TEMPO:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601", errors="coerce")
    for c in COLONNE_LISTA:
        if c in df.columns:
            df[c] = df[c].fillna("[]").apply(ast.literal_eval)
    return df
