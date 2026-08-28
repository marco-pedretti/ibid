# ibid: Piano di implementazione

**Banco di prova per sistemi RAG con attribuzione verificabile**, su modelli piccoli eseguiti in locale, valutato quantitativamente su dataset di benchmark pubblici.

## Il nome

**`ibid`**: dal latino *ibidem*, "nello stesso luogo". È l'abbreviazione usata nelle note bibliografiche per rimandare alla fonte appena citata, senza ripeterla per esteso.

È il nome del progetto perché descrive esattamente ciò che il sistema fa: per ogni affermazione che produce, riportare al punto preciso del documento da cui viene. Non "una risposta con dei link in fondo", ma un rimando verificato all'origine di ogni singola frase.

Convenzioni:

- nome del repository, della cartella di lavoro e del package Python: `ibid` (minuscolo)
- descrizione "About" del repo, obbligatoria e senza metafore:
  > *Banco di prova per RAG con citazioni verificate a livello di frase, su modelli piccoli in locale*

Il nome evocativo attira, la descrizione spiega. Chi scorre una lista di repository dà tre secondi a ciascuno: senza la descrizione, un nome criptico è solo criptico.

---

> **Rinumerazione del 2026-08-13.** L'inserimento della Fase 7 ha spostato di uno le sezioni finali. Chi legge messaggi di commit anteriori a quella data traduca §13→**§14**, §14→**§15**, §15→**§16**, §16→**§17**, e le fasi 7 e 8 di allora nelle attuali 8 e 9. I riferimenti dentro il repo sono aggiornati; i commit non si riscrivono. **§0 e §3, i più citati, non si sono mossi**: è il motivo per cui la rinumerazione era accettabile.

Questo documento è la fonte di verità per l'implementazione. È scritto per essere eseguibile anche da un coding agent: ogni task ha un identificativo, un deliverable e criteri di accettazione verificabili. Le scelte tecnologiche stanno in `STACK.md`.

**Divisione del lavoro fra i documenti.** Qui stanno **decisioni e vincoli**; le **misure** stanno in [`docs/progress.md`](docs/progress.md), che è anche l'unico posto dove si legge cosa è già fatto; le **ipotesi non ancora verificate**, con il protocollo per verificarle, stanno in [`docs/open-questions.md`](docs/open-questions.md). La regola pratica: se un numero cambierebbe rifacendo una misura, non appartiene a questo file, ci appartiene la decisione che quel numero ha motivato. Serve perché il criterio di accettazione di un task deve restare leggibile in una riga: quando ci finisce dentro il resoconto di com'è andata, smette di essere un criterio.

---

## 0. Cosa dimostra il progetto

Tre affermazioni, ognuna sostenuta da una riga di tabella:

1. **L'attribuzione verificata a livello di frase è misurabile**, e i modelli piccoli senza verifica sbagliano in modo sistematico (`citation_precision`).
2. **Il routing automatico della pipeline in base al genere documentale batte una pipeline generica unica**, e il guadagno si vede per dataset.
3. **Con un retrieval buono la taglia del modello conta molto meno di quanto si creda**: ipotesi da testare, i test preliminari la suggeriscono.

Tutto il resto (interfaccia, toggle, upload) serve a rendere queste tre cose visibili.

---

## 1. Stato di partenza

**Già acquisito**: test svolti prima dell'implementazione, output grezzi da conservare in `eval/contamination/`:

- Gemma 4 E4B e 12B: cutoff dichiarato gennaio 2025.
- Su contenuto non presente nei dati di addestramento, entrambi accettano il testo fornito anche contro la propria conoscenza obsoleta (8/8 su quattro esecuzioni). Il grounding funziona anche cross-lingua.
- **Il formato di output non è stabile**: quattro esecuzioni, quattro convenzioni di citazione diverse. Il formato va imposto con esempio e riparato dal codice.
- **Il modello varia tra esecuzioni** anche a parità di tutto: risposte corrette guadagnate e perse. Serve una soglia di rumore prima di dichiarare qualsiasi miglioramento.
- Un prompt che invita il modello a decidere se sa abbastanza lo manda in spirale (fino a ~390 s di ragionamento circolare). Le soglie stanno nel codice.
- Contesto **32k**: nessuna perdita di accuratezza rispetto a 256k, latenza dimezzata, VRAM liberata.

**Vincoli operativi**

- Temperatura **0** su ogni esecuzione di valutazione, annotata nel risultato.
- GPU: AMD RX 6750 XT, 12 GB. Backend Vulkan preferito a ROCm.
- Due persone in pair programming sulla stessa parte.
- **~8 settimane.** Le fasi 0-7 sono il progetto completo. La Fase 8 è extra.

---

## 2. Dataset

Nessun corpus costruito a mano, nessuno scraping, nessun manifest di download da fonti con licenza restrittiva. Solo dataset pubblici con licenza dichiarata, giudizi di rilevanza inclusi e documentazione di cosa contengono.

| Ruolo | Candidato | Perché |
|---|---|---|
| **Demo** | dataset minuscolo, indice committato | `docker compose --profile demo up` in < 2 minuti senza download |
| **Principale** | `vectara/open_ragbench` | PDF reali, hard negative già selezionati, query e risposte incluse, codice di rigenerazione disponibile |
| **Secondo genere** | sottoinsieme visuale con tabelle e figure (ViDoRe v2 o equivalente) | Struttura documentale profondamente diversa: è ciò che fa esistere il routing |

I due dataset principali devono appartenere a **generi documentali diversi**. Se si somigliano troppo, l'affermazione 2 del §0 non è dimostrabile e va scelto un altro secondo dataset.

**Selezione finale in T-03.** I candidati sopra sono indicazioni, non decisioni: la scelta si chiude dopo la verifica di contaminazione.

---

## 3. Contratti dati

Da definire prima di scrivere codice applicativo. Modificarli dopo la Fase 2 invalida i risultati già misurati.

### 3.1 Chunk

```python
class Chunk(BaseModel):
    chunk_id: str          # "{dataset_id}:{doc_id}:{seq}"
    dataset_id: str        # "open_ragbench" | "vidore_v2" | "demo"
    doc_id: str
    doc_genre: str         # assegnato dal profilatore: "academic_pdf" | "table_heavy" | "continuous_text"
    pipeline: str          # pipeline di ingestion effettivamente usata
    section_path: str      # gerarchia se disponibile, altrimenti ""
    page: int
    bbox: tuple[float, float, float, float] | None   # per l'highlight (Fase 7)
    content_type: str      # "text" | "table" | "figure_caption" | "mixed"
    text: str
    source_uri: str        # con deep link quando possibile, es. "...#page=12"
```

`dataset_id` è obbligatorio ovunque: **tutte le metriche si riportano per dataset**, mai aggregate. Un valore medio su generi documentali diversi non significa nulla.

### 3.2 Formato citazione (imposto, non suggerito)

Nel prompt di generazione, con esempio esplicito. Il parser accetta **solo** questa forma:

```
Il valore massimo è 400ms [2][3].
```

Marcatori `[n]` contigui, un numero per chunk, numerazione stabile per sessione. Vietate `[2, 3]`, `[2 e 3]`, `[2]-[3]`. Il parser normalizza le varianti note (sono documentate in `eval/contamination/`, raccolte dai test preliminari) e scarta i marcatori che puntano a chunk non presenti in contesto.

**Intorno ai marcatori il modello è libero di formattare.** Dal 2026-08-19 (U-14) il prompt *invita* markdown e LaTeX dove aiutano invece di imporre prosa piana; il testo grezzo resta il sistema di coordinate su cui viaggiano marcatori, verdetti per frase e frasi scoperte, e la formattazione si applica **come decorazione su intervalli**. Il debito che questo apre è **D-3**.

### 3.3 Risultato di valutazione

```python
class EvalRun(BaseModel):
    run_id: str
    timestamp: datetime
    git_commit: str
    config_hash: str
    dataset_id: str
    model: str             # "gemma4-e4b"
    quantization: str      # "Q4_K_M"
    context_window: int    # 32768
    temperature: float     # 0.0
    reasoning_enabled: bool
    pipeline_mode: str     # "generic" | "routed"
    config: dict[str, Any] # flag di retrieval attivi, vedi src/eval/run_config.py
    metrics: dict[str, float]
```

`config` è additivo (default `{}`) e **non** entra nel calcolo di `config_hash`: i run misurati prima della sua introduzione restano confrontabili. Serve a tenere `pipeline_mode` binario come dichiarato qui sopra, invece di usarlo come etichetta libera in cui infilare `rerank`, `filtered_text`, `docagg` e simili: cosa che rende impossibile selezionare due run che differiscono per un flag solo (§15).

### 3.4 Configurazione

Ogni scelta di retrieval è un parametro in `config.py`. Un'ablation deve essere un ciclo su file di configurazione. Se cambiare il reranker richiede di toccare un modulo, il design è sbagliato.

### 3.5 Contratto UI ↔ API

Scritto **prima** degli endpoint (A-03), e prima di qualunque scelta di design dell'interfaccia. Non descrive come la UI appare: descrive **cosa può chiedere e cosa riceve**. Sta qui e non nella Fase 8 perché è un contratto dati, e perché è ciò che la Fase 7 implementa.

**Deriva dai requisiti già decisi**, non è da inventare:

| requisito di Fase 8 | cosa impone |
|---|---|
| U-02: lista documenti sempre visibile | la risposta porta **sempre** i chunk recuperati, non solo il testo |
| U-05: indicatore di pipeline | ogni chunk porta `pipeline` e `doc_genre` |
| U-07, non verificate marcate, non nascoste | ogni citazione porta il **proprio verdetto**, e l'API non ne filtra nessuna |
| U-03: RAG on/off affiancati | la richiesta accetta il toggle; le due risposte sono confrontabili |
| U-01: cambio dataset senza riavvio | esiste `GET /datasets`; nessuna costante nel frontend |
| U-06: link profondi | ogni citazione porta `source_uri` e `page`; `bbox` resta `null` finché I-06 è rinviato: **dichiararlo, non simularlo** |

#### La verifica arriva dopo il testo, e questo decide il protocollo

`verify_answer()` prende la risposta **completa**: la spezza in claim e per ogni coppia (claim, chunk citato) fa girare il modello NLI. È posteriore alla generazione per costruzione.

Ma l'architettura prevede **SSE streaming**, e U-07 chiede che le citazioni non verificate siano marcate. Quindi mentre i token scorrono, il marcatore `[2]` compare **prima che il suo verdetto esista**.

Ne segue che lo stream **non è una sequenza di token**. Il minimo indispensabile:

```
event: chunks     { "chunks": [...] }                   una volta, appena il retrieval è finito
event: token      { "text": "..." }                     n volte, testo grezzo e provvisorio
event: answer     { "text": "...", "raw_text": "...", "repaired": true,
                    "verification_pending": true, ... }  il testo dopo il parser di C-02
event: citations  { "citations": [...], "uncited_claims": [...] }   dopo la verifica
event: done       { "abstained": false, "timings": {...}, "config": {...} }
event: error      { "message": "...", "stage": "retrieval" }
```

Tre conseguenze decise una volta sola, non scoperte a frontend scritto:

1. **Il testo grezzo non è il testo finale, e si è scelto di streammarlo comunque.** Il parser di C-02 ripara i marcatori (`[1] [2]` → `[1][2]`) e scarta quelli fuori contesto, quindi ciò che scorre in `token` differisce da `answer`. L'alternativa (ritardare lo stream fino al parser) costa lo streaming per intero: la prima parola arriverebbe **dopo** l'ultima, cioè dopo gli ~11 s che U-10 dice esplicitamente di non nascondere.

   Quindi il contratto è: **`token` è provvisorio, `answer` lo sostituisce.** Ne discende una regola per la UI, ed è vincolante: **finché `answer` non arriva, i marcatori che scorrono non sono cliccabili.** Renderli attivi prima significherebbe offrire un link a un `[2]` che il parser potrebbe scartare. `raw_text` viaggia comunque in `answer`, perché è ciò che C-01 misura e perché una UI che voglia mostrare la riparazione deve poter mostrare da cosa.

2. **`chunks` arriva prima di `answer`.** È ciò che rende U-02 realizzabile: la lista documenti compare mentre il modello sta ancora scrivendo.

