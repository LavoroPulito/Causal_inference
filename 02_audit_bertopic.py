#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02 — Audit della regola: topic modeling e ricerca semantica.

Due controlli non supervisionati sulla regola dello script 01:
    A) copertura della regola per cluster BERTopic
    B) post semanticamente vicini a frasi-sonda ma non catturati

Gli audit non definiscono le variabili, le verificano. Vedi
report/stato_progetto.tex.

    python 02_audit_bertopic.py

Input: dati/petrolio/corpus_pulito.csv
Dipendenze: bertopic, sentence-transformers, scikit-learn, pandas, numpy.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================

INPUT_CSV = "dati/petrolio/corpus_pulito.csv"
OUTPUT_DIR = Path("dati/petrolio/audit")

COL_TESTO = "testo"
COL_ID = "post_id"

MODELLO_EMBEDDING = "all-MiniLM-L6-v2"
SEME = 42

MIN_CLUSTER_SIZE = 25
N_NEIGHBORS = 15
N_COMPONENTS = 5

# --- audit A ------------------------------------------------------------------
SOGLIA_COPERTURA_SOSPETTA = 0.5
LESSICO_SPIA = [
    "oil", "crude", "barrel", "petroleum", "gas", "gasoline", "fuel", "energy",
    "opec", "saudi", "iran", "russia", "venezuela", "tanker", "pipeline",
    "refinery", "sanctions", "embargo", "strait", "hormuz", "shipping",
]

# --- audit B ------------------------------------------------------------------
# Descrivono il costrutto, non le parole: il modello trova i post vicini anche
# con vocabolario diverso.
SONDE = [
    "disruption to global oil supply",
    "blocking shipping lanes and tankers",
    "sanctions on energy exports",
    "military action threatening oil production",
    "rising gasoline and fuel prices",
    "agreement to increase oil output",
]
N_SIMILI_PER_SONDA = 40


# ==============================================================================
# UTILITA'
# ==============================================================================

def titolo(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def carica_embedding(docs, outdir):
    """Calcola gli embedding una volta sola e li mette in cache su disco."""
    from sentence_transformers import SentenceTransformer

    cache = outdir / "embeddings.npy"
    embedder = SentenceTransformer(MODELLO_EMBEDDING)

    if cache.exists():
        emb = np.load(cache)
        if len(emb) == len(docs):
            print("Embedding riusati dalla cache.")
            return embedder, emb
        print("Cache incoerente col corpus: ricalcolo.")

    emb = embedder.encode(docs, show_progress_bar=True)
    np.save(cache, emb)
    return embedder, emb


# ==============================================================================
# AUDIT A — TOPIC MODELING
# ==============================================================================

def audit_topic(df, embedder, embeddings, outdir):
    """Copertura della regola per cluster. Le stop words servono solo a rendere
    leggibili le etichette c-TF-IDF, non influiscono sul clustering."""
    titolo("AUDIT A — TOPIC MODELING")

    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP
    from hdbscan import HDBSCAN

    docs = df[COL_TESTO].tolist()

    modello = BERTopic(
        embedding_model=embedder,
        umap_model=UMAP(n_neighbors=N_NEIGHBORS, n_components=N_COMPONENTS,
                        min_dist=0.0, metric="cosine", random_state=SEME),
        hdbscan_model=HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE,
                              metric="euclidean",
                              cluster_selection_method="eom",
                              prediction_data=True),
        vectorizer_model=CountVectorizer(stop_words="english",
                                         ngram_range=(1, 2), min_df=3),
        calculate_probabilities=False,
        verbose=True,
    )

    topics, _ = modello.fit_transform(docs, embeddings)
    df = df.copy()
    df["topic"] = topics

    quota_outlier = (np.array(topics) == -1).mean()
    print(f"\nTopic: {len(set(topics)) - 1} | outlier: {quota_outlier:.1%}")

    tab = (df[df["topic"] != -1]
           .groupby("topic")
           .agg(n=(COL_ID, "size"),
                catturati=("evento_petrolio", "sum"),
                copertura=("evento_petrolio", "mean")))
    tab["termini"] = [
        ", ".join(w for w, _ in (modello.get_topic(t) or [])[:6])
        for t in tab.index
    ]

    print("\nCluster con la maggior parte dei post catturati dalla regola:")
    print(tab.sort_values("catturati", ascending=False)
          .head(12)[["n", "catturati", "copertura", "termini"]]
          .to_string())

    spia = tab["termini"].apply(lambda s: any(w in s for w in LESSICO_SPIA))
    sospetti = tab[spia & (tab["copertura"] < SOGLIA_COPERTURA_SOSPETTA)]

    print("\n--- CLUSTER SOSPETTI (lessico petrolifero, copertura bassa) ---")
    if len(sospetti) == 0:
        print("Nessuno.")
    else:
        print(sospetti[["n", "catturati", "copertura", "termini"]].to_string())

        righe = []
        for t in sospetti.index:
            sub = df[(df["topic"] == t) & (~df["evento_petrolio"])]
            for _, r in sub.head(10).iterrows():
                righe.append({"topic": t, "termini": tab.loc[t, "termini"],
                              COL_ID: r[COL_ID], "testo": r[COL_TESTO][:500]})
        pd.DataFrame(righe).to_csv(outdir / "cluster_sospetti.csv", index=False)

    tab.to_csv(outdir / "copertura_per_cluster.csv")
    return df


