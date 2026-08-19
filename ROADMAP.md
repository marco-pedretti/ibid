# ibid — Piano di implementazione

**Banco di prova per sistemi RAG con attribuzione verificabile**, su modelli piccoli eseguiti in locale, valutato quantitativamente su dataset di benchmark pubblici.

## Il nome

**`ibid`** — dal latino *ibidem*, "nello stesso luogo". È l'abbreviazione usata nelle note bibliografiche per rimandare alla fonte appena citata, senza ripeterla per esteso.

È il nome del progetto perché descrive esattamente ciò che il sistema fa: per ogni affermazione che produce, riportare al punto preciso del documento da cui viene. Non "una risposta con dei link in fondo", ma un rimando verificato all'origine di ogni singola frase.

Convenzioni:

- nome del repository, della cartella di lavoro e del package Python: `ibid` (minuscolo)
- descrizione "About" del repo, obbligatoria e senza metafore:
  > *Banco di prova per RAG con citazioni verificate a livello di frase, su modelli piccoli in locale*

Il nome evocativo attira, la descrizione spiega. Chi scorre una lista di repository dà tre secondi a ciascuno: senza la descrizione, un nome criptico è solo criptico.

---

> **Rinumerazione del 2026-08-13.** L'inserimento della Fase 7 (Servizio e API) ha spostato di uno le sezioni finali. I riferimenti dentro il repo sono stati aggiornati, **ma i messaggi di commit anteriori a quella data no** — non si riscrivono. Chi legge la storia traduca così:
>
> | prima | ora |
> |---|---|
> | §13 Cosa NON fare | **§14** |
> | §14 Regole di lavoro | **§15** |
> | §15 Struttura del repo | **§16** |
> | §16 Rischi | **§17** |
>
> Le sezioni citate più spesso nel codice — §0 (le tre affermazioni) e §3 (contratti dati) — **non si sono mosse**, ed è il motivo per cui la rinumerazione era accettabile. Le fasi si sono spostate di conseguenza: la vecchia Fase 7 (Interfaccia) è ora la Fase 8, la vecchia Fase 8 (Extra) è la Fase 9.

Questo documento è la fonte di verità per l'implementazione. È scritto per essere eseguibile anche da un coding agent: ogni task ha un identificativo, un deliverable e criteri di accettazione verificabili. Le scelte tecnologiche stanno in `STACK.md`.

**Divisione del lavoro fra i documenti.** Qui stanno **decisioni e vincoli**; le **misure** stanno in [`docs/progress.md`](docs/progress.md), che è anche l'unico posto dove si legge cosa è già fatto; le **ipotesi non ancora verificate**, con il protocollo per verificarle, stanno in [`docs/open-questions.md`](docs/open-questions.md). La regola pratica: se un numero cambierebbe rifacendo una misura, non appartiene a questo file — ci appartiene la decisione che quel numero ha motivato. Serve perché il criterio di accettazione di un task deve restare leggibile in una riga: quando ci finisce dentro il resoconto di com'è andata, smette di essere un criterio.

---

## 0. Cosa dimostra il progetto

Tre affermazioni, ognuna sostenuta da una riga di tabella:

1. **L'attribuzione verificata a livello di frase è misurabile**, e i modelli piccoli senza verifica sbagliano in modo sistematico (`citation_precision`).
2. **Il routing automatico della pipeline in base al genere documentale batte una pipeline generica unica**, e il guadagno si vede per dataset.
3. **Con un retrieval buono la taglia del modello conta molto meno di quanto si creda** — ipotesi da testare, i test preliminari la suggeriscono.

Tutto il resto (interfaccia, toggle, upload) serve a rendere queste tre cose visibili.

---

## 1. Stato di partenza

**Già acquisito** — test svolti prima dell'implementazione, output grezzi da conservare in `eval/contamination/`:

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
    config: dict[str, Any] # flag di retrieval attivi — vedi src/eval/run_config.py
    metrics: dict[str, float]
