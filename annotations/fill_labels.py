#!/usr/bin/env python3
"""Riempie il giudizio in da_leggere.csv per i post gia' giudicati nelle
versioni salvate. A parita' di post vale la versione piu' recente."""

from pathlib import Path

import pandas as pd

RADICE = Path(__file__).resolve().parents[1]
CARTELLA = RADICE / "annotazioni"
DA_LEGGERE = RADICE / "dati" / "petrolio" / "da_leggere.csv"

versioni = sorted((p for p in CARTELLA.glob("v*") if p.is_dir()),
                  key=lambda p: int(p.name[1:]))

giudizi = {}
for v in versioni:
    ann = pd.read_csv(v / "da_leggere.csv").dropna(subset=["giudizio"])
    giudizi.update(zip(ann["post_id"], ann["giudizio"]))

df = pd.read_csv(DA_LEGGERE)
prima = df["giudizio"].notna().sum()
df["giudizio"] = df["giudizio"].fillna(df["post_id"].map(giudizi))
df.to_csv(DA_LEGGERE, index=False)

print(f"riempiti {df['giudizio'].notna().sum() - prima} giudizi su {len(df)} righe")
