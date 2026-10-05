// Stato del progetto.
//
// Aggiornamento:
//   python report/typst/numeri.py          (ricalcola le cifre in numeri.json)
//   typst compile report/typst/stato_progetto.typ
//
// Le cifre marcate #n.… vengono da numeri.json e si aggiornano da sole.
// Il testo va rivisto a mano; ogni cambiamento di metodo va nel Registro in fondo.

#let n = json("numeri.json")

#set document(title: "Post di Trump e prezzo del greggio — Stato del progetto")
#set page(paper: "a4", margin: 2.8cm, numbering: "1")
#set text(font: "New Computer Modern", size: 11pt, lang: "it")
#set par(justify: true, leading: 0.65em, spacing: 0.65em, first-line-indent: 1.5em)
#show raw: set text(font: "DejaVu Sans Mono", size: 1.1em)

#set heading(numbering: "1.1")
#show heading: set block(above: 1.6em, below: 1em)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 12pt)
#let sub(title) = heading(level: 2, numbering: none, title)

#set enum(spacing: 5pt, indent: 1em)
#set terms(separator: linebreak(), hanging-indent: 1.6cm, indent: 0pt, tight: false, spacing: 5pt)

#let toprule = table.hline(stroke: 0.8pt)
#let midrule = table.hline(stroke: 0.4pt)
#let bottomrule = table.hline(stroke: 0.8pt)
#show table: set par(first-line-indent: 0pt, justify: false)
#let tabella(..args) = align(center, table(stroke: none, inset: (x: 6pt, y: 4pt), ..args))

// Formattazione dei numeri all'italiana
#let migl(x) = {
  let s = str(x)
  let out = ""
  for (i, c) in s.clusters().enumerate() {
    if i > 0 and calc.rem(s.len() - i, 3) == 0 { out += "\u{202f}" }
    out += c
  }
  out
}
#let pct(x, cifre: 1) = str(calc.round(x * 100, digits: cifre)).replace(".", ",") + "%"
#let dec(x) = str(x).replace(".", ",")

// --- Titolo ---
#align(center)[
  #text(size: 17pt)[Post di Trump e prezzo del greggio] \
  #v(2pt)
  #text(size: 14pt)[Stato del progetto]
  #v(1em)
  #text(size: 12pt)[aggiornato al #n.data]
]
#v(1em)

= La catena di elaborazione

La domanda è se i post di Trump che segnalano un rischio all'offerta di greggio muovano il prezzo del petrolio, e per quanto tempo. Servono tre cose: sapere _quando_ ogni post è stato pubblicato, con precisione sufficiente a isolarne l'effetto; stabilire _quali_ post contano come eventi, con un criterio replicabile; avere una serie di prezzo abbastanza fitta da misurare la reazione nei minuti successivi.

Il lavoro è diviso in script numerati, ciascuno legge l'output del precedente.

/ `00`  corpus: Scarica i post dall'archivio dell'American Presidency Project (UCSB). L'orario di pubblicazione non viene letto dalla pagina ma ricavato dall'identificatore del post, che lo contiene per costruzione. L'ora stampata in pagina serve solo da controllo.

/ `00b`  integrazione: Aggiunge i post che UCSB non ha, presi dall'archivio pubblico di CNN. Anche qui l'orario viene dall'identificatore, estratto dal link del post: le due fonti sono trattate allo stesso modo.

/ `01`  selezione: Scarta ciò che non ha contenuto testuale, applica la regola che definisce l'evento petrolifero, raggruppa i post ravvicinati in episodi e misura quanto possono essere lunghe le finestre di osservazione. L'episodio è l'unità di analisi.

/ `02`  audit: Verifica la regola con due metodi non supervisionati, che non conoscono le liste di termini. Serve a misurare quanto la regola perde, non a definire nulla.

/ `03`  prezzi: Scarica la serie di prezzo al minuto. È ferma, in attesa di decidere quali serie usare.

