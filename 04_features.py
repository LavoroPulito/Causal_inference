#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04 — Features for each episode.

    A  deterministic features           (always)
    B  semantic novelty                 (--novelty)
    C  export the sample to annotate    (--gold)
    D  scoring with a local LLM         (--llm)
    E  manual vs automatic agreement    (--agreement)

The variable of interest is the expected direction on supply, not sentiment;
the unit of analysis is the episode. See report/project_status.typ.

    python 04_features.py
    python 04_features.py --novelty --gold
    python 04_features.py --llm
    python 04_features.py --agreement

Dependencies: pandas, numpy, pyarrow, sentence-transformers, scikit-learn,
scipy, requests; Ollama for step D.
"""

import re
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURATION
# ==============================================================================

EPISODES_CSV = "data/oil/episodes.csv"
OUTPUT_DIR = Path("data/features")

SEED = 42

# --- novelty ------------------------------------------------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
NOVELTY_WINDOW_DAYS = 30

# --- gold standard ------------------------------------------------------------
N_GOLD = 200
N_DOUBLE_ANNOTATION = 50

# --- LLM ----------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "qwen2.5:14b"
TEMPERATURE = 0.0
MAX_PROMPT_CHARS = 4000

# The prompt goes in the thesis appendix together with model and temperature.
PROMPT = """You are annotating social media posts for a study on oil markets.

Read the post and answer ONLY with a JSON object, no other text.

Fields:
- "direction": integer from -2 to 2. Expected effect on global oil SUPPLY.
    -2 = strong threat to supply (blockade, strikes on oil infrastructure, war)
    -1 = mild threat (sanctions talk, rising tension)
     0 = no clear supply implication
    +1 = mild easing (talks, partial sanctions relief)
    +2 = strong easing (deal reached, blockade lifted, output increase)
- "intensity": integer 1-3.
     1 = speculation or commentary
     2 = threat or stated intention
     3 = action declared as done or imminent
- "specificity": integer 0-1.
     1 = names a specific target, quantity, deadline or party
     0 = generic
- "confidence": float 0-1, your own confidence in this annotation.