3. **Il guasto è un evento, non uno stato HTTP.** Quando lo stream è cominciato gli header sono già partiti, e un 500 non è più spedibile: un errore a metà risposta può solo essere un altro evento. Il servizio continua a sollevare (è l'orlo HTTP che traduce) così un CLI vede la traccia di stack e un browser uno stato disegnabile. `stage` esiste perché la UI possa dire «le fonti ci sono, la risposta no» invece di buttare via tutto.

#### Il criterio di completezza

**La UI deve poter leggere lo schema e sapere cosa disegnare in ogni stato**, inclusi «sto aspettando i verdetti», «il modello si è astenuto» e «il retrieval non ha trovato niente». Se uno stato non è rappresentabile, manca un campo, e si scopre ora invece che a frontend scritto.

Due stati meritano di essere nominati, perché è facile crederli deducibili e non lo sono:

- **«Attendo i verdetti»** non è `citations == []`. Quella lista vuota copre tre situazioni diverse: verifica non chiesta, verifica fatta senza citazioni da giudicare, verdetti in arrivo. Con lo streaming la terza è la norma, quindi `answer` porta `verification_pending`.
- **«Chi si è astenuto»** non è un booleano. Il gate di C-04 rifiuta prima di chiamare il modello (costo 0 s di GPU), e il modello che dichiara di non sapere costa ~11 s. Sono eventi diversi, quindi `abstention` vale `""` | `"retrieval"` | `"model"`.

Analogamente **`gate.active: false`** significa «non c'era una soglia calibrata per questa collection e questa modalità», che non è «i punteggi erano alti abbastanza». Confonderle farebbe leggere come garanzia una cosa che non è avvenuta.

#### Cosa il contratto NON copre

Layout, componenti, stile, gestione dello stato lato client, paginazione, cronologia delle query, sessioni salvate. Non incidono sulla forma delle risposte, quindi non vincolano l'API e restano decisioni di Fase 8.

---

## 4. Fase 0: Fetta verticale e gate di contaminazione

**Durata: 1 settimana.** L'obiettivo non è fare bene, è arrivare da un input a un output con citazioni, e verificare che il progetto stia in piedi.

| ID | Task | Criterio di accettazione |
|---|---|---|
| T-01 | Scheletro repo, `compose.yml`, `.env.example`, `Makefile` | `docker compose up` risponde su `/health` |
| T-02 | Smoke test modelli: E2B, E4B, 12B, 26B MoE su Vulkan | Tabella token/s e VRAM in `docs/hardware.md`. Se il 26B non è usabile, deciso e documentato ora |
| T-03 | **Verifica di contaminazione sui dataset candidati** | Vedi sotto. È il gate del progetto |
| T-04 | Caricamento dataset da HuggingFace, normalizzazione allo schema `Chunk` | Conteggio documenti e chunk per dataset stampato |
| T-05 | Ingestion minima (chunk a lunghezza fissa) → Qdrant, retrieval denso, generazione con marcatori | CLI: query in, risposta con citazioni out |
| T-06 | Parser citazioni + scarto marcatori inesistenti | Test unitario sugli output malformati reali già raccolti |
| T-07 | **Verifica licenze delle dipendenze** contro la MIT scelta per il progetto | Tabella licenze in `STACK.md` aggiornata; nessuna dipendenza copyleft in albero. Attenzione a PyMuPDF: è AGPL-3.0 e va evitato |

### T-03 in dettaglio: il gate

Per ogni dataset candidato: 16 domande costruite con lo stesso schema dei test preliminari, sottoposte a E4B e 12B **senza contesto**, temperatura 0, chat separate, più i due controlli positivi.

**Esito atteso (buono):** il modello non conosce i dati specifici, oppure li sbaglia con sicurezza. Si procede.

**Esito da scarto:** il modello risponde correttamente senza retrieval. Il dataset non è utilizzabile come dimostrazione e va sostituito.

**Se tutti i candidati risultano contaminati**, il progetto non muore ma cambia enfasi: il confronto A/B si sposta dalla correttezza alla `citation_precision`, dove il modello nudo non può competere per costruzione, senza contesto non ha nulla da citare. Va deciso qui, non in Fase 5.

**Gate:** una query produce una risposta con almeno una citazione risolvibile a un chunk reale, e il risultato di T-03 è documentato in `docs/contamination.md`.

---

## 5. Fase 1: Ingestion multi-dataset e profilatore

**Durata: 1 settimana.**

| ID | Task | Criterio di accettazione |
|---|---|---|
| I-01 | **Profilatore documenti**: pagine, presenza di strato testuale, densità di tabelle, numero di colonne, profondità della struttura | Produce un report tabellare per dataset. Serve prima come triage, poi per il routing |
| I-02 | Assegnazione `doc_genre` dal profilo | Classificazione su 50 documenti verificata a mano, ≥90% corretta |
| I-03 | Pipeline `continuous_text`: chunking su paragrafi con overlap | Distribuzione delle lunghezze in **token** riportata per dataset, contro la finestra dell'embedder. *Aggiunto il 2026-08-11 e attualmente non soddisfatto*, vedi OQ-04 |
| I-04 | Pipeline `structured_hierarchical`: chunking su sezioni, `section_path` popolato | Come I-03, più `section_path` non vuoto dove la struttura esiste |
| I-05 | Pipeline `table_heavy`: tabella come unità atomica, mai spezzata a metà | Nessun chunk contiene una tabella troncata |
| I-06 | Estrazione bbox e rendering pagine a PNG dove il formato lo consente | `bbox` e `page` popolati per i dataset con PDF |
| I-07 | Indicizzazione `multilingual-e5-large` (densi) + `Qdrant/bm25` (sparsi) su Qdrant, una collection per dataset | Job one-shot: il tempo è riportato, non vincolato. **BGE-M3 sostituirà `multilingual-e5-large` quando fastembed PR #602 sarà mergiato: re-ingestione obbligata, e va trattata come ablation separata, non come patch** |

**I-01 va fatto per primo** anche se serve al routing solo in Fase 3: è lo strumento con cui decidete cosa entra nel corpus e come, e vi risparmia di scoprire a valle che un dataset non è quello che pensavate.

**I-06 è rinviato**: nessuno dei due dataset correnti distribuisce PDF nativi o coordinate, quindi `bbox` resta `None` e l'overlay di U-06 non ha su cosa poggiare. Diventa applicabile solo aggiungendo un dataset con PDF e coordinate esportate. Motivo per esteso in [`docs/progress.md`](docs/progress.md), I-06.

**Gate:** report del profilatore per i tre dataset, e i due dataset principali risultano di generi diversi.

---

## 6. Fase 2: Harness, baseline, rumore

**Durata: 1 settimana.** Il cardine del progetto. Da fare a quattro mani.

| ID | Task | Criterio di accettazione |
|---|---|---|
| E-01 | Import di query e qrels dai dataset, normalizzati a uno schema comune | `eval/golden/{dataset_id}.jsonl` validato |
| E-02 | **Query non rispondibili**: 30-40 per dataset | Vedi nota sotto |
| E-03 | Metriche IR via `ir_measures`: recall@k, MRR, nDCG, success@1 | `make eval` produce un `EvalRun` valido |
| E-04 | **Baseline A**: nessun retrieval, prompt permissivo | Risposte corrette / sbagliate / inventate |
| E-05 | **Baseline B**: nessun retrieval, prompt severo | Tasso di astensione |
| E-06 | **Baseline C**: solo retrieval lessicale | Delta contro il denso **per dataset**, e la configurazione è verificabilmente BM25: modificatore IDF attivo sull'indice, query codificate come query. *Aggiunto il 2026-08-11 e attualmente non soddisfatto*, vedi OQ-03 |
| E-07 | **Rumore di fondo**: 5 esecuzioni della stessa configurazione | Dispersione riportata. Nessuna differenza inferiore a questa soglia sarà mai dichiarata un miglioramento |

**Nota su E-02: è l'unica annotazione che dovete davvero fare, ed è quasi gratis.** I benchmark pubblici non contengono domande senza risposta, ma a voi servono per misurare l'astensione. Il trucco: prendete query del dataset A e ponetele contro il corpus del dataset B. Sono automaticamente non rispondibili, non richiedono scrittura manuale, e sono realistiche. Integratele con una decina scritte a mano su argomenti plausibili ma assenti.

**E-07 va eseguito prima di qualunque ablation.** I test preliminari hanno già mostrato che lo stesso modello sulla stessa domanda cambia risposta tra esecuzioni.

**Gate:** `make eval` gira end-to-end e produce le tre righe di baseline con barre d'errore, per dataset.

---

## 7. Fase 3: Retrieval e routing

**Durata: 2 settimane.** Un miglioramento alla volta, misura in mezzo, risultato committato.

| ID | Task | Criterio di accettazione |
|---|---|---|
| D-01 | **Dashboard interna Streamlit**: confronto EvalRun affiancati per dataset, inspector di chunk recuperati per query freeform | ≥ 2 EvalRun visualizzabili e confrontabili; inspector funziona su query libera contro entrambi i dataset |
| R-01 | Ibrido denso+sparso con fusione RRF | Delta contro baseline C, confrontato col rumore |
| R-02 | Reranker cross-encoder sui top-k | Delta misurato |
| R-03 | Riscrittura query | Delta misurato |
| R-04 | Filtri dalla query verso i metadati (dataset, tipo contenuto) | Delta misurato |
| R-05 | Aggregazione a livello documento per la lista file | Obiettivo distinto dal ranking dei chunk per il contesto |
| R-06 | **Routing automatico**: `doc_genre` → pipeline di ingestion | Ogni chunk porta `pipeline` valorizzato e coerente col proprio `doc_genre`, verificato su un campione. **Il valore non si misura qui ma in R-07** |
| R-07 | **Ablation del routing**: pipeline generica unica contro routing automatico | Delta **per dataset**, mai aggregato. È l'affermazione 2 del §0 |

**Il valore sta in R-07**, non in R-06. Il routing senza la misura del suo effetto è una funzionalità; con la misura è un risultato.

**Gate:** ogni riga della tabella ha un delta, un intervallo e un commento. I risultati negativi restano in tabella.

---

## 8. Fase 4: Citazioni verificate e scaling

**Durata: 1 settimana.**

| ID | Task | Criterio di accettazione |
|---|---|---|
| C-01 | Prompt con chunk numerati ed esempio del formato citazione | Formato §3.2 rispettato in ≥95% delle generazioni |
| C-02 | Parser + validazione + **riparazione** delle varianti note | Test sugli output malformati reali |
| C-03 | Verifica di entailment affermazione ↔ chunk citato (modello NLI in `STACK.md`) | `citation_precision` in tabella |
| C-04 | Astensione: soglia sui punteggi di retrieval **decisa dal codice** | Tasso di astensione corretta su E-02 |
| C-05 | Istruzione esplicita sulla lingua di output | Nessuna risposta mista incoerente su 20 campioni |
| C-06 | **Scaling**: stesso sistema su E2B, E4B, 12B, tutte le metriche + latenza + VRAM | È l'affermazione 3 del §0 |
| C-07 | Riga dedicata all'effetto del ragionamento esteso on/off | Misurato una volta sola, non per ogni configurazione |
| I-08 | **Misura** dei prefissi `query:`/`passage:` di E5 su un indice ridotto, senza re-ingestione | Delta appaiato su doc_R@5, o la sua assenza |
| I-10 | **Misura** del chunking contro la finestra da 512 token dell'embedder, sullo stesso indice ridotto | Delta appaiato su doc_R@5, **misurato separatamente da I-08** |
| C-08 | Premessa di entailment senza il markup delle tabelle OCR, e **rimisura** di `citation_precision` su LEDGER | Le due varianti affiancate sulle stesse generazioni. Chiude la decisione che il gate della fase rimandava |
| C-09 | **Verificatore numerico per il genere tabellare**: `numeric_citation_precision` | Riportata per LEDGER accanto a `citation_precision`, **mai nella stessa colonna**. Validata sul floor test di OQ-05 |

**Perché due task `I-` in questa fase.** Il prefisso indica di cosa parla il task, non in che fase sta (precedente: `D-01` in Fase 3). Entrambi i difetti sono nell'ingestione, ma stanno qui perché **decidono se C-06 può partire**: C-06 è la misura più cara del progetto e l'affermazione 3 del §0 dice *«con un buon retrieval»*. Lanciarlo su una premessa non verificata significa rischiare di rifarlo. I-08 e I-10 **misurano e basta** (le correzioni sono I-09 e I-11, in Fase 5), e vanno misurati **uno alla volta** (§15): vivono nella stessa funzione, `encode()`, e insieme darebbero un delta non attribuibile.

**I-10 è il più grande dei due.** Il tokenizer tronca a 512 token e le pipeline di chunking non lo sanno: il **67,6%** dei chunk di open_ragbench e l'**82,1%** di ledger lo superano, e del chunk mediano entra nell'indice **circa metà del testo**. Il testo intero arriva comunque all'LLM, quindi il sistema risponde su materiale che non ha potuto trovare. Protocolli e numeri in `docs/open-questions.md`, OQ-02 e OQ-04.

**Gate:** confronto sulle non rispondibili tra baseline A e sistema completo, e curva delle metriche in funzione della taglia del modello.

### Ordine di esecuzione (deciso il 2026-08-10, dopo C-03)

L'ordine non è quello della tabella, per la regola del §15. Il vincolo che lo determina: **C-06 rilancia l'intero sistema per ogni taglia di modello**, quindi ogni modifica al comportamento fatta dopo lo invalida.

1. **C-05** (cambia il prompt, e `prompt_hash` entra in `config_hash`): farlo dopo C-04 obbligherebbe a rimisurare C-04.
2. **C-04**: l'ultima modifica alla pipeline. C-03 gli ha già fornito i dati su cui tarare la soglia.
3. **E-04/E-05** (il gate della fase li richiede, e sono indipendenti dagli altri): si possono lanciare in parallelo.
4. **C-07**: una misura sola, non una per configurazione.
5. **I-10, poi I-08**, uno alla volta: vivono nella stessa funzione, `encode()`, e insieme darebbero un delta non attribuibile.
6. **C-08**, poi **C-09**: decidono se la riga LEDGER della curva di scaling dice qualcosa. Su LEDGER `citation_precision` non è interpretabile come proprietà del generatore: il verificatore NLI è fuori distribuzione su claim numerici contro tabelle OCR, e nessuno dei due lati della coppia somiglia a ciò su cui è stato addestrato. C-08 toglie il markup e rimisura; **solo se dopo il numero resta non interpretabile** si costruisce un verificatore diverso per quel genere (C-09): prenderla come una debolezza del modello, o costruire subito il secondo strumento, sarebbe stato decidere senza misurare.
7. **C-06**, per ultimo, ed è la misura più cara del progetto.

Come è andato ciascuno, e quali sono risultati negativi, sta in [`progress.md`](docs/progress.md).

---

## 9. Fase 5: Correttezza delle misure

**Durata: 2–3 giorni** (I-09 esclusa: se scatta, è una settimana).

**Questa fase non contiene miglioramenti.** Il §7 dice che i risultati negativi restano in tabella, e resta vero. Qui c'è la categoria che quella regola non copre: **misure la cui etichetta si è rivelata falsa.** Una riga della Fase 2 si chiama *«E-06, baseline C: retrieval lessicale BM25»* e quella misura non è BM25, non è un risultato negativo da conservare, è il risultato di un'altra cosa, e va rifatto.

Tutte e tre le voci nascono dall'audit del 2026-08-11, in cui le librerie sono state confrontate con la loro documentazione ufficiale. Il fatto, il protocollo e ciò che **non** è dimostrato stanno in [`docs/open-questions.md`](docs/open-questions.md).

| ID | Task | Criterio di accettazione |
|---|---|---|
| I-09 | ~~Prefissi E5 in `encode()`, re-ingestione, rimisura~~, **non applicabile**: era condizionata a I-08, risultato negativo | Vedi `docs/progress.md` e OQ-02 |
| I-11 | ~~Tetto di chunking allineato alla finestra dell'embedder~~, **decisa il 2026-08-12: non adottata** | Nessun effetto sulla generazione; il guadagno di `citation_precision` era la lunghezza della premessa. Da riconsiderare alla prossima re-ingestione per la latenza (−44%). Vedi `progress.md` |
| R-08 | `modifier=IDF` sull'indice sparso (Qdrant lo richiede: fastembed esclude l'IDF di proposito) | E-06 e R-01 rimisurati: **una sola causa cambiata** |
| R-09 | Query BM25 codificate con `query_embed` invece che come documenti | Rimisura **separata** da R-08 |
| R-10 | OQ-01, passi 1–2: perché il routing peggiora LEDGER di 17 punti | Il passo 3 (6–7 h GPU) solo se il 2 è positivo |
| R-11 | `SEARCH_EXACT` / `HNSW_EF` come parametri di ricerca: la ricerca approssimata perde richiamo dove l'indice è denso | Il parametro esiste ed è **spento di default**; acceso, entra nel `config_hash` e le run dense non si spostano |

**R-08 e R-09 non si fanno in un commit solo.** Sono due cause indipendenti (l'IDF vive nell'indice, la codifica della query nel client), e correggerle insieme misurando una volta viola il §15. Costa una rimisura in più: dieci minuti.

> **Cosa hanno comprato quei dieci minuti** (misurato il 2026-08-13): delle due correzioni una muove le metriche di parecchi punti e l'altra di quattro query su diecimila. Correggendole insieme il risultato sarebbe stato attribuito a «OQ-03», e la ripartizione (praticamente 100 a 0) non si sarebbe mai vista. La regola non è pignoleria contabile: è l'unica cosa che distingue una causa da una coincidenza. I numeri in [`progress.md`](docs/progress.md), R-08 e R-09.

**I-09 e I-11 invece condividono la re-ingestione, se scattano entrambe.** Non è un'eccezione al §15: l'attribuzione è già stata fatta a monte, da I-08 e I-10, che misurano una causa ciascuno su un indice ridotto. La re-ingestione completa non è la misura che separa le cause: è l'adozione di due correzioni già separate, e imporne due da 618 minuti ciascuna costerebbe venti ore di GPU per un'informazione già in mano.

**Ordine:** R-08, R-09, R-10 sono indipendenti da I-09 e si possono fare prima. I-09 è la sola che obbliga a rifare tutto ciò che sta sopra, quindi va per ultima.

**Gate:** ogni numero rifatto è affiancato al vecchio in `progress.md`, con detto **quale** delle due misure descriveva cosa. Nessuna riga sostituita in silenzio.

---

## 10. Fase 6: Qualità del codice

**Durata: 3–4 giorni.** Prima della Fase 7, perché il servizio si estrae **sopra** questi moduli: rifattorizzarli dopo significa cristallizzare i difetti dietro un'interfaccia, e poi rifarli due volte.

**Un refactor senza criterio di accettazione è illimitato**, ed è l'unica cosa in questo repo che non avrebbe un numero accanto. Quindi la fase non è "leggibilità e pulizia": è una lista chiusa di difetti già osservati, ognuno con la prova che esiste.

| ID | Task | Criterio di accettazione |
|---|---|---|
| Q-01 | Costruzione di `EvalRun` unificata: oggi sono **5 siti**, `reasoning_enabled` è derivato in 4 e ancora scritto `False` a mano in `src/eval/harness.py` | Un solo posto lo costruisce; il campo non è più scrivibile a mano |
| Q-02 | **Entrambi** gli harness senza dump per query (baseline **e retrieval**) salvano i risultati per query, come già fa quello delle citazioni | Il taglio 45%→17% di E-04/E-05 diventa un test appaiato; e un confronto fra due run di retrieval archiviate non richiede più di ricostruire uno stato a comando |
| Q-03 | `scripts/profile.py` non adombra più il modulo `profile` della standard library | `import transformers` da dentro `scripts/` smette di fallire |
| Q-04 | Igiene di import e lint su `scripts/` | `ruff check` pulito sul repo |
| Q-05 | La scelta del provider ONNX vive in **un posto solo**, e la dipendenza GPU è un extra opzionale di `pyproject.toml` | Nessun file di `src/` nomina `DmlExecutionProvider`; su una macchina senza DirectML l'import riesce e ripiega dichiarandolo |
| Q-06 | **Registro dei dataset**: i dataset disponibili si leggono da un posto solo, non da 14 liste `choices=[...]` scritte a mano | Aggiungere un dataset dello stesso genere richiede il suo loader e una riga nel registro; **nessuno script va toccato** |

