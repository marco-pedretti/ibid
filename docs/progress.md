# Stato di avanzamento

Tracciamento dei task di `ROADMAP.md` man mano che vengono completati. Non sostituisce `ROADMAP.md` (che resta la fonte di verità, immutabile in questo file) — qui si registra solo cosa è stato fatto, quando, e con quale verifica.

## Fase 0 — Fetta verticale e gate di contaminazione

| Task | Stato | Note |
|---|---|---|
| T-01 | ✅ fatto (2026-08-03) | Scheletro repo: `src/{api,datasets,profiling,ingestion,index,retrieval,generation}/`, `compose.yml` (servizio `api` sempre attivo, `qdrant` dietro i profili `full`/`eval`/`demo`), `Dockerfile` multi-stage con `uv`, `pyproject.toml`, `.env.example`, `Makefile`, `.gitignore`, scheletro `eval/`, `dashboard/`, `ui/`, `data/demo/`. Gate verificato dal vivo: `docker compose up --build api` → container `healthy`, `curl /health` → `{"status":"ok"}`. **Non ancora committato in git.** |
| T-02 | non iniziato | Smoke test modelli (E2B/E4B/12B/26B MoE) su Vulkan → `docs/hardware.md`. Richiede build locale di `llama.cpp` con backend Vulkan e download dei modelli GGUF. |
| T-03 | non iniziato | Gate di contaminazione — dipende da T-02 (serve un modello che risponda). |
| T-04 | non iniziato | Caricamento dataset da HuggingFace, normalizzazione a `Chunk`. Non richiede GPU, può partire in parallelo a T-02. |
| T-05 | non iniziato | Ingestion minima → Qdrant, retrieval denso, generazione con marcatori. |
| T-06 | non iniziato | Parser citazioni + scarto marcatori inesistenti. |
| T-07 | non iniziato | Verifica licenze dipendenze. Le dipendenze introdotte finora (FastAPI, uvicorn, pydantic, ruff, pytest) sono già in tabella in `STACK.md` come MIT/BSD — probabilmente già soddisfatto per lo stato attuale, da confermare quando si chiude il task formalmente. |

**Deliberatamente saltato in T-01:** `src/config.py` (nessun parametro di retrieval esiste finché non c'è retrieval — arriva a R-01), logica applicativa nei package vuoti, `uv.lock` (si genera al primo `uv sync` reale).

**Prossimo step da decidere:** T-02, T-04 o T-07 — proposti all'utente il 2026-08-03, nessuno scelto ancora.
