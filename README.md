# Trump's posts and the price of crude oil

**[Project status (PDF)](report/project_status.pdf)** — what has been done,
the verified results, the limits and the decisions still open. Source in
[`report/project_status.typ`](report/project_status.typ).

## Scripts

Each step reads the output of the previous one.

| | | |
|---|---|---|
| `00_scrape_ucsb.py` | corpus | downloads the posts and derives the timestamp from the identifier |
| `00b_update_cnn.py` | integration | same as 00, but takes the posts from the CNN archive; the only source after July 2026 |
| `01_oil_rule.py` | selection | cleaning, actor × mechanism rule, episodes, windows |
| `02_bertopic_audit.py` | audit | tests the rule with topic modeling and semantic search |
| `03_download_prices.py` | prices | one-minute quotes from Dukascopy: test on March 2025, full download refused by the server |
| `03c_download_databento.py` | prices | one-minute futures from Databento: WTI, Brent, gold, S&P 500, EUR/USD (licensed, not versioned) |
| `03b_synthetic_prices.py` | test prices | synthetic WTI, gold and EUR/USD with a known effect of the episodes, to test 06 and 07 |
| `04_features.py` | measurement | features per episode: time, emphasis, novelty, direction |
| `05_episode_table.py` | table | one row per episode: features and manual judgements, dated |
| `06_event_study.py` | event study | abnormal returns after each episode; synthetic series and power test until the price series is chosen |
| `07_causal_discovery.py` | causal discovery | PCMCI+ on a 5-minute grid, CD-NOD on the episodes |
| `update.py` | update | runs 00b, 01, 04 and adds the new episodes to the manual annotation file |

To bring the dataset up to date with the latest posts:

```bash
python update.py
```

New episodes are appended to `data/features/manual_annotations.csv` with empty
judgements. Annotations are matched to episodes through `first_post`, so they
survive any renumbering; an annotated episode whose text changed is marked in
`text_changed`.\
The posts were manually annotated following the guidelines in [`gold_guidelines.md`](annotations/gold_guidelines.md)

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
            bertopic sentence-transformers scikit-learn umap-learn hdbscan scipy \
            tigramite causal-learn
```

Reference versions: pandas 3.0.5, numpy 2.5.1, pyarrow 25.0.1,
bertopic 0.17.4, sentence-transformers 6.0.1, scikit-learn 1.9.0, scipy 1.18.0.

Two dependencies outside Python:

- **Node.js** for `03`, which calls `npx dukascopy-node` to download prices.
- **[Ollama](https://ollama.com)** for step D of `04`, which assigns the
  judgement variables with a local language model. The step was tested on Kaggle
  (`notebooks/llm_scoring_kaggle.ipynb`) and is on hold, because agreement with the
  manual annotation was not sufficient: the variables are annotated by hand in
  `data/features/manual_annotations.csv`. See the report for the results.

For the causal discovery part (`07`) the project uses
[Tigramite](https://github.com/jakobrunge/tigramite) for PCMCI+ and
[causal-learn](https://github.com/py-why/causal-learn) for CD-NOD.
