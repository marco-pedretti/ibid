# Stato di avanzamento

Tracciamento dei task di `ROADMAP.md` man mano che vengono completati. Non sostituisce `ROADMAP.md` (che resta la fonte di verità, immutabile in questo file) — qui si registra solo cosa è stato fatto, quando, e con quale verifica.

## Fase 0 — Fetta verticale e gate di contaminazione

| Task | Stato | Note |
|---|---|---|
| T-01 | ✅ fatto (2026-08-03) | Scheletro repo: `src/{api,datasets,profiling,ingestion,index,retrieval,generation}/`, `compose.yml` (servizio `api` sempre attivo, `qdrant` dietro i profili `full`/`eval`/`demo`), `Dockerfile` multi-stage con `uv`, `pyproject.toml`, `.env.example`, `Makefile`, `.gitignore`, scheletro `eval/`, `dashboard/`, `ui/`, `data/demo/`. Gate verificato dal vivo: `docker compose up --build api` → container `healthy`, `curl /health` → `{"status":"ok"}`. **Non ancora committato in git.** |
| T-02 | ✅ fatto (2026-08-04) | Smoke test via Ollama 0.32.5 (alternativa approvata da STACK.md). Modelli testati: E2B (5.1B Q4_K_M, 91.2 tok/s, 1.9 GB VRAM), E4B (8.0B Q4_K_M, 15.1 tok/s, 3.3 GB), 12B (11.9B Q4_K_M, 2.4 tok/s, 8.1 GB) — tutti 100% GPU. **26B MoE escluso**: file GGUF ~18 GB supera i 12 GB VRAM; curva di scaling C-06 si ferma a 12B (previsto in ROADMAP §14). Tabella in `docs/hardware.md`, dati grezzi in `eval/contamination/smoke_20260804_103814.json`. Fix notevole: Gemma 4 è un thinking model — con `/api/generate` i token vengono consumati dal reasoning invisibile; risolto usando `/api/chat` con `think: false`. Script riutilizzabile in `scripts/smoke_test.py`. |
| T-03 | ✅ fatto (2026-08-04) | Dataset principale: `vectara/open_ragbench` — **nessuna contaminazione significativa**. 16 query da 16 paper diversi + 2 controlli positivi, testate su E4B e 12B senza contesto. Le 4 risposte "corrette" del 12B sono riconducibili a conoscenza disciplinare generale (matematica, medicina, economia, ML), non a training specifico sul paper: le 3 domande con valore numerico preciso (0.0226, $2.5, 8pF→3pF) erano sconosciute a entrambi i modelli. Dataset approvato. Secondo dataset (genere visuale) rinviato a I-01. Analisi in `docs/contamination.md`, dati grezzi in `eval/contamination/contamination_open_ragbench_20260804_112523.json`. Gate completo chiuso in T-05 ✅ |
| T-04 | ✅ fatto (2026-08-04) | Schema `Chunk` e `EvalRun` in `src/datasets/schema.py` (contratti §3 di ROADMAP). Loader `src/datasets/open_ragbench.py`: scarica con `snapshot_download`, normalizza sezioni a `Chunk` (section_id come seq, content_type da presenza tabelle/immagini, tabelle Markdown incluse nel testo). Script `scripts/fetch_dataset.py`. Risultato: **997 documenti, 18840 chunk** (16858 text, 1982 mixed). I 1004 file scaricati includono corpus + queries/answers/qrels già disponibili per E-01. Test unitari in `tests/test_open_ragbench_schema.py` (9/9 pass). |
| T-05 | ✅ fatto (2026-08-04) | Pipeline end-to-end funzionante: `scripts/ingest.py` + `scripts/query.py`. Stack: fastembed + onnxruntime-directml (AMD GPU via DirectX 12, 10 embed/s su testi lunghi), `intfloat/multilingual-e5-large` 1024-dim (BGE-M3 target non ancora in catalogo fastembed), Qdrant 1.18 con `query_points`. Gate verificato: query "SD of RMSE for Ridge Regression?" → risposta con `[1][2]` → valore 0.0226 citato correttamente dal paper 2412.20245v4. Questo è esattamente il valore che i modelli non conoscevano senza contesto in T-03. Problema risolto: PyTorch CPU ~0.06 embed/s → fastembed/DirectML ~10 embed/s (167x). |
| T-06 | ✅ fatto (2026-08-04) | Parser citazioni in `src/generation/citations.py`: `normalize()` (converte `[1,2]`, `[1-3]`, `[1 e 2]`, `[1]-[2]` in `[1][2]`), `filter_valid()` (scarta marcatori fuori contesto), `parse()` (composizione), `extract_cited()` (lista 1-based). `scripts/query.py` ora chiama `parse(answer, len(chunks))` prima di stampare e mostra solo le fonti effettivamente citate. 31 test unitari in `tests/test_citations.py`, tutti passati. |
| T-07 | ✅ fatto (2026-08-04) | Verifica licenze su tutte le dipendenze in `pyproject.toml`. Nessuna copyleft. Tabella in `STACK.md` corretta: rimosso duplicato `sentence-transformers` non-strikethrough, corretta velocità onnxruntime-directml (21→~10 embed/s), aggiunto timestamp di verifica. Licenze confermate da dist-info: pydantic MIT, uvicorn/starlette BSD-3-Clause, ruff MIT, pytest MIT, datasets/huggingface_hub/qdrant-client/fastembed Apache 2.0, onnxruntime-directml MIT. |