```

`config` è additivo (default `{}`) e **non** entra nel calcolo di `config_hash`: i run misurati prima della sua introduzione restano confrontabili. Serve a tenere `pipeline_mode` binario come dichiarato qui sopra, invece di usarlo come etichetta libera in cui infilare `rerank`, `filtered_text`, `docagg` e simili — cosa che rende impossibile selezionare due run che differiscono per un flag solo (§15).

### 3.4 Configurazione

Ogni scelta di retrieval è un parametro in `config.py`. Un'ablation deve essere un ciclo su file di configurazione. Se cambiare il reranker richiede di toccare un modulo, il design è sbagliato.

### 3.5 Contratto UI ↔ API

Scritto **prima** degli endpoint (A-03), e prima di qualunque scelta di design dell'interfaccia. Non descrive come la UI appare: descrive **cosa può chiedere e cosa riceve**. Sta qui e non nella Fase 8 perché è un contratto dati, e perché è ciò che la Fase 7 implementa.

**Deriva dai requisiti già decisi**, non è da inventare:

| requisito di Fase 8 | cosa impone |
|---|---|
| U-02 — lista documenti sempre visibile | la risposta porta **sempre** i chunk recuperati, non solo il testo |
| U-05 — indicatore di pipeline | ogni chunk porta `pipeline` e `doc_genre` |
| U-07 — non verificate marcate, non nascoste | ogni citazione porta il **proprio verdetto**, e l'API non ne filtra nessuna |
| U-03 — RAG on/off affiancati | la richiesta accetta il toggle; le due risposte sono confrontabili |
| U-01 — cambio dataset senza riavvio | esiste `GET /datasets`; nessuna costante nel frontend |
| U-06 — link profondi | ogni citazione porta `source_uri` e `page`; `bbox` resta `null` finché I-06 è rinviato — **dichiararlo, non simularlo** |

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

1. **Il testo grezzo non è il testo finale, e si è scelto di streammarlo comunque.** Il parser di C-02 ripara i marcatori (`[1] [2]` → `[1][2]`) e scarta quelli fuori contesto, quindi ciò che scorre in `token` differisce da `answer`. L'alternativa — ritardare lo stream fino al parser — costa lo streaming per intero: la prima parola arriverebbe **dopo** l'ultima, cioè dopo gli ~11 s che U-10 dice esplicitamente di non nascondere.

   Quindi il contratto è: **`token` è provvisorio, `answer` lo sostituisce.** Ne discende una regola per la UI, ed è vincolante: **finché `answer` non arriva, i marcatori che scorrono non sono cliccabili.** Renderli attivi prima significherebbe offrire un link a un `[2]` che il parser potrebbe scartare. `raw_text` viaggia comunque in `answer`, perché è ciò che C-01 misura e perché una UI che voglia mostrare la riparazione deve poter mostrare da cosa.

2. **`chunks` arriva prima di `answer`.** È ciò che rende U-02 realizzabile: la lista documenti compare mentre il modello sta ancora scrivendo.

3. **Il guasto è un evento, non uno stato HTTP.** Quando lo stream è cominciato gli header sono già partiti, e un 500 non è più spedibile: un errore a metà risposta può solo essere un altro evento. Il servizio continua a sollevare — è l'orlo HTTP che traduce — così un CLI vede la traccia di stack e un browser uno stato disegnabile. `stage` esiste perché la UI possa dire «le fonti ci sono, la risposta no» invece di buttare via tutto.

#### Il criterio di completezza

**La UI deve poter leggere lo schema e sapere cosa disegnare in ogni stato**, inclusi «sto aspettando i verdetti», «il modello si è astenuto» e «il retrieval non ha trovato niente». Se uno stato non è rappresentabile, manca un campo — e si scopre ora invece che a frontend scritto.

Due stati meritano di essere nominati, perché è facile crederli deducibili e non lo sono:

- **«Attendo i verdetti»** non è `citations == []`. Quella lista vuota copre tre situazioni diverse: verifica non chiesta, verifica fatta senza citazioni da giudicare, verdetti in arrivo. Con lo streaming la terza è la norma, quindi `answer` porta `verification_pending`.
- **«Chi si è astenuto»** non è un booleano. Il gate di C-04 rifiuta prima di chiamare il modello — costo 0 s di GPU — e il modello che dichiara di non sapere costa ~11 s. Sono eventi diversi, quindi `abstention` vale `""` | `"retrieval"` | `"model"`.

Analogamente **`gate.active: false`** significa «non c'era una soglia calibrata per questa collection e questa modalità», che non è «i punteggi erano alti abbastanza». Confonderle farebbe leggere come garanzia una cosa che non è avvenuta.

#### Cosa il contratto NON copre

Layout, componenti, stile, gestione dello stato lato client, paginazione, cronologia delle query, sessioni salvate. Non incidono sulla forma delle risposte, quindi non vincolano l'API e restano decisioni di Fase 8.

---

## 4. Fase 0 — Fetta verticale e gate di contaminazione

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

### T-03 in dettaglio — il gate

Per ogni dataset candidato: 16 domande costruite con lo stesso schema dei test preliminari, sottoposte a E4B e 12B **senza contesto**, temperatura 0, chat separate, più i due controlli positivi.

**Esito atteso (buono):** il modello non conosce i dati specifici, oppure li sbaglia con sicurezza. Si procede.

**Esito da scarto:** il modello risponde correttamente senza retrieval. Il dataset non è utilizzabile come dimostrazione e va sostituito.

**Se tutti i candidati risultano contaminati**, il progetto non muore ma cambia enfasi: il confronto A/B si sposta dalla correttezza alla `citation_precision`, dove il modello nudo non può competere per costruzione — senza contesto non ha nulla da citare. Va deciso qui, non in Fase 5.

**Gate:** una query produce una risposta con almeno una citazione risolvibile a un chunk reale, e il risultato di T-03 è documentato in `docs/contamination.md`.

---

## 5. Fase 1 — Ingestion multi-dataset e profilatore

**Durata: 1 settimana.**

| ID | Task | Criterio di accettazione |
|---|---|---|
| I-01 | **Profilatore documenti**: pagine, presenza di strato testuale, densità di tabelle, numero di colonne, profondità della struttura | Produce un report tabellare per dataset. Serve prima come triage, poi per il routing |
| I-02 | Assegnazione `doc_genre` dal profilo | Classificazione su 50 documenti verificata a mano, ≥90% corretta |
| I-03 | Pipeline `continuous_text`: chunking su paragrafi con overlap | Distribuzione delle lunghezze in **token** riportata per dataset, contro la finestra dell'embedder. *Aggiunto il 2026-08-11 e attualmente non soddisfatto* — vedi OQ-04 |
| I-04 | Pipeline `structured_hierarchical`: chunking su sezioni, `section_path` popolato | Come I-03, più `section_path` non vuoto dove la struttura esiste |
| I-05 | Pipeline `table_heavy`: tabella come unità atomica, mai spezzata a metà | Nessun chunk contiene una tabella troncata |
| I-06 | Estrazione bbox e rendering pagine a PNG dove il formato lo consente | `bbox` e `page` popolati per i dataset con PDF |
| I-07 | Indicizzazione `multilingual-e5-large` (densi) + `Qdrant/bm25` (sparsi) su Qdrant, una collection per dataset | Job one-shot: il tempo è riportato, non vincolato. **BGE-M3 sostituirà `multilingual-e5-large` quando fastembed PR #602 sarà mergiato — re-ingestione obbligata, e va trattata come ablation separata, non come patch** |

**I-01 va fatto per primo** anche se serve al routing solo in Fase 3: è lo strumento con cui decidete cosa entra nel corpus e come, e vi risparmia di scoprire a valle che un dataset non è quello che pensavate.

**I-06 è rinviato**: nessuno dei due dataset correnti distribuisce PDF nativi o coordinate, quindi `bbox` resta `None` e l'overlay di U-06 non ha su cosa poggiare. Diventa applicabile solo aggiungendo un dataset con PDF e coordinate esportate. Motivo per esteso in [`docs/progress.md`](docs/progress.md), I-06.

**Gate:** report del profilatore per i tre dataset, e i due dataset principali risultano di generi diversi.

---

## 6. Fase 2 — Harness, baseline, rumore

**Durata: 1 settimana.** Il cardine del progetto. Da fare a quattro mani.

| ID | Task | Criterio di accettazione |
|---|---|---|
| E-01 | Import di query e qrels dai dataset, normalizzati a uno schema comune | `eval/golden/{dataset_id}.jsonl` validato |
| E-02 | **Query non rispondibili**: 30-40 per dataset | Vedi nota sotto |
| E-03 | Metriche IR via `ir_measures`: recall@k, MRR, nDCG, success@1 | `make eval` produce un `EvalRun` valido |
| E-04 | **Baseline A**: nessun retrieval, prompt permissivo | Risposte corrette / sbagliate / inventate |
| E-05 | **Baseline B**: nessun retrieval, prompt severo | Tasso di astensione |
| E-06 | **Baseline C**: solo retrieval lessicale | Delta contro il denso **per dataset**, e la configurazione è verificabilmente BM25: modificatore IDF attivo sull'indice, query codificate come query. *Aggiunto il 2026-08-11 e attualmente non soddisfatto* — vedi OQ-03 |
| E-07 | **Rumore di fondo**: 5 esecuzioni della stessa configurazione | Dispersione riportata. Nessuna differenza inferiore a questa soglia sarà mai dichiarata un miglioramento |

**Nota su E-02 — è l'unica annotazione che dovete davvero fare, ed è quasi gratis.** I benchmark pubblici non contengono domande senza risposta, ma a voi servono per misurare l'astensione. Il trucco: prendete query del dataset A e ponetele contro il corpus del dataset B. Sono automaticamente non rispondibili, non richiedono scrittura manuale, e sono realistiche. Integratele con una decina scritte a mano su argomenti plausibili ma assenti.

**E-07 va eseguito prima di qualunque ablation.** I test preliminari hanno già mostrato che lo stesso modello sulla stessa domanda cambia risposta tra esecuzioni.

**Gate:** `make eval` gira end-to-end e produce le tre righe di baseline con barre d'errore, per dataset.

---

## 7. Fase 3 — Retrieval e routing

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

## 8. Fase 4 — Citazioni verificate e scaling

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
| I-08 | **Misura** dei prefissi `query:`/`passage:` di E5 su un indice ridotto, senza re-ingestione | Delta appaiato su doc_R@5 — o la sua assenza |
| I-10 | **Misura** del chunking contro la finestra da 512 token dell'embedder, sullo stesso indice ridotto | Delta appaiato su doc_R@5, **misurato separatamente da I-08** |
| C-08 | Premessa di entailment senza il markup delle tabelle OCR, e **rimisura** di `citation_precision` su LEDGER | Le due varianti affiancate sulle stesse generazioni. Chiude la decisione che il gate qui sotto rimandava |
| C-09 | **Verificatore numerico per il genere tabellare**: `numeric_citation_precision` | Riportata per LEDGER accanto a `citation_precision`, **mai nella stessa colonna**. Validata sul floor test di OQ-05 |

**Perché due task `I-` in questa fase.** Il prefisso indica di cosa parla il task, non in che fase sta (precedente: `D-01` in Fase 3). Entrambi i difetti sono nell'ingestione, ma stanno qui perché **decidono se C-06 può partire**: C-06 è la misura più cara del progetto e l'affermazione 3 del §0 dice *«con un buon retrieval»*. Lanciarlo su una premessa non verificata significa rischiare di rifarlo. I-08 e I-10 **misurano e basta** — le correzioni sono I-09 e I-11, in Fase 5 — e vanno misurati **uno alla volta** (§15): vivono nella stessa funzione, `encode()`, e insieme darebbero un delta non attribuibile.

**I-10 è il più grande dei due.** Il tokenizer tronca a 512 token e le pipeline di chunking non lo sanno: il **67,6%** dei chunk di open_ragbench e l'**82,1%** di ledger lo superano, e del chunk mediano entra nell'indice **circa metà del testo**. Il testo intero arriva comunque all'LLM, quindi il sistema risponde su materiale che non ha potuto trovare. Protocolli e numeri in `docs/open-questions.md`, OQ-02 e OQ-04.

**Gate:** confronto sulle non rispondibili tra baseline A e sistema completo, e curva delle metriche in funzione della taglia del modello.

### Ordine di esecuzione (deciso il 2026-08-10, dopo C-03)

L'ordine non è quello della tabella, per la regola del §15. Il vincolo che lo determina: **C-06 rilancia l'intero sistema per ogni taglia di modello**, quindi ogni modifica al comportamento fatta dopo lo invalida.

1. **C-05** — cambia il prompt, e `prompt_hash` entra in `config_hash`: farlo dopo C-04 obbligherebbe a rimisurare C-04. Verificabile in gran parte sulle 891 generazioni già salvate, dove le risposte in lingua mista sono ≤1 su 189 — entrambi i corpus sono inglesi, quindi è più una verifica che una correzione.
2. **C-04** — l'ultima modifica alla pipeline. C-03 gli ha già fornito i dati: `uncited_claim_rate` 0,106 e 0,156, astensione al 26,5% su LEDGER contro 5,5% su ORB.
3. **E-04/E-05** — **mai eseguiti** (nessun risultato con `harness: generation` in `eval/results/`), e il gate di questa fase li richiede. Indipendenti dagli altri: si possono lanciare in parallelo.
4. **C-07** — ✅ fatto il 2026-08-12. Una misura sola, e risultato negativo: il guadagno esiste sul testo grezzo e sparisce dopo il parser di C-02. Vedi `docs/progress.md`.
5. **I-10, poi I-08** — ✅ fatti il 2026-08-12. I-10 regge (+1,26 punti a doc@1, p=0,0384, significativo a tutte le profondità), I-08 no. C-06 può partire senza aspettare una re-ingestione: entrambe le correzioni restano in Fase 5, e I-09 non è più giustificata.
6. **C-08** — ✅ fatto il 2026-08-12, risultato negativo: il markup non era la causa (p=0,1112).
7. **C-09** — ✅ fatto il 2026-08-12. `numeric_citation_precision` 0,7328 su LEDGER contro lo 0,2374 dell'NLI sulle stesse coppie; su open_ragbench copertura 0,2%, cioè lo strumento si rifiuta di giudicare la prosa. La riga LEDGER della curva di scaling ora dice qualcosa.
8. **C-06** — ✅ fatto a due punti il 2026-08-13. E2B ed E4B; il 12B costa **240 s/query misurati**, cioè 13,3 ore, ed è scartato col precedente del 26B in T-02. **L'affermazione 3 del §0 resta non determinata**: due punti mostrano un divario grande, il terzo avrebbe detto se la curva si appiattisce.

**Da decidere prima di C-06, non dopo — ora è C-08.** Su LEDGER `citation_precision` non è interpretabile come proprietà del generatore: il verificatore NLI è fuori distribuzione su claim numerici contro tabelle OCR (vedi `docs/progress.md`, C-03). Se C-06 gira così, la curva per taglia del modello ha una riga muta su un dataset su due, e la cosa emerge a run finite.

Quantificato il 2026-08-11 sui 117 chunk citati: la premessa mediana è per il **26,5%** token di markup, il terzo quartile 62,5%, la peggiore 77,2% — mentre il **96,7%** dei claim contiene almeno tre cifre. Non è "il modello è debole": è che nessuno dei due lati della coppia somiglia a ciò su cui è stato addestrato. C-08 toglie il markup e rimisura; se dopo il numero resta non interpretabile, allora serve un verificatore diverso per quel genere, ed è una decisione più grande — ma prenderla ora significherebbe costruire un secondo strumento per aggirare un difetto rimediabile nel primo.

---

## 9. Fase 5 — Correttezza delle misure

**Durata: 2–3 giorni** (I-09 esclusa: se scatta, è una settimana).

**Questa fase non contiene miglioramenti.** Il §7 dice che i risultati negativi restano in tabella, e resta vero. Qui c'è la categoria che quella regola non copre: **misure la cui etichetta si è rivelata falsa.** Una riga della Fase 2 si chiama *«E-06 — baseline C: retrieval lessicale BM25»* e quella misura non è BM25 — non è un risultato negativo da conservare, è il risultato di un'altra cosa, e va rifatto.

Tutte e tre le voci nascono dall'audit del 2026-08-11, in cui le librerie sono state confrontate con la loro documentazione ufficiale. Il fatto, il protocollo e ciò che **non** è dimostrato stanno in [`docs/open-questions.md`](docs/open-questions.md).

| ID | Task | Criterio di accettazione |
|---|---|---|
| I-09 | ~~Prefissi E5 in `encode()`, re-ingestione, rimisura~~ — **non applicabile**: era condizionata a I-08, risultato negativo | Vedi `docs/progress.md` e OQ-02 |
| I-11 | ~~Tetto di chunking allineato alla finestra dell'embedder~~ — **decisa il 2026-08-12: non adottata** | Nessun effetto sulla generazione; il guadagno di `citation_precision` era la lunghezza della premessa. Da riconsiderare alla prossima re-ingestione per la latenza (−44%). Vedi `progress.md` |
| R-08 | `modifier=IDF` sull'indice sparso (Qdrant lo richiede: fastembed esclude l'IDF di proposito) | E-06 e R-01 rimisurati — **una sola causa cambiata** |
| R-09 | Query BM25 codificate con `query_embed` invece che come documenti | Rimisura **separata** da R-08 |
| R-10 | OQ-01, passi 1–2: perché il routing peggiora LEDGER di 17 punti | Il passo 3 (6–7 h GPU) solo se il 2 è positivo |
| R-11 | `SEARCH_EXACT` / `HNSW_EF` come parametri di ricerca: la ricerca approssimata perde richiamo dove l'indice è denso | Il parametro esiste ed è **spento di default**; acceso, entra nel `config_hash` e le run dense non si spostano |

**R-08 e R-09 non si fanno in un commit solo.** Sono due cause indipendenti — l'IDF vive nell'indice, la codifica della query nel client — e correggerle insieme misurando una volta viola il §15. Costa una rimisura in più: dieci minuti.

> **Cosa hanno comprato quei dieci minuti** (misurato il 2026-08-13): R-08 muove fino a **+27,9 punti**, R-09 **4 query su 10.000**. Correggendole insieme il risultato sarebbe stato attribuito a «OQ-03» e la ripartizione — **100 a 0** — non si sarebbe mai vista. La regola non è pignoleria contabile: è l'unica cosa che distingue una causa da una coincidenza.

**I-09 e I-11 invece condividono la re-ingestione, se scattano entrambe.** Non è un'eccezione al §15: l'attribuzione è già stata fatta a monte, da I-08 e I-10, che misurano una causa ciascuno su un indice ridotto. La re-ingestione completa non è la misura che separa le cause — è l'adozione di due correzioni già separate, e imporne due da 618 minuti ciascuna costerebbe venti ore di GPU per un'informazione già in mano.

**Ordine:** R-08, R-09, R-10 sono indipendenti da I-09 e si possono fare prima. I-09 è la sola che obbliga a rifare tutto ciò che sta sopra, quindi va per ultima.

**Gate:** ogni numero rifatto è affiancato al vecchio in `progress.md`, con detto **quale** delle due misure descriveva cosa. Nessuna riga sostituita in silenzio.

---

## 10. Fase 6 — Qualità del codice

**Durata: 3–4 giorni.** Prima della Fase 7, perché il servizio si estrae **sopra** questi moduli: rifattorizzarli dopo significa cristallizzare i difetti dietro un'interfaccia, e poi rifarli due volte.

**Un refactor senza criterio di accettazione è illimitato**, ed è l'unica cosa in questo repo che non avrebbe un numero accanto. Quindi la fase non è "leggibilità e pulizia": è una lista chiusa di difetti già osservati, ognuno con la prova che esiste.

| ID | Task | Criterio di accettazione |
|---|---|---|
| Q-01 | Costruzione di `EvalRun` unificata: oggi sono **5 siti**, `reasoning_enabled` è derivato in 4 e ancora scritto `False` a mano in `src/eval/harness.py` | Un solo posto lo costruisce; il campo non è più scrivibile a mano |
| Q-02 | **Entrambi** gli harness senza dump per query — baseline **e retrieval** — salvano i risultati per query, come già fa quello delle citazioni | Il taglio 45%→17% di E-04/E-05 diventa un test appaiato; e un confronto fra due run di retrieval archiviate non richiede più di ricostruire uno stato a comando |
| Q-03 | `scripts/profile.py` non adombra più il modulo `profile` della standard library | `import transformers` da dentro `scripts/` smette di fallire |
| Q-04 | Igiene di import e lint su `scripts/` | `ruff check` pulito sul repo |
| Q-05 | La scelta del provider ONNX vive in **un posto solo**, e la dipendenza GPU è un extra opzionale di `pyproject.toml` | Nessun file di `src/` nomina `DmlExecutionProvider`; su una macchina senza DirectML l'import riesce e ripiega dichiarandolo |
| Q-06 | **Registro dei dataset**: i dataset disponibili si leggono da un posto solo, non da 14 liste `choices=[...]` scritte a mano | Aggiungere un dataset dello stesso genere richiede il suo loader e una riga nel registro; **nessuno script va toccato** |

**Ogni voce è un difetto che ha già morso**, non un'ipotesi di stile:

- **Q-01** — è la stessa duplicazione che ha lasciato `reasoning_enabled=False` scritto a mano mentre il modello ragionava, difetto che C-01 ha corretto in due harness su tre. Il terzo è ancora così, e non è cosmetico: con `--query-rewrite` quell'harness *usa* il modello (R-03).
- **Q-02** — durante E-04/E-05 la diagnosi dei tre difetti ha richiesto di rigenerare a mano le risposte, perché quelle delle run non esistevano più. **E il 2026-08-13 il difetto ha morso di nuovo, altrove**: le run di retrieval archiviate non salvano i risultati per query, quindi il confronto con loro in R-08 era marginale — due medie, nessun test. È stato possibile fare McNemar solo perché lo stato pre-correzione era **riproducibile a comando**, cosa che non sarà vera la prossima volta.
- **Q-03** — ha già rotto un import durante C-03.
- **Q-05** — il blocco che sceglie `DmlExecutionProvider` è copiato in `src/index/embed.py`, `src/generation/entailment.py` e `src/retrieval/reranker.py`, più due volte in un probe. Non è solo duplicazione: è **la cucitura di U-12**, e finché sta in cinque posti la portabilità Linux è cinque modifiche invece di una.
- **Q-06** — `choices=["open_ragbench", "ledger", "all"]` è scritto a mano in **14 script**. Il nucleo è già agnostico (16 sole occorrenze letterali in tutto `src/`, quasi tutte nei loader, cioè dove devono stare): il coupling è tutto ai bordi. Serve anche a U-01, che chiede di cambiare dataset senza riavvio.

**Q-05 e Q-06 sono nuove, aggiunte il 2026-08-13**, e non sono un allargamento di comodo: la prima è il prerequisito della Fase 7 (un servizio che gira su un'altra macchina probabilmente gira su Linux), la seconda è ciò che rende questo un *testbed* invece di un programma per due dataset.

**Ordine di esecuzione** (§15 chiede di deciderlo prima e di scriverlo):

**Q-03 → Q-06 → Q-04 → Q-05 → Q-01 → Q-02**

Il criterio è ridurre il lavoro rifatto, non la difficoltà crescente. Q-03 e Q-06 toccano entrambi tutti gli script, quindi vanno **prima** di Q-04: passare il lint su `scripts/` e poi rimescolarli significherebbe passarlo due volte. Q-05 è isolato e sta dove capita. Q-01 e Q-02 vanno per ultimi perché sono gli unici due che possono far muovere un numero, e conviene che il gate sia l'ultima cosa a essere messa alla prova invece che la prima.

**Gate, e non è negoziabile: nessuna metrica cambia.** Un refactor puro lascia invariato il conteggio dei test (§15) e lascia invariati i numeri: `scripts/rescore_citations.py` ricalcola le metriche di C-01 dai dump salvati a costo zero, e alla fine della fase deve restituire **gli stessi valori** già registrati. Se cambia un decimale, non era un refactor.

---

## 11. Fase 7 — Servizio e API

**Durata: 1–1,5 settimane.** È la fase che rende il backend sostituibile dal frontend e viceversa, e che gli permette di girare su un'altra macchina. **Non è un ritocco**: è il lavoro architetturale più grande rimasto.

**Il confine, detto una volta.** Il backend espone HTTP; il frontend è un client come un altro. Chiunque può scriverne un secondo, o nessuno. La demo React della Fase 8 è **un** consumatore dell'API, non il suo scopo.

| ID | Task | Criterio di accettazione |
|---|---|---|
| A-01 | **Strato `src/service/`**: una funzione per caso d'uso, chiamata sia dalla CLI sia dall'API | Nessun endpoint contiene logica di pipeline. La stessa richiesta dalla CLI e dall'API produce lo **stesso** risultato, verificato da un test che le confronta |
| A-02 | **La configurazione di una richiesta smette di passare da `cfg` globale**: parametri di retrieval e generazione viaggiano nella richiesta | Due richieste concorrenti con configurazioni diverse non si contaminano — test con due `top_k` diversi in parallelo |
| A-03 | Il **contratto UI ↔ API** del §3.5 è implementato: schema delle risposte ed eventi dello stream | Ogni stato dell'interfaccia previsto in Fase 8 è rappresentabile nello schema, incluse «attendo i verdetti» e «il modello si è astenuto» |
| A-04 | Endpoint FastAPI: `/health`, `/datasets`, `/query` (SSE), `/chunk/{chunk_id}` | `docker compose up` e una query completa da `curl`, senza il frontend |
| A-05 | Backend come servizio in `docker compose`, con `QDRANT_URL` e `LLM_BASE_URL` da ambiente | Backend su una macchina, Qdrant e LLM su un'altra, senza modifiche al sorgente |
| A-06 | **La dashboard Streamlit passa dall'API** invece di eseguire la pipeline | Nessun modulo di `dashboard/` importa `src.index`, `src.retrieval`, `src.generation`, `src.service`, `src.config`, e nessuno apre un client Qdrant. Gli import rimasti sono **elencati con la loro ragione** in `tests/test_dashboard_boundary.py` |
| A-07 | **I tre buchi trovati disegnando la Fase 8**: lista modelli, `reasoning_effort` in richiesta, navigazione del corpus | Nessuna delle quattro schermate della bozza ha bisogno di una costante scritta a mano nel frontend né di una chiamata che non sia all'API. Le aggiunte sono **additive**: un client scritto contro A-04 continua a funzionare, verificato da un test che manda la richiesta minima `{"query": "..."}` |

**A-02 è il task difficile, ed è bene saperlo prima.** Gli harness leggono `cfg` globale — è ciò che ha permesso a R-11 di passare `SEARCH_EXACT` da variabile d'ambiente senza toccare una firma. Comodo per uno script, **impossibile per un servizio**: due richieste concorrenti con `top_k` diverso condividerebbero lo stesso modulo. Finché A-02 non è fatto, l'API è monoutente e non lo sa.

**A-06 è la verifica, non un extra.** La dashboard importa `src.` in **9 moduli, 22 volte**: è il consumatore più esigente che esista già. Se l'API le basta, basterà anche al frontend — e se non le basta, si scopre ora invece che a React scritto. Se dovesse rivelarsi sproporzionata, va **rimandata dichiarandolo**, non silenziosamente omessa: senza, il confine è affermato e non provato.

**Il criterio è stato riscritto eseguendolo** (2026-08-14), e vale la pena dire perché. Era `grep -r "^from src\." dashboard/` — comodo da controllare, e **un proxy per la cosa che interessa**. Sbagliava in due direzioni:

- **Troppo largo.** Catturava la lettura di `eval/results/` e `eval/golden/`, che sono file sul disco della dashboard e non stanno dietro nessun endpoint. Per leggerli servono i contratti dati del §3, e un contratto condiviso è il contrario di una duplicazione. Soddisfare il `grep` avrebbe richiesto o di ricopiare lo schema di `EvalRun` nella dashboard, o di far servire all'API l'archivio degli esperimenti — e la lista di ciò che la Fase 7 espone è dichiarata vincolante poche righe più su.
- **Troppo stretto.** `^from src\.` non vede un import annidato dentro una funzione, che è esattamente dove `state.py` teneva il proprio client Qdrant.

Il criterio nuovo dice la cosa che il vecchio approssimava: **la dashboard non deve *eseguire* la pipeline.** Gli import rimasti sono cinque, ciascuno con la ragione scritta accanto in un test che fallisce se ne compare un sesto senza che qualcuno l'abbia deciso.

> **A-06 ha prodotto anche un endpoint.** Dall'API mancava la metà che non genera: l'unico modo di vedere dei chunk era `/query`, cioè pagare una generazione — 200 generazioni per un batch del Failure Explorer. Da qui `POST /retrieve`, che accetta **molte query in una chiamata** perché l'embedding è batch per natura. È esattamente l'esito che questo task esisteva per provocare.

**A-07 è lo stesso meccanismo una seconda volta** (2026-08-14), e questo dice qualcosa che va scritto: A-06 ha esercitato *un* consumatore, non tutti. La bozza d'interfaccia della Fase 8 — quattro schermate disegnate prima di scrivere React — ne ha rivelati altri tre.

| serve a | manca | perché non si può aggirare |
|---|---|---|
| il menu dei modelli | `models` in `Capabilities`, dal proxy di `GET {LLM_BASE_URL}/v1/models` | il browser **non deve parlare con Ollama**: può non raggiungerlo, e §STACK impone che l'inferenza passi da `LLM_BASE_URL`. Una lista di modelli scritta a mano nel frontend è la lezione di Q-06 che si ripete |
| il toggle «Ragionamento» | `reasoning_effort` in `QueryRequest` | `ConfigView` lo **restituisce** già ma la richiesta non lo accetta: si può vedere quale ha girato, non sceglierlo. È l'asse che C-07 misura, e la UI non può toccarlo |
| sfogliare il corpus | `GET /documents` e `GET /document/{doc_id}/chunks` | c'è `/chunk/{id}` (uno, per id) e `/retrieve` (per query): non c'è modo di **navigare**. Senza, l'esploratore può solo cercare, mai mostrare come un documento è stato spezzato — cioè non può rendere visibile il routing, che è U-05 |

**Perché sta in Fase 7 e non in Fase 8.** La Fase 8 dice «il frontend non importa niente da `src/`»: queste sono modifiche a `src/api/` e `src/service/`, e metterle dentro un task U-xx sarebbe la prima violazione di quella regola il giorno dopo averla scritta.

**Nessuna tocca il contratto esistente**, ed è il criterio: due campi additivi e due endpoint nuovi. La regola inversa — cambiare la forma di ciò che è già stato prodotto — è quella che ha reso caro il §3.2.

> **Un effetto collaterale che vale da solo.** `GET /documents` ha bisogno di contare i chunk per documento, e su `ledger` una scansione dei payload costa 2,07 s (10 s su `ledger_routed`). Con un indice payload su `doc_id` la stessa domanda costa **0,025 s** — 80×. L'indice si aggiunge a una collection esistente **senza rifare i vettori**, esattamente come il modificatore IDF di R-08, e `get_by_chunk_id()` prevedeva questo rimedio nella propria docstring da prima che servisse: ogni citazione cliccata in U-06 passa di lì.

**Cosa questa fase NON fa**, e la lista è vincolante quanto quella sopra: nessuna astrazione del vector store, nessun harness a plugin, nessuna coda di messaggi, nessuna autenticazione, nessun multi-tenancy. Le ragioni stanno in §14 — sono la stessa decisione che ha tenuto fuori LangChain.

**Gate: nessuna metrica cambia, e la CLI continua a funzionare identica.** `scripts/rescore_citations.py` deve restituire gli stessi valori registrati, e ogni script di `scripts/` deve girare come prima. Se l'API esiste ma la CLI si è rotta, non è stato estratto un servizio: è stato riscritto il programma.

---

## 12. Fase 8 — Interfaccia

**Durata: 1 settimana.** Da qui il progetto è completo e presentabile. Costruita **sopra** l'API della Fase 7: il frontend non importa niente da `src/`.

| ID | Task | Criterio di accettazione |
|---|---|---|
| U-00 | **Scheletro**: Vite + React + TypeScript, client SSE scritto a mano, temi chiaro/scuro, i18n IT/EN, `/datasets` all'avvio | I tipi del contratto sono **generati** da `src/api/`, non riscritti a mano: la suite Python fallisce se divergono. Nessuna costante del backend vive nel frontend |
| U-01 | **Selettore dataset**: demo / principale / secondo genere | Cambio dataset senza riavvio |
| U-02 | Nessun selettore di modalità: lista documenti sempre visibile, risposta sintetica sopra | La lista documenti è visibile senza interazione in ogni stato dell'interfaccia |
| U-03 | **Toggle RAG on/off**: stessa query, risposta nuda contro risposta con citazioni, affiancate | Generate dalla stessa query nella stessa sessione |
| U-04 | Toggle del prompt del baseline: permissivo / severo | Mostra la differenza tra invenzione e astensione |
| U-05 | Indicatore della pipeline usata per il documento recuperato | Rende visibile il routing |
| U-06 | Link profondi dalle citazioni; dove ci sono i PDF, PNG di pagina con span evidenziato | Da una citazione si raggiunge la pagina della fonte. L'overlay bbox resta scoperto finché I-06 è rinviato: dichiararlo, non simularlo |
| U-07 | Le citazioni non verificate sono marcate visivamente, non nascoste | Una citazione non verificata da C-03 è distinguibile da una verificata senza aprire nulla, e nessuna delle due è nascosta |
| U-08 | Profilo `demo` con indice committato | `docker compose --profile demo up` in < 2 minuti senza download |
| U-09 | Profili `full` e `eval`, healthcheck, `depends_on: service_healthy` | Primo avvio pulito su macchina vergine |
| U-10 | GIF o video di 90 secondi nel README | ≤ 90 secondi, mostra query → risposta citata → apertura della fonte, senza tagli che nascondano la latenza reale |
| U-11 | README: le tre affermazioni del §0, architettura, tabelle per dataset, screenshot, limiti, future work | Le tre affermazioni del §0 compaiono ciascuna con la tabella per dataset che la sostiene, e la sezione limiti nomina i risultati negativi invece di ometterli |
| U-12 | **Portabilità Linux**: provider ONNX scelto dalla piattaforma, dipendenze GPU come extra opzionali, nessun percorso che assuma Windows | Suite verde e `docker compose --profile demo up` su Linux x86_64, senza modifiche al sorgente |
| U-13 | **Conversazione nuova e cronologia locale**: pulsante «Nuova conversazione», elenco delle conversazioni nella corsia, persistenza in `localStorage` | Si comincia una conversazione nuova senza ricaricare la pagina, e la cronologia sopravvive a un ricaricamento **dichiarando** di essere locale a questo browser. Nessun endpoint, nessuna sessione lato server |

**U-03 è la feature che fa capire il progetto a chiunque**, ed è quasi gratis: i baseline li state già calcolando in Fase 2.

### U-00 — la regola «niente import da `src/`» ha un prezzo, e si paga una volta

«Il frontend non importa niente da `src/`» è la regola giusta: un frontend che importasse la pipeline non ne sarebbe un consumatore, sarebbe un secondo posto in cui la pipeline vive. Ma ne segue che **il contratto del §3.5 esiste in due linguaggi**, e due elenchi scritti a mano divergono — è la lezione di Q-06, in TypeScript. Peggio: la seconda copia diverge *in silenzio*, perché nessun test Python guarda dentro `ui/`.

Quindi `ui/src/api/types.ts` non si scrive, **si genera** da `scripts/gen_api_types.py`, e `tests/test_ui_types.py` fallisce se il file committato non è ciò che il generatore produce oggi. Un campo aggiunto ad `AnswerResponse` senza rigenerare rompe la suite Python: si scopre prima di arrivare al browser, e senza che serva Node per accorgersene.

**Gli eventi SSE non sono modelli pydantic**: `to_wire()` costruisce i payload a mano, ed è l'unico punto del contratto in cui una divergenza non romperebbe nessun tipo Python. Per questo il generatore non li legge, li **esegue**: i nomi dei campi vengono dal dizionario che finisce davvero sul filo.

Due proprietà che il tipo fa rispettare meglio di un test: in `QueryRequest` solo `query` è obbligatorio — cioè il criterio di A-07 verificato dal compilatore a ogni chiamata invece che una volta sola — e le liste di `Capabilities` restano `string[]` e non letterali, perché un valore nuovo lato server deve **arrivare** al frontend, non romperlo.

### Decisioni d'interfaccia prese il 2026-08-14

Ricavate disegnando quattro schermate prima di scrivere React. Quelle che vincolano l'implementazione, non l'estetica.

**La lingua della risposta segue il prompt, non l'interfaccia.** Il selettore IT/EN traduce la cornice — etichette, avvisi, nomi degli stati. Non tocca il testo del modello, gli estratti dei chunk né i messaggi di errore del backend: quelli seguono la lingua della domanda e del corpus. La ragione non è di comodità: far rispondere in italiano su un corpus inglese significherebbe che le citazioni sostengono un testo **tradotto**, e il verificatore NLI di C-03 dovrebbe giudicare cross-lingua un'implicazione che non ha mai misurato in quella condizione. La precisione di citazione è la prima affermazione del §0; non si baratta con una comodità di presentazione.

> **Le query d'esempio sono il caso intermedio, e si risolve mostrando entrambe.** Si leggono nella lingua dell'interfaccia, ma partono in quella del corpus: sotto la traduzione compare la query vera, in mono — il ruolo dei dati, e quella è letteralmente ciò che finisce sul filo. Tradurre anche il testo mandato riporterebbe esattamente il problema di sopra, con l'aggravante che sarebbe il **primo clic** di chi prova il progetto a produrlo.

**Il pannello fonti si apre su `chunks`, non a risposta finita.** Il criterio di U-02 dice «visibile senza interazione in ogni stato», e il protocollo del §3.5 manda `chunks` **prima** del primo token. Le fonti compaiono in ~0,1 s e il testo comincia a ~3 s: l'attesa si riempie invece di premiare, e si vede da dove nasce la risposta mentre nasce.

**U-03 è un layout, non un toggle.** «Affiancate, dalla stessa query, nella stessa sessione» non si ottiene con due messaggi consecutivi in cronologia. Il toggle RAG decide il default della prossima domanda; il confronto è un'azione esplicita su una risposta già data, che la rilancia col RAG invertito e mette le due in due colonne. Il selettore permissivo/severo di U-04 vive **dentro** la colonna senza fonti, l'unico posto dove ha effetto.

**L'esploratore del corpus non è la dashboard.** Vincolo di CLAUDE.md: due UI separate, non fuse. La dashboard confronta configurazioni di retrieval e fa failure analysis — serve a chi misura. L'esploratore mostra **il corpus e come è stato spezzato**: è ciò che rende visibile il routing (U-05) a chi non sa cosa sia un nDCG. Se diventa un confronto A/B di configurazioni, le due UI sono state fuse per sbaglio.

**Lo stream non si legge con `EventSource`.** `/query/stream` è una `POST` e l'`EventSource` del browser fa solo `GET`: serve `fetch` + `ReadableStream` con un parser SSE scritto a mano. Accettare anche `GET` costringerebbe a serializzare quindici parametri in query string — non si fa. Conseguenza voluta: niente riconnessione automatica, che rilancerebbe una generazione da 11 s e produrrebbe una risposta **diversa**. Su caduta si mostra il parziale marcato incompleto, con un «Riprova» esplicito; serve un `AbortController` anche per il pulsante «Ferma».

**La cronologia vive nel browser** (`localStorage`), nessun endpoint, nessuna sessione: non c'è autenticazione né database nello stack, e §14 li tiene fuori. Va **detto** nella UI, non lasciato dedurre — chi cambia macchina non ritrova le sue conversazioni. Questa decisione era presa ma **non era un task**: compariva al §6 fra le cose che non vincolano l'API, qui fra le decisioni d'interfaccia, e nel mockup come voce della corsia — in nessun posto con un ID e un criterio. È diventata **U-13** il 2026-08-14, perché una decisione senza task è la definizione di ciò che non viene fatto. Da eseguire dopo U-07. Cronologia non significa multi-turno: ogni domanda resta indipendente, e riusare i messaggi precedenti per il retrieval è **X-02**.

> **Precisato eseguendo U-13 (2026-08-17).** «Nuova conversazione» è un **pulsante con la forma delle azioni della corsia** — quella di «Esplora il corpus» (`.bottone-esplora`) — e non la prima voce della cronologia, che è dove il mockup la mette (`.crono-voce.attiva`). Consegnata come voce era leggibile ma piatta: la voce più usata della corsia aveva lo stesso peso della meno usata. Come azione d'accento il rischio che aveva suggerito di farne una voce — due controlli con le stesse parole uno sull'altro — non c'è, perché una conversazione senza domande non ha una voce sua: il pulsante *è* il suo posto. Il segno `+` la distingue da «Esplora il corpus» quando saranno una sopra l'altra.

> **La dichiarazione di località sta nel nome della sezione**, «Cronologia locale», col resto della frase nel suggerimento — non in una riga sotto l'elenco. «Solo in questo browser.» era vera e scollegata da ciò di cui parlava: una frase che comincia con «solo» non dice *cosa* sta solo lì. E la cronologia si può **cancellare**, a due tempi: non è nel criterio, ma senza un comando le conversazioni di prova si toglievano solo svuotando `localStorage` dal browser.

> **Si riapre su una conversazione nuova, non su quella che si stava leggendo.** Avevo salvato anche quel dato — «altrimenti la cronologia sopravvive al ricaricamento ma la lettura no» — ed è la lettura sbagliata: chi apre `ibid` lo fa per chiedere qualcosa, quindi ricordare il punto di lettura mette un clic davanti al caso frequente per risparmiarne uno al caso raro. Tornare indietro è una voce della corsia. E una risposta rimasta a metà va sigillata rileggendola — nel deposito ha `fase: "scrittura"`, e al ricaricamento il suo pallino pulserebbe per sempre aspettando uno stream che non esiste più.

**I verdetti non si distinguono solo per colore**: glifo, colore e parola insieme. E il «non sostiene» non è rosso — U-07 dice che non è un errore da nascondere, è il dato. La ragione non è di stile: chi non distingue l'ocra dal verde vedrebbe due pastiglie identiche, e qui la differenza fra le due **è la tesi**.

> **Precisato eseguendo U-07 (2026-08-17).** L'accento resta fuori dai verdetti anche sul marcatore in mezzo alla prosa, e non solo sulle pastiglie. Nel mockup un `[1]` verificato restava accento (`.mk.viva`): con **cinque** stati sullo schermo — inerte, attesa, sostenuta, non sostiene, non verificata — un marcatore sostenuto accento e uno non verificato accento sarebbero indistinguibili, cioè il criterio di U-07 mancato. La bozza non modellava «non verificata», e infatti non aveva il problema. L'accento sopravvive dove la domanda **non è** un verdetto: sul marcatore in attesa, dove la domanda è «è un riferimento valido?» e da `answer` in poi la risposta è sì.

> **L'unità del verdetto è la coppia (frase, chunk), non il marcatore.** Lo stesso `[3]` può comparire in tre frasi e reggerne due; un verdetto per marcatore aggregherebbe la granularità che l'affermazione 1 del §0 esiste per misurare. Ne segue che il frontend deve sapere **dove finiscono le frasi** — e le ritrova invece di ritagliarle, perché una seconda copia di `split_claims` in TypeScript è precisamente ciò che U-00 vieta.

> **Dove ci sono due verificatori, mostrarne uno è mostrare quello sbagliato.** `numeric` è additivo per contratto (§3.5, `schema.py`), e la pastiglia deve mostrarlo **accanto** a `supported`, non al suo posto: su `ledger` il 96,7% dei claim è numerico e l'NLI di C-03 non verifica un'asserzione numerica contro una tabella. Misurato dal vivo il 2026-08-17: capex di Sherwin-Williams, NLI «non sostiene» a 0,208, numerico che trova la cifra dentro la tabella citata. Sceglierne uno in codice sarebbe decidere quale verificatore ha ragione, e quella è una misura, non un `if`.

**I parametri di retrieval stanno sotto «Avanzate»**, chiusi. Un muro di manopole mostra l'ablation, che è il lavoro della dashboard. Restano sempre leggibili in «Dettagli della run», così la configurazione che ha girato non è mai un mistero.

**Il riferimento visivo è [`docs/ui-mockup.html`](docs/ui-mockup.html), ed è vincolante.** Non è un'illustrazione: è dove palette, tipografia e forme sono state decise, e ogni task U-xx ne eredita i token invece di sceglierne di propri. Tre cose in particolare non si cambiano senza dirlo:

- **inchiostro indaco su carta** — accento `#3C4CA8` chiaro / `#97A5F7` scuro, carta `#F7F7F5` / `#131421`. La carta scura è indaco profondo e non grigio neutro: è la stessa tinta dell'accento portata al fondo della scala, ed è ciò che tiene insieme i due temi invece di farli sembrare due progetti;
- **tre ruoli tipografici veri**, e la distinzione non è decorativa: **serif** per il marchio e i titoli (il nome viene da *ibidem*, e la grazia appartiene al mondo bibliografico da cui arriva), **sans** per ciò che si opera, **mono** per i dati — `chunk_id`, marcatori, punteggi, etichette. Tutti font di sistema: U-08 chiede il profilo `demo` senza rete;
- **il marchio** `ib`·`i`·`d` con la **`i` centrale in accento**, serif, weight 600. L'accento della `i` è il token `--marchio`, non `--accent` crudo: su carta chiara l'accento pieno e l'inchiostro sono due scuri quasi uguali di valore e la lettera legge come nera, quindi il token tiene in ciascun tema la variante che si allontana di più dall'inchiostro — resta uguale **l'effetto**, non l'esadecimale. Quella lettera è il punto in cui *ibidem* si lascia intravedere — è l'unica parte dell'interfaccia che spiega il proprio nome senza una nota.
- **i simboli si disegnano, non si scrivono.** Niente glifi di font (`▾`, `↑`, `☾`): il punto precedente impone font di **sistema**, e lì quei caratteri arrivano sottili, più piccoli della loro dimensione nominale e diversi su ogni macchina — a 12 px spariscono. L'insieme sta in `ui/src/ui/Icona.tsx` e ha cinque regole: griglia unica `0 0 16 16`, solo tratto (l'unica eccezione è «sistema», dove il contrasto pieno/vuoto **è** il significato), spessore 2 che scala con la dimensione, estremità e giunti tondi, `currentColor` sempre. Un'icona nuova che le rispetta appartiene all'insieme senza doverla confrontare con le altre.

