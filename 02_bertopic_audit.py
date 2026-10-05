#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02 — Rule audit: topic modeling and semantic search.

Two unsupervised checks on the rule of script 01:
    A) rule coverage for each BERTopic cluster
    B) posts semantically close to probe sentences but not captured

The audits do not define the variables, they test them. See
report/project_status.typ.

    python 02_bertopic_audit.py

Input: data/oil/clean_corpus.csv
Dependencies: bertopic, sentence-transformers, scikit-learn, pandas, numpy.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURATION
# ==============================================================================

INPUT_CSV = "data/oil/clean_corpus.csv"
OUTPUT_DIR = Path("data/oil/audit")

COL_TEXT = "text"
COL_ID = "post_id"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SEED = 42

MIN_CLUSTER_SIZE = 25
N_NEIGHBORS = 15
N_COMPONENTS = 5

# --- audit A ------------------------------------------------------------------
SUSPICIOUS_COVERAGE_THRESHOLD = 0.5
TELLTALE_LEXICON = [
    "oil", "crude", "barrel", "petroleum", "gas", "gasoline", "fuel", "energy",
    "opec", "saudi", "iran", "russia", "venezuela", "tanker", "pipeline",
    "refinery", "sanctions", "embargo", "strait", "hormuz", "shipping",
]

# --- audit B ------------------------------------------------------------------
# They describe the construct, not the words: the model finds close posts even
# when the vocabulary differs.
PROBES = [
    "disruption to global oil supply",
    "blocking shipping lanes and tankers",
    "sanctions on energy exports",
    "military action threatening oil production",
    "rising gasoline and fuel prices",
    "agreement to increase oil output",
]
N_SIMILAR_PER_PROBE = 40


# ==============================================================================
# UTILITIES
# ==============================================================================

def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load_embeddings(docs, outdir):
    """Computes the embeddings once and caches them on disk."""
    from sentence_transformers import SentenceTransformer

    cache = outdir / "embeddings.npy"
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    if cache.exists():
        emb = np.load(cache)
        if len(emb) == len(docs):
            print("Embeddings reused from the cache.")
            return embedder, emb
        print("Cache inconsistent with the corpus: recomputing.")

    emb = embedder.encode(docs, show_progress_bar=True)
    np.save(cache, emb)
    return embedder, emb


# ==============================================================================
# AUDIT A — TOPIC MODELING
# ==============================================================================

def topic_audit(df, embedder, embeddings, outdir):
    """Rule coverage for each cluster. Stop words only make the c-TF-IDF labels
    readable, they do not affect the clustering."""
    heading("AUDIT A — TOPIC MODELING")

    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP
    from hdbscan import HDBSCAN

    docs = df[COL_TEXT].tolist()

    model = BERTopic(
        embedding_model=embedder,
        umap_model=UMAP(n_neighbors=N_NEIGHBORS, n_components=N_COMPONENTS,
                        min_dist=0.0, metric="cosine", random_state=SEED),
        hdbscan_model=HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE,
                              metric="euclidean",
                              cluster_selection_method="eom",
                              prediction_data=True),
        vectorizer_model=CountVectorizer(stop_words="english",
                                         ngram_range=(1, 2), min_df=3),
        calculate_probabilities=False,
        verbose=True,
    )

    topics, _ = model.fit_transform(docs, embeddings)
    df = df.copy()
    df["topic"] = topics

    outlier_share = (np.array(topics) == -1).mean()
    print(f"\nTopics: {len(set(topics)) - 1} | outliers: {outlier_share:.1%}")

    tab = (df[df["topic"] != -1]
           .groupby("topic")
           .agg(n=(COL_ID, "size"),
                captured=("oil_event", "sum"),
                coverage=("oil_event", "mean")))
    tab["terms"] = [
        ", ".join(w for w, _ in (model.get_topic(t) or [])[:6])
        for t in tab.index
    ]

    print("\nClusters with most posts captured by the rule:")
    print(tab.sort_values("captured", ascending=False)
          .head(12)[["n", "captured", "coverage", "terms"]]
          .to_string())

    telltale = tab["terms"].apply(lambda s: any(w in s for w in TELLTALE_LEXICON))
    suspicious = tab[telltale & (tab["coverage"] < SUSPICIOUS_COVERAGE_THRESHOLD)]

    print("\n--- SUSPICIOUS CLUSTERS (oil lexicon, low coverage) ---")
    if len(suspicious) == 0:
        print("None.")
    else:
        print(suspicious[["n", "captured", "coverage", "terms"]].to_string())

        rows = []
        for t in suspicious.index:
            sub = df[(df["topic"] == t) & (~df["oil_event"])]
            for _, r in sub.head(10).iterrows():
                rows.append({"topic": t, "terms": tab.loc[t, "terms"],
                             COL_ID: r[COL_ID], "text": r[COL_TEXT][:500]})
        pd.DataFrame(rows).to_csv(outdir / "suspicious_clusters.csv", index=False)

    tab.to_csv(outdir / "coverage_by_cluster.csv")
    return df


# ==============================================================================
# AUDIT B — SEMANTIC SEARCH
# ==============================================================================

def semantic_audit(df, embedder, embeddings, outdir):
    """Posts close to the probes in embedding space but not captured by the
    rule: the candidate false negatives."""
    heading("AUDIT B — SEMANTIC SEARCH")

    from sklearn.metrics.pairwise import cosine_similarity

    probe_emb = embedder.encode(PROBES)
    sim = cosine_similarity(probe_emb, embeddings)   # (n_probes, n_docs)

    df = df.copy()
    df["max_similarity"] = sim.max(axis=0)
    df["nearest_probe"] = [PROBES[i] for i in sim.argmax(axis=0)]

    rows = []
    for i, probe in enumerate(PROBES):
        order = np.argsort(-sim[i])[:N_SIMILAR_PER_PROBE]

        for pos in order:
            r = df.iloc[pos]
            if r["oil_event"]:
                continue
            rows.append({
                "probe": probe,
                "similarity": round(float(sim[i, pos]), 3),
                COL_ID: r[COL_ID],
                "timestamp": r.get("timestamp_utc", None),
                "text": str(r[COL_TEXT])[:500],
            })

    if rows:
        out = pd.DataFrame(rows).drop_duplicates(subset=COL_ID)
        out.to_csv(outdir / "candidate_false_negatives.csv", index=False)
        print(f"\n{len(out)} candidate false negatives in "
              f"'candidate_false_negatives.csv'.")
    else:
        print("\nNo candidates.")

    return df


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    if "oil_event" not in df.columns:
        raise SystemExit("Missing 'oil_event': run script 01 first.")
    df["oil_event"] = df["oil_event"].astype(bool)
    df = df.reset_index(drop=True)

    print(f"Corpus: {len(df)} posts, of which "
          f"{df['oil_event'].sum()} captured by the rule "
          f"({df['oil_event'].mean():.1%})")

    docs = df[COL_TEXT].astype(str).tolist()
    embedder, embeddings = load_embeddings(docs, OUTPUT_DIR)

    df = topic_audit(df, embedder, embeddings, OUTPUT_DIR)
    df = semantic_audit(df, embedder, embeddings, OUTPUT_DIR)

    df.to_csv(OUTPUT_DIR / "corpus_with_audit.csv", index=False)

    heading("DONE")
    print("coverage_by_cluster.csv         rule coverage per cluster")
    print("suspicious_clusters.csv         oil clusters with low coverage")
    print("candidate_false_negatives.csv   posts similar to the probes but excluded")


if __name__ == "__main__":
    main()
