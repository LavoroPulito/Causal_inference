#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03 — Download degli storici di prezzo al minuto da Dukascopy.

    WTI     variabile principale
    ORO     controllo: rischio geopolitico via bene rifugio
    EUR/USD proxy del dollaro, confondente plausibile
    BRENT   robustezza (copertura incompleta: vedi report)

Scelta degli strumenti, qualita' dei dati e limiti in
report/stato_progetto.tex.

    python 03_scarica_prezzi.py --dry-run
    python 03_scarica_prezzi.py
    python 03_scarica_prezzi.py --solo wti

Dipendenze: pandas, numpy, pyarrow; Node.js per npx dukascopy-node.
"""

import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================

DATA_INIZIO = date(2024, 12, 1)
DATA_FINE = date(2026, 8, 1)      # estremo escluso

TIMEFRAME = "m1"
PREZZO = "bid"

GREZZI_DIR = Path("dati/prezzi/grezzi")
OUTPUT_DIR = Path("dati/prezzi")

# Identificativi Dukascopy. Verificarli con --dry-run prima di una corsa lunga:
# cambiano fra versioni della CLI.
STRUMENTI = {
    "wti":    "lightcmdusd",
    "oro":    "xauusd",
    "eurusd": "eurusd",
    "brent":  "brentcmdusd",
}

BUCO_MINUTI = 15
PAUSA_FRA_CHIAMATE = 1.0


# ==============================================================================
# UTILITA'
# ==============================================================================

def titolo(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def mesi(inizio, fine):
    """Estremi (primo_giorno, primo_giorno_mese_successivo)."""
    cur = date(inizio.year, inizio.month, 1)
    while cur < fine:
        succ = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        yield cur, min(succ, fine)
        cur = succ


def comando(strumento_id, da, a, outdir):
    return [
        "npx", "--yes", "dukascopy-node",
        "-i", strumento_id,
        "-from", da.isoformat(),
        "-to", a.isoformat(),
        "-t", TIMEFRAME,
        "-p", PREZZO,
        "-f", "csv",
        "-dir", str(outdir),
        "-v", "true",
    ]


# ==============================================================================
# DOWNLOAD
# ==============================================================================

def scarica(nome, strumento_id, dry_run=False):
    """Un blocco mensile alla volta; i blocchi gia' presenti si saltano."""
    outdir = GREZZI_DIR / nome
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- {nome} ({strumento_id}) ---")
    falliti = []

    for da, a in mesi(DATA_INIZIO, DATA_FINE):
        gia_presenti = list(outdir.glob(f"*{da.isoformat()}*"))
        if gia_presenti and not dry_run:
            print(f"  {da:%Y-%m}  gia' presente, salto")
            continue

        cmd = comando(strumento_id, da, a, outdir)

        if dry_run:
            print("  " + " ".join(cmd))
            continue

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                print(f"  {da:%Y-%m}  ERRORE\n    {r.stderr.strip()[:300]}")
                falliti.append(str(da))
            else:
                print(f"  {da:%Y-%m}  ok")
        except subprocess.TimeoutExpired:
            print(f"  {da:%Y-%m}  timeout")
            falliti.append(str(da))
        except FileNotFoundError:
            print("\nnpx non trovato: installa Node.js.")
            sys.exit(1)

    return falliti


# ==============================================================================
# UNIONE E NORMALIZZAZIONE
# ==============================================================================

