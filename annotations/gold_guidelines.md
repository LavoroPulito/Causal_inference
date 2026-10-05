# Criteri di annotazione del gold standard

Versione 1 — da congelare dopo la prova su 20 episodi. Se i criteri cambiano, si riannota tutto.

## Principi

- Si annota l'episodio intero (`testo_unito`).
- Si giudica con ciò che era pubblico in quel momento. Niente prezzi, niente fatti successivi.
- Domanda guida: l'episodio cambia ciò che ci si aspetta per l'offerta di greggio nei prossimi giorni?
- La novità non si giudica: la misura già la feature `novita`.

## direzione (−2 … +2)

Effetto atteso sull'**offerta**. Negativo = offerta a rischio (prezzo atteso in salita).

1. Cambia le aspettative sull'offerta? No → **0** (anche se il post è fuori tema).
2. Verso: minaccia, escalation, sanzioni, blocchi → negativo. Accordi, cessate il fuoco, rotte riaperte, più produzione → positivo.
3. Forza: **±2** se tocca i flussi fisici (Hormuz chiuso/riaperto, attacco a infrastrutture, cessate il fuoco concluso); **±1** se tocca le probabilità (negoziati, richieste, minacce generiche, sanzioni su terzi).

Messaggi misti: prevale ciò che cambia lo stato fisico. Se si equivalgono: 0 e nota.

## intensita (1 … 3)

- **1** commento, opinione, previsione
- **2** minaccia, ultimatum, richiesta, intenzione
- **3** azione compiuta o imminente con un momento preciso ("stanotte", "entro 48 ore")

## concretezza (0 / 1)

**1** se nomina almeno uno fra: luogo, impianto o nave specifici; quantità; scadenza; provvedimento specifico (dazio, accordo).

**Convenzione:** se `direzione` = 0, allora `intensita` = 1 e `concretezza` = 0.

## Sempre 0

- Attore o meccanismo citato di passaggio in un post su altro.
- Sondaggi, editoriali linkati, polemiche su fatti già noti.
- Fatti militari senza legame con l'offerta (narcotraffico, droni sulla Polonia).
- Commenti su prezzi già avvenuti.
- Groenlandia.

## Esempi

| episodio | dir | int | conc |
|---|:-:|:-:|:-:|
| "Complete and Total CEASEFIRE (in approximately 6 hours…)" | +2 | 3 | 1 |
| "Iran has officially responded… very weak response… 14 missiles" | +1 | 3 | 1 |
| "very close to meeting our objectives as we consider winding down" | +1 | 2 | 1 |
| "Secondary Tariff on the Country of Venezuela" | −1 | 3 | 1 |
| "Iran must stop the sending of these Supplies" (Houthi) | −1 | 2 | 1 |
| "WE WILL NOT ALLOW ANY ENRICHMENT" (negoziato in corso) | −1 | 2 | 1 |
| Nigeria, "guns-a-blazing" | −1 | 2 | 1 |
| "the nuclear sites in Iran are completely destroyed" (polemica con CNN) | 0 | 1 | 0 |
| "If I didn't terminate… JCPOA" | 0 | 1 | 0 |

## Casi da decidere nella prova

- "Oil is flowing like never before" — vanto retrospettivo (0) o segnale che le rotte resteranno aperte (+1)?
- "Countries that receive Oil through Hormuz must take…" — USA che si sfilano dalla protezione dello stretto (−1)?

## Procedura

1. Prova su 20 episodi, rivedi, congela, riparti da capo.
2. Ordine casuale, non cronologico.
3. Ogni dubbio in `note`.
4. I 50 episodi doppi a una seconda persona, con questo file e senza i tuoi giudizi. Obiettivo: kappa pesato ≥ 0,6 sulla direzione.
5. Controllo: episodi con giudizio 0 nelle versioni della regola devono avere `direzione` 0.
