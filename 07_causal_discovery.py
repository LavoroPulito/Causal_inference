#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07 — Causal discovery: PCMCI+ on the time series, CD-NOD on the episodes.

    PCMCI+  (Tigramite)     regular 5-minute grid: post signal, WTI, gold and
                            EUR/USD returns. Finds lagged and same-bin links.
                            In the same bin a price cannot cause a post: the
                            link can only go from the post to the price.
    CD-NOD  (causal-learn)  one row per episode: annotated variables and the
                            15-minute abnormal returns of WTI and gold, plus
                            time as context variable. An edge from time to a
                            variable means its mechanism changes over the
                            period.

Until the real series is chosen it runs on the synthetic one (03b), whose true
structure is in data/prices/synthetic/truth.json.

    python 07_causal_discovery.py
    python 07_causal_discovery.py --only pcmci
    python 07_causal_discovery.py --prices-dir data/prices --prefix ""

Input:  data/features/episode_table_*.parquet (the latest)
        <prices-dir>/<prefix>{wti,gold,eurusd}.parquet
Output: data/causal_discovery/
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


# ==============================================================================
# CONFIGURATION
# ==============================================================================

TABLE_GLOB = "data/features/episode_table_*.parquet"
OUTPUT_DIR = Path("data/causal_discovery")
SERIES = ["wti", "gold", "eurusd"]

# --- PCMCI+ -------------------------------------------------------------------
BIN = "5min"
TAU_MAX = 4                  # lags, in bins: 20 minutes
PC_ALPHA = 0.01
MISSING = 999.0              # Tigramite flag for missing values

# --- CD-NOD -------------------------------------------------------------------
HORIZON = 15
EPISODE_VARIABLES = ["direction", "intensity", "specificity", "novelty"]
CDNOD_ALPHA = 0.01
# KCI also sees non-linear dependence but, with about 200 episodes, misses even
# the linear one between the WTI and gold returns: Fisher-z is the default
CDNOD_TEST = "fisherz"


