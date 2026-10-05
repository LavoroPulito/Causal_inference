# Trump's posts and the price of crude oil

**[Project status (PDF)](report/project_status.pdf)** — what has been done,
the verified results, the limits and the decisions still open. Source in
[`report/project_status.typ`](report/project_status.typ).

## Scripts

Each step reads the output of the previous one.

| | | |
|---|---|---|
| `00_scrape_ucsb.py` | corpus | downloads the posts and derives the timestamp from the identifier |
| `00b_update_cnn.py` | integration | same as 00, but takes the posts from the CNN archive |
| `01_oil_rule.py` | selection | cleaning, actor × mechanism rule, episodes, windows |
| `02_bertopic_audit.py` | audit | tests the rule with topic modeling and semantic search |
| `03_download_prices.py` | prices | one-minute series from Dukascopy — on hold, see the report |
| `04_features.py` | measurement | features per episode: time, emphasis, novelty, direction |

Outputs go to `data/`. Downloaded HTML pages are cached in `cache_ucsb/`, so a
rerun does not hit the server again. `annotations/` keeps every version of the
rule with its annotated sample; `query/` holds read-only scripts.

The repository was originally written in Italian: `GLOSSARY.md` maps the old
names to the new ones.

## Environment and dependencies

Python 3.14 in a virtualenv (`env_tigramite`), on macOS. Versions matter: the
code uses **pandas 3**, where `astype(str)` no longer converts missing values
and timestamp format inference is stricter than in pandas 2.

```bash
python3.14 -m venv env_tigramite
source env_tigramite/bin/activate
pip install pandas numpy pyarrow requests beautifulsoup4 lxml \
            bertopic sentence-transformers scikit-learn umap-learn hdbscan scipy
```

Reference versions: pandas 3.0.5, numpy 2.5.1, pyarrow 25.0.1,
bertopic 0.17.4, sentence-transformers 6.0.1, scikit-learn 1.9.0, scipy 1.18.0.

Two dependencies outside Python:

- **Node.js** for `03`, which calls `npx dukascopy-node` to download prices.
- **[Ollama](https://ollama.com)** for step D of `04`, which assigns the
  judgement variables with a local model (`qwen2.5:14b`, temperature 0).
  Needed only for that step, which has not been run yet.

For the causal discovery part the project uses
[Tigramite](https://github.com/jakobrunge/tigramite), not included here.