/ `04`  feature: Misura ciascun episodio: orario, lunghezza, enfasi, novità rispetto agli episodi recenti, e le variabili che richiedono lettura (direzione attesa sull'offerta, intensità, concretezza).

Due cartelle di supporto: `annotazioni/` conserva ogni versione della regola insieme al campione annotato con cui è stata valutata; `query/` contiene script di sola lettura per interrogare i dati.

Le feature vanno congelate prima di guardare i prezzi: tararle sui rendimenti significherebbe costruire il risultato invece di misurarlo.

= Dove siamo

#tabella(
  columns: 3,
  align: (left, left, right),
  toprule,
  [Fase], [Stato], [Output],
  midrule,
  [00–00b corpus], [eseguito], [#migl(n.post) post fino al #n.periodo_fine],
  [01 selezione], [eseguito, regola #n.versioni.last().versione], [#migl(n.eventi) eventi, #migl(n.episodi) episodi],
  [02 audit], [da rilanciare], [eseguito sul corpus precedente a CNN],
  [03 prezzi], [fermo], [test su marzo 2025],
  [04 feature], [fasi A, B, C], [#n.feature_colonne colonne, gold standard di #n.gold episodi],
  bottomrule,
)

= Il corpus

#sub[Fonti]

#tabella(
  columns: 2,
  align: (left, right),
  toprule,
  [Fonte], [Post],
  midrule,
  [American Presidency Project (UCSB)], [#migl(n.post_ucsb)],
  [Archivio CNN, solo post assenti in UCSB], [#migl(n.post_cnn)],
  midrule,
  [Totale, dal 1/12/2024 al #n.periodo_fine], [#migl(n.post)],
  bottomrule,
)

UCSB è un archivio curato e non completo. Nel periodo dicembre 2024 – luglio 2026 l'archivio CNN contiene 2#sym.space.nobreak\811 post che UCSB non ha; UCSB copriva quindi circa il 75% della produzione reale. A questi si aggiungono i post successivi al 31 luglio 2026. Truth Social blocca l'accesso automatico all'API (risposta 403), quindi non è usato come fonte diretta.


#sub[Il timestamp]

Truth Social usa identificatori snowflake, in cui i bit alti sono i millisecondi dall'epoch Unix:
$ t_"UTC" = ("post_id" >> 16) / 1000,
  quad
  "seq" = "post_id" thin \& thin "0xFFFF". $
Il campo di sequenza ordina i post pubblicati nello stesso millisecondo. Per entrambe le fonti l'identificatore viene estratto dal link del post.

Controlli: l'annuncio dell'attacco a Fordow risulta alle 19:50 EDT del 21 giugno 2025, l'ora pubblica nota; la data dichiarata da CNN coincide con quella ricavata dall'ID per tutti i post, entro un secondo; per UCSB l'ora in pagina coincide nel #pct(n.verificati_ucsb) dei casi.

#sub[Anomalie di UCSB]

L'archivio stampa l'ora in due formati: a 24 ore (`18:11`) e a 12 ore con meridiano (`1:17 PM`). La prima versione del parser ignorava il meridiano, e il suffisso finiva in testa al testo del post. Corretto. Le anomalie residue non toccano i timestamp, che vengono dall'ID:

#tabella(
  columns: 3,
  align: (left, right, left),
  toprule,
  [Scarto], [Righe], [Causa],
  midrule,
  [180 min], [105], [UCSB stampa in Eastern time dal 15 al 21 settembre 2025],
  [altro], [36], [errori redazionali isolati],
  [assente], [15], [ora non presente in pagina],
  [720 min], [8], [pagina a 24 ore con ora errata (`12:27` per `00:27`)],
  bottomrule,
)

= La pulizia

Dei #migl(n.post) post ne restano #migl(n.corpus_pulito) (#pct(n.corpus_pulito / n.post)).

#tabella(
  columns: 3,
  align: (left, right, left),
  toprule,
  [Criterio], [Rimossi], [Cosa toglie],
  midrule,
  [Senza contenuto], [#migl(n.pulizia.segnaposto)], [video e immagini senza didascalia, segnaposto],
  [Doppi invii entro 2 minuti], [#migl(n.pulizia.doppi)], [testi identici ravvicinati],
  [Boilerplate endorsement], [#migl(n.pulizia.boilerplate)], [il template degli endorsement elettorali],
  [Sotto le 5 parole], [#migl(n.pulizia.corti)], [slogan e frammenti],
  bottomrule,
)

La maggior parte delle rimozioni sono post senza testo: Trump pubblica molti video e immagini senza scrivere nulla. Tolto l'indirizzo del file resta una stringa vuota o la parola `Video`. Escluderli è inevitabile per una regola lessicale, ma è un limite da dichiarare: un video su una raffineria colpita è informazione di mercato, e nessuna regola basata su parole lo vede.

#sub[Problemi aperti]

*Doppi invii.* Il filtro confronta i testi normalizzati (minuscolo, senza punteggiatura). Tutti i post di solo video hanno lo stesso testo normalizzato, `video`, e due video diversi a meno di due minuti di distanza vengono uniti come se fossero un doppio invio. Non cambia il risultato, perché quei post verrebbero comunque scartati, ma rende i conteggi della tabella poco leggibili.

*Ricondivisioni.* Nel corpus ci sono 752 ricondivisioni (`RT`): 460 di post di Trump stesso, 291 di altri account, il resto solo link. Le ricondivisioni dei propri post sono duplicati: stesso testo, identificatore diverso, pubblicate minuti o ore dopo l'originale. Oggi entrano come eventi distinti (vedi la novità, sezione 7). Nel formato CNN, inoltre, il nome dell'account è attaccato al testo (`RT @realDonaldTrumpIran is…`), e la rimozione delle menzioni cancella la prima parola del post.

= La regola

Un post è un evento se contiene almeno un attore dell'offerta e almeno un meccanismo:
$ "evento"_i = bb(1) lr([ |A inter T_i| >= 1 and |M inter T_i| >= 1 ]), $
con $T_i$ i token del post, $A$ la lista degli attori, $M$ quella dei meccanismi.

- *Attori*: Iran e Hormuz, Venezuela, Russia e Ucraina, OPEC e Arabia Saudita, riserva strategica, rotte (Mar Rosso, Houthi, Suez), Nigeria, petrolio esplicito (`oil`, `crude`, `barrel`, `gasoline`, `fuel`).
- *Meccanismi*: interruzione fisica (blocco, mine, petroliere, stretto, porti, oleodotti), azione militare, sanzioni e dazi, negoziato nucleare, cambio di regime, ultimatum, ripresa dei flussi.

Sul corpus pulito: #migl(n.con_attore) post con un attore, #migl(n.con_meccanismo) con un meccanismo, *#migl(n.eventi) eventi*. Di questi, #n.deboli si reggono solo su meccanismi deboli (`military`, `attack`, `strike`, `nuclear`): termini di conflitto che non riguardano direttamente l'offerta.
Ciò nonostante la maggior parte di questi post sono comunque di reale interesse quindi meccanismi deboli rimangono un valido strumento. 
#sub[Criterio di annotazione]

Un post è rilevante (giudizio 1) se riguarda:

+ *il conflitto con l'Iran e lo stretto di Hormuz*: attacchi, danni, cessate il fuoco, negoziati, apertura o chiusura dello stretto. Determinano le aspettative sulla rotta petrolifera più importante.
+ *il nucleare iraniano*: anche le dichiarazioni del tipo "l'Iran non avrà mai l'arma nucleare", lette come segnale di tensione fra Iran e USA.
+ *il Venezuela*: l'azione dell'amministrazione Trump ha interessato i flussi di petrolio venezuelano.
+ *Russia e Ucraina*, quando toccano sanzioni, energia o la fine della guerra.

Non è rilevante (giudizio 0):

+ un attore o un meccanismo citato di passaggio in un post su altro (Bondi, Epstein, il Kennedy Center);
+ sondaggi ed editoriali linkati, polemiche con media e avversari su fatti già noti;
+ fatti militari senza legame con l'offerta (gli attacchi alle barche dei narcotrafficanti, i droni russi sulla Polonia);
+ commenti sui prezzi già avvenuti ("Oil prices are down"): l'informazione va dal prezzo al post, non viceversa;
+ i post sulla Groenlandia, per ora.

#sub[Versioni]

Ogni versione salva in `annotazioni/` la regola e il campione annotato: 100 post catturati (_dentro_) e 50 con un solo criterio soddisfatto (_confine_). La quota di rilevanti nel _dentro_ è la precisione; quella nel _confine_ stima quanti post rilevanti la regola perde. Intervalli di confidenza al 95% (Wilson).

#tabella(
  columns: (auto, 1fr, 1fr, auto, auto),
  align: (left, left, left, right, right),
  toprule,
  [], [Aggiunti], [Tolti], [Precisione], [Rilevanti nel confine],
  midrule,
  ..n.versioni.map(v => (
    v.versione,
    if v.aggiunti.len() > 0 { v.aggiunti.map(raw).join(", ") } else [—],
    if v.tolti.len() > 0 { v.tolti.map(raw).join(", ") } else [—],
    [#pct(v.precisione, cifre: 0) \ #text(size: 8pt)[#pct(v.precisione_ic.at(0), cifre: 0)–#pct(v.precisione_ic.at(1), cifre: 0)]],
    [#pct(v.confine, cifre: 0) \ #text(size: 8pt)[#pct(v.confine_ic.at(0), cifre: 0)–#pct(v.confine_ic.at(1), cifre: 0)]],
  )).flatten(),
  bottomrule,
)

Con la versione corrente il _confine_ conta #migl(n.confine) post. Il richiamo stimato è circa *#pct(n.richiamo, cifre: 0)*: è un limite superiore, perché non conta i post rilevanti privi sia di attori sia di meccanismi. Con 100 e 50 post annotati gli intervalli sono ampi, e le differenze fra versioni vicine non sono significative.

#sub[Struttura della regola]

La regola sbaglia più per eccesso che per difetto: Trump usa le parole chiave anche per attaccare avversari politici. Su 482 post annotati in tutte le versioni, vincoli di vicinanza fra attore e meccanismo (stessa frase, entro 20 parole) tolgono quasi tanti post rilevanti quanti irrilevanti. I falsi positivi non sono un problema lessicale: in "Strong Majority Backs Trump in Stopping Iran's Nuclear Ambitions" attore e meccanismo sono adiacenti, è lo scopo del post a renderlo irrilevante.

Un classificatore semantico (regressione logistica sugli embedding) addestrato sugli stessi 482 giudizi separa rilevanti e irrilevanti con AUC 0,92 in validazione incrociata. Usato come secondo stadio, porta la precisione sul _dentro_ dall'80% all'87% perdendo 6 rilevanti su 217. È una decisione aperta (sezione 10).

= Audit non supervisionato

L'ultima esecuzione è precedente all'integrazione CNN (4#sym.space.nobreak\575 post) e va rilanciata. Risultati su quel corpus: 38 cluster, 37,6% di outlier; copertura della regola 0,66 sul cluster Iran/Hormuz e 0,65 su Russia/Ucraina; 0,43 sul cluster Venezuela/oil/strike, l'unico buco vero. Il cluster sul prezzo della benzina al distributore ha copertura 0,00, coerente con il criterio. La ricerca semantica non trova parafrasi di interruzione dell'offerta fuori dalla regola.

= Episodi, finestra, potenza

Post entro 30 minuti sono un episodio, datato al primo post: #migl(n.eventi) eventi danno *#migl(n.episodi) episodi*, #n.episodi_multipost dei quali con più di un post. L'addensamento è marcato (giugno 2025, marzo–giugno 2026) e fornisce i regimi da confrontare con CD-NOD.

Episodi preceduti da un altro entro un'ora: #pct(n.contaminati_60); entro due ore: #pct(n.contaminati_120). Con la soglia del 15% la finestra evento arriva a due ore.

Effetto minimo rilevabile, test a due code, $alpha = 0,05$, potenza 0,8:
$ "MDE" = (z_(1-alpha\/2) + z_(1-beta)) / sqrt(n) sigma = "2,802" / sqrt(n) sigma. $
Con $n = #n.episodi$: #dec(n.mde) deviazioni standard. Sugli episodi con un prezzo WTI (#pct(n.copertura_wti)): #dec(calc.round(2.8016 / calc.sqrt(n.episodi * n.copertura_wti), digits: 3)).

= Dati di prezzo

Fase ferma. Test su marzo 2025, file in `download/`. Una barra è considerata reale se non sta in un tratto a prezzo costante di almeno un'ora: Dukascopy riempie i periodi a mercato chiuso ripetendo l'ultimo prezzo.

- *Brent*: inutilizzabile. Mancano tutti i martedì e i giovedì del mese, e i giorni presenti si fermano alle 21 UTC.
- *WTI*: copre dalla domenica alle 22 UTC al venerdì alle 21, con una pausa quotidiana fra le 21 e le 22. Le barre della domenica prima delle 22 sono riempimento.
- *Oro*: stessa struttura, scaricato su una sola settimana.

Il #pct(n.copertura_wti) degli episodi cade in orari in cui il WTI ha un prezzo (`query/copertura_post.py`). Il dato `mercato_usa_aperto` (#pct(n.mercato_usa) degli episodi) misura la seduta azionaria, non quella del petrolio, e non indica quanti episodi si perdono.

Questioni aperte:
+ *Copertura del WTI* oltre marzo 2025, non verificata.
+ *Natura del dato*: sono quotazioni CFD di un broker, non prezzi di borsa. Su finestre di minuti la differenza dovrebbe essere trascurabile, ma va avallata.
+ *Episodi senza prezzo*: circa un terzo. Si accetta la perdita, si cerca uno strumento più continuo, o si cambia il disegno per quella fascia?

= Feature

`episodi_features.parquet`: #n.episodi episodi, #n.feature_colonne colonne. Calcolate le fasi A (feature deterministiche), B (novità) e C (campione per il gold standard).

#sub[Novità]

$ "novità"_i = 1 - max_(j : t_i - 30 "gg" <= t_j < t_i) cos(e_i, e_j), $
con $e_i$ l'embedding del testo dell'episodio. Mediana #dec(n.novita.mediana), 10° percentile #dec(n.novita.p10), 90° #dec(n.novita.p90). I valori sono relativi: la variabile serve come ordinamento, non ha una soglia naturale. Verso 0 c'è lo stesso testo ripubblicato; intorno alla mediana lo stesso tema con contenuto diverso; sopra 0,6 contenuti senza precedenti recenti.

Gli episodi con novità sotto 0,15 sono #n.novita_basse, e #n.novita_basse_rt sono ricondivisioni dei propri post: duplicati, non ripetizioni di contenuto. Il legame con la lunghezza del testo è debole (Spearman −0,11), ma la lunghezza resta come controllo.

#sub[Gold standard]

Esportati #n.gold episodi invece di 200: la quota per trimestre è fissa e i trimestri con pochi episodi non la riempiono. Prima di annotarlo conviene togliere le ricondivisioni dei propri post.

= Decisioni da prendere insieme

+ *La serie di prezzo* (sezione 8). Finché non è decisa, la variabile dipendente non esiste.
+ *Regola o regola più classificatore.* Il secondo stadio semantico migliora la precisione, ma la definizione di evento diventa ciò che il modello ha imparato da 482 esempi, e va congelata e dichiarata come un prompt.
+ *Il confine del tema.* Prezzo al distributore, commenti sui mercati, Groenlandia: oggi sono esclusi per criterio di annotazione. Va confermato.
+ *La settimana in Eastern time.* Eccezione dichiarata nel validatore o anomalia documentata.

= Lavoro pianificato

+ Togliere in pulizia le ricondivisioni dei propri post; aggiungere una colonna che distingua le ricondivisioni di altri account.
+ Rendere il filtro dei doppi invii condizionale alla presenza di testo.
+ Rilanciare l'audit sul corpus attuale.
+ Correggere l'esportazione del gold standard per arrivare a 200 episodi; annotarlo, eseguire lo scoring LLM, misurare il kappa pesato.
+ Congelare le feature e annotarne la data.

= Registro delle modifiche

#let voce(data, testo) = [/ #data: #testo]

#voce[2/10/2026][Regola v6: tolto `mine`, che scattava anche come pronome ("not mine"). Calcolate novità semantica e campione per il gold standard. Script `query/orari_serie.py` e `query/copertura_post.py` sulla copertura oraria delle serie.]

#voce[1/10/2026][Integrati #migl(n.post_cnn) post dall'archivio CNN (`00b`), con timestamp dal link. Regola v4: aggiunti `nigeria` e `tariff`. Regola v5: stessa regola, campione rigenerato sul corpus integrato.]

#voce[29/9/2026][Regola v3: tolti `market`, `markets` e i termini di prezzo (`down`, `boom`, `plummet`, `dropping`); commentano prezzi già avvenuti. Aggiunti `regime change`, `ultimatum`, `deadline`, `clock is ticking`, `to flow`. Nella v2 una virgola mancante aveva fuso `dropping` e `regime change` in un solo termine (`droppingregime change` nella tabella delle versioni): nessuno dei due era attivo.]

#voce[29/9/2026][Regola v2: aggiunti `obliterate` e varianti.]

#voce[25/9/2026][Creata la cartella `annotazioni/`: ogni versione conserva regola e campione annotato; `riempi_giudizi.py` riporta i giudizi già dati nei campioni nuovi. Regola v1 annotata, già senza `war`: troppo generico, scattava su qualunque guerra.]

#voce[21/9/2026][Prima stesura. Corretto il parsing dell'ora a 12 ore in `00`; recuperati 12 post persi per il formato dei timestamp in `01`.]
