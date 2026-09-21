#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04 — Feature per episodio.

    A  feature deterministiche          (sempre)
    B  novita' semantica                (--novita)
    C  esporta il campione da annotare  (--gold)
    D  scoring con LLM locale           (--llm)
    E  accordo manuale vs automatico    (--accordo)

La variabile di interesse e' la direzione attesa sull'offerta, non il
sentiment; l'unita' di analisi e' l'episodio. Vedi report/stato_progetto.tex.

    python 04_features.py
    python 04_features.py --novita --gold
    python 04_features.py --llm
    python 04_features.py --accordo

Dipendenze: pandas, numpy, pyarrow, sentence-transformers, scikit-learn,
scipy, requests; Ollama per la fase D.
"""

import re
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================

EPISODI_CSV = "dati/petrolio/episodi.csv"
OUTPUT_DIR = Path("dati/features")

SEME = 42

# --- novita' ------------------------------------------------------------------
MODELLO_EMBEDDING = "all-MiniLM-L6-v2"
FINESTRA_NOVITA_GIORNI = 30

# --- gold standard ------------------------------------------------------------
N_GOLD = 200
N_DOPPIA_ANNOTAZIONE = 50

# --- LLM ----------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELLO_LLM = "qwen2.5:14b"
TEMPERATURA = 0.0
MAX_CARATTERI_PROMPT = 4000

# Il prompt va in appendice alla tesi insieme a modello e temperatura.
PROMPT = """You are annotating social media posts for a study on oil markets.

Read the post and answer ONLY with a JSON object, no other text.

Fields:
- "direzione": integer from -2 to 2. Expected effect on global oil SUPPLY.
    -2 = strong threat to supply (blockade, strikes on oil infrastructure, war)
    -1 = mild threat (sanctions talk, rising tension)
     0 = no clear supply implication
    +1 = mild easing (talks, partial sanctions relief)
    +2 = strong easing (deal reached, blockade lifted, output increase)
- "intensita": integer 1-3.
     1 = speculation or commentary
     2 = threat or stated intention
     3 = action declared as done or imminent
- "concretezza": integer 0-1.
     1 = names a specific target, quantity, deadline or party
     0 = generic
- "confidenza": float 0-1, your own confidence in this annotation.