**Ogni voce è un difetto che ha già morso**, non un'ipotesi di stile: **Q-01** è la stessa duplicazione che ha lasciato `reasoning_enabled=False` scritto a mano mentre il modello ragionava, e l'harness che ancora fa così *usa* il modello quando gira con `--query-rewrite`; **Q-02** ha costretto a rigenerare a mano risposte che le run non avevano salvato, e ha morso una seconda volta sulle run di retrieval archiviate, dove il confronto di R-08 poteva essere solo fra due medie; **Q-03** ha già rotto un import durante C-03; **Q-05** è la cucitura di U-12, e finché il blocco che sceglie il provider ONNX sta in cinque posti la portabilità Linux è cinque modifiche invece di una; **Q-06** è `choices=["open_ragbench", "ledger", "all"]` scritto a mano in **14 script**, mentre il nucleo è già agnostico: il coupling è tutto ai bordi, ed è anche ciò che serve a U-01 per cambiare dataset senza riavvio.

Le ultime due non sono un allargamento di comodo: Q-05 è il prerequisito della Fase 7 (un servizio che gira su un'altra macchina probabilmente gira su Linux), Q-06 è ciò che rende questo un *testbed* invece di un programma per due dataset.

**Ordine di esecuzione** (§15 chiede di deciderlo prima e di scriverlo):

**Q-03 → Q-06 → Q-04 → Q-05 → Q-01 → Q-02**

Il criterio è ridurre il lavoro rifatto, non la difficoltà crescente. Q-03 e Q-06 toccano entrambi tutti gli script, quindi vanno **prima** di Q-04: passare il lint su `scripts/` e poi rimescolarli significherebbe passarlo due volte. Q-05 è isolato e sta dove capita. Q-01 e Q-02 vanno per ultimi perché sono gli unici due che possono far muovere un numero, e conviene che il gate sia l'ultima cosa a essere messa alla prova invece che la prima.

**Gate, e non è negoziabile: nessuna metrica cambia.** Un refactor puro lascia invariato il conteggio dei test (§15) e lascia invariati i numeri: `scripts/rescore_citations.py` ricalcola le metriche di C-01 dai dump salvati a costo zero, e alla fine della fase deve restituire **gli stessi valori** già registrati. Se cambia un decimale, non era un refactor.

---

## 11. Fase 7: Servizio e API

**Durata: 1–1,5 settimane.** È la fase che rende il backend sostituibile dal frontend e viceversa, e che gli permette di girare su un'altra macchina. **Non è un ritocco**: è il lavoro architetturale più grande rimasto.

**Il confine, detto una volta.** Il backend espone HTTP; il frontend è un client come un altro. Chiunque può scriverne un secondo, o nessuno. La demo React della Fase 8 è **un** consumatore dell'API, non il suo scopo.

| ID | Task | Criterio di accettazione |
|---|---|---|
| A-01 | **Strato `src/service/`**: una funzione per caso d'uso, chiamata sia dalla CLI sia dall'API | Nessun endpoint contiene logica di pipeline. La stessa richiesta dalla CLI e dall'API produce lo **stesso** risultato, verificato da un test che le confronta |
| A-02 | **La configurazione di una richiesta smette di passare da `cfg` globale**: parametri di retrieval e generazione viaggiano nella richiesta | Due richieste concorrenti con configurazioni diverse non si contaminano: test con due `top_k` diversi in parallelo |
| A-03 | Il **contratto UI ↔ API** del §3.5 è implementato: schema delle risposte ed eventi dello stream | Ogni stato dell'interfaccia previsto in Fase 8 è rappresentabile nello schema, incluse «attendo i verdetti» e «il modello si è astenuto» |
| A-04 | Endpoint FastAPI: `/health`, `/datasets`, `/query` (SSE), `/chunk/{chunk_id}` | `docker compose up` e una query completa da `curl`, senza il frontend |
| A-05 | Backend come servizio in `docker compose`, con `QDRANT_URL` e `LLM_BASE_URL` da ambiente | Backend su una macchina, Qdrant e LLM su un'altra, senza modifiche al sorgente |
| A-06 | **La dashboard Streamlit passa dall'API** invece di eseguire la pipeline | Nessun modulo di `dashboard/` importa `src.index`, `src.retrieval`, `src.generation`, `src.service`, `src.config`, e nessuno apre un client Qdrant. Gli import rimasti sono **elencati con la loro ragione** in `tests/test_dashboard_boundary.py` |
| A-07 | **I tre buchi trovati disegnando la Fase 8**: lista modelli, `reasoning_effort` in richiesta, navigazione del corpus | Nessuna delle quattro schermate della bozza ha bisogno di una costante scritta a mano nel frontend né di una chiamata che non sia all'API. Le aggiunte sono **additive**: un client scritto contro A-04 continua a funzionare, verificato da un test che manda la richiesta minima `{"query": "..."}` |
| A-09 | **La finestra di contesto la imposta il motore**, e le taglie derivate smettono di essere il modo normale | `EvalRun.context_window` è la finestra **letta** da `/api/ps`, non la costante; `make dev` non crea più modelli e dice una riga quando la finestra attiva non è quella dichiarata; `model_sizes.py --pulisci` toglie in blocco ciò che il progetto ha creato, e solo quello |
| A-08 | **Il catalogo dei modelli**: `Capabilities` porta, accanto ai nomi, famiglia, **finestra massima** e quantizzazione di ciascuno | La coppia (modello, finestra) si legge dal server, **mai dedotta da un nome**, né nel frontend né dal nome della famiglia nel backend. Additivo: `models` resta `string[]` e un client scritto contro A-04 continua a funzionare |

**A-02 è il task difficile, ed è bene saperlo prima.** Gli harness leggono `cfg` globale: è ciò che ha permesso a R-11 di passare `SEARCH_EXACT` da variabile d'ambiente senza toccare una firma. Comodo per uno script, **impossibile per un servizio**: due richieste concorrenti con `top_k` diverso condividerebbero lo stesso modulo. Finché A-02 non è fatto, l'API è monoutente e non lo sa.

**A-08 (la finestra viaggia col nome del modello, e la coppia la risolve il server.** Deciso il 2026-08-19, dopo tre verifiche): `num_ctx` non è un campo del contratto OpenAI e mandarlo comunque ottiene 200 e nessun effetto; un `PARAMETER num_ctx` nel Modelfile invece funziona anche attraverso `/v1`; `/api/ps` non è interrogabile a servizio fermo. Ne segue la forma del task: chi guarda sceglie **modello e finestra separatamente**, e la traduzione fra quella coppia e il nome nel catalogo sta nel **server** (dedurla spezzando una stringa nel frontend sarebbe la quindicesima copia di Q-06, in TypeScript). Il catalogo si legge **per pattern** (`*.context_length`), quindi vale per qualunque famiglia arrivi domani, e porta anche la quantizzazione: `LLM_QUANTIZATION` era una costante vera per coincidenza, come `context_window` e `reasoning_enabled` prima di lei. Chiude **D-14**. Misure in [`progress.md`](docs/progress.md), A-08. **Rivisto da A-09** il 2026-08-24: la traduzione fra coppia e nome resta valida, ma smette di essere il modo *normale* di impostare la finestra.

**A-09 (la finestra viaggia col motore, non più col nome del modello.** Deciso il 2026-08-24, e non ribalta A-08): rimisurato lo stesso giorno, `/v1/chat/completions` continua a non avere un campo per la finestra, e la PR che glielo aggiungeva è stata **chiusa dai maintainer** («non segue la spec di OpenAI»). Quello che A-08 non aveva considerato è `OLLAMA_CONTEXT_LENGTH`: **misurata funzionante attraverso `/v1` su un modello base**, server di prova su :11435, `gemma4:e2b`, `ollama ps` → CONTEXT 32768. Il costo di non averla vista era tutto sulla macchina di chi prova il progetto: `--assicura` girava a ogni `make dev` e lasciava **22 modelli derivati su 30 voci** in `ollama list`, che Ollama non sa nascondere (chiesto tre volte, mai implementato) e che a occhio sembrano duecento GB di roba altrui (i blob sono condivisi, ma la lista ripete la taglia del modello base a ogni riga).

> **E ha scoperto una cosa peggiore del disordine.** Senza quella variabile Ollama sceglie la finestra **da sé**, fra 4k, 32k e 256k, in base alla memoria: su questa macchina dà 32768 (cioè le run di valutazione giravano col numero giusto **per fortuna**, non per costruzione), e su una macchina più piccola darebbe 4096, dove cinque chunk non entrano. Il risultato avrebbe continuato a dichiarare `context_window: 32768`. È esattamente **D-14**, che ora chiude: la finestra si legge da `/api/ps` e finisce nel JSON **misurata**. Resta scoperta una metà sola, ed è una scelta di contratto: il file non distingue «32768 misurato» da «32768 creduto», e distinguerli vuol dire aggiungere un campo a `EvalRun`.

> **Le taglie derivate non spariscono, cambiano ruolo.** Restano l'unico modo di rendere la finestra **scegliibile** (U-16), quindi restano: sotto il namespace `ibid/`, che è la sola cosa che Ollama offra per dire «questi sono di un programma», e opt-in. Il secondo selettore scompare da sé quando la finestra è una sola: è il comportamento già documentato per un motore che non è Ollama, e ora è anche quello del percorso normale.

**A-06 è la verifica, non un extra.** La dashboard importa `src.` in **9 moduli, 22 volte**: è il consumatore più esigente che esista già. Se l'API le basta, basterà anche al frontend, e se non le basta, si scopre ora invece che a React scritto. Se dovesse rivelarsi sproporzionata, va **rimandata dichiarandolo**, non silenziosamente omessa: senza, il confine è affermato e non provato.

> **Il criterio in tabella è stato riscritto eseguendolo** (2026-08-14). Era `grep -r "^from src\." dashboard/`, cioè un proxy: troppo largo (catturava la lettura di `eval/results/`, che sono file sul disco della dashboard e non stanno dietro nessun endpoint), e troppo stretto, perché non vede un import annidato dentro una funzione, che è dove `state.py` teneva il proprio client Qdrant. Il criterio nuovo dice la cosa che il vecchio approssimava: **la dashboard non deve *eseguire* la pipeline.** Com'è andata sta in [`progress.md`](docs/progress.md), A-06.

**A-07 è lo stesso meccanismo una seconda volta** (2026-08-14), e questo dice qualcosa che va scritto: A-06 ha esercitato *un* consumatore, non tutti. La bozza d'interfaccia della Fase 8 (quattro schermate disegnate prima di scrivere React) ne ha rivelati altri tre.

| serve a | manca | perché non si può aggirare |
|---|---|---|
| il menu dei modelli | `models` in `Capabilities`, dal proxy di `GET {LLM_BASE_URL}/v1/models` | il browser **non deve parlare con Ollama**: può non raggiungerlo, e §STACK impone che l'inferenza passi da `LLM_BASE_URL`. Una lista di modelli scritta a mano nel frontend è la lezione di Q-06 che si ripete |
| il toggle «Ragionamento» | `reasoning_effort` in `QueryRequest` | `ConfigView` lo **restituisce** già ma la richiesta non lo accetta: si può vedere quale ha girato, non sceglierlo. È l'asse che C-07 misura, e la UI non può toccarlo |
| sfogliare il corpus | `GET /documents` e `GET /document/{doc_id}/chunks` | c'è `/chunk/{id}` (uno, per id) e `/retrieve` (per query): non c'è modo di **navigare**. Senza, l'esploratore può solo cercare, mai mostrare come un documento è stato spezzato, cioè non può rendere visibile il routing, che è U-05 |

**Perché sta in Fase 7 e non in Fase 8.** La Fase 8 dice «il frontend non importa niente da `src/`»: queste sono modifiche a `src/api/` e `src/service/`, e metterle dentro un task U-xx sarebbe la prima violazione di quella regola il giorno dopo averla scritta.

**Nessuna tocca il contratto esistente**, ed è il criterio: due campi additivi e due endpoint nuovi. La regola inversa (cambiare la forma di ciò che è già stato prodotto) è quella che ha reso caro il §3.2.

**Cosa questa fase NON fa**, e la lista è vincolante quanto quella sopra: nessuna astrazione del vector store, nessun harness a plugin, nessuna coda di messaggi, nessuna autenticazione, nessun multi-tenancy. Le ragioni stanno in §14: sono la stessa decisione che ha tenuto fuori LangChain.

**Gate: nessuna metrica cambia, e la CLI continua a funzionare identica.** `scripts/rescore_citations.py` deve restituire gli stessi valori registrati, e ogni script di `scripts/` deve girare come prima. Se l'API esiste ma la CLI si è rotta, non è stato estratto un servizio: è stato riscritto il programma.

---

## 12. Fase 8: Interfaccia

**Durata: 1 settimana.** Da qui il progetto è completo e presentabile. Costruita **sopra** l'API della Fase 7: il frontend non importa niente da `src/`.

| ID | Task | Criterio di accettazione |
|---|---|---|
| U-00 | **Scheletro**: Vite + React + TypeScript, client SSE scritto a mano, temi chiaro/scuro, i18n IT/EN, `/datasets` all'avvio | I tipi del contratto sono **generati** da `src/api/`, non riscritti a mano: la suite Python fallisce se divergono. Nessuna costante del backend vive nel frontend |
| U-01 | **Selettore dataset**: demo / principale / secondo genere | Cambio dataset senza riavvio |
| U-02 | Nessun selettore di modalità: lista documenti sempre visibile, risposta sintetica sopra | La lista documenti è visibile senza interazione in ogni stato dell'interfaccia |
| U-03 | **La barra di composizione e il confronto affiancato**: toggle RAG, toggle «Ragionamento», menu dei modelli, «Avanzate» chiuso; stessa query, risposta nuda contro risposta con citazioni, affiancate | Generate dalla stessa query nella stessa sessione. Nessun controllo della barra gira a vuoto: ognuno manda il proprio campo di `QueryRequest`, e i parametri sotto «Avanzate» ricompaiono in «Dettagli della run» come quelli che hanno girato davvero |
| U-04 | Toggle del prompt del baseline: permissivo / severo | Mostra la differenza tra invenzione e astensione |
| U-05 | Indicatore della pipeline usata per il documento recuperato | Rende visibile il routing |
| U-06 | Link profondi dalle citazioni; dove ci sono i PDF, PNG di pagina con span evidenziato | Da una citazione si raggiunge la pagina della fonte. L'overlay bbox resta scoperto finché I-06 è rinviato: dichiararlo, non simularlo |
| U-07 | Le citazioni non verificate sono marcate visivamente, non nascoste | Una citazione non verificata da C-03 è distinguibile da una verificata senza aprire nulla, e nessuna delle due è nascosta |
| U-08 | ✅ **Fatto il 2026-08-27** (dettaglio in `progress.md`), con dentro **D-21**: `docker compose --profile demo up` porta su Qdrant, l'indice ridotto e l'API che serve anche l'interfaccia, in **17,9 secondi** con l'immagine gia' costruita (il criterio dice due minuti), di cui 3,7 per caricare l'indice. `data/demo/` sono **1.758 chunk** (658 di `open_ragbench`, 1.100 di `ledger`) e ~21 MB, ~10 in git. **I vettori sono copiati, non ricalcolati**: `build_demo_index.py` li legge dall'indice completo, perche' un ritaglio riembeddato darebbe punteggi *simili*, e il margine con cui il terzo esempio di `ledger` chiude il gate e' +0,0078, meno di quanto una versione diversa di `onnxruntime` sposti uno score. L'unita' di selezione e' il **documento** e non il chunk, altrimenti l'esploratore di A-07 mostrerebbe documenti bucati. **I sei esempi passano anche sull'indice ridotto**, e i due gate si chiudono piu' larghi (+0,0452 contro +0,0227, +0,0199 contro +0,0078): con meno concorrenti il punteggio migliore e' piu' basso. La demo **dichiara di essere una demo**: il caricamento lascia la collection `ibid_demo` col manifesto, `/datasets` riporta `ridotto`, e l'interfaccia lo scrive nello stato vuoto e nella tendina. Due difese contro il guasto peggiore (scrivere sopra l'indice vero): un Qdrant suo con volume suo, e il caricamento che rifiuta una collection senza cartellino. **Arriva qui anche la decisione scritta sotto U-09** (uno stadio Node costruisce `ui/dist` e l'API lo serve dalla stessa origine): senza, il profilo avvierebbe un'API e nessuna interfaccia. *Testo originale:* Profilo `demo` con indice committato |
| U-09 | ✅ **Fatto il 2026-08-28** (dettaglio in `progress.md`). Cio' che restava era il primo avvio su una macchina che non avesse mai costruito l'immagine, ed e' stato fatto su una **Arch mai vista dal progetto**: `docker compose --profile demo up` ha costruito, seminato 1.758 chunk in 1,2 s e servito la pagina, **senza una modifica al sorgente**. Il resto (immagine unica, due profili, healthcheck, `ui/dist` dalla stessa origine) era arrivato con U-08. *Testo originale:* Profili `full` e `eval`, healthcheck, `depends_on: service_healthy` |
| U-10 | ✅ **Fatto il 2026-08-26** (dettaglio in `progress.md`): **due GIF da 18,3 e 23,5 secondi**, insieme meno della meta' del tetto, in italiano e in inglese e **in tema scuro** (`docs/demo.gif` in cima e `docs/fonte.gif` in «Come funziona», 8,8 MB la coppia, **a dimensione nativa 1280x800 e 256 colori**: ridurle a 1000 px ricampionava ogni lettera, ed era cio' che le faceva leggere come compresse). **Sono due ritagli di una ripresa sola** e non due riprese: la seconda partirebbe altrimenti da una risposta gia' pronta, cioe' mostrerebbe la schermata senza l'attesa che l'ha prodotta. Non e' una ripresa a mano: `npm run video` guida il browser vero con Playwright, aspetta **gli eventi dell'interfaccia e non dei secondi**, e la registrazione resta aperta dal primo clic all'ultimo, **senza montaggio**. Il solo taglio dentro il copione e' il confine fra le due GIF; in testa si toglie il caricamento dell'applicazione, cercando nei fotogrammi il primo diverso da quello di attesa. **Il video riceve un fotogramma solo quando la pagina ne dipinge uno**, quindi un'interfaccia carica e ferma non ci comparirebbe affatto: la pausa d'apertura muove il puntatore di un pixel per battito, e tanto basta. **La trappola era la cache del prefill**: la stessa domanda ripetuta scendeva da 16,9 a 3,9 secondi, e la ripresa avrebbe scritto «generation 3,91 s» a schermo senza tagliare un fotogramma; lo script scarica il modello e lo ricarica con un'altra domanda, e i tempi mostrati sono 0,20 / 7,77 / 0,82 / **8,80 s**. Con lo stesso copione, `--scatto` produce la **schermata** che U-11 aveva lasciato indietro. `scripts/video_gif.py` fa la GIF con Pillow, perche' l'ffmpeg di Playwright non ha un encoder GIF. *Testo originale:* GIF o video di 90 secondi nel README |
| U-11 | ✅ **Fatto il 2026-08-25** (dettaglio in `progress.md`): `README.md` in italiano e `README.en.md` accanto, 237 righe ciascuno, con rimando reciproco in cima. Le tre affermazioni hanno ognuna la propria tabella per dataset, e la seconda porta ❌ nel titolo accanto ai due ✅: **il criterio chiedeva due cose che sono la stessa cosa** (l'affermazione 2 *è* un risultato negativo, e tenerla nei limiti invece che nel corpo l'avrebbe nascosta rispettando la lettera). **Nessuna riga aggregata fra i due corpus in tutto il documento**, e dove servirebbe una conclusione unica il testo dice che non esiste. L'avvio descrive ciò che parte oggi, con una nota sola sul profilo `demo` di U-08. **Lo screenshot e' arrivato con U-10** il 2026-08-26 (`docs/screenshot.png` e la sua gemella inglese, prese dallo stesso copione fermato a risposta verificata). **Resta fuori** la descrizione «About» del repo (§1), che si imposta su GitHub. *Testo originale:* README: le tre affermazioni del §0, architettura, tabelle per dataset, screenshot, limiti, future work |
| U-12 | ✅ **Fatto il 2026-08-28** (dettaglio in `progress.md`), con dentro **D-10**. Criterio chiuso in tutti e due i punti: **1.814 test verdi** su Arch (Python 3.14) e 1.808 nell'immagine (Python 3.12), e `docker compose --profile demo up` che parte su una macchina vergine, **senza modifiche al sorgente**. `src/` non aveva assunzioni su Windows: i guasti erano tutti nell'impacchettamento e nella scelta del provider, e sono stati trovati facendo girare le istruzioni su macchine vere invece di rileggerle. Otto, in ordine di comparsa: su Debian/Ubuntu il passo 2.1 non si esegue (niente pip, niente `python3-venv`, PEP 668); `pytest` e `ruff` stavano in `[tool.uv] dev-dependencies`, che pip ignora; `docker compose` e' un pacchetto separato su Arch; `pip install -e ".[gpu-rocm]"` installa **due** distribuzioni di `onnxruntime` e disinstallarne una lascia un modulo vuoto che si importa (**consiglio mio, e ha rotto l'installazione di Marco**: la riparazione e' `--force-reinstall --no-deps`); il pacchetto ROCm di Arch offre MIGraphX e **non** `ROCMExecutionProvider`; quel provider si lega e poi l'inferenza muore se `model.onnx_data` non e' nella CWD; la prima cosa che un estraneo vedeva dopo il recupero era `URLError: <urlopen error [Errno 111] Connection refused>` invece di una frase; e la demo **sopravviveva a un riavvio della macchina**, perche' ereditava `restart: unless-stopped` da un'ancora pensata per il servizio. *Testo originale:* **Portabilità Linux**: provider ONNX scelto dalla piattaforma, dipendenze GPU come extra opzionali, nessun percorso che assuma Windows |
| U-13 | **Conversazione nuova e cronologia locale**: pulsante «Nuova conversazione», elenco delle conversazioni nella corsia, persistenza in `localStorage` | Si comincia una conversazione nuova senza ricaricare la pagina, e la cronologia sopravvive a un ricaricamento **dichiarando** di essere locale a questo browser. Nessun endpoint, nessuna sessione lato server |
| U-14 | **Markdown e LaTeX nella risposta**: il prompt li **invita** invece di vietarli, e l'interfaccia li disegna | Ciò che il modello formatta si legge formattato, in tutte e due le colonne del confronto. I marcatori di citazione, i verdetti per frase e le frasi scoperte restano allineati al testo grezzo: il markdown è **decorazione su intervalli**, non un testo riscritto |
| U-15 | **Con quali parametri è stata data ogni risposta**: la configurazione che ha girato si rilegge nella conversazione, e fra una domanda e l'altra si vede **cosa è cambiato** | Riaprendo una conversazione si sa con quali parametri ogni risposta è stata prodotta, senza aprire niente. Nessun campo nuovo nel contratto né nel deposito: `ConfigView` è già dentro ogni risposta, e ciò che manca è mostrarlo |
| U-16 | **Modello e finestra di contesto, due selettori**: si scelgono separatamente, e le finestre offerte sono solo quelle compatibili col modello scelto | Chi guarda sceglie due cose, non un nome di catalogo. Nessuna convenzione di nomi nel frontend: la coppia arriva da `Capabilities` (A-08). Una finestra che quel modello non regge **non compare**, invece di comparire e fallire |
| U-17 | **Il testo indicizzato**: il documento in fila nella colonna di mezzo, accanto alla mappa, con le cuciture fra un chunk e l'altro visibili | Si legge il documento intero e si vede **dove sono caduti i tagli**, con la stessa selezione della mappa. Ciò che si mostra è il testo **come è stato indicizzato**, non il documento: nell'indice generico i chunk lo partizionano esattamente (misurato: zero sovrapposizioni), in uno instradato no, e in quel caso la vista lo deve dichiarare invece di ripetere il testo condiviso |
| U-18 | **La corsia si comprime**: la colonna di sinistra si riduce a una striscia e torna, e la scelta si ricorda | A corsia chiusa **nessuna funzione sparisce** (nuova conversazione, cronologia, dataset ed esploratore restano raggiungibili), e la colonna di lavoro guadagna davvero lo spazio, invece di lasciare una traccia vuota nella griglia. La scelta sopravvive al ricaricamento, come le larghezze dell'esploratore (U-17) |
| U-19 | **La pagina «Che cos'è»**: cosa fa il progetto, le tre affermazioni del §0 e i limiti | Raggiungibile dalla corsia, in IT/EN come tutto il resto. **Nessuna metrica scritta a mano nel frontend**: i numeri che mostra sono quelli del README e vengono da una fonte sola, oppure non ci sono. Dice anche cosa la demo *non* è: quale modello ha risposto e su quale corpus |
| U-20 | **L'avvio guidato**: si salta, e chi l'ha già fatto non lo rivede | Si salta con **un comando solo**, non torna dopo un ricaricamento, e **non impedisce di fare la prima domanda** mentre è aperto. Dichiara di essere locale a questo browser, come la cronologia di U-13 |
| U-21 | **Il telefono**: l'interfaccia regge una larghezza da telefono | A **390 px** si fa una domanda, si legge la risposta coi verdetti e si apre una fonte, **senza scorrimento orizzontale**. Il criterio di U-02 vale anche lì: la lista documenti resta raggiungibile in ogni stato (raggiungibile, non necessariamente affiancata) |
| U-22 | ✅ **Fatto il 2026-08-26** (dettaglio in `progress.md`): `docs/technical.md`, 907 righe, undici sezioni: le prime cinque nell'ordine del lavoro (cosa serve, installazione, indice, misura), le altre sei da consultare (metriche, contratti, architettura, estensione, guasti, dove sta il resto). **Il criterio ha deciso il metodo**: ogni comando è stato eseguito prima di essere scritto, e le tabelle riportano ciò che ha stampato. Le due run dense complete riproducono **a quattro decimali** le cifre del README (ORB nDCG@10 0,7184 in 56 s; LEDGER 0,2465 in 2 min 52 s), e ogni passo di installazione porta il proprio controllo con l'output atteso. La pagina dice una cosa che il README non poteva dire: **quasi tutto si riproduce senza GPU**, perché i dump per query e quelli di generazione sono committati. **Eseguire il passo due ha rotto Qdrant**: il pin `v1.12.4` di `compose.yml` non sa leggere uno storage scritto dalla `v1.19.0`, difetto vero corretto a parte, ed è esattamente il tipo di cosa che questo criterio esiste per far emergere prima del lettore. **Non ripete i risultati**, che restano nel README: due copie degli stessi numeri divergono al primo aggiornamento. *Testo originale:* **La documentazione tecnica**: architettura, contratti, come si riproduce una misura |
| U-23 | ✅ **Fatto il 2026-08-23** insieme a **D-17**: la forma resta quella di oggi (due a cui il corpus può rispondere e una fuori dal corpus), e di ciascuna è registrato **cosa deve succedere**, nel file accanto alla domanda. La verifica è `scripts/verify_esempi.py`, rieseguibile, e va rilanciata a ogni cambio di indice, embedder o default del recupero: **OQ-09 ha mostrato che l'indice cambia anche da solo**. Vincola U-08, il cui indice ridotto deve contenere i sei `chunk` dichiarati |
| Q-07 | ✅ **Fatto il 2026-08-25** (dettaglio in `progress.md`): lista di **sette** difetti scritta e committata prima di aprire un file. Cinque saldati; **due si sono dissolti al contatto col codice** e il perché è registrato: i «27 export morti» erano 23 firme pubbliche più tre, e le due tabelle non sono la stessa cosa. Su mandato allargato di Marco (*«pulito sia per capirlo che per complessità vera e propria»*) se ne sono aggiunte **tre fuori lista**, dichiarate come tali: l'invariante di concorrenza degli stream scritto tre volte, le due pagine a schermo intero duplicate, e la forma dei comandi di corsia scritta quattro volte. Gate rispettato in tutt'e due i versi: **355 → 365** test Vitest, e il CSS costruito è **byte per byte lo stesso di `main`** (Tailwind genera il foglio leggendo le stringhe di classe, quindi due fogli identici sono due insiemi di classi identici). Ne è nato **D-22**. *Testo originale:* **Lista chiusa di difetti scritta prima di toccare un file**, ognuno con la prova che esiste: è la regola con cui la Fase 6 si è tenuta finita. Gate: il numero di test Vitest **non cala** e nessuna schermata cambia comportamento |