**Deliberatamente saltato in T-01:** `src/config.py` (nessun parametro di retrieval esiste finché non c'è retrieval — arriva a R-01), logica applicativa nei package vuoti, `uv.lock` (si genera al primo `uv sync` reale).

**Fase 0 completa.** Tutti i task T-01…T-07 chiusi.

---

## Fase 1 — Ingestion multi-dataset e profilatore

| Task | Stato | Note |
|---|---|---|
| I-01 | ✅ fatto (2026-08-05) | Profilatore documenti in `src/profiling/profiler.py`: `DocProfile` dataclass + `profile_from_chunks()` (generico su Chunk objects, raggruppa per `dataset_id`/`doc_id`) + `dataset_summary()` + `format_report()`. CLI in `scripts/profile.py` (supporta `--dataset all`). Report open_ragbench: 997 doc, table density 0.103. Report ledger: 494 doc, table density 0.410 — **4× più alto** → generi confermati diversi. Gate superato: `python scripts/profile.py --dataset all` produce il report per entrambi i dataset. 16+17=33 test unitari (profiler + ledger schema), 79/79 pass totali. Scelta e approvazione secondo dataset: **LEDGER** (`artefactory/ledger-long-context-KPI-QA`, CC-BY-4.0), contamination check superato 2026-08-05 — 0/8 corrette con Gemma 12B senza contesto (log in `eval/contamination/contamination_ledger_20260805_093505.json`). Loader in `src/datasets/ledger.py`: pagine split su `<--- Page Split --->`, tabelle HTML, `qrel_doc_id()` per E-01. |
| I-02 | ✅ fatto (2026-08-05) | Classificatore `doc_genre` in `src/profiling/genre.py`: `assign_genre(table_density, avg_section_len)`. Soglie: `table_density ≥ 0.25 → "table_heavy"`, `avg_section_len ≥ 1000 → "academic_pdf"`, altrimenti `"continuous_text"`. Profiler aggiornato per chiamare `assign_genre` su ogni `DocProfile`. Loader `open_ragbench.py` e `ledger.py` aggiornati per calcolare il genere inline senza placeholder. Verifica su 50 documenti (25 per dataset, seed=42): **45/50 = 90.0%** — criterio ≥90% soddisfatto. Dettaglio: open_ragbench 21/25 (`academic_pdf`, 4 outlier ad alta densità di tabelle), ledger 24/25 (`table_heavy`, 1 doc sotto soglia). Full dataset: 864 `academic_pdf` + 133 `table_heavy` su open_ragbench; 465 `table_heavy` + 29 altri su ledger. 10 unit test in `tests/test_genre.py`, 90/90 pass totali. |
| I-03 | ✅ fatto (2026-08-05) | Pipeline `continuous_text` in `src/ingestion/pipeline_continuous_text.py`: `_split_paragraphs()` (separatore `\n\n`, paragrafo come unità atomica), `_group_paragraphs()` (finestra crescente ≥ `chunk_size` chars, poi trim dal fronte fino a mantenere ≥ `overlap` chars), `chunk_document()` (produce `Chunk` con `pipeline="continuous_text"`, `section_path=""`). Default: `chunk_size=1000`, `overlap=200`. Paragrafo più lungo di `chunk_size` esce come chunk singolo senza troncamento. 23 test unitari in `tests/test_pipeline_continuous_text.py`, 113/113 pass totali. |
| I-04 | ✅ fatto (2026-08-05) | Pipeline `structured_hierarchical` in `src/ingestion/pipeline_structured_hierarchical.py`: `_parse_section()` estrae (level, heading, body) dall'heading Markdown embedded nella prima riga (`#{1,6} heading`); `_PathTracker` mantiene uno stack livello-aware per produrre `section_path` (`"Methods > Model"`); `chunk_document()` sub-chunka i body lunghi con i helper di I-03. Sezioni senza heading ereditano il path corrente senza modificare lo stack. content_type derivato dai campi `tables`/`images`. 29 test unitari in `tests/test_pipeline_structured_hierarchical.py`, 142/142 pass totali. |
| I-05 | ✅ fatto (2026-08-05) | Pipeline `table_heavy` in `src/ingestion/pipeline_table_heavy.py`: `_split_segments()` usa `re.split` con gruppo catturante su `<table\b…</table>` per produrre segmenti alternati `("text",…)` / `("table",…)`; ogni segmento `table` diventa un chunk atomico (mai spezzato); i segmenti `text` vengono sub-chunkati con i helper di I-03. `_first_heading()` aggiorna `section_path` a ogni heading Markdown trovato nel testo, e il valore viene ereditato dai chunk tabella che seguono. Criterio accettazione verificato: nessun chunk contiene un `<table` senza il corrispondente `</table>`. Assunzione documentata: tabelle non annidate (conforme al corpus LEDGER Mathpix Markdown). 28 test unitari in `tests/test_pipeline_table_heavy.py`, 170/170 pass totali. |
| I-06 | ⏭ rinviato | Nessun dataset corrente fornisce PDF fisici o coordinate bbox: open_ragbench è JSON pre-processato (no PDF), LEDGER è Mathpix Markdown `.mmd` (PDF sorgente non scaricati, coordinate perse nella conversione OCR). `bbox=None` per entrambi; `page` già popolato dal loader LEDGER. Applicabile solo con un futuro dataset che distribuisce PDF nativi + coordinate. Non blocca E-01→R-07. Nota aggiunta in ROADMAP §5. |
| I-07 | ✅ fatto (2026-08-05) | Indicizzazione con named vectors (dense + sparse) su Qdrant, una collection per dataset. `src/index/embed.py`: aggiunto `encode_sparse()` via `SparseTextEmbedding` (Qdrant/bm25, CPU). `src/index/store.py`: migrato a named vectors (`"dense"` + `"sparse"`), payload esteso con `pipeline` e `section_path`, aggiunto `delete_collection()`. `scripts/ingest.py` riscritto: supporta `--dataset open_ragbench|ledger|all`, `--drop`, `--batch-size`, progress reporting con throughput e ETA, tempo totale in minuti. `scripts/query.py` aggiornato per `using="dense"` e payload completo. Fix test: tolleranza fp32 batch variance su DirectML alzata da 1e-6 a 1e-5. 28 nuovi test in `tests/test_index_embed.py` (18) e `tests/test_index_store.py` (10). **198/198 test passati.** Gate: `python scripts/ingest.py --drop` completato in **122 minuti** su 65.950 chunk totali (18.840 ORB + 47.110 LEDGER), batch=32, RX 6750 XT. Bottleneck: dense embedding ~10 embed/s × 66k chunk ≈ 110 min GPU. Criterio "< 20 min" era per BGE-M3 (PR #602 ancora aperto) — aggiornato in ROADMAP con i numeri reali. Sparse (BM25 CPU): 41s totali. Upsert: 50s totali. |

---

## Fase 2 — Harness, baseline, rumore

| Task | Stato | Note |
|---|---|---|
| E-01 | ✅ fatto (2026-08-05) | Schema `GoldenQuery` + `GoldenQrel` in `src/datasets/golden.py`. Loader `load_open_ragbench_golden()`: 3045 query da `queries.json`/`qrels.json`/`answers.json` — 1 chunk rilevante per query (relevance=2), chunk_id `"open_ragbench:{doc_id}:{section_id}"`. Loader `load_ledger_golden()`: 10000 query dai 10 shard parquet (`eval/data-*-of-*.parquet`) — qrels graduati 0-2, chunk_id `"ledger:{doc_id}:{page:04d}"`. Aggiunto `download_qa()` in `ledger.py`. CLI `scripts/build_golden.py` (supporta `--dataset`). Validazione inline in `validate_golden_file()`. Output: `eval/golden/open_ragbench.jsonl` (3045 righe), `eval/golden/ledger.jsonl` (10000 righe). 26 nuovi test in `tests/test_golden.py`. **224/224 test passati.** |
| E-02 | ✅ fatto (2026-08-05) | Query non rispondibili: **35 per dataset** (25 cross-dataset + 10 manuali), nel range 30-40 previsto. Strategia: query LEDGER (KPI finanziari) poste contro il corpus open_ragbench → non rispondibili per costruzione; viceversa per ledger. 10 query manuali per dataset su argomenti plausibili ma assenti. Campo `answerable: bool = True` aggiunto a `GoldenQuery`; `validate_golden_file()` aggiornata per accettare `qrels=[]` solo se `answerable=False`. `src/datasets/unanswerable.py`: `build_unanswerable_for_open_ragbench()` + `build_unanswerable_for_ledger()`, seed fisso per riproducibilità. `scripts/build_unanswerable.py`: appende ai golden file esistenti, idempotente. Output: `eval/golden/open_ragbench.jsonl` (3045+35=3080 righe), `eval/golden/ledger.jsonl` (10000+35=10035 righe). 24 nuovi test in `tests/test_unanswerable.py`. **248/248 test passati.** |
| E-03 | ✅ fatto (2026-08-05) | Harness IR via `ir_measures` 0.4.3. `src/eval/metrics.py`: `build_qrels()`, `build_run()`, `compute_metrics()` — misure: R@5, R@10, nDCG@10, RR@10 (MRR), Success@1. `src/eval/harness.py`: `run_retrieval_eval()` — carica golden, embeda query in batch, ricerca Qdrant, calcola metriche, restituisce `EvalRun` con `git_commit` e `config_hash`. `scripts/eval.py`: CLI `--dataset`, `--top-k`, `--limit`. `Makefile`: target `eval` ora chiama `scripts/eval.py`. Dipendenze aggiunte: `ir_measures>=0.3`, `pandas>=2.0`. Gate verificato: `python scripts/eval.py --dataset open_ragbench --limit 50` → EvalRun valido in 3.3s (R@5=0.80, nDCG@10=0.68, Success@1=0.54). 18 nuovi test in `tests/test_eval_metrics.py`. **266/266 test passati.** |
| E-04 | ✅ **eseguito (2026-08-11)** — codice dal 2026-08-05 | Baseline A: generazione senza retrieval, prompt permissivo. `src/generation/baseline_prompts.py` (BASELINE_A_SYSTEM + BASELINE_B_SYSTEM + ABSTENTION_PHRASES), `src/generation/judge.py` (LLM-as-judge: CORRECT/WRONG/ABSTAINED), `src/eval/generation_harness.py` (`run_generation_eval()` — genera senza contesto, classifica con euristico + judge, EvalRun con abstention_rate/correct_rate/wrong_rate che sommano a 1.0), `scripts/eval_generation.py` (CLI `--baseline A|B --dataset --limit`), `src/config.py` + `LLM_QUANTIZATION`. Il harness è condiviso con E-05 (stessa logica, system prompt diverso). 31 nuovi test, tutti con mock LLM. **297/297 test passati.** Eseguire: `python scripts/eval_generation.py --baseline A --dataset open_ragbench --limit 50` (richiede LLM su LLM_BASE_URL). |
| E-05 | ✅ **eseguito (2026-08-11)** — codice dal 2026-08-05 | Baseline B: nessun retrieval, prompt severo. L'harness `run_generation_eval()` era già condiviso con E-04 — E-05 aggiunge 6 test dedicati al comportamento strict (`TestBaselineB`): `pipeline_mode="baseline_b"`, frase di astensione esatta da `BASELINE_B_SYSTEM` rilevata da `is_abstained()`, `abstention_rate=1.0` con tutti i candidati astenuti, mix rates corretto, hash diverso da baseline A. Eseguire: `python scripts/eval_generation.py --baseline B --dataset open_ragbench --limit 50`. **303/303 test passati.** |
| E-06 | ✅ fatto (2026-08-05) | Baseline C: retrieval lessicale BM25. `run_retrieval_eval()` esteso con `retrieval_mode="dense"|"sparse"`: sparse usa `encode_sparse(Qdrant/bm25)`+`using="sparse"` invece di `encode(multilingual-e5-large)`+`using="dense"`. `_config_hash()` include `retrieval_mode`. `scripts/eval.py` ha `--retrieval-mode dense|sparse`; sparse → `pipeline_mode="baseline_c"`. Tipo hint `search()` corretto: `list[float] \| SparseVector`. `tests/test_eval_harness.py`: 12 test (dense path, sparse path, config_hash), tutti con mock Qdrant+embed. Eseguire: `python scripts/eval.py --retrieval-mode sparse --dataset open_ragbench --limit 50`. **315/315 test passati.** |
| E-07 | ✅ fatto (2026-08-05) | Rumore di fondo: `src/eval/noise_floor.py` — `compute_noise_floor(runs)` calcola mean/std(pstdev)/min/max per ogni metrica su una lista di EvalRun; `MetricStats` + `NoiseFloorResult` Pydantic; `build_noise_floor_result()` produce il JSON salvabile. `scripts/eval_noise.py`: CLI `--mode retrieval\|generation --n-runs 5 --dataset --retrieval-mode --baseline --limit`; stampa tabella mean/std/min/max e salva in `eval/results/`. Makefile: `noise-floor`. 18 nuovi test. **333/333 test passati.** Eseguire: `make noise-floor` (retrieval, 5 runs) o `python scripts/eval_noise.py --mode generation --baseline A --n-runs 5 --limit 30`. Soglia: nessun miglioramento < std può essere dichiarato tale. |

---

## Fase 3 — Retrieval e routing

| Task | Stato | Note |
|---|---|---|
| D-01 | ✅ fatto (2026-08-05), esteso (2026-08-07) | **Riscrittura del 2026-08-07 descritta nella nota "Dashboard — riscrittura" in fondo a questa fase.** Versione originale: dashboard interna Streamlit in `dashboard/app.py`. Due pagine: **EvalRun Comparator** (carica tutti i JSON da `eval/results/`, multiselect ≥2 run, tabella metrice affiancata con highlight verde/rosso, colonna delta per 2 run) e **Chunk Inspector** (query libera su open_ragbench o ledger, dense o sparse, slider top-k, risultati come expander con score/doc_id/section_path/testo). Helper puri in `dashboard/eval_store.py` (`load_eval_runs`, `run_label`, `compare_table`) testabili senza importare Streamlit. 22 nuovi test in `tests/test_dashboard.py`. `streamlit>=1.35` (Apache 2.0) aggiunto a `pyproject.toml` e tabella licenze `STACK.md`. Makefile: target `dashboard`. **355/355 test passati.** Eseguire: `make dashboard`. |
| R-01 | ✅ fatto (2026-08-05) | Hybrid dense+sparse con RRF in `src/retrieval/hybrid.py`: `rrf_fuse()` (pura, no Qdrant, formula 1/(k+rank)) + `hybrid_search()` (fetch_k candidati da ciascun indice, fuse, restituisce `HybridResult`). `src/config.py`: `RRF_K=60`, `HYBRID_FETCH_K=20`. Harness esteso con path `retrieval_mode="hybrid"`: encode dense+sparse in batch, chiama `hybrid_search()`, passa RRF scores a `build_run()`. CLI `scripts/eval.py` aggiornato (`--retrieval-mode hybrid`, `pipeline_mode="hybrid_rrf"`). 20 nuovi test in `tests/test_retrieval_hybrid.py`. **399/399 test passati.** Eseguire: `python scripts/eval.py --retrieval-mode hybrid --dataset open_ragbench --limit 50`. |
| R-02 | ✅ fatto (2026-08-06) | Cross-encoder reranker in `src/retrieval/reranker.py`: `rerank(query, candidates, model_name, top_n)` via `fastembed TextCrossEncoder` (già incluso in fastembed>=0.6, nessuna nuova dipendenza). Modello: `BAAI/bge-reranker-v2-m3` (Apache 2.0, già approvato in STACK.md). Config: `RERANKER_MODEL` + `RERANK_FETCH_K=20`. Harness: parametro `rerank: bool = False` su `run_retrieval_eval()` — quando True, fetcha `max(RERANK_FETCH_K, top_k)` candidati dal retrieval iniziale e li re-scorifica con il cross-encoder prima di passarli alle metriche IR. `_config_hash()` include `reranker_model` quando rerank=True. CLI `scripts/eval.py`: `--rerank` flag, `pipeline_mode` suffisso `_reranked`. 17 nuovi test in `tests/test_retrieval_reranker.py`. **416/416 test passati.** Eseguire: `python scripts/eval.py --retrieval-mode dense --rerank --dataset open_ragbench --limit 50`. |
| R-03 | ✅ fatto (2026-08-06) | Query rewriting in `src/retrieval/query_rewrite.py`: `rewrite(query, base_url, model)` chiama `generate()` da `src.generation.chat` con un system prompt ottimizzato per retrieval, temperature=0, max_tokens=128, fallback sull'originale in caso di errore. `rewrite_batch()` applica il rewrite in sequenza preservando ordine e lunghezza. Config: `QUERY_REWRITE_MODEL` (default: usa `LLM_MODEL`). Harness: `query_rewrite: bool = False` su `run_retrieval_eval()` — quando True, riscrive i testi di query prima dell'encoding; `_config_hash()` include `query_rewrite_model`. CLI `scripts/eval.py`: `--query-rewrite` flag; pipeline_mode usa suffisso `_rewritten`. 17 nuovi test in `tests/test_retrieval_query_rewrite.py`. **433/433 test passati.** **Delta misurato (smoke test, prime 50 query open_ragbench, Gemma4):** nDCG@10 0.6784→0.6077 (−10.4%), Success@1 0.5400→0.4800 (−11.1%) — **risultato negativo**. Cause probabili: Gemma4 riformula con vocabolario meno tecnico del corpus scientifico open_ragbench; latenza 2.8s/query (140s per 50 query) rende il rewriting impraticabile al full scale. Il flag `--query-rewrite` resta disponibile per ablation futuri (es. con un modello più piccolo/veloce dedicato, o su corpus diverso). |
| R-04 | ✅ fatto (2026-08-06) | Filtri metadata in `src/retrieval/metadata_filter.py`: `build_content_type_filter()` (Qdrant Filter su campo `content_type`) + `infer_content_type()` (keyword heuristic: "table"/"figure"/"graph" → filtro "table", altrimenti nessun filtro). `src/index/store.py`: `search()` accetta `query_filter`; `search_batch()` accetta `filters: list[Filter\|None] \| None` (per-query, gestione batch-aware). `src/eval/harness.py`: parametro `filter_content_type` ("text"\|"table"\|"auto"\|None); in modalità "auto" calcola il filtro per ogni query con `infer_content_type()`; include `filter_content_type` in `_config_hash()`. CLI `scripts/eval.py`: `--filter-content-type text\|table\|mixed\|auto`. 30 nuovi test in `tests/test_retrieval_metadata_filter.py`. **463 test totali.** **Delta misurato (smoke test, 50 query open_ragbench, filtro "text"):** nDCG@10 0.6784→0.6507 (−4.1%), Success@1 0.5400→0.5200 (−3.7%), RR@10 0.6380→0.6140 (−3.8%), R@5 0.8000→0.7600 (−5.0%) — **risultato negativo**. Causa: in open_ragbench i chunk rilevanti sono spesso `content_type="mixed"` (sezioni con testo + tabelle nei paper scientifici); il filtro "text" li esclude. Il flag resta disponibile per ablation su dataset table-heavy (LEDGER) o in modalità "auto" su query che chiedono esplicitamente di tabelle/figure. |
| R-05 | ✅ fatto (2026-08-06) | Aggregazione documento in `src/retrieval/doc_aggregation.py`: `DocResult` + `doc_id_from_chunk_id()` + `aggregate_to_docs(chunk_scores, strategy="max"\|"sum")`. Obiettivo distinto: i chunk servono per il contesto LLM (passaggi esatti), i documenti aggregati per la lista file UI (sorgenti deduplicate). Helper privati in `src/eval/harness.py`: `_build_doc_qrels()` (qrel chunk→doc, max relevance) + `_build_doc_run()` (ScoredDoc chunk→doc via max-pooling per query). Parametro `doc_aggregate: bool = False` su `run_retrieval_eval()`: se True aggiunge `doc_R@5` e `doc_R@10` al dict metrics. CLI `scripts/eval.py`: `--doc-aggregate`. 33 nuovi test in `tests/test_retrieval_doc_aggregation.py`. **496 test totali.** **Delta misurato (smoke test, 50 query open_ragbench, top_k=5):** Chunk R@5=0.8000 vs Doc R@5=**0.9600** (+20%). La lista file trova il documento giusto in 48/50 query, contro 40/50 per il chunk esatto. Le 8 query in più sono casi dove un chunk diverso dallo stesso documento è in top-5 — abbastanza per la lista file, non ottimale come contesto LLM. **Risultato positivo** che valida l'obiettivo distinto. |
| R-06 | ✅ fatto (2026-08-06) | Router in `src/ingestion/router.py`: `route_sections(sections, genre, ...)` per dati strutturati (open_ragbench) → `structured_hierarchical` per `academic_pdf`, `continuous_text` per gli altri (le tabelle in ORB sono Markdown, non HTML — `table_heavy` pipeline non applicabile); `route_text(text, genre, ...)` per dati pagina (ledger) → `table_heavy` per `table_heavy` (atomicità HTML garantita), `continuous_text` altrove. `PIPELINE_FOR_GENRE` dict per tagging. `iter_chunks_routed()` aggiunto a entrambi i loader; ledger accumula `seq_offset` tra le pagine. `scripts/ingest.py`: flag `--pipeline-mode original\|routed` (default `original` per backwards compat). 31 nuovi test in `tests/test_ingestion_router.py`. **527 test totali.** Nessun smoke test di retrieval richiesto: la routing logic è verificata dai test unitari, il delta misurato arriva con R-07. |
| R-07 | ✅ fatto (2026-08-06), **misura definitiva (2026-08-07)** | Infrastruttura ablation: `scripts/ingest.py --collection-suffix routed` crea `open_ragbench_routed` / `ledger_routed` senza toccare le collection originali; `scripts/eval.py --collection NAME --pipeline-mode routed` valuta su una collection alternativa. `src/eval/harness.py`: parametro `collection` in `run_retrieval_eval()` e `_config_hash()`. 15 test in `tests/test_retrieval_routing_ablation.py`. Re-ingestion completata (618 min GPU, 98.312 chunk ORB + 228.331 chunk LEDGER). **I numeri riportati inizialmente (+4% / −20%, 50 query, profondità 5) erano affetti da due difetti corretti il 2026-08-07** — vedi `eval/results/archive/README.md`. **Misura definitiva sui golden set completi** (dense, profondità 10, `doc_R@5`): open_ragbench 3045 query, generic 0.9681 → routed **0.9757**; ledger 10000 query, generic 0.8916 → routed **0.6744**. Test appaiato di McNemar sul criterio binario *"almeno un documento rilevante nei primi 5 documenti"*, stesse query, `scripts/compare_runs.py`: **open_ragbench +0.76 punti** (71 query a favore di routed contro 48, **p=0.043** — reale ma marginale); **ledger −17.03 punti** (1797 a favore di generic contro 94, **p<0.0001** — schiacciante). **Conclusione: l'affermazione 2 del §0 non è sostenuta.** Il routing non batte la pipeline generica: la migliora in modo trascurabile su un genere (+0.76 punti, appena sopra la soglia di significatività su 3045 query) e la peggiora gravemente sull'altro. Ciò che il progetto dimostra davvero è la necessità della misura **per dataset**: un routing di progettazione plausibile è risultato molto sbagliato su un genere, e una media aritmetica (−8 punti) avrebbe nascosto sia il segno opposto sia il fatto che le due metà hanno forza statistica incomparabile. **Risultato negativo, resta in tabella** (§7). Cause del regresso LEDGER: ipotesi non ancora verificate, protocollo in [`docs/open-questions.md`](open-questions.md) (OQ-01).

### Dashboard — riscrittura (2026-08-07)

Non è un task di `ROADMAP.md` (che si ferma a D-01): è un intervento su D-01 già chiuso, fatto sul branch `dashboard-rework`. Motivo: la dashboard era organizzata attorno agli artefatti (un JSON, una collection, un golden file → una pagina), non attorno alle tre affermazioni del §0, e in due punti contraddiceva attivamente il §12.

**1. `EvalRun.config` — `pipeline_mode` torna binario.** Il campo era diventato un'etichetta libera (`generic_filtered_text`, `routed_docagg`, `hybrid_rrf`), contro il contratto §3.3. Conseguenza pratica: impossibile selezionare due run che differiscono per un flag solo. Aggiunto `src/eval/run_config.py` (`build_config` / `config_slug` / `differing_keys`) e il campo `config: dict` a `EvalRun`, additivo con default `{}`. **`config_hash` è rimasto identico di proposito**: ricalcolarlo avrebbe reso non confrontabili i run già riportati qui sopra. `scripts/migrate_eval_results.py` ha ricostruito i 16 risultati storici conservando l'etichetta originale in `config.legacy_pipeline_mode`. §3.3 di `ROADMAP.md` aggiornato.

**2. Rumore di fondo visibile.** `load_eval_runs()` scartava silenziosamente i file `NoiseFloorResult` (nessuna chiave `metrics`): il rumore misurato in E-07 non era **mai** arrivato in dashboard, e la colonna delta coloriva di verde qualunque Δ > 0, incluso uno sotto σ. Ora: `load_noise_floors()` + `match_noise_floor()` (mai fra dataset diversi, §11), barre con whisker ±σ, delta grigio sotto rumore e colorato solo sopra. `is_significant()` restituisce `None` quando il rumore non è mai stato misurato — "non misurato" è diverso da "non significativo", e la pagina lo dice esplicitamente. Il dataset è diventato una scelta singola: un delta cross-dataset non è più esprimibile nella UI.

**3. Retrieval Playground** (era Chunk Inspector). Le collection si leggono da Qdrant invece di essere hardcodate a `["open_ragbench", "ledger"]` — le collection `*_routed` di R-07 erano irraggiungibili proprio dall'unico strumento costruito per ispezionarle. Aggiunti hybrid (R-01) e rerank (R-02), che erano implementati ma non ispezionabili. Nuovo tab A/B fra due configurazioni qualsiasi, con overlap a livello chunk **e** documento: sul confronto `ledger` vs `ledger_routed` la Jaccard chunk è 0.00 e quella documento 0.33, e la UI spiega perché invece di lasciar credere a un guasto.

**4. Failure Explorer** (era Golden Query Browser). Prima mostrava le prime 500 query in ordine di file, una alla volta, con un bottone per query. Ora esegue un batch (embedding e ricerca batchati) e ordina dalla peggiore. Il testo del chunk atteso sta accanto a quello recuperato: senza, non si distingue un retrieval sbagliato da una label sbagliata. `chunk_id_mismatch()` rileva il caso R-07 e lo dichiara invece di lasciar leggere "recall 0" come guasto.

**Primo risultato dallo strumento nuovo** (30 query ledger, dense, top_k=5): `ledger` doc-recall 0.756 con 1/30 fallimenti, `ledger_routed` doc-recall 0.594 con 5/30 — coerente col −20% di R-07. Il dato nuovo è che i fallimenti di `ledger_routed` hanno **score alto** (0.855–0.873): i chunk piccoli non vengono ignorati dal retrieval, vengono recuperati con confidenza *sbagliata*. È un'ipotesi più precisa di "IDF diluito" e va verificata prima di essere scritta come causa.

Verifica: 684 test passati (142 nuovi in `test_eval_run_config.py`, `test_dashboard_noise.py`, `test_dashboard_probe.py`, `test_dashboard_failures.py`); tutte e quattro le pagine eseguite contro Qdrant reale con le 4 collection presenti.

**5. Modularizzazione e leggibilità (stesso branch).** `app.py` era arrivato a ~750 righe con quattro pagine dentro. Ora è un dispatcher di 60 righe e i livelli sono espliciti: `*_store.py` / `retrieval_probe.py` (logica pura, senza Streamlit, testata), `state.py` (loader cache e client Qdrant condivisi), `components.py` (render usati da più pagine), `views/*.py` (una pagina ciascuna, con `render()`). La cartella si chiama `views/` e non `pages/` di proposito: Streamlit tratta `pages/` come multipagina automatica e costruirebbe una sua navigazione sopra il selettore in sidebar.

Due correzioni di leggibilità sul comparator, entrambe emerse guardando la pagina con 5 run selezionati: le card affiancate troncavano ogni valore (`retri…`, `ledg…`, `c4ee…`) proprio quando il valore troncato — il nome della collection — è quello che serve leggere in un'ablation di routing; sostituite da una tabella con **una riga per run**, che non tronca. E le tabelle erano stirate a tutta pagina pur avendo poche colonne, il che allontana i valori dalle etichette: ora usano `width="content"`, gli header sono compatti (`#1 routed·dense-docagg`, 23 caratteri invece di 45) e i numeri sono formattati a 4 decimali con `—` per le metriche che un run non ha calcolato.

**6. Palette e identita delle serie (stesso branch).** Il grafico usava la palette di default di Altair, che con 5 run metteva due blu quasi identici uno accanto all'altro. Sostituita con gli otto slot categorici della reference palette della skill `dataviz`, in `dashboard/palette.py`. L'ordine degli slot **e** il meccanismo di sicurezza per il daltonismo, non decorazione: riordinarli invalida la garanzia.

Validata (OKLab ΔE ×100, simulazione Machado-Oliveira-Fernandes 2009 severita 1.0) contro le superfici su cui Streamlit renderizza davvero, non contro quelle di default della skill: light su `#FFFFFF` → CVD 9.1 (soglia ≥8), vista normale 19.6 (soglia ≥15); dark su `#0E1117` → CVD 8.4 e 19.3. Entrambe passano. In light mode tre slot stanno sotto 3:1 di contrasto: il rilievo documentato e una vista tabellare, che il comparator ha (la tabella metriche sta subito sopra il grafico). Le soglie sono **ri-derivate nei test**, non date per buone: modificare un hex fa fallire la suite invece di spedire un grafico illeggibile.

L'associazione fra `#1` e il run corrispondente e risolta col colore: la tabella "Run a confronto" ha una pastiglia colorata come la serie nel grafico, entrambe da `palette.series_colors`, quindi non serve contare le voci in legenda. Il colore resta **secondo** encoding — l'indice `#N` e l'etichetta portano l'identita da soli, cosi la tabella funziona anche per un lettore daltonico e in stampa. `domain`/`range` espliciti nella scala Vega: senza, aggiungere un run ricolorerebbe gli altri. Oltre 8 run selezionati il comparator avvisa e tronca, perche ciclare le tinte farebbe condividere un colore a due run — peggio che non averlo.

**7. Rendering delle tabelle nei chunk (stesso branch).** I chunk LEDGER sono OCR Mathpix: prosa con blocchi `<table>` inline. `st.markdown` scappa l'HTML, quindi arrivavano a schermo come un muro di `</td><td>` — illeggibili, e per giunta nascondevano proprio la cosa che si era aperto il chunk per guardare. Scartato `unsafe_allow_html=True`: il corpus e dato di terze parti oggi e documenti caricati dall'utente con X-01, quindi sarebbe una via di script injection in uno strumento interno. `dashboard/chunk_render.py` invece **parsa** la tabella e passa i valori a `st.dataframe`: il markup non raggiunge mai il browser come markup. Parser con `html.parser` della stdlib, non lxml/bs4 — le tabelle sono `<tr><td>` piatti da OCR e STACK.md impone una revisione di licenza per ogni nuova dipendenza. Lo split riusa `_split_segments` della pipeline table_heavy, cosi cio che la dashboard mostra come una tabella e esattamente cio che l'ingestion ha trattato come chunk atomico. Corretto anche il taglio a `[:2000]` nel Failure Explorer, che cadeva dentro un tag: ora il cap e per segmento.

**Ipotesi sul −20% di LEDGER → [`docs/open-questions.md`](open-questions.md) (OQ-01).** Guardando i chunk renderizzati sono emersi tre indizi (i chunk tabella non embeddano il proprio `section_path`; sono 12× piu piccoli e per meta non alfabetici; i fallimenti hanno score alto ma documento sbagliato) e una controprova che li complica: `open_ragbench_routed` perde l'heading ancora piu severamente e **migliora**. La causa annotata in R-07 ("IDF diluito") resta una congettura non misurata. OQ-01 contiene le misure, le tre ipotesi ancora in piedi, due trappole nei dati gia raccolti e un protocollo a stadi che parte da due controlli da 10 minuti prima di spendere ore di GPU.

**Rimasto fuori di proposito** (proposti, non implementati): pagina **Claims** con le tre affermazioni del §0 per dataset — ha senso quando la Fase 4 popola le affermazioni 1 e 3; **Corpus Profile** che unisce le statistiche Qdrant a `src/profiling/profiler.py` (un istogramma delle lunghezze chunk avrebbe previsto il risultato di R-07 senza spendere 10h di GPU); **Citation Inspector** per C-01→C-04.

---

## Fase 4 — Citazioni verificate e scaling

| Task | Stato | Note |
|---|---|---|
| C-01 | ✅ fatto (2026-08-10) | **PASS su ledger, non dimostrato su open_ragbench.** Vedi sotto: il risultato è la differenza fra i due, non la media. |
| C-02 | ✅ fatto (2026-08-10) | Parser ricostruito sugli output reali. Ribaltata una regola del T-06 che **fabbricava** citazioni 16 volte su 16. |
| C-03 | ✅ fatto (2026-08-10) | `citation_precision` **0,657 su open_ragbench, 0,366 su ledger** — e i due non si leggono allo stesso modo. Sospeso e riaperto in giornata: il verificatore di STACK.md è stato misurato prima di costruirci sopra, non reggeva, ed è stato sostituito. Vedi sotto. |
| C-04 | ✅ fatto (2026-08-11) | **Astensione corretta 100% su E-02 per entrambi i dataset**, e il gate non causa **nessuna** falsa astensione. Ma il criterio era già al 100% col solo modello: il gate è una garanzia, non una correzione. Vedi sotto. |
| C-05 | ✅ fatto (2026-08-10) | **Criterio soddisfatto senza toccare il prompt.** L'istruzione c'era dal T-0x e non era mai stata verificata: 14/14 risposte nella lingua della domanda, 0 miste. `prompt_hash` invariato. |

### C-01 — Prompt con chunk numerati e formato citazione

**Il numero, per dataset** (gemma4:latest / E4B, Q4_K_M, ctx 32768, T=0, dense top_k=5, 200 query per dataset):

| dataset | conformità | intervallo Wilson 95% | verdetto |
|---|---|---|---|
| **ledger** | **1,0000** (147/147) | [0,9745 – 1,0000] | **PASS** |
| **open_ragbench** | 0,9309 (175/188) | [0,8853 – **0,9591**] | non dimostrato |

Su open_ragbench il criterio 0,95 **cade dentro l'intervallo**: non si può dire che fallisce, solo che non è dimostrato. Servirebbero ~800 query (2,7 h di GPU) perché l'intervallo escluda 0,95; a 400 non basta ancora. Deciso di non spenderle: il residuo è dominato da `[1] [2]`, che è precisamente la variante che il parser di C-02 deve riparare, quindi sapere se il grezzo è 93% o 95% non cambia cosa si costruisce dopo.

**Il risultato è la differenza fra i due dataset, non la media.** Una media darebbe 0,96 e nasconderebbe tutto. Su open_ragbench il **23% dei chunk contiene già marcatori `[n]`** — sono paper accademici, e i paper citano così. Su LEDGER, **zero**: nessun riferimento fra parentesi quadre in 1500 chunk campionati. La causa dominante dei fallimenti su ORB — il modello che cita il sistema di riferimenti del documento invece del nostro — su LEDGER **non può esistere**. Stesso modello, stesso prompt, stessa temperatura: l'errore è sistematico e dipendente dal genere documentale. È l'affermazione 1 del §0.

La previsione era stata scritta **prima** di misurare (commit 4ce5ea0), sulla base del conteggio dei marcatori nel corpus.

**Verificato che l'1,0000 non sia un artefatto**: 54% delle risposte valutate su LEDGER usano 2+ marcatori (22 ne usano 5), quindi la contiguità è stata realmente esercitata; mediana 186 caratteri; astensioni tutte con la frase esatta del prompt.

**Cosa si è misurato e cosa no.** Quattro run su open_ragbench, tutti a 200 query:

| run | prompt | conformità | |
|---|---|---|---|
| 1 | originale, ragionamento acceso | 0,9227 | gonfiato: 17% troncate, 3% vuote |
| 2 | originale, ragionamento spento | 0,8906 | **base onesta** |
| 3 | riscritto sui fallimenti | 0,9309 | |
| 4 | + promemoria vicino alla domanda | 0,8942 | revertito |

Sottoposti al test appaiato di McNemar sulle stesse query, **nessuno dei cambi di prompt sposta la conformità complessiva in modo significativo**: run2→run3 p=0,210, run3→run4 p=0,167, run2→run4 p=1,000. Il "+4 punti" del run 3 era rumore ed era stato dichiarato come risultato — violazione del §12 corretta in 2c8cf0c.

> **Nota sui `config_hash` di questi file** (scoperta durante C-07). I run 3 e 4 sono su disco con lo stesso `config_hash 2878488d` pur avendo due prompt diverse: il promemoria del run 4 è stato aggiunto a `build_user_message`, e `prompt_hash` copriva solo `SYSTEM`. La conclusione qui sopra non ne è toccata — la tabella li ha sempre trattati come due prompt distinte e li ha confrontati appaiati — ma i due file non sono distinguibili dal loro nome. Da C-07 l'hash copre anche il template del messaggio utente; i file già scritti restano come sono, e la presenza del campo `user_template_hash` nel `config` è ciò che distingue le due regole. Il messaggio del commit `da12e50` afferma che i due run erano stati documentati come repliche a parità di configurazione: **non è così**, ed è questa riga a fare fede.

**Ciò che invece regge** è l'effetto sul bersaglio dichiarato del prompt:

> `out_of_range` — 10 query migliorate, 0 peggiorate, **p = 0,0020**

Le risposte che copiavano i riferimenti del documento sono passate da 19 a 4.

**Lezione operativa, valida per tutta la Fase 4:** a 200 query il tasso complessivo non ha potenza statistica per guidare l'iterazione sul prompt. Solo effetti grandi e concentrati su un singolo tipo di violazione sono misurabili. Iterare guardando il totale significa spendere 40 minuti di GPU per un numero non interpretabile — è successo due volte.

### Correzioni di metodo emerse da C-01

**1. Il ragionamento invisibile di Gemma 4 non era mai stato soppresso.** `"think": false` veniva inviato a ogni richiesta dal T-05, ma è un campo dell'API *nativa* di Ollama: su `/v1/chat/completions` viene scartato in silenzio. Misurato sullo stesso prompt — `think:false` 1410 token, `chat_template_kwargs` 1410, `enable_thinking` 1410, `reasoning_effort:"low"` 1410, **`reasoning_effort:"none"` 267**. La correzione usa il parametro standard OpenAI, quindi resta dentro il vincolo di STACK.md. Conseguenze: `MAX_NEW_TOKENS=1024` torna sufficiente invece di tagliare il 17% delle risposte, e `reasoning_enabled` di `EvalRun` si deriva da `cfg.REASONING_EFFORT` invece di essere scritto `False` a mano — prima ogni run dichiarava spento un ragionamento acceso. `REASONING_EFFORT` è l'interruttore già pronto per **C-07**.

**2. E-04/E-05 non sono mai stati eseguiti** — nessun file di risultato in `eval/results/`, le voci di Fase 2 marcano fatto il *codice* e riportano il comando da lanciare. Il controllo fatto oggi riproducendo le condizioni di allora: **baseline A troncato 10/10**, baseline B 4/10. Se fossero stati lanciati prima di stamattina, il 100% delle risposte del baseline permissivo sarebbe stato tagliato e il giudice avrebbe classificato frasi mozzate — e il gate della Fase 4 poggia proprio su quel confronto. Problema chiuso prima di manifestarsi.

**3. R-03 non è coinvolto**: verificato che il rewrite, con prompt corti, non innesca reasoning e restituisce query sensate. Il suo risultato negativo resta valido.

**4. `git_commit()` poteva mentire in due modi.** Ora marca `-dirty` quando ci sono modifiche a file tracciati (i non tracciati sono ignorati di proposito: ogni run scrive i propri risultati, e una spia sempre accesa non informa), e si legge **all'inizio** del run invece che alla fine — un commit fatto durante i quaranta minuti di generazione veniva registrato come quello che aveva prodotto le risposte. Nessun risultato esistente è invalidato: `git_commit` non entra in `config_hash`.

**5. Le generazioni si scrivono man mano**, sotto un nome `.partial` rinominato solo al termine. Un run morto a 190/200 lasciava zero record; ora ne lascia 190, che sono il materiale di C-02. L'esistenza del nome finale è la prova che il run è arrivato in fondo — senza quella distinzione `rescore_citations.py` valuterebbe un run troncato come intero.

**Strumenti nuovi:** `src/generation/citation_format.py` (validatore §3.2 sul testo **grezzo**, prima di `normalize()`: C-01 misura il prompt, C-02 misurerà il parser), `src/eval/citation_harness.py`, `scripts/eval_citations.py`, `scripts/rescore_citations.py` (ricalcola le metriche dalle generazioni salvate a costo zero, così un cambio dello strumento di misura non lascia vecchi e nuovi numeri incomparabili), `src/eval/retrieval_backends.py` (i tre backend estratti da `harness.py`). **921 test.**

**Per C-02**, dai dati raccolti: le varianti da riparare, in ordine di frequenza reale su open_ragbench, sono `[1] [2]` (spazio, 8 risposte su 188), i marcatori fuori contesto, `[1,2]` e `[1-3]`. Le generazioni grezze sono in `eval/results/generations/`. Nota che `[1,2]` compare nel **13,1%** dei chunk del corpus e il modello lo riproduce in 1 risposta su 188: il divieto nel prompt funziona quando viene letto.

**Aperto**: l'astensione su LEDGER è al **26,5%** contro il 5,5% di ORB, quindi la conformità là è calcolata sul 73,5% di query in cui il retrieval ha portato la risposta in contesto. È un dato sul retrieval, non sul formato, ma va letto accanto al numero e riguarda **C-04**.

### C-02 — Parser, validazione e riparazione delle varianti note

Il criterio è «test sugli output malformati **reali**». Il parser esisteva dal T-06 ma era stato scritto contro varianti immaginate alla scrivania, prima che esistesse una singola generazione. C-02 lo ha ricostruito contro le 897 risposte valutate dei cinque dump di C-01.

**Il numero, per dataset** (`scripts/measure_repair.py`, run dello stesso dataset messe insieme):

| dataset | conformità grezza | dopo `parse()` | non conformi recuperate |
|---|---|---|---|
| **ledger** | 1,0000 (147/147) | 1,0000 | — (niente da riparare) |
| **open_ragbench** | 0,9093 (682/750) | **0,9587** | 37/68 (**54,4%**) |

Sulle due run col prompt corrente, singolarmente: 0,9309 → **0,9787** e 0,8942 → **0,9788**.

**Il risultato vero non è il +5 punti, è cosa il parser ha smesso di fare.** Il T-06 espandeva `[1-7]` in `[1][2][3][4][5]` e poi scartava l'eccedenza. Misurato sul corpus: delle **16 occorrenze reali** di costrutti multi-numero — `[1-7]`, `[16,17,18,19]`, `[1]-[21]`, `[102-109]` — **zero** stanno dentro il contesto che dovrebbero citare. Sono la bibliografia del documento sorgente, la stessa causa dominante trovata in C-01. Espanderle non è una riparazione ma una **fabbricazione**: cinque citazioni sicure di sé che il modello non ha mai fatto, e dopo l'espansione lo scarto non può più distinguerle da quelle vere. Su questo corpus la regola T-06 non ha riparato nulla e ha inventato citazioni 16 volte su 16.

Ora l'espansione è condizionata: si applica solo se **ogni** numero è un indice di chunk valido. Le regole restano — `[1,2]` contro 5 chunk *è* una citazione nostra malformata, è solo che il corpus non ne contiene — ma la condizione costa zero quando il costrutto è genuino. Due conseguenze non previste: `[0,1]` sopravvive (zero non è un indice di chunk, quindi l'intervallo matematico non diventa più una citazione dentro una formula), e `filter_valid` deve scavalcare le coppie unite dal trattino invece di smontarle, perché togliere solo `[21]` da `[1]-[21]` lascia `[1]-`, cioè la stessa fabbricazione presa dal lato opposto.

**La riparazione che mancava del tutto**: `[1] [3]`, 40 occorrenze, il difetto riparabile più frequente, e il parser non aveva alcuna regola. Da sola vale 27 delle 37 risposte recuperate.

**Il tetto è sotto il 100%, di proposito.** Dei 31 residui su ORB: **25 sono `no_citation`** — il modello non ha citato affatto, e nessun parser può inventare la citazione mancante; gli altri sono i costrutti fuori contesto che il parser si rifiuta di toccare, e restano segnalati come violazioni proprio perché non ha finto di ripararli.

**La previsione scritta a fine C-01 era in parte sbagliata.** Diceva che le varianti da riparare erano `[1] [2]`, i marcatori fuori contesto, `[1,2]` e `[1-3]`. Le prime due sì. Le ultime due esistono nel corpus ma **mai come citazioni nostre**: sempre come riferimenti del documento. La differenza non si vedeva dal conteggio delle occorrenze, solo guardando i numeri dentro il contesto di ciascuna risposta.

**Materiale e strumenti:** `tests/fixtures/malformed_citations.jsonl` (49 costrutti distinti, 124 occorrenze, con provenienza run + query_id), generato da `scripts/extract_malformed.py` così da essere riderivabile quando arrivano run nuove invece di divergere. La fixture raccoglie anche i costrutti che il checker **scagiona** (gli intervalli matematici): una fixture che contiene solo le cose da aggiustare non può accorgersi di un aggiustamento che eccede. `scripts/measure_repair.py` tiene separate le due misure — far girare la riparazione prima del checker di C-01 darebbe ~100% per costruzione e non direbbe niente né sul prompt né sul parser. **1112 test.**

**Aperto**: `parse()` è chiamato solo da `scripts/query.py`. Il percorso di servizio vero non esiste ancora (Fase 5); quando l'API arriva, la riparazione va agganciata lì e il testo grezzo va comunque conservato, perché è quello che C-01 misura.

### C-03 — Verifica di entailment: lo strumento misurato prima di usarlo

Prima di costruire `citation_precision` sopra mDeBERTa-XNLI — il verificatore che STACK.md imponeva — lo strumento è stato misurato. Non reggeva. Il task è stato **sospeso**, e riaperto solo dopo aver sostituito il modello con una misura a supporto (§6 qui sotto, e la voce nuova in STACK.md).

Le misure sono riproducibili con `scripts/probe_entailment.py {backend|length|separation|compare}`.

#### 1. Il backend è risolto, e non serve nessuna dipendenza nuova

| via | ms/coppia |
|---|---|
| torch CPU (`transformers`) | **4262** |
| onnxruntime + DirectML | **61** |

**~70×.** Il repo `MoritzLaurer/...-2mil7` spedisce lui stesso `onnx/model.onnx` (MIT), quindi niente conversione di terze parti nel percorso di fiducia, e `onnxruntime` + `tokenizers` sono già in albero via fastembed. Verificato che l'export coincida col riferimento torch: **max |Δ P(entail)| = 8,8e-03, verdetti concordi 9/9**. Su torch la strada era comunque chiusa — PyTorch non usa la GPU AMD su Windows, e 4,3 s per coppia rende infattibile qualsiasi run.

#### 2. Il difetto sta nella metrica, non nel modello: il max su N finestre gonfia coi chunk lunghi

mDeBERTa ha una finestra di **512 token**; i nostri chunk hanno mediana **714** e p90 **2582**. La premessa va spezzata in finestre e si prende il massimo — ed è lì che nasce un problema di confronti multipli: ogni finestra in più è un'altra occasione di falso positivo.

Misurato su un claim che **nessuno** dei chunk campionati supporta, quindi ogni punteggio alto è per costruzione un errore:

| finestre del chunk | P(entail) max, mediana | sopra 0,5 |
|---|---|---|
| 1 | 0,002 | 0/6 |
| 2–3 | 0,005 | 0/6 |
| 4–8 | 0,006 | 1/9 |
| 9+ | 0,046 | 1/19 |

**Correlazione fra numero di finestre e P(entail) massima: 0,46–0,54.** Senza controllo, `citation_precision` misurerebbe in parte la lunghezza del chunk citato. È lo stesso tipo di artefatto del troncamento in C-01: una variabile di comodo che entra nel numero e si fa passare per il fenomeno.

#### 3. Con la lunghezza appaiata il segnale c'è, ma è troppo debole

Floor test: il claim è **copiato alla lettera** dal chunk, quindi implicato per costruzione; il negativo è un chunk di un altro documento **con lo stesso numero di finestre**, così il confronto non si può vincere con la lunghezza. 60 coppie per dataset.

| dataset | AUC | IC95 | claim vero sopra 0,5 | chunk estraneo sopra 0,5 |
|---|---|---|---|---|
| **open_ragbench** | 0,664 | [0,567 – 0,760] | 24/60 | **18/60** |
| **ledger** | 0,785 | [0,703 – 0,867] | 29/60 | 5/60 |

Due letture, entrambe scomode:

- **Su un compito in cui il claim è copiato alla lettera, alla soglia naturale di 0,5 il verificatore dichiara non supportate più della metà delle attribuzioni vere** (24/60 e 29/60). Non è una soglia da calibrare: è che le due distribuzioni si sovrappongono.
- **L'errore è di nuovo dipendente dal genere.** Su open_ragbench il 30% dei chunk *estranei* supera 0,5 contro l'8% di LEDGER: sono paper sullo stesso argomento, e un claim tratto da uno sembra implicato dall'abstract di un altro. I bilanci sono specifici per azienda e non si confondono.

#### 4. Su LEDGER il set di validazione per parafrasi non è costruibile

Le `reference_answer` di LEDGER sono **numeri nudi** (`'2104600000'`), non frasi. Il protocollo usato su open_ragbench — frase della risposta di riferimento contro il chunk rilevante — lì non esiste. Il floor test verbatim è stato scelto proprio perché è l'unica costruzione identica sui due generi; qualsiasi confronto fra i due dataset fatto con protocolli diversi non sarebbe stato un confronto.

#### 5. Una porta aperta, e un vincolo da rimettere in discussione

STACK.md impone il modello **multilingue** — ma **entrambi i corpus sono in inglese** (paper arXiv, filing SEC). Il vincolo era una precauzione e qui costa accuratezza senza comprare niente: modelli NLI monolingui addestrati su FEVER/ANLI, cioè proprio su verifica di fatti con premesse lunghe, sono l'alternativa ovvia da misurare col protocollo già scritto. Non è stato fatto perché tocca un documento vincolante e la decisione non è mia.

#### 6. La sostituzione, e perché la leva vera era la finestra

Il vincolo multilingue è rimasto in piedi: la sostituzione è avvenuta **dentro** di esso, quindi non si è relitigata la scelta di STACK.md ma si è cambiato il modello all'interno del vincolo che quella scelta poneva.

Il candidato non è "un modello più bravo", ed è la parte che conta: **`MoritzLaurer/bge-m3-zeroshot-v2.0`** ha una finestra di **8194 token** invece di 512. Sui nostri chunk questo significa che **il 99% entra in un passaggio solo** — quindi N=1, quindi l'artefatto dei confronti multipli del §2 **non si presenta**. Non viene calibrato via: sparisce per costruzione. È MIT, multilingue, e spedisce il proprio `onnx/model.onnx` nel repo del modello, quindi nessuna conversione di terze parti e nessuna dipendenza nuova. La testa è binaria (`entailment` / `not_entailment`), che è esattamente la distinzione che serve.

Confronto appaiato — **le stesse identiche coppie punteggiate dai due modelli**, perché due run indipendenti su due campioni diversi non rispondono alla domanda «l'altro è migliore»:

| dataset | mDeBERTa-v3 (512) | bge-m3-zeroshot (8192) | McNemar esatto |
|---|---|---|---|
| **open_ragbench** | AUC 0,661 [0,564–0,758] | **0,939** [0,894–0,984] | **p = 0,0001** |
| **ledger** | AUC 0,742 [0,654–0,831] | **0,910** [0,856–0,964] | **p = 0,0094** |

**Il guadagno non è nel riconoscere meglio le attribuzioni vere, è nel non approvarne di false:**

| chunk *estranei* sopra 0,5 | prima | dopo |
|---|---|---|
| open_ragbench | 23/60 | **2/60** |
| ledger | 13/60 | **0/60** |

La confusione fra paper diversi del §3 — il difetto peggiore trovato — è scomparsa. Ed è il fallimento che conta: un verificatore che **approva** citazioni sbagliate gonfia `citation_precision`, che è molto peggio di uno pessimista.

Tre vincoli operativi che ne derivano, tutti misurati e tutti finiti in STACK.md:

- **Premessa = chunk intero fino a ~4096 token** (96% dei casi), finestre solo per la coda. Sopra i ~4000 l'attenzione quadratica costa più del windowing: 123 ms a 758 token, 762 ms a 2951, **19,7 s a 7693**.
- **Batch 1.** Il primo tentativo è morto con «risorse di memoria insufficienti»: il padding riempie il batch fino al suo elemento più lungo, quindi 8 sequenze da 4096 chiedono ~8 GB di sole matrici di attenzione.
- **Il costo dipende dal genere, non è un moltiplicatore costante.** Sulle stesse 120 valutazioni: 312 s contro 93 s su open_ragbench, ma **37 s contro 43 s su LEDGER** — dove i chunk stanno in una finestra, il modello grande è più veloce di quello piccolo.

**Cosa questo non dimostra.** Il floor test usa claim copiati alla lettera: vincere lì non garantisce di vincere sulle parafrasi, che è il compito vero, e la sonda per parafrasi si costruisce solo su ORB (§4). E la soglia **non va scelta sugli stessi dati su cui si misura l'accuratezza**, o il numero esce ottimista per costruzione: serve una partizione separata.

#### 7. Il risultato: `citation_precision` per dataset

Calcolato **senza rigenerare**: l'harness di C-01 aveva salvato ogni risposta con i `chunk_ids` che aveva in contesto, quindi bastano quei dump più i testi da Qdrant. Non è una scorciatoia — significa che la metrica di citazione e quella di formato sono misurate **sulle stesse risposte**, quindi una differenza nell'una non si confonde con un campione diverso nell'altra. Le risposte passano prima da `citations.parse`: C-01 misura il grezzo di proposito, C-03 misura ciò che un lettore vedrebbe davvero.

L'unità è la coppia **(affermazione, chunk citato)**, come il §8 formula il task. Più severo che valutare l'unione delle citazioni di una frase, di proposito: un modello che affianca a una citazione giusta due irrilevanti sta facendo ciò che il progetto vuole scoprire, e un punteggio sull'unione gli darebbe il massimo.

| dataset | `citation_precision` | Wilson 95% | `citation_recall` | `uncited_claim_rate` |
|---|---|---|---|---|
| **open_ragbench** | **0,6573** (326/496) | [0,6144 – 0,6977] | 0,6250 | 0,1062 |
| **ledger** | **0,3656** (121/331) | [0,3155 – 0,4187] | 0,2815 | 0,1556 |

`uncited_claim_rate` sta accanto alla precisione perché **la precisione si alza citando di meno**: una citazione sicura e nient'altro farebbe 1,0. Senza quel secondo numero il primo non è leggibile.

**La scelta del modello ha retto in esercizio.** `windowed_premise_rate` è **0,048** su open_ragbench e **0,0000** su LEDGER: il 95% e il 100% delle premesse arrivano intere, quindi l'artefatto dei confronti multipli del §2 — quello che avrebbe reso `citation_precision` in parte una misura della lunghezza dei chunk — non si è presentato. Era la previsione del §6, verificata sui dati veri.

#### 8. Come vanno letti quei due numeri, e perché non allo stesso modo

**Su open_ragbench 0,6573 è un limite inferiore.** Misurato: delle citazioni che puntano al chunk che **i qrels marcano rilevante**, il verificatore ne accetta solo **32 su 47 = 68,1%**. Citare il chunk d'oro non garantisce che *quella specifica frase* ne sia implicata, quindi il 68,1% è a sua volta un limite inferiore sull'accuratezza del verificatore — ma la direzione è certa: una quota consistente dei 170 fallimenti è il verificatore, non il modello. Coerente col floor test, dove a soglia 0,5 si perdeva un terzo dei claim copiati alla lettera.

**Su LEDGER 0,3656 non è interpretabile come proprietà del generatore.** Guardando i casi veri: le premesse sono **markup HTML di tabelle OCR** (`<table><tr><td rowspan="2">`) e le affermazioni sono valori numerici estratti da quelle tabelle. Un modello NLI addestrato su prosa è fuori distribuzione su entrambi i lati. Lo stesso controllo dei qrels lì produce **3 sole coppie**, quindi non si può nemmeno quantificare l'errore dello strumento.

> **È un risultato per dataset, non un fallimento del task.** L'attribuzione verificata a livello di frase è misurabile sulla prosa continua; sui documenti a tabelle, con questo verificatore, **non lo è ancora**. È la stessa struttura trovata in C-01 e C-02 — il comportamento dipende dal genere documentale — e una media fra 0,66 e 0,37 la cancellerebbe.

**Una correzione plausibile provata e scartata.** L'ipotesi ovvia era che il markup delle tabelle disturbasse il modello. Misurato su 24 coppie LEDGER, premessa con tag rimossi contro premessa grezza: mediana 0,263 → 0,283, sopra soglia 5/24 → 4/24, **0 migliorate e 1 peggiorata**. Non è il markup: è che il modello non sa verificare claim numerici contro tabelle. La pulizia non è stata spedita.

Confondente minore, misurato per escluderlo: le affermazioni che parlano *del contesto* invece che del fatto («the context does not provide a specific figure…») non possono essere implicate da niente. Sono lo **0,2%** su ORB e il **6,1%** su LEDGER — reali ma non sono ciò che muove i numeri.

**La soglia non è tarata.** 0,5 è il confine naturale della testa binaria, scelto a priori: una soglia adattata sulle stesse risposte su cui si riporta la metrica la gonfia per costruzione. Calibrarla richiede una partizione separata ed è un task a sé. A 0,5 il verificatore è pessimista, quindi entrambi i numeri sopra sono conservativi — la direzione sicura per una metrica che deve mostrare che il sistema è affidabile.

#### Errori di metodo commessi qui

**1. La prima sonda dava AUC 0,53 e sarebbe stata un risultato falso.** Il tetto di 12 finestre copriva 2600 token di un chunk da 4810: la frase sotto esame cadeva **fuori** da ogni finestra, e stavo chiedendo al modello di implicare un claim da un testo che non lo conteneva. Controllato prima di scriverlo da qualche parte — `claim dentro qualche finestra: False` — e con la finestra giusta lo stesso caso dà 0,94.

**2. Una sonda ha dato AUC 0,41, sotto il caso puro.** Impossibile, e per questo utile: era il segnale che i negativi erano sistematicamente più lunghi dei positivi. È così che è stato trovato l'artefatto del §2. Un risultato assurdo va inseguito, non arrotondato.

**3. A n=25 l'AUC oscillava fra 0,66 e 0,74 fra due campionamenti.** Le cifre riportate sopra sono a n=60 e con l'intervallo accanto, che è largo comunque.

**Rischio pre-esistente trovato per caso:** `scripts/profile.py` fa ombra al modulo stdlib `profile`, che torch importa. Qualsiasi script in `scripts/` che tocchi torch fallisce con un `ModuleNotFoundError: GenerationMixin` che non c'entra niente. `probe_entailment.py` si toglie da solo la propria directory da `sys.path`; la causa resta.

### C-05 — Istruzione esplicita sulla lingua di output

**Criterio soddisfatto senza modificare il prompt.** L'istruzione `"Respond in the same language as the question"` c'era già: portata da `e3d6130`, un commit di refactor dell'era T-0x, e **mai verificata**. C-05 non era quindi «aggiungere una riga» ma «dimostrare che quella riga funziona», che è il criterio che il ROADMAP scrive.

**Il baseline, dalle generazioni già salvate.** Su 891 risposte: 873 inglesi, 18 non identificabili (formule, risposte cortissime), **0 miste**. Il difetto non si manifesta sui nostri corpus — ma questo non dimostra niente sull'istruzione, perché entrambi i corpus sono inglesi: una risposta inglese a una domanda inglese è compatibile con un prompt che non dice nulla sulla lingua.

**La prova vera.** 20 query reali del golden, 10 per dataset, tradotte a mano in it/es/fr/de, poste contro **gli stessi chunk inglesi**. Il retrieval gira sulla query inglese originale e poi resta fisso: tradurre anche la query sposterebbe il recupero, e una risposta sbagliata sarebbe un fallimento di retrieval travestito da fallimento di lingua.

| | ledger | open_ragbench |
|---|---|---|
| campioni | 10 (5 astensioni) | 10 (1 astensione) |
| lingua della domanda | **5/5** | **9/9** |
| **risposte miste** | **0/5** | **0/9** |
| formato §3.2 ancora rispettato | 5/5 | 9/9 |

Il terzo controllo non è decorativo: una riga di prompt che sistema la lingua e rompe le citazioni non sarebbe un miglioramento. Esempio reale, domanda in tedesco contro chunk inglesi:

> *Umbrella Sampling wird verwendet, um Zustände $s_{i}$ aus einer verallgemeinerten Markov-Kette zu sampeln… **[3]***

**`prompt_hash` resta `3a50ef63`.** Nessuna modifica al prompt significa che i numeri di C-01 restano validi e che C-04 misurerà su un prompt stabile — che è esattamente il motivo per cui la regola d'ordine del §12 mette C-05 prima di C-04.

#### Il reperto: l'astensione resta inglese, di proposito

Tutte e 6 le astensioni sono tornate `Insufficient information.` qualunque fosse la lingua della domanda. A prima vista è proprio la «risposta mista incoerente» che C-05 cerca.

**Non è un difetto da correggere.** È un *token di protocollo*, non prosa: `citation_format.is_abstention` lo confronta esattamente, e una frase che variasse per lingua renderebbe il **tasso di astensione dipendente dalla lingua in cui una query è stata scritta** — una metrica che si muove per una ragione che non c'entra col retrieval. Localizzarlo spetta alla UI (Fase 5), che rende il token. Tre test in `test_generation_prompt.py` esistono perché qualcuno, un giorno, vedrà l'astensione inglese sotto una domanda italiana e la "aggiusterà".

#### Nota a margine, da non sopravvalutare

Su LEDGER le astensioni sono 5/10 con domanda tradotta contro il 26,5% storico con domanda inglese, **a retrieval identico**. Suggerisce che il modello sia più cauto quando la domanda non è nella lingua dei chunk, ma n=10: è un'osservazione, non un risultato. Riguarda **C-04**.

**Strumenti nuovi:** `src/generation/language.py` (rilevamento per frase su parole funzione pesate, nessuna dipendenza nuova — STACK.md impone una revisione di licenza per ognuna, e `langdetect` sarebbe un pacchetto da mantenere per un controllo su venti campioni), `scripts/probe_language.py`, `tests/fixtures/multilingual_queries.jsonl`. **1201 test.**

### C-04 — Astensione: soglia sui punteggi di retrieval decisa dal codice

**Il criterio era già soddisfatto prima di scrivere una riga.** Misurato per primo, sulle 35 query non rispondibili di E-02 per dataset: il modello da solo si astiene **35/35 su entrambi**. Un gate non può alzare un tasso già al 100%, e può solo abbassarlo rifiutando domande rispondibili — quindi il task è stato ricostruito attorno a cosa il gate *garantisce* invece che a cosa migliora.

#### Il risultato

| | open_ragbench | ledger |
|---|---|---|
| **astensione corretta su E-02** | **100%** (35/35) | **100%** (35/35) |
| — di cui dal **gate** | 13 (37,1%) | **34 (97,1%)** |
| — di cui dal modello | 22 | 1 |
| astensione falsa *rispetto al golden* | 8,3% (5/60) | 23,3% (14/60) |
| — **causate dal gate** | **0** | **0** |
| secondi di LLM spesi su E-02 | **139 s** (erano 401 s) | **7 s** (erano 176 s) |

**Il gate non ha rifiutato nemmeno una domanda rispondibile**, su 120 query mai viste in calibrazione. La calibrazione all'1% prometteva 0,0% e 0,7% sul suo holdout; su un terzo insieme disgiunto il risultato è 0/60 e 0/60. È l'unica cifra qui che sia una conferma fuori campione — la quota catturata su E-02 (37,1% e 97,1%) coincide con la calibrazione per aritmetica, non per validazione: stessa soglia sugli stessi punteggi.

**E il risparmio è reale**: su LEDGER il gate intercetta 34 non rispondibili su 35 prima di chiamare il modello, e la GPU passa da 176 s a 7 s.

#### La scoperta: le astensioni "false" non sono false

L'8,3% e soprattutto il **23,3%** di LEDGER sembrano un difetto grave — il modello che rifiuta un quarto delle domande legittime. Prima di scriverlo, il controllo: **in quei casi il retrieval aveva davvero portato la risposta?**

> Delle 5 astensioni "false" di open_ragbench, il chunk marcato rilevante dai qrels era fra i 5 recuperati in **1 caso**. Delle 14 di LEDGER, in **1 caso**.

Quindi in 17 casi su 19 **il contesto non conteneva la risposta, e il modello ha detto onestamente di non averla**. Erano astensioni *corrette*, contate come errori perché la metrica confronta con l'etichetta del golden invece che con il contesto realmente ricevuto.

Il tasso di falsa astensione vera — il modello rifiuta **con la risposta in mano** — è **1/60 su entrambi i dataset**.

> **Una metrica costruita sull'etichetta del dato può accusare il componente sbagliato.** Il sistema che si giudicava sull'astensione stava in realtà misurando il recall del retrieval, e il pezzo che sembrava rotto era l'unico a comportarsi bene.

Il vero problema che quei numeri rivelano non riguarda C-04: è che **su LEDGER il retrieval non porta il chunk giusto in una quota consistente di query rispondibili**. Riguarda la Fase 3, non l'astensione.

#### Cosa vuol dire "deciso dal codice"

La lettura ingenua sarebbe: metti un numero in `config.py` invece di lasciar decidere al modello. Ma un numero scelto a occhio in un file di configurazione è ancora una decisione arbitraria, solo spostata di posto. Qui le due cose sono separate:

- **la politica la sceglie un umano**: `ABSTENTION_BUDGET = 1%`, cioè quante domande rispondibili si accetta di rifiutare;
- **la soglia la deriva il codice dai dati**: `scripts/calibrate_abstention.py` calcola 0,7924 e 0,8289 come percentile dei punteggi reali.

Budget all'1% e non di più perché **non c'è niente da guadagnare**: il modello cattura già tutto, quindi un budget più alto comprerebbe solo domande legittime rifiutate. A titolo di documentazione, il compromesso misurato:

| budget | ORB corretta / falsa | LEDGER corretta / falsa |
|---|---|---|
| **1%** | 37,1% / **0,0%** | 97,1% / 0,7% |
| 2% | 54,3% / 2,0% | 100% / 2,7% |
| 5% | 77,1% / 4,0% | 100% / 8,0% |
| 10% | 94,3% / **14,7%** | 100% / 9,3% |

#### Perché un gate che non migliora la metrica esiste comunque

Tre ragioni, nessuna delle quali è il tasso di astensione:

1. **Una garanzia non è un'osservazione.** 35/35 descrive un modello a una temperatura sotto un prompt. **C-06 farà girare lo stesso sistema su E2B ed E4B**, e la disponibilità a dire "non so" è esattamente ciò che degrada con la taglia. Una soglia sui punteggi non sa quale modello viene dopo.
2. **Costo**, ora quantificato: 401 s → 139 s e 176 s → 7 s su E-02.
3. **Verificabilità.** Una soglia in `config.py` è una politica dichiarata; la propensione di un modello ad astenersi non lo è.

#### Dettagli di progetto che non sono dettagli

**La separazione dei punteggi, di nuovo dipendente dal genere.** AUC top-1 fra rispondibili e non rispondibili: **0,972 su open_ragbench, 0,9995 su LEDGER**. I bilanci sono formulaici, quindi la distribuzione delle rispondibili è stretta (0,828–0,897) e una query di paper ci cade nettamente sotto; i paper sono eterogenei (0,778–0,923) e si sovrappongono alle intruse. È il motivo per cui il gate cattura il 97% su uno e il 37% sull'altro.

**Top-1 e non la media dei top-5.** Su ORB separa meglio (0,972 contro 0,954), e una media su cinque chunk diluisce un buon risultato con quattro riempitivi — che è il caso che il gate deve lasciar passare.

**Il gate decide prima della chiamata al modello.** Uno che gira dopo non è una garanzia: è un filtro su qualcosa di già inventato, e costa gli 11,5 s che doveva risparmiare.

**Una soglia appartiene alla coppia (collezione, modo di retrieval).** Il coseno denso sta intorno a 0,8, la fusione RRF intorno a 0,02: una coppia non calibrata restituisce *nessuna opinione* e la run lo registra, invece di astenersi su tutto o su niente in silenzio.

**Calibrazione senza fuga.** Le non rispondibili non entrano mai nel calcolo della soglia — è il percentile delle sole rispondibili — e le rispondibili sono divise in tre fette disgiunte: `[0:150]` calibrazione, `[150:300]` holdout, `[300:360]` valutazione. Tre script ricavano le loro fette dallo stesso shuffle con lo stesso seed, e niente nel codice imponeva l'accordo: ora un test verifica la disgiunzione, perché un seed cambiato non darebbe un errore ma un numero plausibile e privo di significato.

**Strumenti nuovi:** `src/retrieval/abstention.py`, `scripts/calibrate_abstention.py`, `scripts/eval_abstention.py`, gate agganciato a `scripts/query.py`. `ABSTENTION_ANSWER` è ora una costante unica in `prompt.py` — il prompt che la chiede al modello e il gate che la emette senza modello devono usare lo stesso identico token (C-05); `prompt_hash` resta `3a50ef63`. **1223 test.**

### E-04 / E-05 — Baseline senza retrieval, eseguiti (2026-08-11)

Il codice era pronto dal 5 agosto; **le run non erano mai state lanciate**, e il gate della Fase 4 le richiede. Eseguirle ha prodotto i numeri attesi e, come sempre, tre difetti che solo l'esecuzione poteva far emergere.

#### I criteri: risposte corrette/sbagliate (E-04) e tasso di astensione (E-05)

100 query rispondibili per dataset, `gemma4:latest`, T=0, **nessun contesto recuperato**.

| | astensione | corrette | **sbagliate** |
|---|---|---|---|
| **A** (prompt permissivo) / open_ragbench | 0,120 | 0,430 | **0,450** |
| **B** (prompt severo) / open_ragbench | **0,420** | 0,410 | **0,170** |
| A / ledger | **1,000** | 0,000 | 0,000 |
| B / ledger | 1,000 | 0,000 | 0,000 |

**Su open_ragbench il prompt severo taglia le risposte sbagliate da 45% a 17% perdendo 2 punti di corrette.** Le marginali sono *compatibili* con «le astensioni in più vengono quasi tutte da risposte sbagliate», ma l'harness non salva i verdetti per query: è un'inferenza dai totali, non un fatto dimostrato. Per dimostrarlo servirebbe il dump per query, come fa `citation_harness` dal C-01.

**Su LEDGER entrambi i baseline si astengono su tutto.** Senza contesto il modello non tenta nemmeno una domanda su un bilancio.

#### Il gate della Fase 4: baseline A contro sistema completo, sulle non rispondibili

| sulle 35 non rispondibili di E-02 | baseline A (nessun retrieval) | sistema completo (C-04) |
|---|---|---|
| open_ragbench | **20,0%** inventate | **0%** |
| ledger | **97,1%** inventate | **0%** |

Su LEDGER si passa da 97% a zero. È l'affermazione centrale del progetto in numeri: **il grounding non aggiunge conoscenza, sopprime la confabulazione.**

#### L'asimmetria 20% / 97% non è una proprietà dei dataset

Sarebbe facile leggerla come «open_ragbench è più facile». È il **tipo di domanda** a decidere, non l'etichetta del dataset:

| domanda posta senza contesto | comportamento del modello |
|---|---|
| **finanziaria** (bilanci) | rifiuta — sa di non poter consultare un filing |
| **accademica** (paper) | risponde dalla memoria parametrica, e inventa |

Le non rispondibili di ORB sono query finanziarie poste contro i paper; quelle di LEDGER sono query accademiche poste contro i bilanci. Con questa chiave i quattro numeri delle rispondibili tornano insieme agli altri due: ORB (accademiche) 11-12% di astensione e 45% di errori, LEDGER (finanziarie) 100% di astensione.

> Il guadagno del sistema completo è **massimo esattamente dove il modello è più sicuro di sé e più sbagliato.** Dove già rifiutava, il retrieval aggiunge poco; dove confabulava al 97%, lo azzera.

Indizio secondario: il rifiuto sistematico sulle finanziarie è coerente con i controlli di contaminazione di T-03. Non è una prova — è un'assenza di evidenza contraria, e va trattata come tale.

#### Tre difetti trovati eseguendo

**1. Il rilevatore di astensione non riconosceva i rifiuti veri.** La prima misura sulle non rispondibili diceva che il modello inventava 35 risposte su 35. Le aveva rifiutate tutte, ogni volta con una formulazione assente dalla lista: `I do not have access to specific, real-time financial data ...`.

Il difetto era invisibile perché **sul percorso delle rispondibili una risposta che l'euristica manca arriva comunque al giudice LLM**, che restituisce `abstained` — ecco perché LEDGER dava 100% mentre `is_abstained()` non ne riconosceva nemmeno una. Il ramo per le non rispondibili non ha un giudice (non c'è un riferimento con cui confrontare) e le contava come inventate.

