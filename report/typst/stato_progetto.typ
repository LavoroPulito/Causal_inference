// Conversione di stato_progetto.tex

#set document(title: "Post di Trump e prezzo del greggio — Stato del progetto")
#set page(paper: "a4", margin: 2.8cm)
#set text(size: 11pt, lang: "it")
#set par(justify: true, leading: 0.65em, spacing: 0.65em, first-line-indent: 1.5em)

#show raw: set text(font: ("New Computer Modern Mono", "DejaVu Sans Mono"), size: 0.9em)

// Titoli: sezioni numerate, sottosezioni senza numero (tranne dove indicato)
#set heading(numbering: "1.1")
#show heading: set block(above: 1.6em, below: 1em)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 12pt)
#let sub(title) = heading(level: 2, numbering: none, title)

// Liste
#set enum(spacing: 5pt, indent: 1em)
#set terms(separator: linebreak(), hanging-indent: 1.6cm, indent: 0pt, tight: false, spacing: 5pt)

// Tabelle in stile booktabs
#let toprule = table.hline(stroke: 0.8pt)
#let midrule = table.hline(stroke: 0.4pt)
#let bottomrule = table.hline(stroke: 0.8pt)
#show table: set par(first-line-indent: 0pt, justify: false)

// --- Titolo ---
#align(center)[
  #text(size: 17pt)[Post di Trump e prezzo del greggio] \
  #v(2pt)
  #text(size: 14pt)[Stato del progetto]
  #v(1em)
  #text(size: 12pt)[21 settembre 2026]
]
#v(1em)

= La catena di elaborazione

La domanda è se i post di Trump che segnalano un rischio all'offerta di greggio muovano il prezzo del petrolio, e per quanto tempo. Rispondere richiede tre cose: sapere _quando_ ogni post è stato pubblicato, con precisione sufficiente a isolarne l'effetto; stabilire _quali_ post contano come eventi, con un criterio che un revisore possa replicare; e avere una serie di prezzo abbastanza fitta da misurare la reazione nei minuti successivi.

Il lavoro, fin ora, è diviso in cinque script numerati, ciascuno dei quali legge l'output del precedente.

/ `00`  scraping: Costruisce il corpus dall'archivio dell'American Presidency Project. Il punto non banale è il tempo: l'orario di pubblicazione non viene letto dalla pagina ma ricavato dall'identificatore del post, che lo contiene per costruzione. Il confronto fra i due serve da controllo di qualità sull'intero dataset.

/ `01`  selezione: Porta da "tutti i post" a "gli eventi rilevanti". Scarta ciò che non ha contenuto testuale, applica la regola che definisce l'evento petrolifero, raggruppa i post ravvicinati in episodi e misura quanto possono essere lunghe le finestre di osservazione prima che due episodi si sovrappongano. L'episodio, non il post, è l'unità di analisi.

/ `02`  audit: Risponde all'obiezione prevedibile a qualunque definizione basata su parole chiave: _hai trovato solo quello che cercavi_. Applica due metodi non supervisionati, che non conoscono le liste di termini, e verifica se emergono post rilevanti fuori dalla regola. Non definisce nulla: serve a misurare quanto la regola perde.

/ `03`  prezzi: Procura la serie di prezzo al minuto contro cui misurare la reazione. È la fase ferma, in attesa di decidere insieme quali serie storiche usare.

/ `04`  feature: Porta da "quali post contano" a "quanto e in che direzione ciascuno spinge". Feature calcolate da regole (orario, lunghezza, enfasi), novità semantica rispetto agli episodi recenti, e le variabili che richiedono lettura: direzione attesa sull'offerta, intensità, concretezza.

I primi tre script costruiscono la variabile esplicativa e ne verificano la tenuta; il quarto la gradua; il terzo fornisce la variabile dipendente. La separazione è deliberata: le feature vanno congelate prima di guardare i prezzi, altrimenti tararle sui rendimenti significherebbe costruire il risultato invece di misurarlo.

= Dove siamo

