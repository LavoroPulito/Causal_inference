#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01 — Pulizia del corpus, regola petrolifera, episodi, intervalli.

    FASE 1  pulizia        duplicati, segnaposto, boilerplate
    FASE 2  regola         attore x meccanismo
    FASE 3  campione       post da annotare a mano
    FASE 4  episodi        burst collassati
    FASE 5  intervalli     dimensionamento della finestra evento

Le motivazioni delle scelte sono in report/stato_progetto.tex.

    python 01_regola_petrolio.py

Input: dati/truth_posts.csv
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================

INPUT_CSV = "dati/truth_posts.csv"
OUTPUT_DIR = Path("dati/petrolio")

COL_TESTO = "testo"
COL_TIMESTAMP = "timestamp_utc"
COL_ID = "post_id"

SEME = 42

# --- pulizia ------------------------------------------------------------------
MIN_PAROLE = 5

# Si deduplica su post_id, non sul testo: un testo ripubblicato con ID diverso
# e' un evento distinto. Si collassano solo i doppi invii ravvicinati.
COLLASSA_RIPUBBLICAZIONI_ENTRO_MINUTI = 2   # 0 per disattivare

PATTERN_SEGNAPOSTO = [
    r"^\s*\[\s*response to previous truth post\s*\]\s*$",
    r"^\s*\[\s*no content\s*\]\s*$",
    r"^\s*$",
]
PATTERN_BOILERPLATE = [
    r"complete and total endorsement",
    r"(?:he|she) (?:will|has) never let you down",
]

# --- campionamento per lettura manuale ----------------------------------------
N_CAMPIONE_DENTRO = 100
N_CAMPIONE_CONFINE = 50

# --- episodi ------------------------------------------------------------------
SOGLIA_BURST_MINUTI = 30

# --- intervalli ---------------------------------------------------------------
FINESTRE_MINUTI = [1, 2, 5, 10, 15, 30, 60, 120]
QUOTA_SOVRAPPOSIZIONE_ACCETTABILE = 0.15


# ==============================================================================
# LA REGOLA
# ==============================================================================

ATTORI = [
    # Iran
    "iran", "iranian", "iranians", "tehran", "khamenei", "irgc",
    "revolutionary guard", "hormuz", "persian gulf",
    # Venezuela
    "venezuela", "venezuelan", "maduro", "caracas", "pdvsa",
    # Russia / Ucraina
    "russia", "russian", "russians", "putin", "moscow", "kremlin",
    "rosneft", "lukoil", "gazprom", "nord stream", "urals",
    "ukraine", "ukrainian", "zelensky", "zelenskyy", "kyiv",
    # produttori e istituzioni del greggio
    "opec", "saudi", "saudi arabia", "aramco",
    "strategic petroleum reserve", "spr",
    # rotte e navigazione
    "red sea", "houthi", "houthis", "suez", "bab el mandeb",
    # mercato
    "market", "markets"
    ]

MECCANISMI = [
    # interruzione fisica dell'offerta
    "blockade", "blockading", "mine", "mines", "interdict", "interdiction",
    "tanker", "tankers", "shipping", "strait", "waterway", "vessel", "vessels",
    "convoy", "port", "ports", "pipeline", "refinery", "refineries",
    "shadow fleet", "dark fleet",
    # azione militare
    "strike", "strikes", "military", "navy", "naval", "bomber", "bombers",
    "attack", "attacked", "war", "destroy", "destroyed", "drone", "drones",
    # sanzioni ed embargo
    "sanction", "sanctions", "sanctioned", "embargo", "price cap",
    "secondary tariff", "secondary tariffs",
    # petrolio esplicito
    "oil", "crude", "barrel", "barrels", "petroleum", "gasoline", "fuel",
    # negoziato nucleare
    "nuclear", "enrichment", "jcpoa",
    # prezzo
    "come down", "boom", "going down", "coming down"
]

# Solo diagnostica: segnalano un possibile falso positivo se sono l'unico
# meccanismo presente.
MECCANISMI_DEBOLI = ["war", "military", "attack", "strike", "strikes", "nuclear", "down"]


# ==============================================================================
# UTILITA'
# ==============================================================================