POST:
\"\"\"{text}\"\"\"
"""


# ==============================================================================
# UTILITIES
# ==============================================================================

def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load():
    df = pd.read_csv(EPISODES_CSV)
    for c in ("start", "end"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
    if "joined_text" not in df.columns:
        raise SystemExit("Missing 'joined_text': rerun 01_oil_rule.py")
    df["joined_text"] = df["joined_text"].fillna("").astype(str)
    return df.sort_values("start").reset_index(drop=True)


# ==============================================================================
# STEP A — DETERMINISTIC FEATURES
# ==============================================================================

def deterministic_features(df):
    """Time, calendar, length, emphasis. No model involved."""
    heading("STEP A — DETERMINISTIC FEATURES")
    t = df["start"]
    local = t.dt.tz_convert("America/New_York")
    minutes = local.dt.hour * 60 + local.dt.minute

    df = df.copy()
    df["hour_utc"] = t.dt.hour
    df["hour_ny"] = local.dt.hour
    df["weekday"] = local.dt.dayofweek
    df["weekend"] = df["weekday"] >= 5
    df["us_market_open"] = (~df["weekend"]) & minutes.between(9 * 60 + 30, 16 * 60)

    text = df["joined_text"]
    df["n_chars"] = text.str.len()
    df["n_exclamations"] = text.str.count("!")
    df["n_uppercase"] = text.str.count(r"[A-Z]")
    df["uppercase_share"] = (df["n_uppercase"] /
                             text.str.count(r"[A-Za-z]").replace(0, np.nan))
    df["n_shouted_words"] = text.str.count(r"\b[A-Z]{4,}\b")

    print(f"Episodes: {len(df)}")
    print(f"During US market hours   : {df['us_market_open'].mean():.1%}")
    print(f"On weekends              : {df['weekend'].mean():.1%}")
    print(f"Posts per episode (median): {df['n_post'].median():.0f}")
    print(f"Uppercase share (median)  : {df['uppercase_share'].median():.2f}")
    return df


# ==============================================================================
# STEP B — SEMANTIC NOVELTY
# ==============================================================================

def novelty(df, outdir):
    """novelty = 1 - max cosine similarity with the episodes of the previous
    window. Close to 1 = new content, close to 0 = repetition."""
    heading("STEP B — SEMANTIC NOVELTY")
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    cache = outdir / "episode_embeddings.npy"
    emb_model = SentenceTransformer(EMBEDDING_MODEL)

    if cache.exists() and len(np.load(cache)) == len(df):
        emb = np.load(cache)
        print("Embeddings reused from the cache.")
    else:
        emb = emb_model.encode(df["joined_text"].tolist(), show_progress_bar=True)
        np.save(cache, emb)

    window = pd.Timedelta(days=NOVELTY_WINDOW_DAYS)
    values, similar = [], []

    for i in range(len(df)):
        t_i = df.loc[i, "start"]
        prev = df.index[(df["start"] < t_i) & (df["start"] >= t_i - window)]
        if len(prev) == 0:
            values.append(1.0)
            similar.append(None)
            continue
        sim = cosine_similarity(emb[i:i + 1], emb[prev])[0]
        values.append(float(1 - sim.max()))
        similar.append(int(prev[int(sim.argmax())]))

    df = df.copy()
    df["novelty"] = values
    df["most_similar_episode"] = similar

    print(f"Novelty — median {np.median(values):.3f}, "
          f"p10 {np.percentile(values, 10):.3f}, "
          f"p90 {np.percentile(values, 90):.3f}")
    print(f"Episodes nearly identical to a previous one (novelty < 0.15): "
          f"{(df['novelty'] < 0.15).sum()}")
    return df


# ==============================================================================
# STEP C — SAMPLE FOR MANUAL ANNOTATION
# ==============================================================================

def export_gold(df, outdir):
    """Sample stratified by quarter, plus a subset for inter-annotator
    agreement."""
    heading("STEP C — SAMPLE TO ANNOTATE")
    rng = np.random.default_rng(SEED)

    df = df.copy()
    df["_stratum"] = df["start"].dt.to_period("Q")
    per_stratum = max(1, N_GOLD // df["_stratum"].nunique())

    chosen = []
    for _, g in df.groupby("_stratum"):
        n = min(per_stratum, len(g))
        chosen.extend(rng.choice(g.index, size=n, replace=False))

    gold = df.loc[sorted(chosen)].copy()

    columns = ["episode_id", "start", "n_post", "joined_text"]
    if "novelty" in gold.columns:
        columns.append("novelty")
    gold = gold[columns]

    for c in ["direction", "intensity", "specificity", "notes"]:
        gold[c] = ""

    gold.to_csv(outdir / "gold_to_annotate.csv", index=False)

    double = gold.sample(n=min(N_DOUBLE_ANNOTATION, len(gold)),
                         random_state=SEED)
    double.to_csv(outdir / "gold_double_annotation.csv", index=False)

    print(f"Exported {len(gold)} episodes to 'gold_to_annotate.csv'.")
    print(f"Of these, {len(double)} also in 'gold_double_annotation.csv' "
          "for inter-annotator agreement.")
    print("The annotation guidelines must be fixed before starting: if they "
          "change, everything is annotated again.")


# ==============================================================================
# STEP D — SCORING WITH A LOCAL LLM
# ==============================================================================

def llm_scoring(df, outdir):
    """Automatic annotation, resumable. Model, prompt and temperature are saved
    next to the results."""
    heading("STEP D — SCORING WITH A LOCAL LLM")
    import requests

    outfile = outdir / "llm_annotations.jsonl"
    done = set()
    if outfile.exists():
        with open(outfile, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["episode_id"])
                except Exception:
                    pass
        print(f"Resuming: {len(done)} episodes already annotated.")

    (outdir / "llm_prompt.txt").write_text(
        f"model: {LLM_MODEL}\ntemperature: {TEMPERATURE}\n\n{PROMPT}",
        encoding="utf-8")

    todo = df[~df["episode_id"].isin(done)]
    print(f"To annotate: {len(todo)}")

    ok, errors = 0, 0
    with open(outfile, "a", encoding="utf-8") as f:
        for i, (_, r) in enumerate(todo.iterrows(), 1):
            text = r["joined_text"][:MAX_PROMPT_CHARS]
            try:
                resp = requests.post(OLLAMA_URL, timeout=180, json={
                    "model": LLM_MODEL,
                    "prompt": PROMPT.format(text=text),
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": TEMPERATURE, "seed": SEED},
                })
                answer = json.loads(resp.json()["response"])
                answer["episode_id"] = int(r["episode_id"])
                f.write(json.dumps(answer, ensure_ascii=False) + "\n")
                f.flush()
                ok += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  error on {r['episode_id']}: {str(e)[:120]}")

            if i % 50 == 0:
                print(f"  {i}/{len(todo)}  (ok {ok}, errors {errors})")

    print(f"\nCompleted {ok}, errors {errors}.")
    if errors > len(todo) * 0.05:
        print("High error rate: check Ollama and the validity of the JSON.")

    if outfile.exists():
        ann = pd.read_json(outfile, lines=True)
        ann = ann.drop_duplicates(subset="episode_id", keep="last")
        ann = ann.rename(columns={c: f"llm_{c}" for c in ann.columns
                                  if c != "episode_id"})
        df = df.merge(ann, on="episode_id", how="left")

        if "llm_direction" in df.columns:
            print("\nDistribution of the estimated direction:")
            print(df["llm_direction"].value_counts().sort_index().to_string())
    return df


# ==============================================================================
# STEP E — AGREEMENT
# ==============================================================================

def agreement(df, outdir):
    """Spearman and quadratic weighted kappa between manual and LLM annotation.
    Below 0.4 the automatic variable is not used."""
    heading("STEP E — MANUAL vs AUTOMATIC AGREEMENT")
    gold_file = outdir / "gold_annotated.csv"
    if not gold_file.exists():
        print("Missing 'gold_annotated.csv'. Annotate 'gold_to_annotate.csv', "
              "rename it and rerun.")
        return

    from scipy.stats import spearmanr
    from sklearn.metrics import cohen_kappa_score

    gold = pd.read_csv(gold_file)
    merged = gold.merge(df, on="episode_id", suffixes=("_man", "_auto"))

    for field in ["direction", "intensity", "specificity"]:
        col_auto = f"llm_{field}"
        if field not in merged.columns or col_auto not in merged.columns:
            continue
        sub = merged[[field, col_auto]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub) < 20:
            print(f"{field}: too few cases ({len(sub)})")
            continue

        rho, p = spearmanr(sub[field], sub[col_auto])
        k = cohen_kappa_score(sub[field].astype(int), sub[col_auto].astype(int),
                              weights="quadratic")
        exact = (sub[field] == sub[col_auto]).mean()

        print(f"\n{field}  (n={len(sub)})")
        print(f"  Spearman       : {rho:+.3f}  (p={p:.1e})")
        print(f"  weighted kappa : {k:+.3f}")
        print(f"  exact agreement: {exact:.1%}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--novelty", action="store_true")
    ap.add_argument("--gold", action="store_true")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--agreement", action="store_true")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load()

    df = deterministic_features(df)

    if args.novelty:
        df = novelty(df, OUTPUT_DIR)
    if args.gold:
        export_gold(df, OUTPUT_DIR)
    if args.llm:
        df = llm_scoring(df, OUTPUT_DIR)
    if args.agreement:
        agreement(df, OUTPUT_DIR)

    df.to_parquet(OUTPUT_DIR / "episode_features.parquet", index=False)

    heading("DONE")
    print(f"episode_features.parquet   {len(df)} episodes, "
          f"{len(df.columns)} columns")
    print("\nFreeze the features, with the date, before touching prices.")

if __name__ == "__main__":
    main()