La pipeline arriva fino alle feature deterministiche per episodio. Testo, regola di selezione, episodi e audit non supervisionato sono stati eseguiti e hanno prodotto output su disco; i prezzi sono ancora allo stadio di test; la parte di annotazione (manuale e LLM) non è iniziata.

#align(center, table(
  columns: 3,
  align: (left, left, right),
  stroke: none,
  inset: (x: 6pt, y: 4pt),
  toprule,
  [Fase], [Stato], [Output],
  midrule,
  [00 scraping UCSB], [eseguito], [8\u{202f}619 post, 98,1% verificati],
  [01 pulizia e regola], [eseguito, in taratura], [4\u{202f}575 post, 362 eventi, 329 episodi],
  [02 audit BERTopic], [eseguito], [38 cluster, 84 candidati falsi negativi],
  [03 prezzi Dukascopy], [solo test su marzo 2025], [10 file in `download/`],
  [04 feature], [solo fase A], [329 episodi, 18 colonne],
  bottomrule,
))

= Il corpus e i timestamp

Lo scraper ha interrogato tutti i 608 giorni fra il 1 dicembre 2024 e il 31 luglio 2026. Tre pagine risultano assenti sul server, cinque giorni sono elencati in `giorni_falliti.txt`, i restanti hanno prodotto 8\u{202f}619 post distribuiti su 597 giorni (mediana 10 post al giorno, massimo 177).

Il timestamp è derivato dall'identificatore del post. Truth Social eredita da Mastodon gli ID snowflake, in cui i bit alti sono i millisecondi dall'epoch Unix:
$ t_"UTC" = ("post_id" >> 16) / 1000,
  quad
  "seq" = "post_id" thin \& thin "0xFFFF". $
Il campo di sequenza ordina i post pubblicati nello stesso millisecondo, cosa che serve dentro i burst. Il 98,0% dei timestamp ha secondi diversi da zero, come atteso: si può essere precisi anche al millisecondo.

#sub[Il formato dell'ora in pagina]

L'archivio non usa un formato solo. Su un campione di 766 blocchi di post, 457 riportano l'ora a 24 ore senza suffisso (`18:11`) e 305 a 12 ore con meridiano (`1:17 PM`, `7:05 A.M.`). La prima versione del parser cercava ``(\d{1,2}):(\d{2})`` e ignorava il suffisso, quindi leggeva `1:17 PM` come l'una di notte.

L'effetto sulla validazione era vistoso: 1\u{202f}908 righe segnalate come anomale, di cui 1\u{202f}752 con uno scarto di esattamente 720 minuti — cioè dodici ore, la firma di un meridiano perduto. La correzione cerca l'ora, poi ancora la ricerca del meridiano subito dopo di essa, e richiede maiuscola e confine di parola per non scambiare per meridiano l'inizio del testo che segue un orario a 24 ore (`10:08 Amazing…`, `09:36 A MUST WATCH…`: due casi presenti nel corpus).

Dopo la correzione le righe verificate passano da 6\u{202f}711 a *8\u{202f}455 su 8\u{202f}619, il 98,1%*. Le 164 anomalie residue si scompongono così:

#align(center, table(
  columns: 3,
  align: (left, right, left),
  stroke: none,
  inset: (x: 6pt, y: 4pt),
  toprule,
  [Scarto], [Righe], [Causa],
  midrule,
  [180 min], [105], [UCSB stampa in Eastern time dal 15 al 21 settembre 2025],
  [altro], [36], [scarti irregolari, errori redazionali isolati],
  [assente], [15], [ora non presente in pagina],
  [720 min], [8], [pagina a 24 ore con ora errata (`12:27` per `00:27`)],
  bottomrule,
))

I 105 casi a tre ore cadono tutti in una singola settimana, in cui l'archivio ha cambiato fuso senza dichiararlo; gli 8 residui a 720 minuti non sono un formato che sfugge alla regex ma errori di trascrizione su pagine che usano il formato a 24 ore. Nessuno dei due gruppi tocca i timestamp effettivi, che vengono dagli ID: riguardano solo la colonna di controllo. La settimana in Eastern time resta segnalata come anomala, in attesa di decidere se trattarla come eccezione dichiarata.

