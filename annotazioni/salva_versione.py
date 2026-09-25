#!/usr/bin/env python3
"""Salva da_leggere.csv annotato e la regola che l'ha generato in annotazioni/vN."""

import shutil
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
CARTELLA = RADICE / "annotazioni"

versioni = [int(p.name[1:]) for p in CARTELLA.glob("v*") if p.is_dir()]
nuova = CARTELLA / f"v{max(versioni, default=0) + 1}"
nuova.mkdir()

shutil.copy(RADICE / "dati" / "petrolio" / "da_leggere.csv", nuova)
shutil.copy(RADICE / "01_regola_petrolio.py", nuova)

print(f"salvata {nuova.relative_to(RADICE)}")