**U-03 è la feature che fa capire il progetto a chiunque**, ed è quasi gratis: i baseline li state già calcolando in Fase 2.

### U-00: la regola «niente import da `src/`» ha un prezzo, e si paga una volta

«Il frontend non importa niente da `src/`» è la regola giusta: un frontend che importasse la pipeline non ne sarebbe un consumatore, sarebbe un secondo posto in cui la pipeline vive. Ma ne segue che **il contratto del §3.5 esiste in due linguaggi**, e due elenchi scritti a mano divergono: è la lezione di Q-06, in TypeScript. Peggio: la seconda copia diverge *in silenzio*, perché nessun test Python guarda dentro `ui/`.

Quindi `ui/src/api/types.ts` non si scrive, **si genera** da `scripts/gen_api_types.py`, e `tests/test_ui_types.py` fallisce se il file committato non è ciò che il generatore produce oggi. Gli eventi SSE non sono modelli pydantic (`to_wire()` costruisce i payload a mano) quindi il generatore non li legge, li **esegue**: i nomi dei campi vengono dal dizionario che finisce davvero sul filo.

### Decisioni d'interfaccia

Ricavate disegnando quattro schermate prima di scrivere React (2026-08-14) e precisate eseguendo i task. Quelle che vincolano l'implementazione, non l'estetica; come sono state applicate sta in [`progress.md`](docs/progress.md).

**La lingua della risposta segue il prompt, non l'interfaccia.** Il selettore IT/EN traduce la cornice: etichette, avvisi, nomi degli stati. Non tocca il testo del modello, gli estratti dei chunk né i messaggi di errore del backend: quelli seguono la lingua della domanda e del corpus. La ragione non è di comodità: far rispondere in italiano su un corpus inglese significherebbe che le citazioni sostengono un testo **tradotto**, e il verificatore NLI di C-03 dovrebbe giudicare cross-lingua un'implicazione che non ha mai misurato in quella condizione. La precisione di citazione è la prima affermazione del §0; non si baratta con una comodità di presentazione.

> **Le query d'esempio sono il caso intermedio, e si risolve mostrando entrambe.** Si leggono nella lingua dell'interfaccia, ma partono in quella del corpus: sotto la traduzione compare la query vera, in mono (il ruolo dei dati, e quella è letteralmente ciò che finisce sul filo). Tradurre anche il testo mandato riporterebbe esattamente il problema di sopra, con l'aggravante che sarebbe il **primo clic** di chi prova il progetto a produrlo.

**Il pannello fonti si apre su `chunks`, non a risposta finita.** Il criterio di U-02 dice «visibile senza interazione in ogni stato», e il protocollo del §3.5 manda `chunks` **prima** del primo token. Le fonti compaiono in ~0,1 s e il testo comincia a ~3 s: l'attesa si riempie invece di premiare, e si vede da dove nasce la risposta mentre nasce.

**U-03 è un layout, non un toggle.** «Affiancate, dalla stessa query, nella stessa sessione» non si ottiene con due messaggi consecutivi in cronologia. Il toggle RAG decide il default della prossima domanda; il confronto è un'azione esplicita su una risposta già data, che la rilancia col RAG invertito e mette le due in due colonne. Il selettore permissivo/severo di U-04 vive **dentro** la colonna senza fonti, l'unico posto dove ha effetto. Il secondo braccio riparte dalla configurazione **che ha girato**, non dalla barra: è il §15 dentro l'interfaccia, e rilanciare con le opzioni correnti metterebbe nelle due colonne anche un modello diverso o un `top_k` cambiato nel frattempo.

