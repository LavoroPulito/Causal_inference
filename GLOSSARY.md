# Glossary

The repository was written in Italian and translated to English in October 2026.
This table maps the old names to the new ones, for reading commits made before
the translation.

## Folders

| Italian | English |
|---|---|
| `dati/` | `data/` |
| `dati/petrolio/` | `data/oil/` |
| `dati/prezzi/grezzi/` | `data/prices/raw/` |
| `annotazioni/` | `annotations/` |

## Files

| Italian | English |
|---|---|
| `00_scraper_ucsb.py` | `00_scrape_ucsb.py` |
| `00b_aggiorna_cnn.py` | `00b_update_cnn.py` |
| `01_regola_petrolio.py` | `01_oil_rule.py` |
| `02_audit_bertopic.py` | `02_bertopic_audit.py` |
| `03_scarica_prezzi.py` | `03_download_prices.py` |
| `query/_comune.py` | `query/_common.py` |
| `query/precisione.py` | `query/precision.py` |
| `query/orari_serie.py` | `query/series_hours.py` |
| `query/copertura_post.py` | `query/post_coverage.py` |
| `annotazioni/salva_versione.py` | `annotations/save_version.py` |
| `annotazioni/riempi_giudizi.py` | `annotations/fill_labels.py` |
| `annotazioni/criteri_gold.md` | `annotations/gold_guidelines.md` |
| `report/stato_progetto.typ` | `report/project_status.typ` |
| `report/numeri.py`, `numeri.json` | `report/numbers.py`, `numbers.json` |
| `anomalie.csv` | `anomalies.csv` |
| `giorni_falliti.txt` | `failed_days.txt` |
| `corpus_pulito.csv` | `clean_corpus.csv` |
| `eventi_petrolio.csv` | `oil_events.csv` |
| `episodi.csv` | `episodes.csv` |
| `da_leggere.csv` | `to_review.csv` |
| `cluster_sospetti.csv` | `suspicious_clusters.csv` |
| `copertura_per_cluster.csv` | `coverage_by_cluster.csv` |
| `corpus_con_audit.csv` | `corpus_with_audit.csv` |
| `falsi_negativi_candidati.csv` | `candidate_false_negatives.csv` |
| `episodi_features.parquet` | `episode_features.parquet` |
| `emb_episodi.npy` | `episode_embeddings.npy` |
| `gold_da_annotare.csv` | `gold_to_annotate.csv` |
| `gold_doppia_annotazione.csv` | `gold_double_annotation.csv` |
| `gold_annotato.csv` | `gold_annotated.csv` |
| `llm_annotazioni.jsonl` | `llm_annotations.jsonl` |

## Columns

| Italian | English |
|---|---|
| `testo` | `text` |
| `data_pagina`, `ora_pagina_pacific` | `page_date`, `page_time_pacific` |
| `data_da_id_pacific`, `ora_da_id_pacific` | `id_date_pacific`, `id_time_pacific` |
| `sequenza` | `sequence` |
| `scarto_minuti` | `offset_minutes` |
| `verificato` | `verified` |
| `fonte` | `source` |
| `n_parole`, `n_parole_tot` | `n_words`, `n_words_total` |
| `attori_trovati`, `meccanismi_trovati` | `actors_found`, `mechanisms_found` |
| `ha_attore`, `ha_meccanismo` | `has_actor`, `has_mechanism` |
| `evento_petrolio` | `oil_event` |
| `solo_meccanismi_deboli` | `weak_mechanisms_only` |
| `nuovo_episodio`, `episodio_id` | `new_episode`, `episode_id` |
| `inizio`, `fine` | `start`, `end` |
| `primo_post`, `testo_unito`, `durata_min` | `first_post`, `joined_text`, `duration_min` |
| `gruppo`, `giudizio` | `group`, `label` |
| `catturati`, `copertura`, `termini` | `captured`, `coverage`, `terms` |
| `similarita`, `similarita_max` | `similarity`, `max_similarity` |
| `sonda`, `sonda_piu_vicina` | `probe`, `nearest_probe` |
| `ora_utc`, `ora_ny`, `giorno_settimana` | `hour_utc`, `hour_ny`, `weekday` |
| `mercato_usa_aperto` | `us_market_open` |
| `n_caratteri`, `n_esclamativi` | `n_chars`, `n_exclamations` |
| `n_maiuscole`, `quota_maiuscole`, `n_parole_urlate` | `n_uppercase`, `uppercase_share`, `n_shouted_words` |
| `novita`, `episodio_piu_simile` | `novelty`, `most_similar_episode` |
| `direzione`, `intensita`, `concretezza`, `confidenza` | `direction`, `intensity`, `specificity`, `confidence` |
| `note` | `notes` |

## Values

| column | Italian | English |
|---|---|---|
| `group` | `dentro` | `inside` |
| `group` | `confine` | `boundary` |

## Rule

| Italian | English |
|---|---|
| `ATTORI` | `ACTORS` |
| `MECCANISMI` | `MECHANISMS` |
| `MECCANISMI_DEBOLI` | `WEAK_MECHANISMS` |
| evento, episodio | event, episode |
| precisione, richiamo | precision, recall |
| novità | novelty |