`ok` / `warn` / `wait` restano separati dall'accento: un verdetto colorato con l'accento smette di essere un verdetto e diventa decorazione.

> **Il rosso è entrato con U-13 (2026-08-17), e solo per ciò che distrugge.** `danger` non è un `warn` più acceso: colorare «cancella la cronologia» con l'ocra dei verdetti darebbe lo stesso segnale a un rilievo — una citazione che non regge — e a un'azione irreversibile. Vale per il comando che cancella e per niente altro: se un giorno comparisse su un verdetto o su un avviso, la domanda da farsi è cosa è cambiato nella tesi del §0.

**Le query d'esempio dello stato vuoto vincolano U-08.** Tre esempi, uno per affermazione del §0, così che la demo *sia* l'argomento invece di illustrarlo — e il video di U-10 abbia già il suo copione. Ma nel profilo `demo` l'indice contiene solo i chunk d'oro di ~30 query: se gli esempi non sono **quelle**, il primo clic di chi prova il progetto finisce in un'astensione. I due task si decidono insieme.

### Come si avvia, oggi e alla fine

Due comandi diversi per due destinatari diversi, e confonderli è ciò che rende un progetto difficile da provare.

| | comando | cosa serve prima |
|---|---|---|
| **chi tocca il codice** | `make dev` | Node, e Docker acceso. Qdrant lo avvia lui se e' fermo; senza Ollama parte lo stesso e lo **dice** |
| **chi vuole solo vederlo** | `docker compose --profile demo up` (U-08) | Docker, e basta |

