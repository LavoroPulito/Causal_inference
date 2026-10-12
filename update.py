#!/usr/bin/env python3
"""
Update — brings the dataset up to date with the latest posts.

    1  00b   new posts from the CNN archive
    2  01    cleaning, rule, episodes (the review sample is left untouched)
    3  04    deterministic features and novelty
    4        new episodes added to data/features/manual_annotations.csv

Annotated episodes are matched through `first_post`, the ID of their first post,
not through `episode_id`, which is a running number and shifts whenever a post
is inserted before the end of the corpus. If an annotated episode gains or
loses posts, its text is updated, the judgements are kept and `text_changed`
is set to True until it is reviewed.

    python update.py
    python update.py --no-download     rule and features only, after editing 01
"""

import sys
import argparse
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "data/truth_posts.csv"
EVENTS = ROOT / "data/oil/oil_events.csv"
FEATURES = ROOT / "data/features/episode_features.parquet"
ANNOTATIONS = ROOT / "data/features/manual_annotations.csv"

JUDGEMENTS = ["direction", "intensity", "specificity"]
FROM_EPISODES = ["episode_id", "first_post", "start", "n_post", "joined_text", "novelty"]


def run(script, *args):
    print(f"\n>>> {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, script, *args], cwd=ROOT, check=True)


def merge_annotations():
    ann = pd.read_csv(ANNOTATIONS, dtype={"notes": str})
    ann["notes"] = ann["notes"].fillna("")
    for c in JUDGEMENTS:
        ann[c] = ann[c].astype("Int64")
    ann["text_changed"] = ann["text_changed"].fillna(False).astype(bool)

    events = pd.read_csv(EVENTS, usecols=["post_id", "episode_id"])
    ep = pd.read_parquet(FEATURES, columns=FROM_EPISODES)
    ep["start"] = ep["start"].astype(str)
    ep = ep.set_index("episode_id", drop=False)

    # the old first post may now sit in the middle of an episode
    ann["_episode"] = ann["first_post"].map(events.set_index("post_id")["episode_id"])
    found = ann["_episode"].notna()
    lost = ann[~found]
    merged = ann[found & ann.duplicated("_episode", keep=False)]

    cur = ep.loc[ann.loc[found, "_episode"]]
    cur.index = ann.index[found]
    changed = found & (ann["joined_text"] != cur["joined_text"].reindex(ann.index))
    ann.loc[changed | ann.index.isin(merged.index), "text_changed"] = True
    # a recomputed novelty differs in the last digits: keep the stored value
    same = (ann["novelty"] - cur["novelty"].reindex(ann.index)).abs() < 1e-6
    cur.loc[same[same].index, "novelty"] = ann.loc[same[same].index, "novelty"]
    for c in FROM_EPISODES:
        ann.loc[found, c] = cur[c]
    ann.loc[~found, "episode_id"] = pd.NA

    new = ep[~ep["episode_id"].isin(ann.loc[found, "_episode"])].copy()
    new["gold"] = False
    for c in JUDGEMENTS:
        new[c] = pd.array([pd.NA] * len(new), dtype="Int64")
    new["notes"] = ""
    new["text_changed"] = False

    columns = ann.columns.drop("_episode")
    out = pd.concat([ann[columns], new[columns].sort_values("start")], ignore_index=True)
    out["episode_id"] = out["episode_id"].astype("Int64")
    out["first_post"] = out["first_post"].astype("int64")
    out.to_csv(ANNOTATIONS, index=False)

    print("\n" + "=" * 78)
    print("MANUAL ANNOTATIONS")
    print(f"episodes in the file       : {len(out)}")
    print(f"new, to annotate           : {len(new)}")
    print(f"text changed, to review    : {int(out['text_changed'].sum())}")
    print(f"without judgements         : {int(out['direction'].isna().sum())}")
    for _, r in new.sort_values("start").iterrows():
        print(f"  + {r['episode_id']:>4}  {r['start'][:16]}  {r['joined_text'][:90]}")
    if len(merged):
        print(f"\n{len(merged)} annotated episodes now fall in the same episode "
              "(text_changed set):")
        print(merged[["first_post", "_episode", "start"]].to_string(index=False))
    if len(lost):
        print(f"\n{len(lost)} annotated episodes no longer pass the rule "
              "(kept, episode_id empty):")
        print(lost[["first_post", "start"]].to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true",
                    help="skip the CNN archive, rerun only rule and features")
    args = ap.parse_args()

    n_before = len(pd.read_csv(CORPUS, usecols=["post_id"]))
    if not args.no_download:
        run("00b_update_cnn.py")
    run("01_oil_rule.py", "--no-sample")
    run("04_features.py", "--novelty")
    merge_annotations()

    n_after = len(pd.read_csv(CORPUS, usecols=["post_id"]))
    print(f"\ncorpus: {n_before} -> {n_after} posts")


if __name__ == "__main__":
    main()
