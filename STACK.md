# Stack tecnologico

Complemento a `ROADMAP.md`. Congelare queste scelte è un task di Fase 0: cambiare stack a metà progetto costa più di qualsiasi errore di scelta iniziale.

---

## Le quattro decisioni che contano

Tutto il resto è dettaglio. Queste quattro determinano com'è il progetto.

**1. Python per tutto il backend.** Non c'è alternativa seria: l'intero ecosistema di retrieval, embedding e valutazione vive lì.

**2. UI web, non Flutter.** Motivazioni nella sezione UI: è la scelta meno ovvia del documento.

**3. Nessun framework RAG.** Niente LangChain, niente LlamaIndex per l'orchestrazione. Sezione dedicata sotto.

**4. Due UI distinte:** una interna per valutazione e debug, una per la demo. Servono a cose diverse e mescolarle rovina entrambe.

---

## Backend

| Ambito | Scelta | Note |
|---|---|---|
| Linguaggio | Python 3.12 | |
| Dipendenze | **uv** | Veloce, lockfile, sostituisce pip/venv/poetry. In Dockerfile fa la differenza sui tempi di build |
| API | **FastAPI** + uvicorn | Streaming SSE nativo, schemi Pydantic, OpenAPI gratis |
| Validazione | Pydantic v2 | I modelli dei dati sono documentazione dell'architettura |
| Task lunghi | Nessuna coda | L'ingestion è un job one-shot. Celery/Redis qui sono over-engineering |

## Ingestion e parsing

| Ambito | Scelta | Note |
|---|---|---|
| PDF: rendering e bbox | **pypdfium2** | Rendering pagina a immagine e coordinate. Licenza permissiva, compatibile MIT |
| PDF: tabelle e layout | **pdfplumber** (MIT) | Estrazione tabelle e metadati di layout a livello di parola. Più lento, ma alla vostra scala irrilevante |
| Tabelle e struttura | **Docling** (MIT) | Se serve output più strutturato. Più lento |
| ~~PyMuPDF~~ | **da evitare** | Vedi §Licenze. È AGPL-3.0: vi costringerebbe ad abbandonare la MIT |
| HTML | trafilatura o selectolax | Se il corpus include pagine web |
| Chunking | **Scritto da voi** | ~150 righe, sulla struttura del documento. I text splitter generici sono la causa numero uno di retrieval mediocre |

## Retrieval