> **La barra intera è U-03 (2026-08-19).** Il mockup mette cinque controlli sotto il campo (RAG, «Ragionamento», il modello, il prompt del baseline, «Avanzate»), e solo due avevano un ID. Gli altri tre stavano nel disegno, in queste decisioni e persino nell'API, in nessun posto con un criterio: cioè la situazione della cronologia prima che diventasse U-13, e **una decisione senza task è la definizione di ciò che non viene fatto**. Vengono qui perché la barra la costruisce U-03, che è il primo che ne ha bisogno.

> **Due di quei controlli portano un argomento, non solo un campo.** Il menu dei modelli è l'**affermazione 3 del §0** resa toccabile: cambiare taglia sulla stessa query, col confronto affiancato lì accanto. Resta **vuoto** quando l'endpoint dei modelli non risponde, invece di mostrare quello configurato: elencarlo affermerebbe che esiste, che è esattamente ciò che non si è potuto verificare (A-07). Il toggle «Ragionamento» ha il problema opposto: accende una cosa che **C-07 ha misurato come risultato negativo**, quindi il suggerimento porta quei numeri. È l'unico comando dell'interfaccia che dichiara il proprio costo, ed è giusto che sia questo: il progetto misura anche ciò che non funziona, e nasconderlo dietro un interruttore muto sarebbe la prima volta che una misura resta fuori dalla UI perché è scomoda.

**Ogni controllo si apre sul valore in vigore, e niente della barra si ricorda oltre la sessione.** I valori li pubblica il servizio (`GET /config`): preselezionare il primo dell'elenco delle capacità scriverebbe sopra la scelta del deployment una scelta che nessuno ha fatto. E il dataset è una preferenza, mentre «RAG spento, prompt permissivo, `top_k` 20» è un esperimento: ritrovarlo impostato domani è il modo in cui un risultato si legge come il prodotto.

**L'esploratore del corpus non è la dashboard.** Vincolo di CLAUDE.md: due UI separate, non fuse. La dashboard confronta configurazioni di retrieval e fa failure analysis: serve a chi misura. L'esploratore mostra **il corpus e come è stato spezzato**: è ciò che rende visibile il routing (U-05) a chi non sa cosa sia un nDCG. Se diventa un confronto A/B di configurazioni, le due UI sono state fuse per sbaglio.

**Lo stream non si legge con `EventSource`.** `/query/stream` è una `POST` e l'`EventSource` del browser fa solo `GET`: serve `fetch` + `ReadableStream` con un parser SSE scritto a mano. Accettare anche `GET` costringerebbe a serializzare quindici parametri in query string, non si fa. Conseguenza voluta: niente riconnessione automatica, che rilancerebbe una generazione da 11 s e produrrebbe una risposta **diversa**. Su caduta si mostra il parziale marcato incompleto, con un «Riprova» esplicito; serve un `AbortController` anche per il pulsante «Ferma».

**La cronologia vive nel browser** (`localStorage`), nessun endpoint, nessuna sessione: non c'è autenticazione né database nello stack, e §14 li tiene fuori. Va **detto** nella UI, non lasciato dedurre: chi cambia macchina non ritrova le sue conversazioni. Cronologia non significa multi-turno: ogni domanda resta indipendente, e riusare i messaggi precedenti per il retrieval è **X-02**.

**I verdetti non si distinguono solo per colore**: glifo, colore e parola insieme. E il «non sostiene» non è rosso: U-07 dice che non è un errore da nascondere, è il dato. La ragione non è di stile: chi non distingue l'ocra dal verde vedrebbe due pastiglie identiche, e qui la differenza fra le due **è la tesi**. Dove i verificatori sono due (l'NLI di C-03 e il numerico di C-09) si mostrano **entrambi**: sceglierne uno in codice sarebbe decidere quale ha ragione, e quella è una misura, non un `if`.

**Il modello è invitato a formattare, e l'interfaccia lo disegna** (deciso il 2026-08-19, U-14). Fino a lì il prompt imponeva prosa piana, ma la sceglieva perché era ciò che l'interfaccia sapeva disegnare, e col divieto attivo da un lato solo le due colonne di U-03 differivano **anche** per il formato, cioè la seconda variabile che il §15 vieta. Il testo grezzo resta il sistema di coordinate: i verdetti per frase arrivano come intervalli su ciò che il modello ha scritto, quindi il markdown si applica **come decorazione su intervalli** e non come testo riscritto. Il debito che ne segue è dichiarato in **D-3**: `prompt_hash` è cambiato, e le run di citazioni a disco valgono per un prompt che non è più quello in vigore.

**I parametri di retrieval stanno sotto «Avanzate»**, chiusi. Un muro di manopole mostra l'ablation, che è il lavoro della dashboard. Restano sempre leggibili in «Dettagli della run», così la configurazione che ha girato non è mai un mistero.

### Il riferimento visivo è vincolante

[`docs/ui-mockup.html`](docs/ui-mockup.html) non è un'illustrazione: è dove palette, tipografia e forme sono state decise, e ogni task U-xx ne eredita i token invece di sceglierne di propri. Tre cose in particolare non si cambiano senza dirlo:

- **inchiostro indaco su carta**: accento `#3C4CA8` chiaro / `#97A5F7` scuro, carta `#F7F7F5` / `#131421`. La carta scura è indaco profondo e non grigio neutro: è la stessa tinta dell'accento portata al fondo della scala, ed è ciò che tiene insieme i due temi invece di farli sembrare due progetti;
- **tre ruoli tipografici veri**, e la distinzione non è decorativa: **serif** per il marchio e i titoli (il nome viene da *ibidem*, e la grazia appartiene al mondo bibliografico da cui arriva), **sans** per ciò che si opera, **mono** per i dati (`chunk_id`, marcatori, punteggi, etichette). Tutti font di sistema: U-08 chiede il profilo `demo` senza rete;
- **il marchio** `ib`·`i`·`d` con la **`i` centrale in accento**, serif, weight 600. L'accento della `i` è il token `--marchio`, non `--accent` crudo: su carta chiara l'accento pieno e l'inchiostro sono due scuri quasi uguali di valore e la lettera legge come nera, quindi il token tiene in ciascun tema la variante che si allontana di più dall'inchiostro (resta uguale **l'effetto**, non l'esadecimale). Quella lettera è il punto in cui *ibidem* si lascia intravedere: è l'unica parte dell'interfaccia che spiega il proprio nome senza una nota.
- **i simboli si disegnano, non si scrivono.** Niente glifi di font (`▾`, `↑`, `☾`): il punto precedente impone font di **sistema**, e lì quei caratteri arrivano sottili, più piccoli della loro dimensione nominale e diversi su ogni macchina, a 12 px spariscono. L'insieme sta in `ui/src/ui/Icona.tsx` e ha cinque regole: griglia unica `0 0 16 16`, solo tratto (l'unica eccezione è «sistema», dove il contrasto pieno/vuoto **è** il significato), spessore 2 che scala con la dimensione, estremità e giunti tondi, `currentColor` sempre. Un'icona nuova che le rispetta appartiene all'insieme senza doverla confrontare con le altre.

`ok` / `warn` / `wait` restano separati dall'accento: un verdetto colorato con l'accento smette di essere un verdetto e diventa decorazione. E il **rosso** (`danger`) vale per ciò che distrugge e per niente altro: colorare «cancella la cronologia» con l'ocra dei verdetti darebbe lo stesso segnale a un rilievo e a un'azione irreversibile; se un giorno comparisse su un verdetto, la domanda da farsi è cosa è cambiato nella tesi del §0.

**Le query d'esempio dello stato vuoto vincolano U-08.** Tre esempi, uno per affermazione del §0, così che la demo *sia* l'argomento invece di illustrarlo, e il video di U-10 abbia già il suo copione. Ma nel profilo `demo` l'indice contiene solo i chunk d'oro di ~30 query: se gli esempi non sono **quelle**, il primo clic di chi prova il progetto finisce in un'astensione. I due task si decidono insieme, e **D-17** è la prova che il vincolo era reale.

### Come si avvia, oggi e alla fine

Due comandi diversi per due destinatari diversi, e confonderli è ciò che rende un progetto difficile da provare.

| | comando | cosa serve prima |
|---|---|---|
| **chi tocca il codice** | `make dev` | Node, e Docker acceso. Qdrant lo avvia lui se è fermo; senza Ollama parte lo stesso e lo **dice** |
| **chi vuole solo vederlo** | `docker compose --profile demo up` (U-08) | Docker, e basta |

`make dev` avvia l'API, **aspetta** che risponda, poi avvia Vite; chiudendo si porta via entrambi. L'attesa non è cortesia: senza, il primo `/datasets` parte contro una porta chiusa e la pagina si apre già in stato di guasto, che chi guarda legge come un bug del frontend.

Controlla anche i servizi, e **non allo stesso modo**: senza indice non funziona niente, quindi Qdrant viene avviato e l'avvio si ferma se non ci riesce; senza modello invece si sfoglia il corpus, si cambia dataset e il recupero risponde: cade solo la generazione, quindi Ollama è un avviso e non un blocco. Trattarli uguali impedirebbe di lavorare sull'interfaccia mentre la GPU è occupata da una valutazione, che è metà del lavoro di questa fase. **Docker Desktop non lo apre**: è un'applicazione con interfaccia, ci mette un minuto, e il comando per avviarla è diverso su ognuno dei tre sistemi che U-12 vuole supportare.

**Nella consegna il proxy non esiste.** Il frontend viene costruito (`vite build`) dentro l'immagine con uno stadio Node, e **l'API serve `ui/dist` come file statici**: stessa origine, un container in meno, e soprattutto la ragione per cui il backend non ha CORS smette di essere un'aspirazione e diventa vera. È una decisione di U-09, e va scritta ora perché è ciò che rende legittimo il proxy di sviluppo di U-00: un proxy che nascondesse un problema di CORS destinato a ripresentarsi in produzione sarebbe un debito, non una comodità.

### U-08 in dettaglio: quale indice riceve chi arriva, e quale no

**Il problema, detto una volta.** Chi arriva da GitHub trova il codice, non i vettori. Rigenerarli costa ~2 ore di GPU più il download dei corpus da HuggingFace. Nessuno prova un progetto a quel prezzo, e un README che lo chiede sta dicendo «non provarlo».

**Le strade erano tre, e sono due.** Decisione di Marco il **2026-08-27**, rivedendo U-08 finito: *«come revisione di roadmap questa versione di demo è più che sufficiente, non faremo la versione con l'indice completo»*. La via di mezzo, lo snapshot Qdrant pubblicato come asset di Release, **non si fa**.

| bisogno | cosa riceve | costo | dove sta |
|---|---|---|---|
| **vedere com'è** | indice `demo` committato | < 2 min, zero rete | in git, `data/demo/` |
| **riprodurre le misure** | ingestione completa | ~2 h di GPU | `make fetch-datasets && make ingest` |

**Perché regge senza la via di mezzo.** Lo snapshot serviva a un bisogno intermedio, «provare sul dataset vero senza aspettare due ore di GPU», e quel bisogno si è rivelato più stretto di come sembrava a scriverlo: chi vuole solo vedere è servito in 17,9 secondi, chi vuole misurare deve comunque ingerire, perché **è l'ingestione a produrre i vettori su cui poggia ogni numero** di `docs/progress.md`. In mezzo restava chi vuole interrogare il corpus intero senza misurare niente: un pubblico che non abbiamo, per 160 MB da mantenere allineati a ogni cambio di embedder o di chunking, con la garanzia che il giorno in cui divergono nessuno se ne accorge (un indice interrogato con un altro embedder risponde **spazzatura senza errore**).

Ne resta un solo confine da tenere netto, ed è quello di sempre: solo l'ingestione rigenera i vettori. `data/demo/` serve a **mostrare**, e va dichiarato come tale: un demo che sembra riprodurre le misure è peggio di nessun demo. Nell'interfaccia lo dicono il campo `ridotto`, lo stato vuoto e la pagina «Che cos'è».

**La verifica sulle licenze resta valida, e adesso riguarda `data/demo/`.** Era stata fatta per lo snapshot, ma il ragionamento non dipendeva dal formato: un indice contiene **il testo dei chunk**, non solo i vettori, quindi non è un artefatto derivato opaco, è il corpus riorganizzato. I 1.758 chunk committati sono esattamente quello.

| dataset | licenza | ridistribuibile | obbligo |
|---|---|---|---|
| `vectara/open_ragbench` | Apache 2.0 | sì | licenza + NOTICE accanto all'artefatto |
| `artefactory/ledger-long-context-KPI-QA` | CC-BY-4.0 | sì | attribuzione accanto all'artefatto |

**«Accanto all'artefatto»** era la parte delicata quando l'artefatto era un archivio scaricabile: chi lo prende da una release può non aver mai visto `data/README.md`. Senza release il problema si scioglie da sé: **l'artefatto è il repository**, e l'attribuzione sta nel file accanto ai dati.

**I vettori densi non comprimono** (1024 dimensioni × 4 byte per punto). Vale ancora, e adesso si vede sul peso di `data/demo/`: 20,7 MB nel working tree e ~10,2 in git, quasi tutti nei due `.npy`, che sono float32 quasi incomprimibili. Ogni piano che assuma una compressione migliore è sbagliato.

**Cosa non fare, e perché** (le prime due sono la ragione per cui `data/demo/` è un ritaglio piccolo e non un indice intero):

- **Committare uno snapshot in git.** GitHub rifiuta i file oltre 100 MB, e anche sotto quella soglia un binario nella storia la gonfia per sempre: si cancella dal working tree, non dai commit.
- **Git LFS sul piano gratuito.** 1 GB di banda al mese: si esaurisce dopo sei cloni, e dal settimo chi clona vede un errore invece del dataset. È il modo peggiore di fallire: sembra funzionare finché il progetto non interessa a nessuno.
- **Distribuire un indice senza dire da quale commit e con quale modello di embedding è stato costruito.** Un indice è legato al modello che l'ha prodotto: interrogarlo con un altro restituisce spazzatura *senza errore*. È il `manifest.json` di `data/demo/`, che porta commit, embedder denso e sparso, e i conteggi per dataset.

**U-12 è più piccolo di quanto sembri, e non è rinviabile.** Il criterio di U-09 è «primo avvio pulito su macchina vergine», e una macchina Linux è una macchina vergine: un progetto MIT pensato per essere provato da altri non è presentabile se gira su un sistema operativo solo. `src/index/embed.py` sceglie già il provider DirectML solo se disponibile e ripiega su CPU, quindi su Linux il codice **gira già**; mancano l'ordine di preferenza dei provider Linux (senza, si finisce su CPU anche con GPU capace) e la dipendenza GPU dichiarata in `pyproject.toml` invece che solo nella tabella di `STACK.md`. L'inferenza LLM non è coinvolta: Ollama gira su Vulkan, che è lo stesso codice llama.cpp sui due sistemi. Cosa resta da **provare** e non solo da elencare è in **D-10**.

---

## Debiti aperti: cosa resta da far girare e da sistemare

**Senza numero di proposito.** I riferimenti `§13`–`§17` sono citati in decine di commenti nel codice: rinumerarli per infilare una sezione qui li renderebbe tutti sbagliati, e un documento che si aggiorna rompendo i suoi lettori non è una fonte di verità. Sta dopo la Fase 8 perché è lì che i debiti si sono accumulati.

Ogni voce dice **cosa fare**, non solo cosa manca. Un debito senza il comando che lo salda è un promemoria, e i promemoria non si saldano.

> **`D-1` e `D-01` non sono la stessa famiglia.** Qui i debiti sono `D-1`…`D-21`; `D-01` è la dashboard Streamlit della Fase 3. La collisione è nata dopo, e si tiene così: rinominare l'una o gli altri sposterebbe riferimenti in commit e commenti già scritti, per guadagnare una cifra.

### A. Misure da rifare: richiedono la GPU, e un via libera

`prompt_hash` è cambiato due volte: con la correzione del prompt di C-01, e con U-14 che ha rovesciato la regola sul formato. Le **17 run di citazioni** a disco valgono per prompt che non sono più quello in vigore, e ogni numero di conformità va citato **insieme al prompt a cui si riferisce**.

