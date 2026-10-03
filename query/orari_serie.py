#!/usr/bin/env python3
"""In quali orari le serie di download/ hanno dati.

    python query/orari_serie.py
"""

import pandas as pd

from _comune import carica_serie, copertura_oraria

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

for nome, df in carica_serie().items():
    print(f"\n=== {nome}: {df['t'].min():%Y-%m-%d} -> {df['t'].max():%Y-%m-%d} | "
          f"barre {len(df)}, reali {int(df['reale'].sum())}, "
          f"giorni con barre reali {df.loc[df['reale'], 't'].dt.date.nunique()} ===")

    ora = df["t"].dt.hour
    per_ora = pd.DataFrame({"barre": df.groupby(ora).size(),
                            "reali": df[df["reale"]].groupby(ora[df["reale"]]).size()})
    print("\nbarre per ora UTC")
    print(per_ora.reindex(range(24), fill_value=0).fillna(0).astype(int).T.to_string())

    cop = copertura_oraria(df).unstack()
    cop.index = GIORNI
    print("\n% di minuti con una barra reale, per giorno e ora UTC")
    print((cop * 100).round().astype(int).to_string())