# ==============================================================================
# AUDIT B — RICERCA SEMANTICA
# ==============================================================================

def audit_semantico(df, embedder, embeddings, outdir):
    """Post vicini alle sonde nello spazio degli embedding ma non catturati
    dalla regola: i candidati falsi negativi."""
    titolo("AUDIT B — RICERCA SEMANTICA")

    from sklearn.metrics.pairwise import cosine_similarity

    emb_sonde = embedder.encode(SONDE)
    sim = cosine_similarity(emb_sonde, embeddings)   # (n_sonde, n_doc)

    df = df.copy()
    df["similarita_max"] = sim.max(axis=0)
    df["sonda_piu_vicina"] = [SONDE[i] for i in sim.argmax(axis=0)]

    righe = []
    for i, sonda in enumerate(SONDE):
        ordine = np.argsort(-sim[i])[:N_SIMILI_PER_SONDA]

        for pos in ordine:
            r = df.iloc[pos]
            if r["evento_petrolio"]:
                continue
            righe.append({
                "sonda": sonda,
                "similarita": round(float(sim[i, pos]), 3),
                COL_ID: r[COL_ID],
                "timestamp": r.get("timestamp_utc", None),
                "testo": str(r[COL_TESTO])[:500],
            })

    if righe:
        out = pd.DataFrame(righe).drop_duplicates(subset=COL_ID)
        out.to_csv(outdir / "falsi_negativi_candidati.csv", index=False)
        print(f"\n{len(out)} candidati falsi negativi in "
              f"'falsi_negativi_candidati.csv'.")
    else:
        print("\nNessun candidato.")

    return df


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    if "evento_petrolio" not in df.columns:
        raise SystemExit("Manca 'evento_petrolio': lancia prima lo script 01.")
    df["evento_petrolio"] = df["evento_petrolio"].astype(bool)
    df = df.reset_index(drop=True)

    print(f"Corpus: {len(df)} post, di cui "
          f"{df['evento_petrolio'].sum()} catturati dalla regola "
          f"({df['evento_petrolio'].mean():.1%})")

    docs = df[COL_TESTO].astype(str).tolist()
    embedder, embeddings = carica_embedding(docs, OUTPUT_DIR)

    df = audit_topic(df, embedder, embeddings, OUTPUT_DIR)
    df = audit_semantico(df, embedder, embeddings, OUTPUT_DIR)

    df.to_csv(OUTPUT_DIR / "corpus_con_audit.csv", index=False)

    titolo("FATTO")
    print("copertura_per_cluster.csv       copertura della regola per cluster")
    print("cluster_sospetti.csv            cluster petroliferi poco coperti")
    print("falsi_negativi_candidati.csv    post simili alle sonde ma esclusi")


if __name__ == "__main__":
    main()
