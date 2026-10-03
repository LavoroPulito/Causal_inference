#!/usr/bin/env python3
"""Quota di post che cadono in orari in cui le serie di download/ hanno dati.

Ogni post riceve la copertura del suo giorno della settimana e della sua ora
UTC (quota di minuti con una barra reale, vedi orari_serie.py). La media sui
post e' la percentuale attesa di post con un prezzo disponibile.

    python query/copertura_post.py
"""

from _comune import carica, carica_serie, copertura_oraria

insiemi = {"tutti i post": carica("posts"), "selezionati da 01": carica("eventi")}

for nome, df in carica_serie().items():
    cop = copertura_oraria(df)
    print(f"\n=== {nome} ({df['t'].min():%Y-%m-%d} -> {df['t'].max():%Y-%m-%d}) ===")
    for etichetta, posts in insiemi.items():
        t = posts["timestamp_utc"].dropna()
        quota = cop.reindex(list(zip(t.dt.dayofweek, t.dt.hour))).mean()
        print(f"  {etichetta:18s} {len(t):6d} post  ->  {quota:.1%} in orari con dati")
