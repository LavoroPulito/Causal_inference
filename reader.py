#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controllo rapido della copertura giornaliera di un file scaricato da
Dukascopy: giorni con barre contro giorni feriali attesi nel periodo."""

import pandas as pd

FILE = "download/lightcmdusd-m1-bid-2025-03-01-2025-04-01.csv"
DA, A = "2025-03-01", "2025-03-31"

df = pd.read_csv(FILE)
df["t"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

presenti = df["t"].dt.date.nunique()
attesi = pd.bdate_range(DA, A).size
print(f"giorni con dati: {presenti} su {attesi} feriali attesi")