= La pulizia

Dei 8\u{202f}619 post scaricati ne sopravvivono alla pulizia *4\u{202f}575*, il 53,1%.
Segue una tabella dei post rimossi:
#align(center, table(
  columns: 3,
  align: (left, right, left),
  stroke: none,
  inset: (x: 6pt, y: 4pt),
  toprule,
  [Criterio], [Post rimossi], [Cosa toglie],
  midrule,
  [Segnaposto senza contenuto], [1\u{202f}849], [repost e immagini senza didascalia],
  [Doppi invii entro 2 minuti], [497], [testi identici ravvicinati],
  [Boilerplate endorsement], [730], [il template degli endorsement elettorali],
  [Sotto le 5 parole], [968], [slogan e frammenti],
  midrule,
  [Totale], [4\u{202f}044], [],
  bottomrule,
))

#sub[La causa: un post su tre non ha testo proprio]

Trump pubblica moltissimi video e immagini senza scrivere nulla. Nella pagina d'archivio un post del genere compare come la parola _Video_ seguita dall'indirizzo del file, oppure come il solo indirizzo. Gli indirizzi vengono rimossi all'inizio della pulizia — sono rumore per qualunque ricerca lessicale — e quello che resta è una stringa vuota o la sola parola `Video`. In tutto sono *2\u{202f}749 post, il 31,9% del corpus*: 1\u{202f}804 diventano vuoti e 945 si riducono a `Video`.

Sono post reali, non errori di scraping, ma non contengono niente su cui una regola basata su parole possa lavorare. Escluderli è inevitabile.

#sub[Il criterio dei doppi invii rimuove post reali]

Il caso da correggere è il secondo filtro. Serve a eliminare il doppio invio accidentale: lo stesso messaggio pubblicato due volte a pochi secondi di distanza è un gesto comunicativo solo, non due eventi. Per riconoscere "lo stesso messaggio" i testi vengono confrontati in forma _normalizzata_: tutto minuscolo, via la punteggiatura, spazi compattati. È una chiave di confronto, non il testo che verrà analizzato dopo. Così "Deal with Iran!!!" e "deal with iran" diventano entrambi `deal with iran` e risultano uguali.

#sub[Cosa comporta]

Va sottolineato che il 47% dei post non è scartato in fase di pulizia per una selezione aggressiva.
I post sono scartati perché privi di contenuto e quindi per "costruzione", sono irrilevanti per i nostri scopi.

Si può valutare l'implementazione di un filtro a parte più specifico che chiarisca con precisione le proporzioni di tali post per un puro fine analitico. Ai fini dell'estrazione delle features è irrilevante.

Resta un limite che non si risolve spostando filtri. Un post di solo media può benissimo essere rilevante per la domanda di ricerca — un video di una raffineria colpita è informazione di mercato a tutti gli effetti — e nessuna regola lessicale può riconoscerlo. Conviene dichiararlo insieme al criterio di campionamento invece di lasciarlo implicito in una fase di pulizia.

= La regola e gli eventi

La regola richiede la congiunzione di un attore dell'offerta e di un meccanismo:
$ "evento"_i = bb(1) lr([ |A inter T_i| >= 1 and |M inter T_i| >= 1 ]), $
con $T_i$ i token del post $i$, $A$ la lista degli attori e $M$ quella dei meccanismi. Sul corpus pulito: 631 post con almeno un attore, 810 con almeno un meccanismo, *362 eventi* (7,9%). I termini che reggono la regola sono concentrati — `iran` (223), `russia` (65), `hormuz` (62), `ukraine` (57) fra gli attori; `military` (97), `war` (95), `nuclear` (87), `strait` (67), `oil` (64) fra i meccanismi.

Due problemi di taratura emergono dalle liste stesse.