**D-1 e D-2 sono saldate** (2026-08-21): due run da 200 domande col prompt in vigore, una per corpus, e da lì l'ancora di `config_hash` torna a puntare al codice che gira. I numeri stanno in [`progress.md`](docs/progress.md). Resta D-3, che chiede una cosa diversa: non i numeri di oggi, ma il confronto **appaiato** fra i due prompt sulle stesse domande.

> ✅ **Questa sezione è chiusa** (2026-08-23). D-1 e D-2 il 21 agosto, D-3 il 22, D-4 il 23, e l'affermazione 3 la sera del 22. Le righe restano perché il **comando** e il **costo vero** di ognuna sono il materiale con cui si preventiva la prossima, e in tre casi su quattro il preventivo era sbagliato, sempre nello stesso verso.

| # | Cosa | Comando | Costo |
|---|---|---|---|
| D-3 | ✅ **Saldato il 2026-08-22** (dettaglio in `progress.md`): quattro run da 200 domande, due per corpus, stesso codice e stesso giorno, fra i bracci cambia **il prompt e basta**. **Il prompt di U-14 non costa conformità**, e la previsione rinviata resta non confermata: l'effetto è dentro la linea di rumore misurata sullo stesso strumento. Cambia **quali** risposte sono conformi (10 su 188) e non **quante** (6 peggiorate, 4 migliorate) |
| D-4 | ✅ **Saldato il 2026-08-23** (dettaglio in `progress.md`): **otto configurazioni**, due corpus, golden set completi, tutte in ricerca esatta. Il reranker fa **una cosa sola e la fa sempre** (Success@1 migliora in tutti e quattro i confronti appaiati, da +3,8 a **+16,3** punti, p<0,0001), e ne rompe un'altra dove non c'era margine: `doc_R@5` **peggiora** su `ledger` in tutte e due le modalità (−0,63 e −1,42, p=0,0014 e p<0,0001). È lo specchio di **OQ-06**, col segno scambiato. **La configurazione migliore dipende dal genere**: `hybrid+rerank` su `open_ragbench`, `dense+rerank` su `ledger`. Costo reale **6 h 04** contro le 5 h di preventivo: lo smoke da 200 query dava 0,69 s a query, la media vera è 0,89 |

> **D-3 non è un ricontrollo, è una previsione da falsificare.** Prima di U-14 il markdown pieno era stato **valutato e scartato**, e non per estetica: la verifica di C-03 è a livello di **frase**, e una riga di tabella non è una frase. L'argomento registrato in [`progress.md`](docs/progress.md) diceva che una risposta con una tabella verrebbe fuori *«più bella e meno verificata»* (celle senza citazione, o citazioni che il verificatore non sa attribuire), e che una tabella generata **fonde** numeri presi da chunk diversi in una struttura inventata dal modello, cioè nasconde proprio il punto in cui la tracciabilità si perde. La decisione è stata rovesciata su richiesta il 2026-08-19, e quell'argomento **non è stato confutato: è stato rinviato a una misura.** Se `citation_precision` cala col prompt nuovo, la previsione era giusta e la regola sul formato va ripensata, non difesa.

> **Cosa D-1 e D-2 hanno già detto, e cosa no** (2026-08-21). Le tabelle generate su 337 risposte valutate sono **zero**, col prompt nuovo come col vecchio: il meccanismo preciso che la previsione temeva non si è presentato. Ciò che è cambiato è la forma minuta (elenchi da 8 a 63 su `open_ragbench`, da 4 a 33 su `ledger`), e la conformità grezza è rimasta ferma là (0,9263 → 0,9255) mentre su `ledger` è scesa (1,0000 → 0,9664) **per una ragione estranea al markdown**: quattro rifiuti scritti con parole proprie, che è D-19. Niente di questo è appaiato, quindi non decide: D-3 resta la misura, con un'ipotesi più stretta di quando è stata scritta.

> **Un'obiezione dell'epoca invece è caduta, e va detto perché.** Si diceva che un renderer Markdown avrebbe letto `[2][3]` come *reference link* di CommonMark, reinterpretando proprio la forma che il §3.2 impone. Non succede: `markdown.ts` non tocca le quadre, e i marcatori continuano a uscire da `marcatoriDelTesto`, che era già l'unica implementazione nel frontend. Non è una seconda copia del contratto di citazione: è il contratto che resta l'unico a leggerle.

### B. Debiti dell'interfaccia

| # | Cosa | Dove nasce |
|---|---|---|
| D-5 | ✅ **Saldato il 2026-08-22** (dettaglio in `progress.md`): un foglio **per risposta**, aperto dal comando accanto a «Confronta», coi quattro dati dell'indice e tutti i campi di `ConfigView`. Lo stream ora porta anche `collection`. *Testo originale:* **«Dettagli della run» non esiste.** I quattro dati dell'indice (collection, punti, dimensione densa, vettori sparsi) che U-01 mostrava nella colonna centrale sono usciti di scena quando la chat ha preso quel posto. Il §12 li vuole sempre leggibili, e lì devono tornare insieme ai parametri di «Avanzate» | U-02, dichiarato alla consegna |
| D-7 | ✅ **Saldato il 2026-08-22** (dettaglio in `progress.md`): `CitationView.threshold` e `ConfigView.entailment_threshold`, in sola lettura, con l'assenza da `QueryRequest` protetta da un test e da `NON_RICHIEDIBILI` nel frontend. *Testo originale:* **La soglia dei verdetti non arriva al frontend.** `CitationView` porta `score` e `supported` ma non la soglia, quindi la pastiglia mostra `0,717` senza una scala. Il precedente è già in casa: `GateView` spedisce `threshold` accanto al proprio `score`. Va esposta **in lettura, in `ConfigView`/`CitationView`, mai accettata in `QueryRequest`**: una soglia scelta da chi chiama si potrebbe tarare sulla stessa risposta che deve giudicare, ed è un'assenza protetta da un test | U-07 |
| D-8 | ✅ **Saldato il 2026-08-24** (dettaglio in `progress.md`), **col modo che il debito stesso indicava**: `composizione.ts` prende il testo grezzo con ciò che gli sta sopra e restituisce una lista di pezzi (testo con la sua veste, marcatore, formula, ognuno col proprio offset), e `Testo.tsx` si limita a metterci addosso delle classi. **18 test, da 358 a 376**, e la scelta di U-00 di non avere jsdom non è stata riaperta. Provano l'incrocio, non le parti: la matematica che ha la precedenza (`$x[3]$` resta una formula), gli intervalli che si ritagliano invece di sparire a cavallo di una formula o di due celle, e i caratteri di sintassi che se ne vanno all'ultimo passo senza spostare il testo di un carattere. Ognuno verificato **a mutazione** prima di essere creduto. *Testo originale:* **La composizione di U-14 non ha un test.** `markdown.ts` ne ha 15 suoi, ma l'incrocio fra markdown, marcatori e verdetti si verifica solo a schermo: `ui/` non ha jsdom, per scelta di U-00. Se un giorno serve, il modo che rispetta quella scelta è estrarre la composizione in una funzione pura che restituisce intervalli invece di nodi | U-14 |
| D-17 | ✅ **Saldato il 2026-08-23** insieme a **U-23** (dettaglio in `progress.md`): ogni esempio dichiara `atteso` (chunk e posizione, oppure che il gate si chiuda e con quanto margine), e `scripts/verify_esempi.py` lo controlla contro l'indice vero, **in ANN e in esatta**. I due di `ledger` sono stati sostituiti con query verificate in **posizione 1** (erano 5 e *mai*); i due di `open_ragbench` erano già a posto. **La verifica ha trovato anche ciò che il debito non sapeva**: i due esempi «fuori corpus» **non chiudevano il gate** (0,8225 contro 0,7924 e 0,8417 contro 0,8289), quindi l'astensione la decideva il modello e non la soglia, il caso che il §15 esclude. Sostituiti con domande che lo chiudono, a +0,0227 e +0,0078 di margine. Ne è nata **OQ-10**: su `ledger` cambiare *anno* non basta a chiudere il gate, cambiare *azienda* sì. *Testo originale:* **Gli esempi dello stato vuoto non sono mai stati verificati contro la pipeline, e uno non funziona.** |
| D-18 | ✅ **Chiuso il 2026-08-24 come decisione: le collection instradate restano fuori dall'interfaccia** (dettaglio in `progress.md`). Il debito chiedeva *come* presentarle, e la risposta è che non si presentano. Con la ricerca esatta (l'unico confronto legittimo fra due indici di densità diversa, §15) il routing **perde 13,72 punti** di `doc_R@5` su `ledger` e ne guadagna **1,06** su `open_ragbench`: offrirlo come modo scegliibile metterebbe nell'interfaccia una pipeline che sul genere tabellare recupera peggio, e un elenco che offre due strade dichiara da solo che sono alternative alla pari. L'affermazione 2 resta confutabile dove è **misurata** (R-07, la tabella del §0 e quella del README), e non in una demo che mostra una risposta per volta e non sa confrontare niente. Conseguenza accettata: la targhetta di U-05 dice sempre «taglio generico», ed è **vero**. *Testo originale:* **Le collection *routed* esistono e non sono raggiungibili dall'interfaccia.** `/datasets` pubblica solo le generiche, quindi la demo non instrada mai e la targhetta di U-05 mostra sempre «taglio generico»: si vede che il routing **non** è in gioco, non lo si vede all'opera. `QueryRequest` accetta già `collection`, quindi manca solo la scelta, ma offrirle raddoppierebbe l'elenco dei corpus con due voci che sono varianti dello stesso, e va deciso come si presentano. Da tenere insieme al fatto che su `ledger` il routing **perde** 17 punti (OQ-01): renderlo visibile significa anche renderlo confutabile, che è il punto | U-05, dichiarato alla consegna |

### C. Dichiarati altrove, e ancora aperti