`make dev` avvia l'API, **aspetta** che risponda, poi avvia Vite; chiudendo si porta via entrambi. L'attesa non è cortesia: senza, il primo `/datasets` parte contro una porta chiusa e la pagina si apre già in stato di guasto, che chi guarda legge come un bug del frontend.

Controlla anche i servizi, e **non allo stesso modo**: senza indice non funziona niente, quindi Qdrant viene avviato (`docker compose start qdrant`, e solo in mancanza `up -d`) e l'avvio si ferma se non ci riesce; senza modello invece si sfoglia il corpus, si cambia dataset e il recupero risponde — cade solo la generazione, quindi Ollama è un avviso e non un blocco. Trattarli uguali impedirebbe di lavorare sull'interfaccia mentre la GPU è occupata da una valutazione, che è metà del lavoro di questa fase.

**Docker Desktop non lo apre.** È un'applicazione con interfaccia, ci mette un minuto, e il comando per avviarla è diverso su ognuno dei tre sistemi che U-12 vuole supportare: un avvio che dipende dal sistema operativo di chi lo lancia è esattamente ciò che quello script esiste per evitare.

**Nella consegna il proxy non esiste.** Il frontend viene costruito (`vite build`) dentro l'immagine con uno stadio Node, e **l'API serve `ui/dist` come file statici**: stessa origine, un container in meno, e soprattutto la ragione per cui il backend non ha CORS smette di essere un'aspirazione e diventa vera. È una decisione di U-09, e va scritta ora perché è ciò che rende legittimo il proxy di sviluppo di U-00 — un proxy che nascondesse un problema di CORS destinato a ripresentarsi in produzione sarebbe un debito, non una comodità.