| Ambito | Scelta | Note |
|---|---|---|
| Vector store | **Qdrant** | Containerizza pulito, gestisce vettori densi **e sparsi** in named vectors: una collection, due indici, ibrido senza un secondo motore |
| Embedding denso | **`intfloat/multilingual-e5-large`** | 1024-dim, 100+ lingue, Apache 2.0. Via fastembed 0.8.0 + onnxruntime-directml: ~10 embed/s su RX 6750 XT via DirectX 12, senza CUDA né ROCm. **Finestra 512 token, e richiede i prefissi `query: ` / `passage: `**, vedi sotto |
| Embedding sparso | **`Qdrant/bm25`** | fastembed `SparseTextEmbedding`. Statistico (no GPU), multilingual (18 lingue con stopword list), Apache 2.0, ~1 MB. Entra in R-01 (ibrido RRF) |
| Embedding target | **BAAI/bge-m3** | Dense+sparse+multi-vector in un unico passaggio, MIT. Quando disponibile in fastembed (PR #602 aperto a luglio 2026): cambiare `EMBEDDING_MODEL` in `config.py` e re-ingest. Non blocca R-01 |
| GPU backend | **onnxruntime-directml** | DirectML in maintenance mode (nessuna nuova feature, patch sicurezza garantite). Windows ML non applicabile per la RX 6750 XT: l'EP AMD per GPU discrete (MIGraphX) richiede un driver esatto e non supporta ancora scenari GenAI; VitisAI è solo per NPU Ryzen AI. DirectML rimane la scelta corretta ed è incluso in Windows ML come legacy EP |
| Reranker | **BAAI/bge-reranker-base** | Cross-encoder multilingue (XLM-RoBERTa), MIT, 1.04GB. Attivo in fastembed 0.8.0. Target: bge-reranker-v2-m3 quando disponibile |
| Fusione | RRF, scritto da voi | Venti righe |

### Due vincoli del modello denso, scoperti nell'audit del 2026-08-11

Non erano scritti qui, e il secondo era già stato usato (su un altro modello) per prendere una decisione.

**1. La finestra è di 512 token, direzione destra.** Tutto ciò che segue viene scartato prima dell'embedding. Le pipeline di chunking non lo sanno: il 67,6% dei chunk di open_ragbench e l'82,1% di ledger superano quel limite, e del chunk mediano entra nell'indice **circa metà del testo**. Il testo intero arriva comunque all'LLM in generazione, quindi il sistema risponde su materiale che non ha potuto trovare.

**L'asimmetria vale la pena di essere annotata.** Poche righe più sotto, in *Modelli e inferenza*, mDeBERTa-v3 è **scartato come verificatore proprio perché** *«ha una finestra di 512 token; i nostri chunk hanno mediana ~730 e p90 ~2900»*. Il fatto era noto, scritto, e sufficiente a rifiutare un modello. L'embedder ha la stessa finestra e nessuno ha fatto il collegamento: il ragionamento è stato applicato con rigore in un punto e non in quello adiacente. Misurato dopo: sul chunk *giusto* di open_ragbench la mediana è 564 token quando il retrieval lo trova e **1.525 quando lo manca** (p = 0,00087, `scripts/probe_truncation.py`).

**2. I prefissi `query: ` e `passage: ` non vengono aggiunti.** La model card li richiede (*«otherwise you will see a performance degradation»*), e fastembed li lascia al chiamante: la classe che serve questo modello (`PooledEmbedding`) non sovrascrive `query_embed` né `passage_embed`, che quindi chiamano `embed()` nudo. Sono asimmetrici fra query e passaggio, quindi non è un difetto che si semplifica in un confronto.

Nessuno dei due è ancora corretto, di proposito: correggerli cambia ogni numero denso già misurato. Le misure che decidono stanno in `ROADMAP.md` come **I-10** e **I-08**, le correzioni come **I-11** e **I-09**; il fatto, il protocollo e ciò che non è dimostrato in `docs/open-questions.md`, OQ-04 e OQ-02.

> **Decisioni fissate in Fase 1 (agosto 2026):** modello denso scelto (`multilingual-e5-large`), sparso scelto (`Qdrant/bm25`), GPU backend confermato (DirectML). Non cambiare modello dopo aver iniziato a misurare: le righe della tabella non sono più confrontabili. La sostituzione con BGE-M3 è pianificata ma avverrà come ablation separata con re-ingestion completa, non come patch incrementale.

## Modelli e inferenza

| Ambito | Scelta | Note |
|---|---|---|
| Server | **llama.cpp** (`llama-server`) | Build **Vulkan** sulla 6750 XT: molto meno doloroso di ROCm su RDNA2 |
| Alternativa | Ollama | Più comodo, meno controllo sui parametri. Va benissimo |
| Interfaccia | Endpoint **OpenAI-compatibile** dietro `LLM_BASE_URL` | Il vincolo architetturale più importante: il repo resta eseguibile da chiunque, non solo sulla tua macchina |
| Modelli | Gemma 4 E2B / E4B / 12B / 26B MoE | Il 26B MoE (3.8B attivi) è il candidato migliore per 12 GB. Verificate in Fase 0 |
| Finestra di contesto | **`OLLAMA_CONTEXT_LENGTH=32768`** sul motore, non nella richiesta | Il contratto OpenAI non ha un campo per la finestra: la decide chi avvia il server (A-09). Senza, Ollama sceglie da sé fra 4k, 32k e 256k in base alla memoria, e a 4096 cinque chunk non entrano |
| Attenzione | **`OLLAMA_FLASH_ATTENTION=1`** | Misurata sul 12B: **4× sul prefill**. Non è un default di Ollama, va impostata a mano: dettaglio in [`docs/hardware.md`](docs/hardware.md) |
| Entailment | **`MoritzLaurer/bge-m3-zeroshot-v2.0`** (MIT, multilingue) | Per la verifica delle citazioni. Preferitelo all'LLM: più veloce, deterministico, e la metrica non dipende dal modello che state valutando. Sostituisce mDeBERTa-v3 NLI a seguito della misura in C-03, vedi sotto |

#### Le due variabili del motore si impostano fuori dal progetto, e vanno dette

Sono le uniche due cose che il repo **non può garantire da sé**: stanno nel
processo che serve i modelli, che può essere su un'altra macchina o condiviso
con qualcun altro. Il progetto le dichiara, le verifica dove può (`make dev` lo
dice se la finestra attiva non è quella dichiarata, e ogni `EvalRun` registra
quella **misurata**), ma non le scrive al posto di nessuno.

**Su Windows** si impostano una volta e valgono per il servizio:

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_CONTEXT_LENGTH','32768','Machine')
[Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION','1','Machine')
# poi riavviare Ollama: il servizio legge l'ambiente all'avvio
```

**Su Linux/macOS**, `OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_FLASH_ATTENTION=1 ollama serve`,
oppure le stesse due righe nel service file.

**La finestra si può anche impostare dallo slider nelle impostazioni dell'app
Ollama**, ed è la stessa cosa: una variabile e uno slider scrivono lo stesso
numero nel motore. Il progetto non ha bisogno di sapere quale delle due si è
usata, ed è il punto di A-09, **la finestra si misura invece di crederla**:
`make dev` lo dice se quella attiva non è quella dichiarata, e ogni `EvalRun`
registra quella letta da `/api/ps`. Vale anche come controllo dello slider
stesso, che in alcune versioni dell'app è stato segnalato come ignorato: dopo la
prima risposta, `ollama ps` mostra la colonna `CONTEXT` e chiude la questione.

> **La finestra non viaggia più col nome del modello** (A-09). Fino al
> 2026-08-24 il progetto creava un modello derivato per ogni coppia (modello,
> finestra) (l'unica strada che Ollama documenti, e che resta l'unica se le)
> finestre servono **scegliibili**, ma il conto lo pagava chi aveva solo voluto
> provare il progetto: ventidue voci in più in `ollama list`, che Ollama non sa
> nascondere. Ora quelle taglie sono opt-in (`python scripts/model_sizes.py
> --assicura`) e si tolgono in blocco (`--pulisci`).

#### Perché non più mDeBERTa-v3 NLI (misurato in C-03, 2026-08-10)

La scelta originale era **mDeBERTa-v3 NLI multilingue**. È stata misurata prima di costruirci sopra `citation_precision`, e non regge su questo corpus. Il vincolo che contava (**multilingue, licenza permissiva, nessuna dipendenza nuova**) resta rispettato: non si sta relitigando la decisione, si sta cambiando il modello dentro il vincolo che la decisione poneva.

La ragione è strutturale, non una questione di qualità del modello. mDeBERTa ha una finestra di **512 token**; i nostri chunk hanno mediana ~730 e p90 ~2900. La premessa va spezzata in finestre e si prende il massimo, e il massimo su N finestre è un problema di **confronti multipli**: ogni finestra in più è un'altra occasione di falso positivo. Misurata su claim che nessun chunk campionato supporta, la correlazione fra numero di finestre e P(entailment) massima è **0,46–0,54**: `citation_precision` avrebbe misurato in parte la lunghezza del chunk citato.

`bge-m3-zeroshot-v2.0` ha una finestra di **8194 token**, quindi il **99% dei nostri chunk entra in un passaggio solo** e l'artefatto non si presenta: eliminato per costruzione, non calibrato via.

Floor test appaiato (stesse identiche coppie per i due modelli, claim copiato alla lettera dal chunk, negativo appaiato per lunghezza in token, 60 coppie per dataset):

| dataset | mDeBERTa-v3 (512) | bge-m3-zeroshot (8192) | McNemar esatto |
|---|---|---|---|
| open_ragbench | AUC 0,661 [0,564–0,758] | **AUC 0,939** [0,894–0,984] | **p = 0,0001** |
| ledger | AUC 0,742 [0,654–0,831] | **AUC 0,910** [0,856–0,964] | **p = 0,0094** |

Il guadagno non è nel riconoscere meglio le attribuzioni vere: è nel **non approvarne di false**. Chunk estranei sopra soglia 0,5: da **23/60 a 2/60** su open_ragbench, da 13/60 a **0/60** su ledger. È il fallimento che conta, perché un verificatore che approva citazioni sbagliate gonfia la metrica, il che è molto peggio di uno pessimista.

Riproducibile con `python scripts/probe_entailment.py compare {open_ragbench|ledger}`.

**Cosa cambia in pratica** (vincoli operativi, non preferenze):

- Premessa = **chunk intero fino a ~4096 token** (96% dei casi, un passaggio, nessun artefatto); finestre solo per la coda. Sopra i ~4000 token l'attenzione quadratica costa più del windowing: misurati 123 ms a 758 token, 762 ms a 2951, **19,7 s a 7693**.
- **Batch 1** per questo modello. L'attenzione è quadratica e il padding riempie il batch fino al suo elemento più lungo: 8 sequenze da 4096 chiedono ~8 GB di sole matrici di attenzione e l'allocatore DirectML rifiuta.
- La testa è **binaria** (`entailment` / `not_entailment`) invece che a tre classi. È quella giusta: serve *supportato / non supportato*, e la distinzione fra `neutral` e `contradiction` non viene usata.
- Il costo dipende dal genere, non è un moltiplicatore costante: sulle stesse 120 valutazioni, 312 s contro 93 s su open_ragbench ma **37 s contro 43 s su ledger**, dove i chunk stanno in una finestra.

## Valutazione

| Ambito | Scelta | Note |
|---|---|---|
| Metriche IR | **`ir_measures`** o `pytrec_eval` | Implementazioni standard di nDCG, MRR, recall@k. Meglio che scriverle a mano: sono confrontabili con la letteratura |
| Metriche generazione | **RAGAS** | Faithfulness, answer relevancy, context precision |
| Citation precision | Scritta da voi | È la vostra metrica distintiva, nessuna libreria la fa come vi serve |
| Runner | **pytest** | La suite di valutazione come test: i test di regressione arrivano gratis |
| Tracing *(opzionale)* | **Langfuse** self-hosted | Un container in più. Utile per il debug, e "osservabilità" in un progetto studentesco si nota |

## UI

### Perché non Flutter

Flutter lo conosci, ed è la ragione per cui la tentazione c'è. Ma qui è la scelta sbagliata:

- Ciò che serve (testo in streaming con marcatori di citazione cliccabili, immagine di pagina con overlay evidenziato, link profondi) è **nativo del web** e faticoso altrove.
- Il progetto deve girare con `docker compose up`. Una UI web è una cartella di file statici; Flutter Web aggiunge SDK Dart e build pesante all'immagine.
- Chi apre il repo vuole vedere uno screenshot o provarlo in dieci secondi, dal browser.
- Il valore di Flutter è il mobile nativo. Qui non serve.

Se ci tieni a usare Flutter, il posto giusto è un **client mobile separato** in un secondo repo, dopo che il progetto è chiuso. Non dentro questo.

### Demo UI

| Ambito | Scelta | Note |
|---|---|---|
| Frontend | **React + Vite** | Riconoscibile, integrazione PDF ben documentata. In alternativa **htmx + JS vanilla** se volete zero toolchain JS: più veloce da fare, meno "standard" da mostrare |
| Streaming | **SSE** | La risposta arriva token per token; i marcatori si risolvono a fine frase |
| Pagine sorgente | **PNG pre-renderizzato + overlay `div` posizionati** | Molto più semplice di PDF.js: le immagini le avete già dalla Fase 1, le bbox pure. Nessun rendering PDF nel browser |
| Stile | Tailwind | Non spendeteci tempo |

### Dashboard interna (Fase 2-3)

**Streamlit**, separato dalla demo. Serve a voi: confrontare configurazioni di retrieval, ispezionare i chunk recuperati per una query, annotare il golden set, guardare dove il sistema sbaglia.

È lo strumento giusto per un pannello di lavoro, ed è sbagliato per la demo, dove serve controllo su streaming e overlay. Tenerle separate significa che nessuna delle due deve fare compromessi.

---

## Niente framework RAG

LangChain e LlamaIndex non vanno usati per l'orchestrazione. Tre ragioni:

1. **Il progetto dimostra che capite i pezzi.** Un pipeline dentro astrazioni altrui dimostra che sapete leggere una documentazione. In colloquio, "ho implementato RRF e il reranking" è una conversazione; "ho usato un `RetrievalQA`" la chiude.
2. **Le loro astrazioni cambiano spesso**, e vi ritrovereste a debuggare la libreria invece del sistema.
3. **Vi serve controllo fine** su citazioni, validazione, astensione e soglie, cioè esattamente le parti che i framework incapsulano.

L'orchestrazione che vi serve sta in ~300 righe leggibili. Usate le librerie per i pezzi verticali (parsing, embedding, vector store, metriche), non per la struttura.

---

## Infrastruttura e qualità

| Ambito | Scelta | Note |
|---|---|---|
| Container | **Docker Compose** con profili `demo` / `full` / `eval` | |
| Entry point | **Makefile** | `make ingest`, `make eval`, `make demo`. Il README diventa tre righe |
| Build | Dockerfile a tre stadi: `node:24-slim` per il frontend, `python:3.12-slim` con uv per l'ambiente, `python:3.12-slim` per eseguire | Node sta **solo nello stadio di build**: l'immagine finale contiene `ui/dist`, non `node_modules` |
| Lint/format | **ruff** | Sostituisce black + isort + flake8 |
| Type check | mypy sui moduli core | Opzionale, ma sui tipi dei chunk aiuta davvero |
| Hook | pre-commit | ruff + controllo di non committare modelli o indici pesanti |
| CI | GitHub Actions: lint + unit test | **Niente modelli in CI.** La valutazione gira in locale e i risultati si committano con l'hash del commit |
| Golden set | JSON in git | È piccolo. Niente DVC |
| Modelli e indici | Volumi, mai nell'immagine | Eccezione: il mini-indice del profilo `demo`, committato in `data/demo/` (1.758 chunk, ~21 MB) e **montato**, non copiato: cambiarlo non ricostruisce l'immagine |
| Frontend in produzione | `vite build` in uno stadio Node, e l'API serve `ui/dist` dalla stessa origine | È ciò che rende vera, invece che aspirazionale, la scelta di non avere CORS nel backend. In sviluppo resta il proxy di Vite |

## Struttura del repo

```
├── compose.yml              # profili demo / full / eval
├── Makefile
├── README.md
├── ROADMAP.md
├── STACK.md
├── .env.example
├── src/
│   ├── ingestion/           # parsing, chunking, metadati, rendering pagine
│   ├── index/               # embedding, upsert Qdrant
│   ├── retrieval/           # ibrido, RRF, rerank, filtri, riscrittura query
│   ├── generation/          # prompt, parsing citazioni, entailment, astensione
│   ├── api/                 # FastAPI
│   └── config.py            # tutto parametrizzato: si cambia esperimento senza toccare il codice
├── eval/
│   ├── golden/              # query annotate, incluse le non rispondibili
│   ├── metrics/
│   └── results/             # JSON per run, con hash commit
├── dashboard/               # Streamlit interna
├── ui/                      # frontend demo
└── data/                    # gitignored, tranne il mini-corpus demo
```

`config.py` è più importante di quanto sembri: se ogni scelta di retrieval è un parametro, un'ablation è un ciclo su file di config invece di una serie di commit da rifare a mano.

---

## Licenze

**Il progetto è rilasciato sotto licenza MIT.** Questa scelta vincola le dipendenze: nessuna libreria con licenza copyleft può entrare nel dependency tree.

### La trappola da ricordare: PyMuPDF

PyMuPDF (e la libreria MuPDF che incapsula) è disponibile **solo sotto AGPL-3.0 o licenza commerciale**. AGPL è copyleft con clausola di rete: chi distribuisce software che usa PyMuPDF (inclusi SaaS, applicazioni web e **immagini Docker**) deve rilasciare il proprio codice sotto AGPL-3.0 oppure acquistare una licenza commerciale da Artifex.

Un repository pubblico più un'immagine Docker sono distribuzione. Con PyMuPDF in albero, `ibid` dovrebbe essere AGPL, non MIT.

Perché conta anche per un progetto di portfolio: molte aziende vietano l'AGPL per policy e richiedono revisione legale prima di qualsiasi deployment. Un ingegnere che valuta il vostro lavoro potrebbe non poter clonare il repo sulla macchina di lavoro.

Alternative permissive già in tabella: **pypdfium2** per rendering e bbox, **pdfplumber** (MIT) per tabelle e layout, **Docling** (MIT) per output strutturato.

> Nota: con i dataset presi da HuggingFace il PDF potrebbe non servire affatto nel percorso principale. Verificatelo in Fase 0: se i dataset scelti forniscono testo e immagini già estratti, la dipendenza PDF resta solo per l'upload custom opzionale.

### Licenze delle dipendenze principali

| Componente | Licenza | Compatibile MIT |
|---|---|---|
| FastAPI, Pydantic, uvicorn | MIT / BSD | sì |
| datasets (HuggingFace) | Apache 2.0 | sì |
| huggingface_hub | Apache 2.0 | sì |
| qdrant-client | Apache 2.0 | sì |
| fastembed 0.8.0 | Apache 2.0 | sì |
| onnxruntime-directml | MIT | sì: abilita AMD GPU via DirectX 12 (~10 embed/s su RX 6750 XT vs ~0.06 embed/s PyTorch CPU) |
| ~~sentence-transformers~~ | ~~Apache 2.0~~ | rimossa, PyTorch senza CUDA/ROCm su Windows: ~0.06 embed/s |
| Qdrant (client e server) | Apache 2.0 | sì |
| intfloat/multilingual-e5-large | Apache 2.0 | sì: modello denso attivo; 1024-dim, 100+ lingue |
| Qdrant/bm25 | Apache 2.0 | sì: modello sparso attivo; statistico, multilingual |
| BAAI/bge-m3 | MIT | sì: modello target (non ancora in fastembed, PR #602 aperto) |
| BAAI/bge-reranker-base | MIT | sì: reranker attivo; bge-reranker-v2-m3 non ancora disponibile in fastembed 0.8.0 |
| MoritzLaurer/bge-m3-zeroshot-v2.0 | MIT | sì: verificatore di entailment attivo (C-03); multilingue, finestra 8194 token, ONNX nel repo del modello stesso |
| ~~MoritzLaurer/mDeBERTa-v3-...-xnli-2mil7~~ | ~~MIT~~ | sostituito, finestra 512 token contro chunk con p90 ~2900: vedi §Modelli e inferenza |
| llama.cpp / Ollama | MIT | sì |
| pandas | BSD-3-Clause | sì: lettura parquet LEDGER e manipolazione dati |
| ir_measures 0.4.3 | MIT | sì: nDCG, Recall@k, MRR, Success@1 per E-03 |
| RAGAS | Apache 2.0 | sì |
| streamlit>=1.35 | Apache 2.0 | sì: dashboard interna (D-01) |
| ruff, pytest, uv | MIT / Apache 2.0 | sì |
| prettier 3.9.6 | MIT | sì (formattatore del solo `ui/`, e solo di sviluppo): non entra in `dist`. Colma l'asimmetria con `ruff`, che copriva metà del repo |
| pypdfium2 | permissiva | sì |
| pdfplumber, Docling | MIT | sì |
| **PyMuPDF** | **AGPL-3.0** | **no** |

Frontend (`ui/`, introdotto in U-00 il 2026-08-14). Licenze lette dai `package.json` in `node_modules`, non dedotte:

| Componente | Versione | Licenza | Compatibile MIT |
|---|---|---|---|
| react, react-dom | 19.2.8 | MIT | sì |
| vite, @vitejs/plugin-react | 8.2.1 / 6.0.5 | MIT | sì |
| tailwindcss, @tailwindcss/vite | 4.3.3 | MIT | sì |
| vitest | 4.1.10 | MIT | sì |
| typescript | 7.0.2 | Apache-2.0 | sì: solo build |
| @types/react, @types/react-dom | 19.2.x | MIT | sì: solo tipi |
| katex | 0.18.4 | MIT | sì: nel bundle, font compresi |
| **lightningcss** | 1.32.0 | **MPL-2.0** | sì, **ma va detto**, vedi sotto |
| playwright, playwright-core | 1.62.1 | Apache-2.0 | sì: solo sviluppo, vedi sotto |
| oxlint | 1.80.0 | MIT | sì: solo sviluppo, vedi sotto |

**`oxlint` è entrato con D-13** (2026-08-28) ed è il linter TypeScript che il progetto non aveva: `prettier` formatta e basta, e ciò che trova qualcosa è `react-hooks/exhaustive-deps`, perché qui le liste di dipendenze degli hook sono scritte a mano. **Non è `eslint`**, e la ragione è misurata, non preferita: `typescript-eslint` rifiuta di partire su TypeScript 7 (*«typescript-eslint does not support TS 7.0»*, provato il 2026-08-28), e la strada che indica lui stesso è affiancare una seconda copia di TypeScript alla 7 già in albero. `oxlint` è un binario unico che il TypeScript lo analizza da solo: **nessuna dipendenza** (`dependencies: {}`, verificato in `node_modules`; le 19 `optionalDependencies` sono lo stesso binario compilato per 19 piattaforme, e npm ne installa uno), nessun vincolo di peer, e non entra nel bundle.

**`lightningcss` è l'unica dipendenza copyleft dell'albero**, tirata dentro da Tailwind 4 come trasformatore CSS. È MPL-2.0, cioè copyleft **a livello di file**: obbliga a mantenere sotto MPL i file di *quella* libreria se modificati e ridistribuiti, e non si propaga al progetto che la usa. Non è nella lista vietata (GPL / AGPL / LGPL-static), è una dipendenza di *build* che non finisce nel bundle servito, e il CSS che produce è un output, non un'opera derivata dei suoi sorgenti. Resta segnalata qui perché la regola dice di segnalare, non di valutare in silenzio: toglierla richiederebbe rinunciare a Tailwind, che STACK indica come scelta di stile.

**`katex` è l'unica dipendenza che finisce davvero nel bundle servito** (U-02, 2026-08-14), e porta con sé i propri font. È una deroga dichiarata al «tutti font di sistema» del §12: quella regola esiste perché U-08 vuole il profilo `demo` avviabile **senza rete**, e i font di KaTeX sono file locali emessi da `vite build` accanto al bundle, nessuna richiesta a un CDN. La ragione per cui non si usa invece MathML col font matematico di sistema è la stessa per cui i simboli dell'interfaccia sono disegnati e non scritti: un carattere risolto dal sistema è diverso su ogni macchina, e una formula lo è in modo molto più visibile di un caret. Costo misurato: +260 kB di JS e +190 kB di font sul bundle (147 kB gzip il JS). L'unica dipendenza a runtime di katex è `commander` (MIT), che serve al suo eseguibile da riga di comando e non al browser.

**`playwright` e' entrato con U-10** (2026-08-26) e serve a una cosa sola: registrare il video del README eseguendo il copione dal vivo, cosi' che la ripresa si rifaccia con un comando quando l'interfaccia cambia. E' una dipendenza di **sviluppo**, non compare in nessun import di `src/` e non finisce nel bundle; il browser che scarica (~150 MB) sta nella cache dell'utente, fuori dal repository. Porta con se' un solo pacchetto, `playwright-core`, con la stessa licenza.

Nessuna GPL, AGPL o LGPL nell'albero. Conteggio del 2026-08-26 leggendo il campo `license` di ogni `package.json` sotto `node_modules`, 71 pacchetti: **59 MIT, 6 Apache-2.0, 3 ISC, 2 MPL-2.0** (lo stesso `lightningcss` e il suo binario per piattaforma), **1 BSD-3-Clause**.

**Verifica T-07 (2026-08-04):** tutte le dipendenze in `pyproject.toml` controllate; nessuna copyleft in albero. Licenze confermate da LICENSE file nelle dist-info: pydantic MIT, uvicorn/starlette BSD-3-Clause, ruff MIT, pytest MIT.

**Regola per chi aggiunge dipendenze** (persone e coding agent): prima di introdurre una libreria, verificarne la licenza e aggiornare questa tabella. Qualsiasi licenza copyleft (GPL, AGPL, LGPL con linking statico) va segnalata e discussa prima dell'inserimento, non dopo.

### Dataset usati

| Dataset | Repo HuggingFace | Licenza | Compatibile MIT | Note |
|---|---|---|---|---|
| `vectara/open_ragbench` | `vectara/open_ragbench` | Apache 2.0 | sì | Dataset principale (academic PDFs) |
| `artefactory/ledger-long-context-KPI-QA` | `artefactory/ledger-long-context-KPI-QA` | CC-BY-4.0 | sì | Secondo dataset (annual reports, table-heavy); contamination check superato 2026-08-05 (0/8 corrette senza contesto con Gemma 12B) |

### Codice, dati e modelli sono cose distinte

- **Codice** → MIT, file `LICENSE` nella radice.
- **Dati** → la licenza MIT non copre i dataset. Serve un `data/README.md` che elenchi, per ciascun dataset usato o committato, la licenza e l'attribuzione richiesta.
- **Modelli** → non li ridistribuite, li invocate soltanto, quindi nessun obbligo. Ma indicate nel README quali modelli usate e sotto quali termini.

---

## Cosa NON usare

- **LangChain / LlamaIndex** per l'orchestrazione (sopra)
- **Flutter** per questa UI (sopra)
- **Fine-tuning** di qualsiasi cosa: nessun ritorno rispetto al lavoro sul retrieval, e con la valutazione impostata bene lo potete anche dimostrare
- **Kubernetes**, code di messaggi, autenticazione, multi-tenancy: nessuno guarderà quella parte
- **GPU passthrough in Docker** come requisito: opzionale, mai obbligatorio per far partire il progetto