def titolo(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def pattern_di(termini):
    return r"\b(" + "|".join(re.escape(x) for x in termini) + r")\b"


def trovati(serie_lower, termini):
    """Per ogni riga, la lista dei termini effettivamente trovati."""
    rx = re.compile(pattern_di(termini))
    return serie_lower.fillna("").astype(str).apply(
        lambda t: sorted(set(m.group(0) for m in rx.finditer(t))))


def normalizza(t):
    t = str(t).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ==============================================================================
# FASE 1 — PULIZIA
# ==============================================================================

def pulisci(df):
    """Rimozioni in ordine di sicurezza, ciascuna contata."""
    titolo("FASE 1 — PULIZIA")
    n0 = len(df)
    df = df.copy()

    # fillna prima di astype: con pandas 3 astype(str) lascia i NaN mancanti
    df[COL_TESTO] = df[COL_TESTO].fillna("").astype(str)

    df[COL_TESTO] = (df[COL_TESTO]
                     .str.replace(r"http\S+|www\.\S+", " ", regex=True)
                     .str.replace(r"@\w+", " ", regex=True)
                     .str.replace(r"&amp;", "&", regex=True)
                     .str.replace(r"\s+", " ", regex=True)
                     .str.strip())

    dup_id = df.duplicated(subset=COL_ID, keep="first")
    print(f"post_id duplicati          : {dup_id.sum()}  (artefatti, rimossi)")
    df = df[~dup_id]

    mask = pd.Series(False, index=df.index)
    for p in PATTERN_SEGNAPOSTO:
        mask |= df[COL_TESTO].str.match(p, case=False, na=False)
    print(f"Segnaposto senza contenuto : {mask.sum()}")
    df = df[~mask]

    df["_norm"] = df[COL_TESTO].apply(normalizza)
    n_testi_ripetuti = int(df.duplicated(subset="_norm", keep="first").sum())
    print(f"Testi identici ripubblicati: {n_testi_ripetuti}  (CONSERVATI)")
    if n_testi_ripetuti > 0:
        print("  piu' ripubblicati:")
        for t, c in df["_norm"].value_counts().head(3).items():
            print(f"    {c}x  {t[:60]}")

    if COLLASSA_RIPUBBLICAZIONI_ENTRO_MINUTI > 0:
        df = df.sort_values(["_norm", COL_TIMESTAMP])
        gap = df.groupby("_norm")[COL_TIMESTAMP].diff().dt.total_seconds().div(60)
        doppi = gap.notna() & (gap <= COLLASSA_RIPUBBLICAZIONI_ENTRO_MINUTI)
        print(f"Doppi invii entro {COLLASSA_RIPUBBLICAZIONI_ENTRO_MINUTI} min   "
              f": {doppi.sum()}  (collassati)")
        df = df[~doppi].sort_values(COL_TIMESTAMP)

    low = df[COL_TESTO].fillna("").astype(str).str.lower()
    mb = pd.Series(False, index=df.index)
    for p in PATTERN_BOILERPLATE:
        mb |= low.str.contains(p, regex=True, na=False)
    print(f"Boilerplate endorsement    : {mb.sum()}")
    df = df[~mb]

    df["n_parole"] = df[COL_TESTO].str.split().str.len()
    corti = df["n_parole"] < MIN_PAROLE
    print(f"Sotto le {MIN_PAROLE} parole            : {corti.sum()}")
    df = df[~corti]

    df = df.drop(columns=["_norm"]).reset_index(drop=True)
    print(f"\nRimasti: {len(df)} su {n0} ({len(df)/n0:.1%})")
    return df


# ==============================================================================
# FASE 2 — REGOLA
# ==============================================================================

def applica_regola(df):
    """Congiunzione attore x meccanismo, con tracciamento dei termini trovati."""
    titolo("FASE 2 — REGOLA PETROLIFERA")
    low = df[COL_TESTO].fillna("").astype(str).str.lower()

    df = df.copy()
    df["attori_trovati"] = trovati(low, ATTORI)
    df["meccanismi_trovati"] = trovati(low, MECCANISMI)
    df["ha_attore"] = df["attori_trovati"].str.len() > 0
    df["ha_meccanismo"] = df["meccanismi_trovati"].str.len() > 0
    df["evento_petrolio"] = df["ha_attore"] & df["ha_meccanismo"]

    n = int(df["evento_petrolio"].sum())
    print(f"Con almeno un ATTORE      : {df['ha_attore'].sum()}")
    print(f"Con almeno un MECCANISMO  : {df['ha_meccanismo'].sum()}")
    print(f"EVENTI (entrambi)         : {n}  ({n/len(df):.1%} del corpus)")

    ev = df[df["evento_petrolio"]]

    print("\nAttori piu' frequenti negli eventi:")
    ca = pd.Series([x for l in ev["attori_trovati"] for x in l]).value_counts()
    print(ca.head(12).to_string())

    print("\nMeccanismi piu' frequenti negli eventi:")
    cm = pd.Series([x for l in ev["meccanismi_trovati"] for x in l]).value_counts()
    print(cm.head(12).to_string())

    solo_deboli = ev["meccanismi_trovati"].apply(
        lambda l: len(l) > 0 and all(x in MECCANISMI_DEBOLI for x in l))
    print(f"\nEventi retti SOLO da meccanismi deboli: {solo_deboli.sum()} "
          f"({solo_deboli.mean():.1%} degli eventi)")

    df["solo_meccanismi_deboli"] = False
    df.loc[ev.index[solo_deboli], "solo_meccanismi_deboli"] = True

    print("\nEventi per mese:")
    print(ev.groupby(ev[COL_TIMESTAMP].dt.to_period("M")).size().to_string())

    return df


# ==============================================================================
# FASE 3 — CAMPIONE DA LEGGERE A MANO
# ==============================================================================

def campiona(df, outdir):
    """Estrae i post catturati ('dentro') e quelli con un solo criterio
    soddisfatto ('confine'), per stimare precisione e richiamo."""
    titolo("FASE 3 — CAMPIONE DA LEGGERE A MANO")
    rng = np.random.default_rng(SEME)

    dentro = df[df["evento_petrolio"]]
    confine = df[df["ha_attore"] ^ df["ha_meccanismo"]]

    def pesca(sub, n, etichetta):
        if len(sub) == 0:
            return pd.DataFrame()
        idx = rng.choice(sub.index, size=min(n, len(sub)), replace=False)
        out = sub.loc[idx, [COL_ID, COL_TIMESTAMP, COL_TESTO,
                            "attori_trovati", "meccanismi_trovati"]].copy()
        out.insert(0, "gruppo", etichetta)
        out["giudizio"] = ""      # da compilare: ok / falso / dubbio
        return out

    campione = pd.concat([
        pesca(dentro, N_CAMPIONE_DENTRO, "dentro"),
        pesca(confine, N_CAMPIONE_CONFINE, "confine"),
    ])
    campione.to_csv(outdir / "da_leggere.csv", index=False)

    print(f"Catturati dalla regola : {len(dentro)}  "
          f"(campionati {min(N_CAMPIONE_DENTRO, len(dentro))})")
    print(f"Al confine             : {len(confine)}  "
          f"(campionati {min(N_CAMPIONE_CONFINE, len(confine))})")
    print("\nSalvato 'da_leggere.csv' con la colonna 'giudizio' da compilare.")


# ==============================================================================
# FASE 4 — EPISODI
# ==============================================================================

def costruisci_episodi(eventi, outdir):
    """Collassa i post ravvicinati in un episodio, datato al primo post."""
    titolo("FASE 4 — EPISODI (burst collassati)")

    ev = eventi.sort_values(COL_TIMESTAMP).copy()
    gap_min = ev[COL_TIMESTAMP].diff().dt.total_seconds().div(60)
    ev["nuovo_episodio"] = (gap_min.isna()) | (gap_min > SOGLIA_BURST_MINUTI)
    ev["episodio_id"] = ev["nuovo_episodio"].cumsum()

    ep = ev.groupby("episodio_id").agg(
        inizio=(COL_TIMESTAMP, "min"),
        fine=(COL_TIMESTAMP, "max"),
        n_post=(COL_ID, "size"),
        n_parole_tot=("n_parole", "sum"),
        primo_post=(COL_ID, "first"),
        testo_unito=(COL_TESTO, lambda s: " || ".join(s)),
    ).reset_index()
    ep["durata_min"] = (ep["fine"] - ep["inizio"]).dt.total_seconds() / 60

    print(f"Eventi (post singoli) : {len(ev)}")
    print(f"Episodi (soglia {SOGLIA_BURST_MINUTI} min): {len(ep)}")
    print(f"Riduzione             : {1 - len(ep)/len(ev):.1%}")
    print(f"\nPost per episodio: mediana {ep['n_post'].median():.0f}, "
          f"max {ep['n_post'].max()}")
    print("Distribuzione:")
    print(ep["n_post"].value_counts().sort_index().head(8).to_string())

    ep.to_csv(outdir / "episodi.csv", index=False)
    return ev, ep


# ==============================================================================
# FASE 5 — INTERVALLI
# ==============================================================================

def intervalli(ep):
    """Finestra evento massima compatibile con la distanza fra episodi."""
    titolo("FASE 5 — INTERVALLI FRA EPISODI")

    if len(ep) < 2:
        print("Troppi pochi episodi.")
        return

    ts = ep["inizio"].sort_values()
    d = ts.diff().dt.total_seconds().div(60).dropna()
    giorni = max((ts.max() - ts.min()).days, 1)

    print(f"Episodi: {len(ts)} su {giorni} giorni "
          f"({len(ts)/giorni*30.44:.1f} al mese)")

    print("\nPercentili dell'intervallo fra episodi (minuti):")
    for p in [1, 5, 10, 25, 50, 75]:
        v = np.percentile(d, p)
        extra = f"  ({v/60:.1f} ore)" if v >= 120 else ""
        print(f"  p{p:<3}: {v:>10.1f} min{extra}")

    print("\nQuota di episodi preceduti da un altro entro la finestra:")
    ok = []
    for w in FINESTRE_MINUTI:
        q = (d < w).mean()
        stato = "ok" if q < QUOTA_SOVRAPPOSIZIONE_ACCETTABILE else "contaminata"
        print(f"  {w:>4} min : {q:>6.1%}   {stato}")
        if q < QUOTA_SOVRAPPOSIZIONE_ACCETTABILE:
            ok.append(w)

    if ok:
        print(f"\nFinestra evento massima dal lato testuale: {max(ok)} minuti.")
    else:
        print("\nSovrapposizione oltre soglia gia' a 1 minuto: alza "
              "SOGLIA_BURST_MINUTI.")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    # format esplicito: i timestamp che cadono su un secondo esatto sono scritti
    # senza parte frazionaria, e pandas 3 inferisce il formato dalla prima riga
    df[COL_TIMESTAMP] = pd.to_datetime(df[COL_TIMESTAMP], utc=True,
                                       format="ISO8601", errors="coerce")
    df = df.dropna(subset=[COL_TIMESTAMP]).sort_values(COL_TIMESTAMP)
    print(f"Caricati {len(df)} post da {INPUT_CSV}")
    print(f"Periodo (UTC): {df[COL_TIMESTAMP].min()} -> {df[COL_TIMESTAMP].max()}")

    df = pulisci(df)
    df = applica_regola(df)
    campiona(df, OUTPUT_DIR)

    eventi = df[df["evento_petrolio"]].copy()
    if len(eventi) < 2:
        print("\nTroppi pochi eventi: allarga le liste e rilancia.")
        return

    ev, ep = costruisci_episodi(eventi, OUTPUT_DIR)
    intervalli(ep)

    df.to_csv(OUTPUT_DIR / "corpus_pulito.csv", index=False)
    ev.to_csv(OUTPUT_DIR / "eventi_petrolio.csv", index=False)

    titolo("FATTO")
    print("corpus_pulito.csv    corpus con le colonne della regola")
    print(f"eventi_petrolio.csv  {len(ev)} post catturati, con episodio_id")
    print(f"episodi.csv          {len(ep)} episodi, unita' di analisi")
    print("da_leggere.csv       campione da annotare a mano")


if __name__ == "__main__":
    main()