def unisci(nome):
    """Unisce i CSV mensili in una serie ordinata in UTC. Il campo temporale
    puo' essere epoch (ms o s) o stringa ISO a seconda della versione."""
    outdir = GREZZI_DIR / nome
    file_csv = sorted(outdir.glob("*.csv"))
    if not file_csv:
        print(f"{nome}: nessun CSV trovato.")
        return None

    pezzi = []
    for f in file_csv:
        try:
            pezzi.append(pd.read_csv(f))
        except Exception as e:
            print(f"  illeggibile {f.name}: {e}")

    if not pezzi:
        return None

    df = pd.concat(pezzi, ignore_index=True)
    df.columns = [c.strip().lower() for c in df.columns]

    col_t = next((c for c in df.columns
                  if c in ("timestamp", "time", "date", "datetime")), df.columns[0])

    if pd.api.types.is_numeric_dtype(df[col_t]):
        unita = "ms" if df[col_t].iloc[0] > 1e11 else "s"
        df["t"] = pd.to_datetime(df[col_t], unit=unita, utc=True)
    else:
        df["t"] = pd.to_datetime(df[col_t], utc=True, errors="coerce")

    df = (df.dropna(subset=["t"])
            .drop_duplicates(subset="t", keep="last")
            .sort_values("t")
            .reset_index(drop=True))

    tieni = ["t"] + [c for c in ("open", "high", "low", "close", "volume")
                     if c in df.columns]
    return df[tieni]


# ==============================================================================
# CONTROLLO QUALITA'
# ==============================================================================

def qualita(nome, df):
    """Copertura oraria e buchi infrasettimanali: determina quanti episodi
    avranno un prezzo utilizzabile."""
    print(f"\n--- {nome} ---")
    print(f"Barre           : {len(df):,}")
    print(f"Periodo (UTC)   : {df['t'].min()} -> {df['t'].max()}")

    gap = df["t"].diff().dt.total_seconds().div(60)
    print(f"Intervallo mediano: {gap.median():.1f} min")

    prec = df["t"].shift(1)
    weekend = prec.dt.dayofweek.isin([4, 5, 6])
    buchi = gap > BUCO_MINUTI
    buchi_feriali = buchi & ~weekend

    print(f"Buchi > {BUCO_MINUTI} min   : {buchi.sum()} "
          f"(di cui {buchi_feriali.sum()} infrasettimanali)")

    if buchi_feriali.sum():
        peggiori = (df.assign(gap=gap)[buchi_feriali]
                    .nlargest(5, "gap")[["t", "gap"]])
        print("  i piu' lunghi:")
        for _, r in peggiori.iterrows():
            print(f"    {r['t']}  {r['gap']:.0f} min")

    per_ora = df["t"].dt.hour.value_counts().sort_index()
    print(f"Ore coperte     : {len(per_ora)}/24  "
          f"(min {per_ora.min():,} barre, max {per_ora.max():,})")

    if "close" in df.columns:
        strani = (df["close"] <= 0).sum()
        if strani:
            print(f"  ATTENZIONE: {strani} barre con close <= 0")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="stampa i comandi senza eseguirli")
    ap.add_argument("--solo", help="scarica un solo strumento (es. wti)")
    args = ap.parse_args()

    if not args.dry_run and shutil.which("npx") is None:
        print("npx non trovato. Installa Node.js, oppure usa --dry-run.")
        sys.exit(1)

    if args.solo and args.solo not in STRUMENTI:
        print(f"Strumento sconosciuto. Disponibili: {list(STRUMENTI)}")
        sys.exit(1)

    GREZZI_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    da_fare = ({args.solo: STRUMENTI[args.solo]} if args.solo else STRUMENTI)

    titolo("DOWNLOAD")
    falliti = {}
    for nome, sid in da_fare.items():
        f = scarica(nome, sid, dry_run=args.dry_run)
        if f:
            falliti[nome] = f

    if args.dry_run:
        print("\nDry run: niente scaricato.")
        return

    titolo("UNIONE E CONTROLLO QUALITA'")
    serie = {}
    for nome in da_fare:
        df = unisci(nome)
        if df is None or df.empty:
            print(f"{nome}: niente da unire.")
            continue
        qualita(nome, df)
        df.to_parquet(OUTPUT_DIR / f"{nome}_m1.parquet", index=False)
        serie[nome] = df

    if falliti:
        print("\nBLOCCHI FALLITI (rilancia lo script: riprende da questi)")
        for n, mm in falliti.items():
            print(f"  {n}: {', '.join(mm)}")

    titolo("FATTO")
    for nome, df in serie.items():
        print(f"  {nome}_m1.parquet   {len(df):,} barre")


if __name__ == "__main__":
    main()