> Una rete di sicurezza che nasconde un buco nel controllo primario è una cosa da sapere: **il buco si vede solo dove la rete non c'è.**

Le frasi aggiunte vengono dall'output reale, non dall'immaginazione. Impatto retroattivo **misurato** con `rescore_citations.py` sui quattro dump di C-01: ogni run ricalcola il valore registrato, **+0,0000** — col contesto il modello usa il token esatto, mai questa formulazione. E le due riesecuzioni di controllo su ORB confermano che i numeri non si spostano: A da 0,110/0,440/**0,450** a 0,120/0,430/**0,450** (una query su cento passa dal giudice all'euristica), B **identico** a tre decimali. Il 45% è ora confermato da due strade indipendenti.

**2. `pipeline_mode` violava il §3.3.** L'harness ci scriveva `baseline_a` / `baseline_b`, ma il contratto lo definisce `"generic" | "routed"` e `config` esiste proprio perché quel campo non diventi un'etichetta libera. Il test di contratto su disco non l'aveva mai preso perché **non era mai esistito un file di baseline da controllare**. Corretto, e i quattro file già prodotti migrati con la convenzione di `migrate_eval_results.py`: cambia il campo, non la misura.

**3. `EvalRun.config` non veniva popolato affatto**, e `reasoning_enabled` era scritto come letterale `False` — la stessa dichiarazione non verificata che C-01 aveva trovato altrove. Ora derivato da `cfg.REASONING_EFFORT`, che i baseline finalmente passano davvero al modello: prima l'argomento era omesso e il default lo fissava in silenzio, quindi non avrebbero potuto girare nella condizione di **C-07** nemmeno volendo. Il **giudice** invece resta fissato a `"none"` e non legge la config: è lo strumento di misura, e uno strumento che cambia insieme al proprio soggetto non può attribuire la differenza a nessuno dei due.

**Aperto**: l'harness dei baseline non salva le risposte per query. È il motivo per cui il taglio 45% → 17% resta un'inferenza dai totali invece di un test appaiato, e per cui i tre difetti sopra hanno richiesto di rigenerare le risposte a mano per essere diagnosticati. `citation_harness` ha risolto lo stesso problema in C-01. **1232 test.**
