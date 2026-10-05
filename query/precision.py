#!/usr/bin/env python3
"""Quota di righe di un gruppo di da_leggere.csv con un dato giudizio.

    python query/precisione.py                       # dentro, giudizio 1
    python query/precisione.py --gruppo confine      # stesso conto sul confine
"""

import argparse
import math

from _comune import carica


def wilson(k, n, z=1.96):
    """Intervallo di confidenza al 95% per una proporzione."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / den
    semi = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return centro - semi, centro + semi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gruppo", default="dentro")
    ap.add_argument("--valore", type=float, default=1)
    args = ap.parse_args()

    df = carica("da_leggere")
    g = df[df["gruppo"] == args.gruppo]
    if g.empty:
        raise SystemExit(f"Nessuna riga nel gruppo '{args.gruppo}'. "
                         f"Gruppi presenti: {sorted(df['gruppo'].unique())}")

    n = len(g)
    annotate = int(g["giudizio"].notna().sum())
    print(f"gruppo '{args.gruppo}': {n} righe, {annotate} annotate")
    if annotate == 0:
        return

    k = int((g["giudizio"] == args.valore).sum())
    basso, alto = wilson(k, n)
    print(f"giudizio = {args.valore:g}: {k} su {n} = {k / n:.1%}")
    print(f"IC 95% (Wilson): {basso:.1%} - {alto:.1%}")
    if annotate < n:
        print(f"attenzione: {n - annotate} righe senza giudizio contano al "
              f"denominatore; sulle sole annotate la quota e' {k / annotate:.1%}")


if __name__ == "__main__":
    main()