POST:
\"\"\"{testo}\"\"\"
"""


# ==============================================================================
# UTILITA'
# ==============================================================================

def titolo(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def carica():
    df = pd.read_csv(EPISODI_CSV)
    for c in ("inizio", "fine"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
    if "testo_unito" not in df.columns:
        raise SystemExit("Manca 'testo_unito': rilancia 01_regola_petrolio.py")
    df["testo_unito"] = df["testo_unito"].fillna("").astype(str)
    return df.sort_values("inizio").reset_index(drop=True)


# ==============================================================================
# FASE A — FEATURE DETERMINISTICHE
# ==============================================================================

def feature_deterministiche(df):
    """Ora, calendario, lunghezza, enfasi. Nessun modello di mezzo."""
    titolo("FASE A — FEATURE DETERMINISTICHE")
    t = df["inizio"]
    locale = t.dt.tz_convert("America/New_York")
    minuti = locale.dt.hour * 60 + locale.dt.minute

    df = df.copy()
    df["ora_utc"] = t.dt.hour
    df["ora_ny"] = locale.dt.hour
    df["giorno_settimana"] = locale.dt.dayofweek
    df["weekend"] = df["giorno_settimana"] >= 5
    df["mercato_usa_aperto"] = (~df["weekend"]) & minuti.between(9 * 60 + 30, 16 * 60)

    testo = df["testo_unito"]
    df["n_caratteri"] = testo.str.len()
    df["n_esclamativi"] = testo.str.count("!")
    df["n_maiuscole"] = testo.str.count(r"[A-Z]")
    df["quota_maiuscole"] = (df["n_maiuscole"] /
                             testo.str.count(r"[A-Za-z]").replace(0, np.nan))
    df["n_parole_urlate"] = testo.str.count(r"\b[A-Z]{4,}\b")

    print(f"Episodi: {len(df)}")
    print(f"In orario di mercato USA : {df['mercato_usa_aperto'].mean():.1%}")
    print(f"Nel weekend              : {df['weekend'].mean():.1%}")
    print(f"Post per episodio (mediana): {df['n_post'].median():.0f}")
    print(f"Quota maiuscole (mediana)  : {df['quota_maiuscole'].median():.2f}")
    return df


# ==============================================================================
# FASE B — NOVITA' SEMANTICA
# ==============================================================================

def novita(df, outdir):
    """novita = 1 - max similarita' coseno con gli episodi della finestra
    precedente. Vicino a 1 = contenuto nuovo, vicino a 0 = ripetizione."""
    titolo("FASE B — NOVITA' SEMANTICA")
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    cache = outdir / "emb_episodi.npy"
    emb_model = SentenceTransformer(MODELLO_EMBEDDING)

    if cache.exists() and len(np.load(cache)) == len(df):
        emb = np.load(cache)
        print("Embedding riusati dalla cache.")
    else:
        emb = emb_model.encode(df["testo_unito"].tolist(), show_progress_bar=True)
        np.save(cache, emb)

    finestra = pd.Timedelta(days=FINESTRA_NOVITA_GIORNI)
    valori, simili = [], []

    for i in range(len(df)):
        t_i = df.loc[i, "inizio"]
        prec = df.index[(df["inizio"] < t_i) & (df["inizio"] >= t_i - finestra)]
        if len(prec) == 0:
            valori.append(1.0)
            simili.append(None)
            continue
        sim = cosine_similarity(emb[i:i + 1], emb[prec])[0]
        valori.append(float(1 - sim.max()))
        simili.append(int(prec[int(sim.argmax())]))

    df = df.copy()
    df["novita"] = valori
    df["episodio_piu_simile"] = simili

    print(f"Novita' — mediana {np.median(valori):.3f}, "
          f"p10 {np.percentile(valori, 10):.3f}, "
          f"p90 {np.percentile(valori, 90):.3f}")
    print(f"Episodi quasi identici a uno precedente (novita < 0.15): "
          f"{(df['novita'] < 0.15).sum()}")
    return df


# ==============================================================================
# FASE C — CAMPIONE PER ANNOTAZIONE MANUALE
# ==============================================================================

def esporta_gold(df, outdir):
    """Campione stratificato per trimestre, piu' un sottoinsieme per l'accordo
    fra annotatori."""
    titolo("FASE C — CAMPIONE DA ANNOTARE")
    rng = np.random.default_rng(SEME)

    df = df.copy()
    df["_strato"] = df["inizio"].dt.to_period("Q")
    per_strato = max(1, N_GOLD // df["_strato"].nunique())

    scelti = []
    for _, g in df.groupby("_strato"):
        n = min(per_strato, len(g))
        scelti.extend(rng.choice(g.index, size=n, replace=False))

    gold = df.loc[sorted(scelti)].copy()

    colonne = ["episodio_id", "inizio", "n_post", "testo_unito"]
    if "novita" in gold.columns:
        colonne.append("novita")
    gold = gold[colonne]

    for c in ["direzione", "intensita", "concretezza", "note"]:
        gold[c] = ""

    gold.to_csv(outdir / "gold_da_annotare.csv", index=False)

    doppia = gold.sample(n=min(N_DOPPIA_ANNOTAZIONE, len(gold)),
                         random_state=SEME)
    doppia.to_csv(outdir / "gold_doppia_annotazione.csv", index=False)

    print(f"Esportati {len(gold)} episodi in 'gold_da_annotare.csv'.")
    print(f"Di questi, {len(doppia)} anche in 'gold_doppia_annotazione.csv' "
          "per l'accordo fra annotatori.")
    print("I criteri di annotazione vanno fissati prima di cominciare: se "
          "cambiano, si riannota da capo.")


# ==============================================================================
# FASE D — SCORING CON LLM LOCALE
# ==============================================================================

def scoring_llm(df, outdir):
    """Annotazione automatica, ripartibile. Modello, prompt e temperatura
    vengono salvati accanto ai risultati."""
    titolo("FASE D — SCORING CON LLM LOCALE")
    import requests

    outfile = outdir / "llm_annotazioni.jsonl"
    gia_fatti = set()
    if outfile.exists():
        with open(outfile, encoding="utf-8") as f:
            for riga in f:
                try:
                    gia_fatti.add(json.loads(riga)["episodio_id"])
                except Exception:
                    pass
        print(f"Ripresa: {len(gia_fatti)} episodi gia' annotati.")

    (outdir / "llm_prompt.txt").write_text(
        f"modello: {MODELLO_LLM}\ntemperatura: {TEMPERATURA}\n\n{PROMPT}",
        encoding="utf-8")

    da_fare = df[~df["episodio_id"].isin(gia_fatti)]
    print(f"Da annotare: {len(da_fare)}")

    ok, errori = 0, 0
    with open(outfile, "a", encoding="utf-8") as f:
        for i, (_, r) in enumerate(da_fare.iterrows(), 1):
            testo = r["testo_unito"][:MAX_CARATTERI_PROMPT]
            try:
                resp = requests.post(OLLAMA_URL, timeout=180, json={
                    "model": MODELLO_LLM,
                    "prompt": PROMPT.format(testo=testo),
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": TEMPERATURA, "seed": SEME},
                })
                dati = json.loads(resp.json()["response"])
                dati["episodio_id"] = int(r["episodio_id"])
                f.write(json.dumps(dati, ensure_ascii=False) + "\n")
                f.flush()
                ok += 1
            except Exception as e:
                errori += 1
                if errori <= 3:
                    print(f"  errore su {r['episodio_id']}: {str(e)[:120]}")

            if i % 50 == 0:
                print(f"  {i}/{len(da_fare)}  (ok {ok}, errori {errori})")

    print(f"\nCompletati {ok}, errori {errori}.")
    if errori > len(da_fare) * 0.05:
        print("Tasso di errore alto: controlla Ollama e la validita' del JSON.")

    if outfile.exists():
        ann = pd.read_json(outfile, lines=True)
        ann = ann.drop_duplicates(subset="episodio_id", keep="last")
        ann = ann.rename(columns={c: f"llm_{c}" for c in ann.columns
                                  if c != "episodio_id"})
        df = df.merge(ann, on="episodio_id", how="left")

        if "llm_direzione" in df.columns:
            print("\nDistribuzione della direzione stimata:")
            print(df["llm_direzione"].value_counts().sort_index().to_string())
    return df


# ==============================================================================
# FASE E — ACCORDO
# ==============================================================================

def accordo(df, outdir):
    """Spearman e kappa pesato quadratico fra annotazione manuale e LLM.
    Sotto 0.4 la variabile automatica non si usa."""
    titolo("FASE E — ACCORDO MANUALE vs AUTOMATICO")
    gold_file = outdir / "gold_annotato.csv"
    if not gold_file.exists():
        print("Manca 'gold_annotato.csv'. Annota 'gold_da_annotare.csv', "
              "rinominalo e rilancia.")
        return

    from scipy.stats import spearmanr
    from sklearn.metrics import cohen_kappa_score

    gold = pd.read_csv(gold_file)
    merge = gold.merge(df, on="episodio_id", suffixes=("_man", "_auto"))

    for campo in ["direzione", "intensita", "concretezza"]:
        col_auto = f"llm_{campo}"
        if campo not in merge.columns or col_auto not in merge.columns:
            continue
        sub = merge[[campo, col_auto]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub) < 20:
            print(f"{campo}: troppi pochi casi ({len(sub)})")
            continue

        rho, p = spearmanr(sub[campo], sub[col_auto])
        k = cohen_kappa_score(sub[campo].astype(int), sub[col_auto].astype(int),
                              weights="quadratic")
        esatta = (sub[campo] == sub[col_auto]).mean()

        print(f"\n{campo}  (n={len(sub)})")
        print(f"  Spearman      : {rho:+.3f}  (p={p:.1e})")
        print(f"  kappa pesato  : {k:+.3f}")
        print(f"  accordo esatto: {esatta:.1%}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--novita", action="store_true")
    ap.add_argument("--gold", action="store_true")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--accordo", action="store_true")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = carica()

    df = feature_deterministiche(df)

    if args.novita:
        df = novita(df, OUTPUT_DIR)
    if args.gold:
        esporta_gold(df, OUTPUT_DIR)
    if args.llm:
        df = scoring_llm(df, OUTPUT_DIR)
    if args.accordo:
        accordo(df, OUTPUT_DIR)

    df.to_parquet(OUTPUT_DIR / "episodi_features.parquet", index=False)

    titolo("FATTO")
    print(f"episodi_features.parquet   {len(df)} episodi, "
          f"{len(df.columns)} colonne")
    print("\nLe feature vanno congelate, con la data, prima di toccare i prezzi.")

if __name__ == "__main__":
    main()