### U-08 in dettaglio — come e quando si pubblica l'indice

**Il problema, detto una volta.** Chi arriva da GitHub trova il codice, non i vettori. Rigenerarli costa **~2 ore di GPU** (122 minuti misurati in I-07 per 65.950 chunk) più il download dei corpus da HuggingFace. Nessuno prova un progetto a quel prezzo, e un README che lo chiede sta dicendo «non provarlo».

**Le tre strade non sono alternative: sono tre bisogni diversi**, e vanno tutte e tre documentate perché chi arriva non sa quale è la sua.

| bisogno | cosa riceve | costo | dove sta |
|---|---|---|---|
| **vedere com'è** | indice `demo` committato | < 2 min, zero rete | in git, `data/demo/` |
| **provare sul dataset vero** | snapshot Qdrant | 161 MB da scaricare | asset di **GitHub Release** |
| **riprodurre le misure** | ingestione completa | ~2 h di GPU | `make fetch-datasets && make ingest` |

Solo la terza rigenera i vettori, ed è quella su cui poggia ogni numero in `docs/progress.md`. Le prime due servono a **mostrare**, e vanno dichiarate come tali: un demo che sembra riprodurre le misure è peggio di nessun demo.

#### Misure, prese il 2026-08-14 su cui la scelta si basa

