# Stack tecnologico

Complemento a `ROADMAP.md`. Congelare queste scelte è un task di Fase 0: cambiare stack a metà progetto costa più di qualsiasi errore di scelta iniziale.

---

## Le quattro decisioni che contano

Tutto il resto è dettaglio. Queste quattro determinano com'è il progetto.

**1. Python per tutto il backend.** Non c'è alternativa seria: l'intero ecosistema di retrieval, embedding e valutazione vive lì.

**2. UI web, non Flutter.** Motivazioni nella sezione UI — è la scelta meno ovvia del documento.

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
| PDF — rendering e bbox | **pypdfium2** | Rendering pagina a immagine e coordinate. Licenza permissiva, compatibile MIT |
| PDF — tabelle e layout | **pdfplumber** (MIT) | Estrazione tabelle e metadati di layout a livello di parola. Più lento, ma alla vostra scala irrilevante |
| Tabelle e struttura | **Docling** (MIT) | Se serve output più strutturato. Più lento |
| ~~PyMuPDF~~ | **da evitare** | Vedi §Licenze. È AGPL-3.0: vi costringerebbe ad abbandonare la MIT |
| HTML | trafilatura o selectolax | Se il corpus include pagine web |
| Chunking | **Scritto da voi** | ~150 righe, sulla struttura del documento. I text splitter generici sono la causa numero uno di retrieval mediocre |

## Retrieval

