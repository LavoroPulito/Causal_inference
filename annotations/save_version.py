#!/usr/bin/env python3
"""Saves the annotated to_review.csv and the rule that generated it in annotations/vN."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "annotations"

versions = [int(p.name[1:]) for p in FOLDER.glob("v*") if p.is_dir()]
new = FOLDER / f"v{max(versions, default=0) + 1}"
new.mkdir()

shutil.copy(ROOT / "data" / "oil" / "to_review.csv", new)
shutil.copy(ROOT / "01_oil_rule.py", new)

print(f"saved {new.relative_to(ROOT)}")