| # | Cosa |
|---|---|
| D-9 | **I-06 rinviato**: nessun dataset corrente distribuisce PDF nativi o coordinate, quindi `bbox` resta `None` e l'overlay di U-06 non ha su cosa poggiare. Si sblocca solo aggiungendo un dataset con PDF e coordinate esportate: **dichiararlo, non simularlo** |
| D-10 | ✅ **Fatto il 2026-08-28 dentro U-12.** Provati, e l'esito ribalta l'ipotesi. `ROCMExecutionProvider` **non esiste** sulla macchina che lo dovrebbe avere: il pacchetto ROCm di Arch spedisce `libonnxruntime_providers_migraphx.so` e non quello ROCm, quindi il nome in elenco non veniva mai scelto e la macchina finiva su CPU **con ROCm installato e una GPU capace**, in silenzio. MIGraphX, che l'elenco non nomina, sulla stessa RX 6750 XT fa **26,3 embed/s** contro i 10,0 di DirectML e i 2,4 della CPU: il piu' veloce dei tre, e **resta fuori dall'elenco**, perche' cerca i pesi esterni nella directory corrente e senza quelli l'inferenza muore *dopo* che la sessione si e' legata al provider. Sceglierlo da soli sposterebbe la rottura dall'avvio alla prima query. Resta raggiungibile con `ONNX_PROVIDERS`, che esiste per questo, e il secondo costo e' scritto accanto: 278 s di compilazione del grafo alla prima esecuzione contro 1,2 alla seconda. Lo strumento e' `scripts/verify_platform.py`, che guarda **tre cose e non una** (cosa la macchina offre, cosa il progetto sceglie, su cosa la sessione e' finita) e misura **due volte buttando la prima**, senza la quale il numero di MIGraphX si leggeva 0,1 embed/s. CUDA resta dichiarato e non verificato: qui non c'e' hardware NVIDIA. *Testo originale:* **U-12**: `ROCMExecutionProvider` e `CUDAExecutionProvider` sono nell'ordine di preferenza **dichiarati e non verificati**. La portabilità Linux si chiude provandoli, non elencandoli |
| D-11 | **Le dieci domande** di [`open-questions.md`](docs/open-questions.md), OQ-01…OQ-10: quattro chiuse (OQ-03, OQ-05, OQ-07, OQ-08), le altre no. La più cara resta la prima: perché il routing peggiora `ledger` di 17 punti, cioè il motivo per cui l'affermazione 2 del §0 non è sostenuta. L'ultima è la più scomoda: **OQ-09**, l'ANN di `ledger` che dal 21 agosto rende dodici punti meno a configurazione identica |
| D-12 | **I 50 `E402` sono soppressi, non corretti.** La correzione vera è installare il progetto (`pip install -e .`) e cancellare le tre righe di bootstrap da ogni script. Non è igiene, è un cambiamento del modo di lavorare: oggi `python scripts/eval.py` funziona su un clone appena scaricato |
| D-14 | ✅ **Saldato il 2026-08-24 da A-09** (dettaglio in `progress.md`): **impostato** (`OLLAMA_CONTEXT_LENGTH=32768` sul motore, dichiarata in `STACK.md` accanto a `OLLAMA_FLASH_ATTENTION`), e **verificato**, perché `EvalRun.context_window` è ora la finestra letta da `/api/ps` e non la costante. Chi costruisce un `EvalRun` senza misurarla ottiene il valore dichiarato **e un avviso**, mai un default silenzioso. **Resta una metà**, ed è di contratto: il JSON non distingue «32768 misurato» da «32768 creduto» (serve un campo in `EvalRun`, cioè toccare il §3, e non si fa di passaggio). *Testo originale:* **`context_window` è dichiarato e non impostato.** `CONTEXT_WINDOW = 32768` esiste in due soli posti: la costante in `config.py` e `EvalRun.context_window`, dove finisce in **ogni** risultato registrato. Il payload di `chat.py` non lo manda, non esiste un campo standard OpenAI per la finestra, e `num_ctx` è nativo di Ollama. Misurato il 2026-08-19: mandandolo comunque sul filo l'endpoint risponde **200 e lo ignora** (`num_ctx: 4096` → `/api/ps` continua a dire 32768), che è peggio di un rifiuto. Oggi il numero è *vero* perché il default di questo modello coincide, ma è una coincidenza, non una misura. **È la stessa classe di difetto di `reasoning_enabled`**, che questo stesso file documenta come «una dichiarazione che nessuno verificava, e per un periodo è stata falsa in ogni run»: un campo più in là. Da decidere: derivarlo, marcarlo come non verificato, o toglierlo |
| D-15 | **Il suggerimento del ragionamento porta i numeri di gemma4, e la barra lascia scegliere un altro modello.** `SFORZO = {none, high}` e le cifre nel suggerimento (+0,6 punti, 9,5× i token, astensioni da 56 a 90) vengono da C-07, misurato su gemma4. Scegliendo `qwen3.5` quel testo descrive la misura di un modello diverso, e che quel modello onori `reasoning_effort` non l'ha verificato nessuno. Va o legato al modello, o dichiarato per quale modello vale |
| D-16 | **Le due colonne del confronto differiscono anche per il prompt, non solo per il RAG.** U-14 aveva rovesciato la regola sul formato proprio per chiudere questo scarto, e lo ha ristretto senza chiuderlo: il braccio con le fonti ha «Use Markdown where it helps the reader… Do not use it for decoration» più l'obbligo di stare dentro i chunk, quello nudo (`baseline_prompts.py`) non ha **nessuna** regola di formato: è letteralmente «Answer the question to the best of your ability». Osservato alla revisione di U-04: «risponde comunque» produce la risposta più lunga e meglio impaginata delle due, cioè la più convincente è quella che non si può controllare. Parte è **il fenomeno da mostrare** e parte è un artefatto dei prompt, e le due non si separano guardandole. Chiuderlo del tutto vuol dire toccare `baseline_prompts.py`, che rende E-04/E-05 non più confrontabili, cioè proprio il 45%→17% che il suggerimento di U-04 cita. Da decidere **misurando**, con D-3 |
| D-19 | ✅ **Saldato il 2026-08-22** (dettaglio in `progress.md`): tupla separata `SELF_WORDED_REFUSALS` dietro le guardie di `is_abstention`, `ABSTENTION_PHRASES` intatta. E-04/E-05 non si muove: passa dal rilevatore guardato, e tutte e dieci le risposte interessate portano un marcatore. `ledger` va a 1,0000 e 0,9931. *Testo originale:* **Un rifiuto scritto con parole proprie non è un'astensione, e conta come violazione di formato.** Il prompt chiede la stringa esatta `Insufficient information.`; in D-2 quattro risposte su `ledger` hanno rifiutato per conto loro («The provided context does not contain the operating income figure…»), e `is_abstention` non le riconosce, perché la frase non è nell'elenco di `ABSTENTION_PHRASES`. Sono corte e senza marcatori, quindi le altre due condizioni le passano. Finiscono fra le valutate come `no_citation`, e **sono l'intero calo di `ledger`** (1,0000 → 0,9664): senza di loro il numero sarebbe 0,9931. Le due letture sono tutt'e due difendibili (il modello ha disobbedito a un'istruzione esatta, oppure ha rifiutato e basta), e la scelta non è gratis: `ABSTENTION_PHRASES` è lo **stesso** elenco di E-04/E-05, quindi allargarlo sposta anche quelle. Da decidere, e poi da riapplicare con `rescore_citations.py`, che non costa GPU | D-2, 2026-08-21 |
| D-20 | **Il `config_hash` nomina la configurazione, non lo stato dell'indice.** Il 13 e il 22 agosto due run di `ledger` dense in ricerca approssimata si chiamano tutt'e due **`5c3c7fa2`** e riportano `doc_R@5` 0,8915 e 0,7705: **due misure diverse con lo stesso nome**. È lo specchio del difetto che R-08 corresse aggiungendo `sparse_idf` all'hash: là due misure diverse condividevano un nome perché mancava un *parametro*, qui perché è cambiato l'**indice**, che in un hash non ci sta per intero. Nessun campo di `EvalRun` lo registra: `collection` dice **quale**, non **com'era**. Il rimedio più piccolo che funzionerebbe non prova l'identità, **la falsifica**: salvare accanto alla run ciò che Qdrant già espone su quella collection (conteggio punti, numero di segmenti, schema payload), così che due run non confrontabili si **vedano** invece di sembrare la stessa. Costa una chiamata a `get_collection` e un campo. **Non è gratis**: tocca lo schema di ogni risultato registrato (§3), e un campo nuovo dentro il `config_hash` orfanerebbe ogni misura già a disco, quindi va aggiunto **accanto** all'hash, non dentro. Da decidere. *Nato da OQ-09, 2026-08-22* |
| D-21 | ✅ **Fatto il 2026-08-27 dentro U-08.** Il riscaldamento sta in `src/service/warmup.py`, parte dal ciclo di vita di FastAPI e **non blocca**: `Application startup complete` compare prima delle due righe di caricamento. Misurato con la cache HF piena: embedder 2,4 s, verificatore 3,1 s, e il primo `/retrieve` passa da **2,83 s a 0,34**. Il warning dell'Hub adesso compare all'avvio invece che a meta' della prima risposta. Scalda cio' che i **default** faranno usare invece di una lista sua, quindi col reranker spento non carica ~1 GB di VRAM inutile; un modello che fallisce lascia finire gli altri; `WARMUP=0` lo spegne, per lavorare all'interfaccia mentre la GPU e' occupata da una valutazione. *Limite dichiarato:* rende **raro** il caso brutto, non impossibile. *Testo originale:* I modelli ONNX si caricano alla prima richiesta, e la prima verifica contatta l'Hub anche a cache piena.** Osservato il 2026-08-23 guardando i log dell'API: l'embedder si carica alla prima query e il verificatore NLI alla prima **citazione da verificare** (`entailment.py`, `_load` dietro `lru_cache`), e `hf_hub_download` fa comunque una richiesta per controllare la revisione: il warning *«unauthenticated requests to the HF Hub»* è quella. Oggi costa un giro di rete; per **U-08/U-09** significa che la demo dipende dalla raggiungibilità di huggingface.co **al momento della prima risposta con citazioni**, non alla costruzione dell'immagine: dietro una rete chiusa o un limite di frequenza il guasto arriva a metà di una dimostrazione. **Il rimedio è scaldare i modelli all'avvio, in un thread di sottofondo.** Si sovrappone al frontend che si carica e a chi legge lo stato vuoto, e quando non fa in tempo la prima query paga quello che paga oggi, non è mai peggio. Toglie anche l'artefatto che ha già ingannato una misura qui (*«erano tempi di prima query, cioè caricamento dei modelli riportato come costo per richiesta»*, A-05). **Il vincolo che un'implementazione sbaglierebbe per prima**: non bloccante. `/health` deve continuare a voler dire «vivo, e nient'altro», la sua docstring spiega che `depends_on: service_healthy` di U-09 lo usa per l'ordine di avvio, quindi scaldare *prima* di rispondere farebbe aspettare l'orchestratore per 2,5 GB su una cache fredda. **E non `HF_HUB_OFFLINE=1` come default**: A-05 ha scartato i modelli dentro l'immagine, quindi su un volume vuoto l'offline impedirebbe per sempre il primo avvio, che è esattamente il criterio di U-09. Resta buono come variabile di shell su una macchina che li ha già. *Limite dichiarato:* il riscaldamento in sottofondo rende **raro** il caso brutto, non impossibile; garantirlo vorrebbe dire un endpoint di *readiness* separato da `/health`, cioè toccare il contratto per un caso che dura trenta secondi una volta per avvio. Non lo vale. Da fare **dentro U-08**, che è l'unico posto da cui si verifica che serva |
| D-22 | ✅ **Saldato il 2026-08-25**, il giorno dopo essere nato: `Modo.tsx` prende `FORMA`, `RIPOSO` e `MOSSA` dal modulo, coi margini interni del selettore del prompt: l'altra pillola senza glifo. I quattro bottoni passano da 10 a 11 px, guadagnano `bg-surface` a riposo e un grigio un filo più scuro; lo stato acceso non si muove, perché era già identico. **Dopo, la forma senza glifo è una sola in tutta l'interfaccia** e nessuna pillola è più disegnata a mano. Nota di metodo: qui il CSS costruito resta identico e **non prova niente** (tutte le utility in gioco erano già usate altrove, e quel confronto vede una classe *persa*, non una classe *cambiata*). *Testo originale:* **La pillola del mockup esiste in due misure, e nessuno sa perché.** `pastiglia.ts` la tiene a 11 px (`FORMA`, `RIPOSO`, `MOSSA`) e la usano sei controlli della barra e del confronto; `Modo.tsx` la ridisegna a 10 px e la usano **quattro bottoni, tutti nell'esploratore**: «Com'è stato spezzato»/«Il testo indicizzato» nella colonna di mezzo e «Leggibile»/«Grezzo» sul chunk scelto. Lo stato **acceso è già identico** nei due (`border-accent bg-accent-soft text-accent`), il che dice che uno è nato copiando l'altro: la divergenza è tutta a riposo (10 px contro 11, `text-muted` contro `text-ink-2`, e nessun fondo contro `bg-surface`). **Il rimedio più piccolo esiste già nel modulo e `Modo` non lo usa**: due dei sei siti (il numero a passi, il selettore del prompt) prendono `FORMA` e ci mettono i margini interni propri, perché `PASTIGLIA` ha `pl-[7px] pr-2.5` asimmetrici che servono a chi porta un glifo davanti, e `Modo` un glifo non ce l'ha. Ridotto così, resta da decidere **guardando** e sono due domande sole: se l'11 px stia bene in una colonna dove il resto è 12, e se quei due bottoni debbano avere un fondo o restare trasparenti, sono gli unici della famiglia che stanno dentro una colonna invece che sopra una barra. Non saldato in Q-07 perché cambia dei pixel, cioè proprio il gate di quel task. *Nato da Q-07, 2026-08-25* |
| D-13 | ✅ **Fatto il 2026-08-28** (dettaglio in `progress.md`): il linter c'e', ed e' **`oxlint`, non `eslint`**, per una ragione misurata e non preferita: `typescript-eslint` si rifiuta di partire su TypeScript 7 e la strada che indica e' affiancare una seconda copia di TypeScript a quella gia' in albero. Accesa **una regola sola**, quella che il debito nominava, e i due rilievi che trova sono tutti e due veri: in `dataset.tsx` un `useMemo` memoizzava contro un array costruito nuovo a ogni render, e in `esploratore.tsx` una deroga voluta smette di essere una nota in prosa e diventa una riga che il linter legge. **Restano 67 rilievi triati e non zittiti**, elencati in `progress.md`: alcuni sono difetti veri (5 valori di contesto ricostruiti a ogni render), altri chiedono di cambiare una convenzione del progetto e non li decide chi implementa. Il piu' numeroso e' di quelli: **18 `rules-of-hooks` che non sono difetti**, ma la protesta della regola contro gli hook chiamati `usaX` invece che `useX`. *Testo originale:* **Nessun linter per il TypeScript.** `prettier` formatta e basta; ciò che troverebbe qualcosa è `react-hooks/exhaustive-deps`, e in questo repo le liste di dipendenze degli `useCallback` sono scritte a mano. Proposta, non decisa |

**La regola che tiene insieme la lista**: nessuno di questi debiti è una scusa per non consegnare, e nessuno può essere chiuso in silenzio. Quando uno si salda, la riga sparisce da qui e il risultato (anche negativo, soprattutto negativo) entra nella tabella che gli compete.

---

## Il piano di chiusura

**Quattro decisioni prese il 2026-08-20**, e ognuna toglie lavoro invece che aggiungerlo:

1. **Il repository è pubblico.** Ne segue che l'immagine può stare su un registro pubblico invece che dentro un file da 2 GB. *Valeva anche per gli asset di Release, scaricabili senza autenticazione: quella metà è decaduta il 2026-08-27, quando la via dello snapshot pubblicato è stata tolta da U-08. L'indice della demo sta in git.*
2. **Niente demo ospitata**, e non per pigrizia: verificato il 2026-08-20. Non esiste GPU gratuita: il modello andrebbe preso in prestito da un endpoint OpenAI-compatibile (che l'architettura permetterebbe senza toccare `src/`, ed è il pregio di `LLM_BASE_URL`), ma **il limite che morde è 6.000 token al minuto**, e una query RAG con cinque chunk ne consuma quattro o cinque mila: circa **una domanda al minuto**. In più ogni piano gratuito dorme, e chi arriva per primo paga il caricamento di ~2,5 GB di modelli ONNX. Un link lento e a quota è peggio di nessun link. Si consegna `docker compose --profile demo up` (U-08) e il video di U-10; l'hosting è **X-06**, in Fase 9.
3. **Niente RASD e Design Document formali.** Si consegnano il README (U-11) e la documentazione tecnica (U-22). **Il README principale è in italiano**, con un secondo in inglese accanto (`README.en.md`) e un rimando reciproco in cima a entrambi: il progetto è scritto in italiano (ROADMAP, `progress.md`, i commenti nel codice), e un README inglese davanti a un quaderno italiano prometterebbe una cosa che il repo non mantiene. `ROADMAP.md`, `progress.md` e `open-questions.md` restano in italiano e non si traducono: sono il quaderno di lavoro, non la vetrina.
4. **Nessuna scadenza.** Le tappe che seguono sono ordinate per **dipendenza e per rischio**, non compresse: nessuna di esse va tagliata a metà per far entrare la successiva.

### Le tappe, in ordine

| | tappa | cosa contiene | perché sta qui |
|---|---|---|---|
| **1** | ✅ **Fatta** (2026-08-24) | **L'interfaccia finita**: U-18, U-19, U-20, U-21, e i quattro debiti che erano lavoro d'interfaccia (**D-5**, **D-7**, **D-17**, **D-18**) | Tutte le funzionalità **prima** del refactor: aggiungerne una dopo significa risporcare ciò che si è appena pulito. Tre debiti sono stati saldati scrivendo codice; **D-18 è stato chiuso decidendo di non farlo**: le collection instradate recuperano peggio, e l'affermazione 2 si confuta sulle misure di R-07, non su un menù a tendina. **D-8** non era in elenco ed è stato saldato subito dopo, il 2026-08-24, **senza riaprire U-00**: la composizione è uscita dal JSX ed è diventata provabile, che era il modo scritto nel debito stesso |
| **2** | ✅ **Fatta** (2026-08-23) | **D-3**, **D-4**, i due passi a costo zero di **OQ-07** e **OQ-08**, e l'**affermazione 3** a tre punti. In più, non previsti: **OQ-09** (l'ANN di `ledger` cambiato sotto ai piedi) e le due manopole del motore che valevano un fattore tre | Era l'unica tappa vincolata dalla GPU, ed è andata in parallelo alla 1 come previsto: `make dev` ha retto mentre la scheda era occupata |
| **3** | ✅ **Fatta** (2026-08-25) | **Q-07**, e tre voci fuori lista che il mandato di Marco ha aperto | Il momento era quello giusto per la ragione scritta: a comportamento fermo il gate si può verificare davvero, e il CSS identico a `main` è la prova che si poteva pretendere solo qui |
| **4** | ✅ **Fatta** (2026-08-26) | **I documenti**: **U-11**, **U-22**, **U-10** | Qui i numeri esistono già, arrivati dalla tappa 2. Scrivere il README prima significherebbe citare misure fatte con un prompt che non è più quello in vigore |
| **5** | ✅ **Fatta** (2026-08-28) | **La consegna**: **U-08**, **U-09**, **U-12**, **D-10** e l'immagine pubblica su registro (`.github/workflows/immagine.yml`, sui tag e a mano). Le attribuzioni stanno in `data/README.md`, accanto ai dati: senza snapshot pubblicati l'artefatto e' il repository. **Il default resta la costruzione locale**: se puntasse al registro, un clone senza rete verso `ghcr.io` non si avvierebbe, e quello e' proprio il criterio di U-09 | U-12 non è un extra: il container **è** Linux, e il criterio di U-09 dice «primo avvio pulito su macchina vergine». Provato su una Arch che non aveva mai visto il progetto, ed e' li' che sono usciti gli otto guasti |
| **6** | **Extra** | Fase 9, §13 | Solo se avanza voglia |

### Le tre affermazioni, allo stato dei fatti

Il criterio di U-11 chiede che **ognuna** compaia col proprio tavolo di misure. Due oggi non reggono, e vanno scritte per quello che sono invece che scoperte mentre si scrive il README:

- **1 (la precisione di citazione è misurabile.** Regge, e dal 2026-08-21 i numeri valgono per il prompt in vigore): **0,9255** grezzo e **0,9628** dopo il parser su `open_ragbench`, **0,9664** e **0,9732** su `ledger` (D-1 e D-2). Resta **D-3**, che non aggiunge numeri ma dice se il prompt di U-14 ne è la causa.
- **2 (il routing batte la pipeline generica.** **Non sostenuta, e adesso si sa di quanto.** Con **ricerca esatta**) l'unico confronto legittimo fra due indici di densità diversa, §15: il routing guadagna **+1,06 punti** di `doc_R@5` su `open_ragbench` e ne **perde 13,72** su `ledger`. Gli otto punti che separano quel −13,72 dal −21,71 che si leggeva prima **erano il richiamo dell'indice, non il routing** (R-11). Nel README va così, per dataset e mai aggregata: *il valore del routing dipende dal genere, e sul genere tabellare la pipeline scritta a mano per lui peggiora il recupero.* È un risultato negativo per l'affermazione, ed è il reperto più interessante del progetto: il §7 dice che i risultati negativi restano in tabella.
- **3: la taglia conta meno del previsto.** **Sostenuta, e nella forma forte** (2026-08-22). I tre punti, dopo il parser di C-02, sulle 91 query di `open_ragbench` che tutti e tre hanno risposto: **E2B 0,8681 → E4B 0,9670 → 12B 0,9670**. Il salto c'è **una volta sola** (E2B→E4B +9,9 punti, **9 query a 0, p=0,0039**), e poi la curva è piatta: E4B→12B **+0,0000**, una query per parte, **p=1,0000**, al doppio della latenza (19,2 s contro 9,4). Nel README va detta così, con i due limiti accanto: è misurata sulla **conformità di formato** (il terzo punto non ha il verificatore NLI, quindi `citation_precision` resta a due punti) e **solo su open_ragbench**, dove su `ledger` E4B è già a 1,0000 e non c'è dove salire, che per l'affermazione è un modo diverso di dire la stessa cosa. Dettaglio in `progress.md`, C-06.

> **Il prezzo era sbagliato di cinque volte, e la decisione del 2026-08-20 è caduta con lui.** I 240 s a domanda venivano da T-02, misurati col *thinking* acceso e con il 12B probabilmente non tutto in VRAM. Rimisurato il 2026-08-22 con lo strumento vero, `eval_citations.py --model gemma4:12b --limit 6`, embedding e recupero inclusi (sono **43,5 s**): p50 35,6 s, p90 86 s, 261 s per sei domande. Dettaglio in [`docs/hardware.md`](docs/hardware.md).
>
> **Quindi le 100 costano ~1 h 15**, non 6,7 ore, e le 50 ne costerebbero 40 minuti. **Deciso il 2026-08-22: si fanno le 100**, che era il piano originale. Trentacinque minuti in più comprano barre d'errore strette invece che larghe, cioè tolgono il caveat che avrebbe dovuto accompagnare il risultato, e **fanno sparire un lavoro**: il filtro sulle query di `rescore_citations.py` serviva solo perché il 12B girava su un sottoinsieme. A 100 non serve.

#### Com'è andata (2026-08-22 sera)

> ✅ **Fatta.** 2.554 s, 25,5 s a domanda, non 1 h 15 e non le 6 h 40 del preventivo originale. Fra la stima e la run sono saltate fuori due manopole del motore che valevano insieme un fattore tre, ed è la ragione per cui la run è stata avviata e fermata tre volte: la flash attention (spenta, e sul 12B vale 4× sul prefill) e la sessione ONNX dell'embedder, che l'harness teneva in VRAM per tutta la generazione. Le due sono in [`docs/hardware.md`](docs/hardware.md); la correzione al codice è mergiata. **I tre controlli qui sotto sono serviti tutti**, ed è per questo che restano scritti.

#### Pronto a partire (verificato il 2026-08-22)

Tre cose sono state controllate perché la run non vada rifatta:

1. **Le query sono le stesse.** I dump E2B (`20260812_163452`) ed E4B (`20260812_170338`) sono le stesse 100 domande, nello stesso ordine, e coincidono con le prime 100 rispondibili del golden set. `--limit 100` sul 12B dà lo stesso insieme senza filtrare niente.
2. **Il recupero riproduce.** I `chunk_ids` mandati in contesto il 12 agosto sono **100 su 100 identici**, stesso ordine, a quelli che il recupero dà oggi. R-08, R-11 e la reindicizzazione stanno in mezzo e non hanno spostato `open_ragbench`.
3. **I due punti sono stati riscoiati con il rilevatore di D-19**, perché i tre punti vanno misurati con lo stesso strumento: E2B passa da 0,8211 a **0,8478**, E4B resta **0,9263**. Senza il rescore il salto E2B→E4B sarebbe sembrato più largo di 2,7 punti.

Resta una variabile sola, il prompt: quei dump usano `3a50ef63`, il codice in vigore `53a5e756`. **Si tiene ferma girando il 12B col prompt vecchio**, così la run ha una sola differenza: il modello. La curva parla di taglia, e il prompt è disturbo; che i due siano indistinguibili lo dice D-3, con la linea di rumore accanto.

```
python scripts/eval_citations.py --dataset open_ragbench --model gemma4:12b --limit 100 \
    --system-prompt-file eval/results/generations/20260812_170338_open_ragbench.prompt.txt
```


### Le due collection instradate: si tengono, e restano fuori dall'interfaccia

`open_ragbench_routed` (98.312 punti, 683 MB) e `ledger_routed` (228.331, 1,4 GB) non sono materiale di scarto: **sono il secondo braccio di R-07**, cioè l'unica misura che decide l'affermazione 2. Tre decisioni, e la terza è quella che non era ovvia.

1. **Non si cancellano.** Liberano 2,1 GB e costano la riproducibilità: senza, R-07 non si rifà se non re-ingerendo, che è ordine di due ore di GPU. Un numero nel README di cui non esiste più il modo di rifare la misura è un numero che vale meno.
2. **Non si pubblicano**, e dal 2026-08-27 non si pubblica piu' niente: la via di mezzo (snapshot Qdrant su Release) e' stata tolta rivedendo U-08. Questi 2,1 GB servivano comunque a chi riproduce, e chi riproduce ingerisce.
3. **Nell'interfaccia non entrano**: deciso il **2026-08-24**, ed è la chiusura di **D-18**. Il debito chiedeva *come* presentarle senza raddoppiare l'elenco dei corpus, e la risposta è che non si presentano: in ricerca esatta il routing **perde 13,72 punti** su `ledger` e ne guadagna **1,06** su `open_ragbench`, e un elenco che offre due strade dichiara da solo che sono alternative alla pari. Confutabile il routing lo è dove è **misurato** (R-07, che mette i due bracci sulla stessa riga), mentre la demo mostra una risposta per volta e non sa confrontare niente: sarebbe una scelta in più che non decide nulla, davanti a chi non ha modo di sapere quale delle due è peggio. La targhetta di U-05 resta costante su «taglio generico», ed è vero.

> **Con questa decisione cade anche la ragione principale per cui la demo doveva girare in ricerca esatta**, e vale la pena tenerla scritta perché era l'argomento forte. Su `ledger_routed` l'ANN restituisce l'84,8% del vero top-5 e più di una query su tre riceve un top-5 sbagliato (R-11): esposte col default, quelle collection avrebbero fatto vedere il routing **più il difetto dell'indice** (l'errore che R-11 ha trovato in R-07, stavolta mostrato a chi guarda invece che scritto in una tabella), e sarebbe sembrato peggiore di com'è di otto punti. Fuori dall'interfaccia, quel rischio non esiste più.
>
> **La scelta resta comunque, per una ragione più debole e non nulla: OQ-09.** Sulle generiche la ricerca esatta sposta le metriche fra **0,0000 e 0,0046** e costa **2,5 ms contro 1,4**, cioè niente in tutti e due i sensi. Ma l'ANN di `ledger` ha reso **dodici punti in meno a configurazione identica**, da solo, sotto un task che non lo toccava; la ricerca esatta riproduce bit per bit. Una dimostrazione che qualcuno riavvia fra sei mesi ha più bisogno di quella garanzia di quanta ne abbia la valutazione, che i propri numeri li rifà. Va detto in U-19 (è l'unico punto in cui la demo non è configurata come la valutazione), e **non è ancora in `compose.yml`**: è lavoro di U-08.
>
> Oggi `SEARCH_EXACT` è una manopola di piattaforma e non un campo della richiesta (§3.4, e la classificazione di A-02): per la demo basta l'ambiente, e non serve toccare il contratto.

### Cosa questa lista non contiene, di proposito

- **Autenticazione, quote, limitazione per IP.** Servivano solo alla demo ospitata; senza hosting non hanno un destinatario, e il §14 le teneva fuori.
- **Un secondo indice o un secondo corpus.** L'affermazione 2 si chiude misurando quello che c'è, non aggiungendo materiale.
- **Il multi-turno.** Resta **X-02**: ogni domanda è indipendente, e riusare i messaggi precedenti per il recupero è un'altra cosa.

---

## 13. Fase 9: Extra, in ordine di priorità

Solo se avanza tempo. Nessuno di questi è necessario perché il progetto sia completo.

| ID | Task | Nota |
|---|---|---|
| X-01 | Upload dataset custom: collection Qdrant per sessione con TTL, limiti espliciti su file/MB/pagine, barra di avanzamento reale | Isolamento verificato con due sessioni concorrenti. Non serve cambiare vector store |
| X-02 | Multi-turno: contestualizzazione su cronologia, riusando il riscrittore di R-03 | **Il retrieval avviene sulla query riscritta**, mai sul messaggio grezzo né sulla cronologia concatenata |
| X-03 | Controllo di scala: qualche migliaio di documenti non annotati | Solo tempo di indicizzazione, latenza, dimensione indice, VRAM |
| X-04 | Retrieval visivo in stile ColPali sul dataset table-heavy | Il più ambizioso. Timebox rigido, si taglia senza rimpianti |
| X-05 | **La finestra di contesto decisa dall'hardware**: la preparazione guarda VRAM e memoria, sceglie la taglia di partenza e crea quelle che ha senso avere | Rinviato di proposito il 2026-08-19: U-16 dà la scelta con una partenza fissa a 32k (la finestra con cui il progetto misura), e questo la fa dipendere dalla macchina. Ci finisce anche la voce «non fissata», tolta dal menu perché era l'unica che non è una misura: qui tornerebbe come *una misura scelta guardando l'hardware*. Serve una sonda di sistema: Ollama non pubblica la VRAM totale, e `/api/ps` elenca solo i modelli **caricati** |
| X-06 | **La demo ospitata**: un'istanza pubblica che risponde senza scaricare niente | Rinviato di proposito il 2026-08-20, con la ragione scritta nel piano di chiusura. Se un giorno si fa, tre cose sono obbligatorie e non facoltative: un tetto per chi interroga, un modo di dire «quota esaurita» che non sia un errore, e una riga che dichiara **quale modello ha risposto**, perché non sarà quello con cui il progetto ha misurato |

---

## 14. Cosa NON fare

- **Costruire un corpus a mano o fare scraping.** Era la voce di costo più grande ed è stata eliminata di proposito.
- **Corpus con licenza restrittiva** (regolamenti FIA, specifiche 3GPP e simili): niente PDF nel repo, niente immagini Docker con documenti dentro, niente snapshot Qdrant con il testo nel payload.
- **Metriche aggregate su dataset diversi.** Sempre per `dataset_id`.
- **Dichiarare un miglioramento senza confrontarlo con E-07.**
- **Lasciare al modello la decisione di astenersi.** La soglia sta nel codice.
- **Lasciare al modello il formato delle citazioni.** Imposto e riparato.
- **Fine-tuning**, **LangChain / LlamaIndex** per l'orchestrazione, **Kubernetes**, code di messaggi, autenticazione, multi-utente reale.

---

## 15. Regole di lavoro

**Per entrambi**

- Ogni fase finisce con numeri committati in `eval/results/`, con hash del commit.
- Mai due modifiche senza misurare in mezzo.
- **Prima di confrontare una metrica fra due configurazioni, verificare che il cambiamento non muova anche lo strumento che la misura.** Il tetto di chunking di I-11 sembrava alzare `citation_precision` di undici punti: era la lunghezza delle premesse, a cui quel verificatore è sensibile. Una metrica è confrontabile solo lungo gli assi che non toccano il suo strumento, e quali siano va saputo prima, non dopo.
- **Due indici di taglia o densità diversa non si confrontano con la ricerca approssimata.** HNSW perde più richiamo dove i punti sono più fitti, quindi il confronto fra due pipeline misura anche il divario fra i due richiami: **un terzo del guadagno attribuito al routing in R-07 era l'indice** (R-11). Usare `SEARCH_EXACT=1`, oppure verificare prima con `scripts/probe_index_density.py` che il richiamo sia equivalente: costa un minuto e non serve nessun golden set.
- **Un test pre-registrato protegge dallo scegliere il test dopo aver visto i dati. Non protegge dall'aver scelto il test sbagliato prima.** Il passo 2 di OQ-01 era scritto in anticipo e dava un delta a favore dell'ipotesi; un braccio di controllo con un dato **finto** dava lo stesso identico delta, perché in regime di quasi-pareggio qualunque perturbazione ribalta una frazione di casi. Ogni esperimento vuole un controllo che dica **cosa sta misurando**, e il controllo non è nel protocollo per definizione: il protocollo è ciò di cui si dubita.
- **Una misura la cui etichetta si rivela falsa non è un risultato negativo da conservare: è un risultato da rifare.** Il §7 dice che i risultati negativi restano in tabella, e vale per una misura che ha risposto *male* alla domanda giusta. Non copre il caso in cui la domanda era un'altra, `E-06` si chiamava *«retrieval lessicale BM25»* e misurava qualcos'altro. La riga non si cancella: si rifà, e le due misure restano affiancate con detto quale descriveva cosa. Distinguere i due casi è il motivo per cui esiste la Fase 5.
- **L'ordine dei task dentro una fase non è quello della tabella.** Ciò che cambia il comportamento va prima di ciò che lo misura, e una misura costosa ripetuta per N configurazioni va per ultima: qualsiasi modifica al comportamento fatta dopo la invalida, e ce ne si accorge a GPU spesa. Prima di iniziare una fase, ordinare i suoi task su questo criterio e scriverlo nella sezione della fase.
- Temperatura 0 e finestra 32k su ogni run di valutazione, annotate nel risultato.
- README aggiornato a ogni fase.
- Gate non superato → non si avanza.
- `Co-authored-by:` in ogni commit.
- Un branch per fase, PR anche essendo in due: la descrizione della PR è la documentazione della fase.
- Timebox anti-blocco: due ore senza progressi → TODO e si passa oltre.

**Per un coding agent**

- I contratti in §3 sono vincolanti. Non introdurre campi né rinominarli senza aggiornare questo documento.
- Ogni task ha un criterio di accettazione: implementa il test che lo verifica insieme al codice.
- Nessuna dipendenza nuova senza aggiornare `STACK.md`, **inclusa la sua licenza**. Il progetto è MIT: nessuna libreria copyleft (GPL, AGPL) può entrare in albero. PyMuPDF in particolare è AGPL-3.0: usare `pypdfium2` e `pdfplumber`.
- Nessuna chiamata diretta a un server modelli: passare sempre da `LLM_BASE_URL`.
- I parametri di retrieval vivono in `config.py`. Non incorporarli nel codice dei moduli.
- Non committare modelli o indici, tranne il mini-indice del profilo `demo`.
- Ogni funzione di valutazione riceve e restituisce `dataset_id`. Nessuna metrica senza di esso.

---

## 16. Struttura del repo

```
├── compose.yml              # profili demo / full / eval
├── Dockerfile               # multi-stage: build del frontend + servizio Python
├── Makefile                 # fetch-datasets, ingest, eval, dev, demo, dashboard
├── README.md · ROADMAP.md · STACK.md · CLAUDE.md · .env.example
├── src/
│   ├── datasets/            # caricamento HF, normalizzazione a Chunk
│   ├── profiling/           # profilatore documenti, assegnazione doc_genre
│   ├── ingestion/           # le 3 pipeline, chunking, bbox, rendering
│   ├── index/               # embedding, upsert Qdrant (una collection per dataset)
│   ├── retrieval/           # ibrido, RRF, rerank, filtri, riscrittura, routing
│   ├── generation/          # prompt, parsing e riparazione citazioni, entailment, astensione
│   ├── eval/                # harness, metriche, config di run
│   ├── service/             # un caso d'uso per funzione: CLI e API chiamano qui (A-01)
│   ├── api/                 # FastAPI, eventi SSE
│   ├── providers.py         # scelta del provider ONNX, in un posto solo (Q-05)
│   └── config.py
├── eval/
│   ├── contamination/       # prompt, chiavi, output grezzi dei test pre-implementazione
│   ├── golden/              # query e qrels normalizzati, incluse le non rispondibili
│   ├── metrics/
│   └── results/             # un EvalRun per esecuzione, con hash commit, più i dump per query
├── scripts/                 # CLI di ingestione, valutazione, migrazione e sonde
├── tests/                   # suite Python, inclusi i test di confine (dashboard, tipi UI)
├── dashboard/               # Streamlit interna per debug e confronto configurazioni
├── ui/                      # frontend demo: api/ (contratto generato), app/ (stato), ui/ (viste)
├── docs/                    # progress.md, open-questions.md, hardware.md, ui-mockup.html
└── data/                    # gitignored, tranne il mini-dataset demo
```

---

## 17. Rischi

| Rischio | Quando lo scoprite | Mitigazione |
|---|---|---|
| **Tutti i dataset candidati contaminati** | T-03, prima settimana | Enfasi su `citation_precision` invece che sulla correttezza |
| I due dataset principali troppo simili | Gate Fase 1 | Sostituire il secondo, costo ~1 giorno |
| Il routing non produce delta misurabili | R-07 | Resta una funzionalità documentata; l'affermazione 2 cade, le altre due reggono |
| Il rumore di fondo è più grande dei delta | E-07 | Più esecuzioni, golden set più ampio, metriche più discriminanti (success@1 invece di recall@10) |
| 26B inutilizzabile sulla GPU | T-02 | Si scala a 12B, la curva regge |
| Tempo che finisce | Sempre | Fase 8 è tutta tagliabile; entro la Fase 7 il progetto è completo |