| collection | punti | su disco | snapshot | compresso |
|---|---|---|---|---|
| `open_ragbench` | 18.840 | 212 MB | 212 MB | **161 MB** |
| `ledger` | 47.110 | 445 MB | — | ~340 MB |
| `open_ragbench_routed` | 98.312 | 683 MB | — | — |
| `ledger_routed` | 228.331 | 1,4 GB | — | — |

I vettori densi sono 1024 dimensioni × 4 byte per punto e **non comprimono**: 161 su 212 MB è il 76%, cioè quasi niente. Ogni piano che assuma una compressione migliore è sbagliato.

#### La licenza permette di ridistribuire, ed è la prima cosa da verificare

Uno snapshot contiene **il testo dei chunk**, non solo i vettori. Non è un artefatto derivato opaco: è il corpus, riorganizzato.

| dataset | licenza | ridistribuibile | obbligo |
|---|---|---|---|
| `vectara/open_ragbench` | Apache 2.0 | sì | licenza + NOTICE accanto all'artefatto |
| `artefactory/ledger-long-context-KPI-QA` | CC-BY-4.0 | sì | attribuzione accanto all'artefatto |

**«Accanto all'artefatto» e non solo nel repo**: chi scarica uno snapshot da una release può non aver mai visto `data/README.md`. L'attribuzione va nel corpo della release e in un file dentro l'archivio.