| Ambito | Scelta | Note |
|---|---|---|
| Vector store | **Qdrant** | Containerizza pulito, gestisce vettori densi **e sparsi** in named vectors: una collection, due indici, ibrido senza un secondo motore |
| Embedding denso | **`intfloat/multilingual-e5-large`** | 1024-dim, 100+ lingue, Apache 2.0. Via fastembed 0.8.0 + onnxruntime-directml: ~10 embed/s su RX 6750 XT via DirectX 12, senza CUDA né ROCm |
| Embedding sparso | **`Qdrant/bm25`** | fastembed `SparseTextEmbedding`. Statistico (no GPU), multilingual (18 lingue con stopword list), Apache 2.0, ~1 MB. Entra in R-01 (ibrido RRF) |
| Embedding target | **BAAI/bge-m3** | Dense+sparse+multi-vector in un unico passaggio, MIT. Quando disponibile in fastembed (PR #602 aperto a luglio 2026): cambiare `EMBEDDING_MODEL` in `config.py` e re-ingest. Non blocca R-01 |
| GPU backend | **onnxruntime-directml** | DirectML in maintenance mode (nessuna nuova feature, patch sicurezza garantite). Windows ML non applicabile per la RX 6750 XT: l'EP AMD per GPU discrete (MIGraphX) richiede un driver esatto e non supporta ancora scenari GenAI; VitisAI è solo per NPU Ryzen AI. DirectML rimane la scelta corretta ed è incluso in Windows ML come legacy EP |
| Reranker | **bge-reranker-v2-m3** | Cross-encoder multilingue. Sul retrieval con modelli piccoli vale più di qualsiasi prompt |
| Fusione | RRF, scritto da voi | Venti righe |

> **Decisioni fissate in Fase 1 (agosto 2026):** modello denso scelto (`multilingual-e5-large`), sparso scelto (`Qdrant/bm25`), GPU backend confermato (DirectML). Non cambiare modello dopo aver iniziato a misurare: le righe della tabella non sono più confrontabili. La sostituzione con BGE-M3 è pianificata ma avverrà come ablation separata con re-ingestion completa, non come patch incrementale.

## Modelli e inferenza

| Ambito | Scelta | Note |
|---|---|---|
| Server | **llama.cpp** (`llama-server`) | Build **Vulkan** sulla 6750 XT: molto meno doloroso di ROCm su RDNA2 |
| Alternativa | Ollama | Più comodo, meno controllo sui parametri. Va benissimo |
| Interfaccia | Endpoint **OpenAI-compatibile** dietro `LLM_BASE_URL` | Il vincolo architetturale più importante: il repo resta eseguibile da chiunque, non solo sulla tua macchina |
| Modelli | Gemma 4 E2B / E4B / 12B / 26B MoE | Il 26B MoE (3.8B attivi) è il candidato migliore per 12 GB. Verificate in Fase 0 |
| Entailment | **mDeBERTa-v3 NLI** multilingue | Per la verifica delle citazioni. Preferitelo all'LLM: più veloce, deterministico, e la metrica non dipende dal modello che state valutando |

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

- Ciò che serve — testo in streaming con marcatori di citazione cliccabili, immagine di pagina con overlay evidenziato, link profondi — è **nativo del web** e faticoso altrove.
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

È lo strumento giusto per un pannello di lavoro — ed è sbagliato per la demo, dove serve controllo su streaming e overlay. Tenerle separate significa che nessuna delle due deve fare compromessi.

---

## Niente framework RAG

LangChain e LlamaIndex non vanno usati per l'orchestrazione. Tre ragioni:

1. **Il progetto dimostra che capite i pezzi.** Un pipeline dentro astrazioni altrui dimostra che sapete leggere una documentazione. In colloquio, "ho implementato RRF e il reranking" è una conversazione; "ho usato un `RetrievalQA`" la chiude.
2. **Le loro astrazioni cambiano spesso**, e vi ritrovereste a debuggare la libreria invece del sistema.
3. **Vi serve controllo fine** su citazioni, validazione, astensione e soglie — cioè esattamente le parti che i framework incapsulano.

L'orchestrazione che vi serve sta in ~300 righe leggibili. Usate le librerie per i pezzi verticali (parsing, embedding, vector store, metriche), non per la struttura.

---

## Infrastruttura e qualità

| Ambito | Scelta | Note |
|---|---|---|
| Container | **Docker Compose** con profili `demo` / `full` / `eval` | |
| Entry point | **Makefile** | `make ingest`, `make eval`, `make demo`. Il README diventa tre righe |
| Build | Dockerfile multi-stage con uv | |
| Lint/format | **ruff** | Sostituisce black + isort + flake8 |
| Type check | mypy sui moduli core | Opzionale, ma sui tipi dei chunk aiuta davvero |
| Hook | pre-commit | ruff + controllo di non committare modelli o indici pesanti |
| CI | GitHub Actions: lint + unit test | **Niente modelli in CI.** La valutazione gira in locale e i risultati si committano con l'hash del commit |
| Golden set | JSON in git | È piccolo. Niente DVC |
| Modelli e indici | Volumi, mai nell'immagine | Eccezione: il mini-indice del profilo `demo`, che va committato |

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

PyMuPDF (e la libreria MuPDF che incapsula) è disponibile **solo sotto AGPL-3.0 o licenza commerciale**. AGPL è copyleft con clausola di rete: chi distribuisce software che usa PyMuPDF — inclusi SaaS, applicazioni web e **immagini Docker** — deve rilasciare il proprio codice sotto AGPL-3.0 oppure acquistare una licenza commerciale da Artifex.

Un repository pubblico più un'immagine Docker sono distribuzione. Con PyMuPDF in albero, `ibid` dovrebbe essere AGPL, non MIT.

Perché conta anche per un progetto di portfolio: molte aziende vietano l'AGPL per policy e richiedono revisione legale prima di qualsiasi deployment. Un ingegnere che valuta il vostro lavoro potrebbe non poter clonare il repo sulla macchina di lavoro.

Alternative permissive già in tabella: **pypdfium2** per rendering e bbox, **pdfplumber** (MIT) per tabelle e layout, **Docling** (MIT) per output strutturato.

> Nota: con i dataset presi da HuggingFace il PDF potrebbe non servire affatto nel percorso principale. Verificatelo in Fase 0 — se i dataset scelti forniscono testo e immagini già estratti, la dipendenza PDF resta solo per l'upload custom opzionale.

### Licenze delle dipendenze principali

| Componente | Licenza | Compatibile MIT |
|---|---|---|
| FastAPI, Pydantic, uvicorn | MIT / BSD | sì |
| datasets (HuggingFace) | Apache 2.0 | sì |
| huggingface_hub | Apache 2.0 | sì |
| qdrant-client | Apache 2.0 | sì |
| fastembed 0.8.0 | Apache 2.0 | sì |
| onnxruntime-directml | MIT | sì — abilita AMD GPU via DirectX 12 (~10 embed/s su RX 6750 XT vs ~0.06 embed/s PyTorch CPU) |
| ~~sentence-transformers~~ | ~~Apache 2.0~~ | rimossa — PyTorch senza CUDA/ROCm su Windows: ~0.06 embed/s |
| Qdrant (client e server) | Apache 2.0 | sì |
| intfloat/multilingual-e5-large | Apache 2.0 | sì — modello denso attivo; 1024-dim, 100+ lingue |
| Qdrant/bm25 | Apache 2.0 | sì — modello sparso attivo; statistico, multilingual |
| BAAI/bge-m3 | MIT | sì — modello target (non ancora in fastembed, PR #602 aperto) |
| bge-reranker-v2-m3 | Apache 2.0 | sì |
| llama.cpp / Ollama | MIT | sì |
| ir_measures | MIT | sì |
| RAGAS | Apache 2.0 | sì |
| ruff, pytest, uv | MIT / Apache 2.0 | sì |
| pypdfium2 | permissiva | sì |
| pdfplumber, Docling | MIT | sì |
| **PyMuPDF** | **AGPL-3.0** | **no** |

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
- **Fine-tuning** di qualsiasi cosa: nessun ritorno rispetto al lavoro sul retrieval — e con la valutazione impostata bene lo potete anche dimostrare
- **Kubernetes**, code di messaggi, autenticazione, multi-tenancy: nessuno guarderà quella parte
- **GPU passthrough in Docker** come requisito: opzionale, mai obbligatorio per far partire il progetto
