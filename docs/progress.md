# Stato di avanzamento

Tracciamento dei task di `ROADMAP.md` man mano che vengono completati. Non sostituisce `ROADMAP.md` (che resta la fonte di verità, immutabile in questo file) — qui si registra solo cosa è stato fatto, quando, e con quale verifica.

## Fase 0 — Fetta verticale e gate di contaminazione

| Task | Stato | Note |
|---|---|---|
| T-01 | ✅ fatto (2026-08-03) | Scheletro repo: `src/{api,datasets,profiling,ingestion,index,retrieval,generation}/`, `compose.yml` (servizio `api` sempre attivo, `qdrant` dietro i profili `full`/`eval`/`demo`), `Dockerfile` multi-stage con `uv`, `pyproject.toml`, `.env.example`, `Makefile`, `.gitignore`, scheletro `eval/`, `dashboard/`, `ui/`, `data/demo/`. Gate verificato dal vivo: `docker compose up --build api` → container `healthy`, `curl /health` → `{"status":"ok"}`. **Non ancora committato in git.** |
| T-02 | ✅ fatto (2026-08-04) | Smoke test via Ollama 0.32.5 (alternativa approvata da STACK.md). Modelli testati: E2B (5.1B Q4_K_M, 91.2 tok/s, 1.9 GB VRAM), E4B (8.0B Q4_K_M, 15.1 tok/s, 3.3 GB), 12B (11.9B Q4_K_M, 2.4 tok/s, 8.1 GB) — tutti 100% GPU. **26B MoE escluso**: file GGUF ~18 GB supera i 12 GB VRAM; curva di scaling C-06 si ferma a 12B (previsto in ROADMAP §14). Tabella in `docs/hardware.md`, dati grezzi in `eval/contamination/smoke_20260804_103814.json`. Fix notevole: Gemma 4 è un thinking model — con `/api/generate` i token vengono consumati dal reasoning invisibile; risolto usando `/api/chat` con `think: false`. Script riutilizzabile in `scripts/smoke_test.py`. |
| T-03 | ✅ fatto (2026-08-04) | Dataset principale: `vectara/open_ragbench` — **nessuna contaminazione significativa**. 16 query da 16 paper diversi + 2 controlli positivi, testate su E4B e 12B senza contesto. Le 4 risposte "corrette" del 12B sono riconducibili a conoscenza disciplinare generale (matematica, medicina, economia, ML), non a training specifico sul paper: le 3 domande con valore numerico preciso (0.0226, $2.5, 8pF→3pF) erano sconosciute a entrambi i modelli. Dataset approvato. Secondo dataset (genere visuale) rinviato a I-01. Analisi in `docs/contamination.md`, dati grezzi in `eval/contamination/contamination_open_ragbench_20260804_112523.json`. |
| T-04 | non iniziato | Caricamento dataset da HuggingFace, normalizzazione a `Chunk`. Non richiede GPU, può partire in parallelo a T-02. |
| T-05 | non iniziato | Ingestion minima → Qdrant, retrieval denso, generazione con marcatori. |
| T-06 | non iniziato | Parser citazioni + scarto marcatori inesistenti. |
| T-07 | non iniziato | Verifica licenze dipendenze. Le dipendenze introdotte finora (FastAPI, uvicorn, pydantic, ruff, pytest) sono già in tabella in `STACK.md` come MIT/BSD — probabilmente già soddisfatto per lo stato attuale, da confermare quando si chiude il task formalmente. |

**Deliberatamente saltato in T-01:** `src/config.py` (nessun parametro di retrieval esiste finché non c'è retrieval — arriva a R-01), logica applicativa nei package vuoti, `uv.lock` (si genera al primo `uv sync` reale).

**Prossimo step:** T-04 (caricamento dataset) o T-07 (licenze) — entrambi non bloccanti e parallelizzabili. T-05 dipende da T-04. Il gate completo di T-03 (citazione risolvibile a chunk) si chiude in T-05.