*Termini di mercato usati come attori.* `market` e `markets` sono nella lista degli attori, e `boom`, `come down`, `going down`, `coming down` in quella dei meccanismi. Non sono attori dell'offerta né meccanismi di interruzione: sono commento sui prezzi. Venticinque eventi (6,9%) si reggono esclusivamente su questi termini.
Anche se leggendoli sono chiaramente fuori tema (e.g. "The MARKETS are going to BOOM", "This is Biden's Stock Market") li ho inseriti perché le date di molti post sono post attacco in Venezuela o in iran da interpretare come un riferimento a quanto stava succedendo in quel periodo.
Se tolti, gli eventi scendono a 337. Il costo in numerosità è modesto.

*Il 44,5% degli eventi si regge solo su meccanismi deboli* (`war`, `military`, `attack`, `strike`, `nuclear`, `down`), cioè termini che indicano conflitto ma non offerta di greggio. La diagnostica è già implementata e segnala il caso; 161 eventi su 362 ricadono lì.
Nel file `dati/petrolio/da_leggere.csv` è presente un campione di 150 da controllare per verificare la correttezza della regola. Da una prima esamina si capisce che la regola tende più a prendere un falso positivo che un falso negativo (Trump a volte tira fuori le parole chiavi scelte solo per parlare male dei suoi avversari politici).
Tutta via a causa della già scarsa presenza di post ho preferito non proseguire con una cernita più severa.

*UPDATE*-- \
Ho creato la cartella annotazioni che tiene traccia delle varie versioni della regola e dei file da controllare.
questa sarà utile sia a tenere traccia delle performance di ogni versione della regola sia ad autocompilare il giudizio dei post che sono già stati giudicati.

== Il criterio della regola

si ritengono interessanti i post in cui Trump parla di:
+ *il conflitto iraniano e lo stretto di hormuz*: qualsiasi news riguardi l'apertura dello stretto o il raggiungimento di un accordo con gli iraniani è rilevante per capire le aspettative future sulla rotta petrolifera più importante.
+ *Venezuela*: l'attacco intrapreso dall'amministrazione Trump in Venezuela ha interessato gli approvvigionamenti di petrolio americano dalle navi venezuelane
+ *Previsioni di Trump sul mercato*: in molti post trump incita i suoi lettori a comprare. Spesso si stratta di propaganda e basta. Ciò nonostante, in un'analisi che riguarda l'influenza che ha un uomo sul mercato è interessante anche quando il presidente USA elargisce esplicitamente consigli finanziari.
+ *obliterate* è un buon meccanismo
+ *iran will not have a nuclear weapon*: in generale lo leggo come segno di tensione fra iran e USA.

= Audit non supervisionato

L'audit è stato rilanciato sul corpus corretto: 38 cluster con il 37,6% di outlier. La copertura della regola per cluster è coerente con il disegno: 0,66 sul cluster Iran/Hormuz (195 su 297 post catturati), 0,65 su Ucraina/Russia (46 su 71). Le piccole variazioni rispetto all'esecuzione precedente vengono dalla ricostruzione degli embedding su testi ripuliti e non cambiano il quadro.

Tre cluster hanno lessico petrolifero e copertura bassa. Il più rilevante è Venezuela/#sym.zws;oil/#sym.zws;strike, con copertura *0,43*: 23 post catturati su 54. Il tema è dichiaratamente dentro il perimetro della tesi, quindi quella copertura indica un buco vero nella lista dei termini, non un falso allarme.

Gli altri due stanno fuori per costruzione: uno raccoglie la politica energetica interna (EPA, permessi), l'altro — `prices`, `gasoline`, `inflation` — il prezzo al distributore, con copertura *0,00*. Che il clustering isoli quest'ultimo a ogni riesecuzione non è un difetto della regola, ma dice che il confine fra prezzo al consumo americano e offerta globale di greggio conviene scriverlo per esteso invece di lasciarlo implicito nelle liste.

La ricerca semantica restituisce 84 candidati falsi negativi, con similarità mediana 0,45 e massima 0,65. I più vicini alle sonde sono commenti sul prezzo al distributore (e.g. "Gasoline Retailers must get their Prices down", "Gasoline just broke \$1.98 a Gallon"). Nessuna parafrasi di interruzione dell'offerta compare fra i candidati: il richiamo della regola sul suo perimetro dichiarato sembra alto, e questo è il risultato che l'audit doveva produrre.

