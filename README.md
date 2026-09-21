# Post di Trump e prezzo del greggio

**[Stato del progetto (PDF)](report/stato_progetto.pdf)** — cosa è stato fatto,
i risultati verificati, i limiti e le decisioni ancora aperte. Sorgente in
[`report/stato_progetto.tex`](report/stato_progetto.tex).

## Gli script

Cinque fasi, ciascuna legge l'output della precedente.

| | | |
|---|---|---|
| `00_scraper_ucsb.py` | corpus | scarica i post e ne deriva il timestamp dall'identificatore |
| `01_regola_petrolio.py` | selezione | pulizia, regola attore × meccanismo, episodi, finestre |
| `02_audit_bertopic.py` | audit | verifica la regola con topic modeling e ricerca semantica |
| `03_scarica_prezzi.py` | prezzi | serie al minuto da Dukascopy — fase ferma, vedi report |
| `04_features.py` | misura | feature per episodio: orario, enfasi, novità, direzione |

Gli output finiscono in `dati/`. Le pagine HTML scaricate sono messe in cache in
`cache_ucsb/`, così una riesecuzione non ripassa dal server.

## Ambiente e dipendenze

Python 3.14 in un virtualenv (`env_tigramite`), su macOS. Le versioni contano:
il codice usa **pandas 3**, dove `astype(str)` non converte più i valori
mancanti e l'inferenza del formato dei timestamp è più rigida che in pandas 2.

```bash
python3.14 -m venv env_tigramite
source env_tigramite/bin/activate
pip install pandas numpy pyarrow requests beautifulsoup4 lxml \
            bertopic sentence-transformers scikit-learn umap-learn hdbscan scipy
```

Versioni di riferimento: pandas 3.0.5, numpy 2.5.1, pyarrow 25.0.1,
bertopic 0.17.4, sentence-transformers 6.0.1, scikit-learn 1.9.0, scipy 1.18.0.

Due dipendenze esterne a Python:

- **Node.js** per `03`, che chiama `npx dukascopy-node` per scaricare i prezzi.
- **[Ollama](https://ollama.com)** per la fase D di `04`, che assegna le
  variabili di giudizio con un modello locale (`qwen2.5:14b`, temperatura 0).
  Serve solo per quella fase, che non è ancora stata eseguita.

Per la parte di causal discovery il progetto usa
[Tigramite](https://github.com/jakobrunge/tigramite), non incluso qui.