def heading(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def event_study_module():
    """06 has a name that cannot be imported directly."""
    spec = importlib.util.spec_from_file_location("event_study", "06_event_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ==============================================================================
# PCMCI+
# ==============================================================================

def grid(table, prices):
    """One row per 5-minute bin. Returns are log returns in percent between
    the last prices of consecutive bins; a bin without prices is missing. The
    post signal is the sum of the directions of the episodes starting in it."""
    cols = {}
    for name, df in prices.items():
        close = df.set_index("t")["close"].resample(BIN).last()
        cols[name] = 100 * np.log(close).diff()
    g = pd.DataFrame(cols)
    bins = table["start"].dt.floor(BIN)
    g.insert(0, "post", table.groupby(bins)["direction"].sum().reindex(g.index, fill_value=0))
    return g


def link_assumptions(names):
    """All links allowed, except a price causing the post in the same bin.
    "-?>" means: the link may exist, and only in this direction. Same-bin links
    must be stated on both sides."""
    links = {j: {} for j in range(len(names))}
    for j in range(len(names)):
        for i in range(len(names)):
            for tau in range(TAU_MAX + 1):
                if tau == 0 and i == j:
                    continue
                if tau > 0:
                    links[j][(i, -tau)] = "-?>"
                elif names[i] == "post":
                    links[j][(i, 0)] = "-?>"
                elif names[j] == "post":
                    links[j][(i, 0)] = "<?-"
                else:
                    links[j][(i, 0)] = "o?o"
    return links


def run_pcmci(table, prices, outdir):
    heading("PCMCI+ — 5-minute grid")
    from tigramite import data_processing as pp
    from tigramite.pcmci import PCMCI
    from tigramite.independence_tests.parcorr import ParCorr

    g = grid(table, prices)
    print(f"Bins: {len(g):,}, with prices {g['wti'].notna().mean():.1%}, "
          f"with a post {(g['post'] != 0).sum()}")

    data = pp.DataFrame(g.fillna(MISSING).to_numpy(), var_names=list(g.columns),
                        missing_flag=MISSING)
    pcmci = PCMCI(dataframe=data, cond_ind_test=ParCorr(significance="analytic"),
                  verbosity=0)
    names = list(g.columns)
    res = pcmci.run_pcmciplus(tau_min=0, tau_max=TAU_MAX, pc_alpha=PC_ALPHA,
                              link_assumptions=link_assumptions(names))

    rows = []
    for i in range(len(names)):
        for j in range(len(names)):
            for tau in range(TAU_MAX + 1):
                link = res["graph"][i, j, tau]
                if link == "" or (tau == 0 and i > j):
                    continue
                rows.append({"cause": names[i], "lag_min": tau * 5, "link": link,
                             "effect": names[j], "val": res["val_matrix"][i, j, tau],
                             "p": res["p_matrix"][i, j, tau]})
    links = pd.DataFrame(rows).sort_values(["effect", "cause", "lag_min"])
    print("\nLinks found (lag in minutes; --> directed, o-o not oriented):")
    print(links.round(4).to_string(index=False))
    links.to_csv(outdir / "pcmci_links.csv", index=False)


# ==============================================================================
# CD-NOD
# ==============================================================================

def run_cdnod(table, price_files, outdir, test):
    heading(f"CD-NOD — episodes, abnormal returns at {HORIZON} min")
    from causallearn.search.ConstraintBased.CDNOD import cdnod
    from causallearn.graph.GraphNode import GraphNode
    from causallearn.utils.PCUtils.BackgroundKnowledge import BackgroundKnowledge

    es = event_study_module()
    data = table.copy()
    for name in ["wti", "gold"]:
        car = es.abnormal_returns(table, es.read_prices(price_files[name]))
        car = car[(car["horizon"] == HORIZON) & (car["status"] == "ok")]
        data = data.merge(car[["first_post", "car"]].rename(columns={"car": f"car_{name}"}),
                          on="first_post")
    names = EPISODE_VARIABLES + ["car_wti", "car_gold"]
    data = data.dropna(subset=names)

    # time as context: days since the first episode
    days = (data["start"] - data["start"].min()).dt.total_seconds().to_numpy() / 86400
    print(f"Episodes with both returns: {len(data)}")

    # time order: a return measured after the post cannot cause its content
    bk = BackgroundKnowledge()
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if a.startswith("car_") and b in EPISODE_VARIABLES:
                bk.add_forbidden_by_node(GraphNode(f"X{i + 1}"), GraphNode(f"X{j + 1}"))

    cg = cdnod(data[names].to_numpy(float), days.reshape(-1, 1), alpha=CDNOD_ALPHA,
               indep_test=test, background_knowledge=bk, show_progress=False)

    labels = {f"X{k + 1}": n for k, n in enumerate(names + ["time"])}
    edges = []
    for e in cg.G.get_graph_edges():
        text = str(e)
        for k in sorted(labels, key=len, reverse=True):
            text = text.replace(k, labels[k])
        edges.append(text)
    print(f"\nEdges, {test} test (--> directed, --- not oriented):")
    for e in sorted(edges):
        print(f"  {e}")
    (outdir / f"cdnod_edges_{test}.txt").write_text("\n".join(sorted(edges)) + "\n")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices-dir", default="data/prices/synthetic")
    ap.add_argument("--prefix", default="synthetic_")
    ap.add_argument("--only", choices=["pcmci", "cdnod"])
    ap.add_argument("--cdnod-test", default=CDNOD_TEST, choices=["fisherz", "kci"])
    args = ap.parse_args()

    table_path = sorted(Path().glob(TABLE_GLOB))[-1]
    table = pd.read_parquet(table_path)
    files = {s: Path(args.prices_dir) / f"{args.prefix}{s}.parquet" for s in SERIES}
    print(f"Episode table: {table_path} ({len(table)} episodes)")
    print(f"Prices: {args.prices_dir}/{args.prefix}*.parquet")

    outdir = OUTPUT_DIR / Path(args.prices_dir).name
    outdir.mkdir(parents=True, exist_ok=True)

    if args.only != "cdnod":
        prices = {s: pd.read_parquet(f) for s, f in files.items()}
        run_pcmci(table, prices, outdir)
    if args.only != "pcmci":
        run_cdnod(table, files, outdir, args.cdnod_test)
    print(f"\nSaved to {outdir}/")


if __name__ == "__main__":
    main()