#### Come — il meccanismo

Qdrant ripristina **direttamente da un URL**, quindi non c'è nessun file da maneggiare a mano:

```
POST /collections/open_ragbench/snapshots/recover
{"location": "https://github.com/<org>/ibid/releases/download/<tag>/open_ragbench.snapshot"}
```

Cosa pubblicare, e cosa no: `open_ragbench` e `ledger`. **Non** le varianti `_routed` (2,1 GB insieme) — servono all'ablation R-07, cioè a chi riproduce, e chi riproduce ingerisce.

#### Quando

- **L'indice `demo`**: dentro U-08, perché è ciò che quel task consegna. Va costruito dai chunk d'oro di ~30 query più distrattori — ordine di 1.500–2.000 chunk, ~10–15 MB, che stanno in git senza LFS. `dataset_id: "demo"` è già nello schema `Chunk` del §3: era previsto.
- **Lo snapshot su Release**: al primo tag pubblico, insieme a U-11 (il README che presenta il progetto). Prima non ha destinatari, e uno snapshot pubblicato prima delle misure definitive invecchia male — va rigenerato a ogni re-ingestione che cambia i vettori.

#### Cosa non fare, e perché

- **Committare lo snapshot in git.** GitHub rifiuta i file oltre 100 MB, e anche sotto quella soglia un binario nella storia la gonfia per sempre: si cancella dal working tree, non dai commit.
- **Git LFS sul piano gratuito.** 1 GB di banda al mese: si esaurisce dopo sei cloni, e dal settimo chi clona vede un errore invece del dataset. È il modo peggiore di fallire — sembra funzionare finché il progetto non interessa a nessuno.
- **Pubblicare uno snapshot senza dire da quale commit e con quale modello di embedding è stato costruito.** Un indice è legato al modello che l'ha prodotto (§A-02: interrogarlo con un altro embedder restituisce spazzatura *senza errore*). Il tag della release e il nome del modello vanno nel corpo della release.