= Episodi, finestra evento, potenza

Post entro 30 minuti l'uno dall'altro sono collassati in un episodio, datato al primo post. I 362 eventi danno *329 episodi*: 297 con un solo post, 31 con due, 1 con tre. Solo il 9,7% è multi-post, il che rende l'attribuzione del movimento molto più semplice di quanto ci si aspettasse. Identità e datazione degli episodi sono invariate rispetto a prima della correzione: cambia il testo di 179 di essi, non quali siano.

32,5% in orario di mercato USA, 24,0% nel weekend, 16,9 episodi al mese su un arco di 593 giorni. L'addensamento è marcato — giugno 2025, marzo, aprile e giugno 2026 — e fornisce i regimi naturali da confrontare con CD-NOD senza doverli scegliere a posteriori.

Gli intervalli fra episodi sono ampi: il primo percentile è 36 minuti, la mediana 19,5 ore. La quota di episodi contaminati da un altro dentro la finestra resta nulla fino a 30 minuti, sale al 3,4% a un'ora e al 10,1% a due ore. Con la soglia del 15% adottata, *la finestra evento arriva a due ore* senza problemi di sovrapposizione. Il vincolo, quindi, non viene dal testo ma dai prezzi.

La numerosità minima rilevabile si legge dalla formula standard per un test a due code su una media:
$ "MDE" = (z_(1-alpha\/2) + z_(1-beta)) / sqrt(n) sigma
  = "2,802" / sqrt(n) sigma
  quad (alpha = "0,05", 1-beta = "0,8"). $
Con $n = 329$ si rilevano effetti da 0,154 deviazioni standard del rendimento sulla finestra. Dividendo per direzione attesa si sale attorno a 0,22, e sui 247 episodi che avranno effettivamente un prezzo (sezione seguente) a 0,178. Sono soglie praticabili per un evento macro su finestre di minuti, ma non lasciano margine per sottogruppi ulteriori.

= Dati di prezzo: cosa dicono i test

#align(center, table(
  columns: 4,
  align: (left, right, right, right),
  stroke: none,
  inset: (x: 6pt, y: 4pt),
  toprule,
  [], [Brent (`brentcmdusd`)], [WTI (`lightcmdusd`)], [Oro (`xauusd`)],
  midrule,
  [Barre nel mese], [12\u{202f}720], [36\u{202f}780], [—],
  [Giorni feriali coperti], [10 / 21], [21 / 21], [5 / 5 nel test],
  [Ore UTC coperte], [0–20], [0–23], [0–23],
  [Barre per giorno], [1\u{202f}260], [1\u{202f}440], [1\u{202f}440],
  bottomrule,
))

Il Brent è inutilizzabile: metà dei giorni feriali manca del tutto e i giorni presenti si fermano alle 20:59 UTC. Il WTI copre tutti i giorni feriali e l'intera giornata. Ristretto a lunedì–venerdì: nessun buco superiore a 15 minuti, 5,5% di barre a volume nullo, deviazione standard dei rendimenti al minuto di $"4,3" times 10^(-4)$, 20% di rendimenti esattamente nulli. Sono valori normali per dati al minuto su un future energetico.

La riserva riguarda la domenica. Le barre domenicali sono il 92,6% a volume nullo e riportano il prezzo di chiusura del venerdì congelato per ventidue ore: cinque tratti da oltre 1\u{202f}300 minuti a prezzo identico, uno per ogni domenica del mese. Sono riempimento sintetico, non quotazioni, e vanno scartate. Sul totale del mese il 21% delle barre cade in tratti costanti di almeno un'ora; sui soli giorni feriali scende al 3,6%.

Tenendo conto di sabato, domenica fino alle 22 UTC e venerdì dopo le 21, *82 episodi su 329 (24,9%) restano senza quotazione* e ne rimangono 247 utilizzabili. Con il solo Brent sarebbero stati 211. La perdita non è casuale: colpisce un'intera fascia di calendario, quindi va confrontata la distribuzione delle feature fra episodi persi e conservati. Il primo controllo disponibile — il numero di post per episodio — non mostra differenze (1,08 contro 1,10), ma il confronto va rifatto su tutte le feature una volta che esistono.

Da qui la fase è ferma. Il test dice che una strada praticabile esiste, non che sia quella giusta, e la scelta conviene farla prima di scaricare venti mesi di dati. Restano aperte tre questioni.

+ *Quanto in là arriva il WTI.* Marzo 2025 è coperto senza buchi, ma è un mese solo. La copertura sul resto del periodo non è verificata, e lo stesso vale per l'oro, scaricato finora su cinque giorni.
+ *Che dato è.* Sono quotazioni CFD di un broker, non prezzi di borsa: seguono il future sottostante con uno spread proprio. Su finestre di pochi minuti la differenza dovrebbe essere trascurabile, ma è un'assunzione da avallare, non da dare per buona.
+ *Gli episodi senza mercato.* Un quarto degli episodi cade quando non esiste un prezzo. Si accetta la perdita dichiarandola, si cerca uno strumento con copertura più ampia, o si tratta quella fascia in modo diverso nel disegno?

Lo script 03 è ancora impostato sul Brent come variabile principale: verrà allineato quando la scelta sarà fatta.

= Feature

`episodi_features.parquet` contiene i 329 episodi con 18 colonne. Sono presenti solo le feature deterministiche della fase A — ora UTC e New York, giorno, weekend, orario di mercato, caratteri, esclamativi, maiuscole, parole urlate.

La correzione del parser ha avuto un effetto misurabile. Le due lettere `AM`/`PM` contavano come maiuscole e gonfiavano la misura di enfasi: la quota di maiuscole era sovrastimata su *177 episodi su 329*, di 0,005 in mediana e fino a 0,027. La mediana complessiva scende da 0,1065 a 0,1029. È una distorsione piccola ma non innocua, perché dipendeva dal formato della pagina d'archivio e non dal post, quindi entrava nelle feature come rumore arbitrario.

Mancano la novità semantica, il gold standard e lo scoring LLM. La novità è l'unica delle tre che non richiede annotazione:
$ "novità"_i = 1 - max_(j : t_i - 30 "gg" <= t_j < t_i) cos(e_i, e_j), $
con $e_i$ l'embedding del testo unito dell'episodio. Conviene calcolarla subito, perché è la feature che serve a distinguere l'informazione nuova dalla ripetizione ed è indipendente da tutto il resto.

Il codice della fase D salva già modello, prompt e temperatura accanto ai risultati, che è la condizione minima perché una feature generata da un LLM sia riproducibile.

= Decisioni da prendere insieme

Prima di proseguire ho bisogno di un consiglio sulle seguenti tematiche:

+ *La serie di prezzo*, nei termini della sezione precedente. Finché non è decisa, la variabile dipendente non esiste e l'event study non si può impostare.
+ *La settimana in Eastern time.* Dal 15 al 21 settembre 2025 l'archivio stampa gli orari in un fuso diverso senza dichiararlo. I timestamp restano corretti perché vengono dagli identificatori, ma il controllo di qualità segnala 105 righe. O diventa un'eccezione dichiarata nel validatore, o resta un'anomalia documentata: in tesi cambia solo come la si racconta.
+ *Il confine del tema.* Un post sul prezzo della benzina al distributore non è un rischio all'offerta globale, ma è a un passo, e sia la ricerca semantica sia il clustering continuano a riportarlo a galla. Conviene fissare il criterio adesso e per iscritto, prima che sia un'annotazione a deciderlo caso per caso.

= Lavoro già pianificato

+ Introdurre un filtro esplicito per i post di solo media, contato a parte, invece di lasciarli distribuiti su tre criteri; e rendere il criterio dei doppi invii condizionale alla presenza di testo.
+ Valutare di togliere `market`, `markets` e i termini di prezzo dalle liste; aggiungere i termini mancanti del cluster Venezuela.
+ Calcolare la novità semantica ed esportare il gold standard; annotarlo, eseguire lo scoring LLM, misurare il kappa pesato.
+ Congelare le feature e annotare la data.