**U-12 sta in Fase 7 e non in Fase 8** perché il criterio di U-09 è "primo avvio pulito su macchina vergine", e una macchina Linux è una macchina vergine: un progetto MIT pensato per essere provato da altri non è presentabile se gira su un sistema operativo solo. Non è però un lavoro grande, ed è più piccolo di quanto sembri: `src/index/embed.py` sceglie già `DmlExecutionProvider` solo se disponibile e ripiega su CPU, quindi su Linux il codice **gira già**. Mancano due cose, misurate il 2026-08-10: la lista provider non contiene `ROCMExecutionProvider`/`CUDAExecutionProvider`, quindi su Linux si finisce su CPU anche con GPU capace (2,38 embed/s contro ~10: l'ingestion passa da ~2 a ~8 ore); e `onnxruntime-directml` non è dichiarato in `pyproject.toml`, quindi la dipendenza GPU esiste solo nella tabella di `STACK.md`. L'inferenza LLM non è coinvolta: Ollama gira su Vulkan, che è lo stesso codice llama.cpp sui due sistemi.

---

## 13. Fase 9 — Extra, in ordine di priorità

Solo se avanza tempo. Nessuno di questi è necessario perché il progetto sia completo.

| ID | Task | Nota |
|---|---|---|
| X-01 | Upload dataset custom: collection Qdrant per sessione con TTL, limiti espliciti su file/MB/pagine, barra di avanzamento reale | Isolamento verificato con due sessioni concorrenti. Non serve cambiare vector store |
| X-02 | Multi-turno: contestualizzazione su cronologia, riusando il riscrittore di R-03 | **Il retrieval avviene sulla query riscritta**, mai sul messaggio grezzo né sulla cronologia concatenata |
| X-03 | Controllo di scala: qualche migliaio di documenti non annotati | Solo tempo di indicizzazione, latenza, dimensione indice, VRAM |
| X-04 | Retrieval visivo in stile ColPali sul dataset table-heavy | Il più ambizioso. Timebox rigido, si taglia senza rimpianti |

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
- **Prima di confrontare una metrica fra due configurazioni, verificare che il cambiamento non muova anche lo strumento che la misura.** Il tetto di chunking di I-11 sembrava alzare `citation_precision` di 11 punti; erano le premesse più corte, e quel verificatore accetta il 79% sotto i 343 token contro il 58% sopra i 1.784. Una metrica è confrontabile solo lungo gli assi che non toccano il suo strumento, e quali siano va saputo prima, non dopo.
- **Due indici di taglia o densità diversa non si confrontano con la ricerca approssimata.** HNSW è approssimato, e perde più richiamo dove i punti sono più fitti: su `ledger_routed` restituisce l'84,8% del vero top-5 contro il 98,9% di `ledger`. Il confronto fra le due pipeline misurava quindi anche il divario fra i due richiami, e **8 dei 21,7 punti attribuiti al routing in R-07 erano l'indice** (R-11). Usare `SEARCH_EXACT=1`, oppure verificare prima con `scripts/probe_index_density.py` che il richiamo sia equivalente: costa un minuto e non serve nessun golden set.
- **Un test pre-registrato protegge dallo scegliere il test dopo aver visto i dati. Non protegge dall'aver scelto il test sbagliato prima.** Il passo 2 di OQ-01 era scritto in anticipo e dava +17,33% a favore dell'ipotesi; un braccio di controllo con un dato **finto** dava lo stesso identico +17,33%, perché in regime di quasi-pareggio qualunque perturbazione ribalta una frazione di casi. Ogni esperimento vuole un controllo che dica **cosa sta misurando**, e il controllo non è nel protocollo per definizione — il protocollo è ciò di cui si dubita.
- **Una misura la cui etichetta si rivela falsa non è un risultato negativo da conservare: è un risultato da rifare.** Il §7 dice che i risultati negativi restano in tabella, e vale per una misura che ha risposto *male* alla domanda giusta. Non copre il caso in cui la domanda era un'altra — `E-06` si chiamava *«retrieval lessicale BM25»* e misurava qualcos'altro. La riga non si cancella: si rifà, e le due misure restano affiancate con detto quale descriveva cosa. Distinguere i due casi è il motivo per cui esiste la Fase 5.
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
- Nessuna dipendenza nuova senza aggiornare `STACK.md`, **inclusa la sua licenza**. Il progetto è MIT: nessuna libreria copyleft (GPL, AGPL) può entrare in albero. PyMuPDF in particolare è AGPL-3.0 — usare `pypdfium2` e `pdfplumber`.
- Nessuna chiamata diretta a un server modelli: passare sempre da `LLM_BASE_URL`.
- I parametri di retrieval vivono in `config.py`. Non incorporarli nel codice dei moduli.
- Non committare modelli o indici, tranne il mini-indice del profilo `demo`.
- Ogni funzione di valutazione riceve e restituisce `dataset_id`. Nessuna metrica senza di esso.

---

## 16. Struttura del repo

```
├── compose.yml              # profili demo / full / eval
├── Makefile                 # fetch-datasets, ingest, eval, demo
├── README.md
├── ROADMAP.md
├── STACK.md
├── .env.example
├── src/
│   ├── datasets/            # caricamento HF, normalizzazione a Chunk
│   ├── profiling/           # profilatore documenti, assegnazione doc_genre
│   ├── ingestion/           # le 3 pipeline, chunking, bbox, rendering
│   ├── index/               # embedding, upsert Qdrant (una collection per dataset)
│   ├── retrieval/           # ibrido, RRF, rerank, filtri, riscrittura, routing
│   ├── generation/          # prompt, parsing e riparazione citazioni, entailment, astensione
│   ├── api/
│   └── config.py
├── eval/
│   ├── contamination/       # prompt, chiavi, output grezzi dei test pre-implementazione
│   ├── golden/              # query e qrels normalizzati, incluse le non rispondibili
│   ├── metrics/
│   └── results/             # un EvalRun per esecuzione, con hash commit
├── dashboard/               # Streamlit interna per debug e confronto configurazioni
├── ui/                      # frontend demo
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
