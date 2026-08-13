# Stato di avanzamento

Tracciamento dei task di `ROADMAP.md` man mano che vengono completati. Non sostituisce `ROADMAP.md` (che resta la fonte di verità, immutabile in questo file) — qui si registra solo cosa è stato fatto, quando, e con quale verifica.

## Fase 0 — Fetta verticale e gate di contaminazione

| Task | Stato | Note |
|---|---|---|
| T-01 | ✅ fatto (2026-08-03) | Scheletro repo: `src/{api,datasets,profiling,ingestion,index,retrieval,generation}/`, `compose.yml` (servizio `api` sempre attivo, `qdrant` dietro i profili `full`/`eval`/`demo`), `Dockerfile` multi-stage con `uv`, `pyproject.toml`, `.env.example`, `Makefile`, `.gitignore`, scheletro `eval/`, `dashboard/`, `ui/`, `data/demo/`. Gate verificato dal vivo: `docker compose up --build api` → container `healthy`, `curl /health` → `{"status":"ok"}`. **Non ancora committato in git.** |
| T-02 | ✅ fatto (2026-08-04) | Smoke test via Ollama 0.32.5 (alternativa approvata da STACK.md). Modelli testati: E2B (5.1B Q4_K_M, 91.2 tok/s, 1.9 GB VRAM), E4B (8.0B Q4_K_M, 15.1 tok/s, 3.3 GB), 12B (11.9B Q4_K_M, 2.4 tok/s, 8.1 GB) — tutti 100% GPU. **26B MoE escluso**: file GGUF ~18 GB supera i 12 GB VRAM; curva di scaling C-06 si ferma a 12B (previsto in ROADMAP §17). Tabella in `docs/hardware.md`, dati grezzi in `eval/contamination/smoke_20260804_103814.json`. Fix notevole: Gemma 4 è un thinking model — con `/api/generate` i token vengono consumati dal reasoning invisibile; risolto usando `/api/chat` con `think: false`. Script riutilizzabile in `scripts/smoke_test.py`. |
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
| I-07 | ✅ fatto (2026-08-05) | Indicizzazione con named vectors (dense + sparse) su Qdrant, una collection per dataset. `src/index/embed.py`: aggiunto `encode_sparse()` via `SparseTextEmbedding` (Qdrant/bm25, CPU). `src/index/store.py`: migrato a named vectors (`"dense"` + `"sparse"`), payload esteso con `pipeline` e `section_path`, aggiunto `delete_collection()`. `scripts/ingest.py` riscritto: supporta `--dataset open_ragbench|ledger|all`, `--drop`, `--batch-size`, progress reporting con throughput e ETA, tempo totale in minuti. `scripts/query.py` aggiornato per `using="dense"` e payload completo. Fix test: tolleranza fp32 batch variance su DirectML alzata da 1e-6 a 1e-5. 28 nuovi test in `tests/test_index_embed.py` (18) e `tests/test_index_store.py` (10). **198/198 test passati.** Gate: `python scripts/ingest.py --drop` completato in **122 minuti** su 65.950 chunk totali (18.840 ORB + 47.110 LEDGER), batch=32, RX 6750 XT. Bottleneck: dense embedding ~10 embed/s × 66k chunk ≈ 110 min GPU. Criterio "< 20 min" era per BGE-M3 (PR #602 ancora aperto) — aggiornato in ROADMAP con i numeri reali. Sparse (BM25 CPU): 41s totali. Upsert: 50s totali.  **Perché il criterio originale (`< 20 minuti`) non è stato rispettato:** era calibrato su BGE-M3, che produce denso e sparso in un passaggio solo. Con `multilingual-e5-large` il collo di bottiglia è l'embedding denso a ~10 chunk/s: 66k chunk ≈ 110 minuti di GPU, e il criterio descriveva un modello che non è quello adottato. Job one-shot, accettato. Con BGE-M3 il tempo scenderà per costruzione. |

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

Non è un task di `ROADMAP.md` (che si ferma a D-01): è un intervento su D-01 già chiuso, fatto sul branch `dashboard-rework`. Motivo: la dashboard era organizzata attorno agli artefatti (un JSON, una collection, un golden file → una pagina), non attorno alle tre affermazioni del §0, e in due punti contraddiceva attivamente il §15.

**1. `EvalRun.config` — `pipeline_mode` torna binario.** Il campo era diventato un'etichetta libera (`generic_filtered_text`, `routed_docagg`, `hybrid_rrf`), contro il contratto §3.3. Conseguenza pratica: impossibile selezionare due run che differiscono per un flag solo. Aggiunto `src/eval/run_config.py` (`build_config` / `config_slug` / `differing_keys`) e il campo `config: dict` a `EvalRun`, additivo con default `{}`. **`config_hash` è rimasto identico di proposito**: ricalcolarlo avrebbe reso non confrontabili i run già riportati qui sopra. `scripts/migrate_eval_results.py` ha ricostruito i 16 risultati storici conservando l'etichetta originale in `config.legacy_pipeline_mode`. §3.3 di `ROADMAP.md` aggiornato.

**2. Rumore di fondo visibile.** `load_eval_runs()` scartava silenziosamente i file `NoiseFloorResult` (nessuna chiave `metrics`): il rumore misurato in E-07 non era **mai** arrivato in dashboard, e la colonna delta coloriva di verde qualunque Δ > 0, incluso uno sotto σ. Ora: `load_noise_floors()` + `match_noise_floor()` (mai fra dataset diversi, §15), barre con whisker ±σ, delta grigio sotto rumore e colorato solo sopra. `is_significant()` restituisce `None` quando il rumore non è mai stato misurato — "non misurato" è diverso da "non significativo", e la pagina lo dice esplicitamente. Il dataset è diventato una scelta singola: un delta cross-dataset non è più esprimibile nella UI.

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
| C-07 | ✅ fatto (2026-08-12) | **Risultato negativo, e resta in tabella.** Il ragionamento esteso guadagna +4,4 punti di conformità *grezza* su open_ragbench (p=0,0386) e **+0,6 dopo il parser di C-02** (p=1,0000), perché tutto il guadagno è nella variante `[1] [2]` che il parser ripara gratis. Su ledger nessun effetto. Costo: **9,5× i token**, e l'astensione su ledger da 0,280 a 0,450. Vedi sotto. |
| I-10 | ✅ fatto (2026-08-12) | **Effetto reale, piccolo.** Il tetto a 512 token guadagna **+1,26 punti a doc@1** (p=0,0384) su 1.903 query, e regge a tutte e tre le profondità (p=0,038 / 0,040 / 0,034). Costo: **4,05× i chunk**. Vedi sotto. |
| C-08 | ✅ fatto (2026-08-12) | **Risultato negativo: il markup non era la causa.** Rendere le tabelle OCR in righe leggibili porta `citation_precision` su LEDGER da 0,3656 a 0,3263 — 35 citazioni perse contro 22 guadagnate, **p = 0,1112**. Il verificatore è indifferente alla forma della tabella. Flag lasciato spento. La diagnosi che resta è in `open-questions.md`, OQ-05. |
| C-09 | ✅ fatto (2026-08-12) | **`numeric_citation_precision` 0,7328 su LEDGER**, contro lo 0,2374 che l'NLI dà sulle stesse coppie. Copertura 39,6%; su open_ragbench 0,2% — lo strumento si rifiuta di giudicare la prosa invece di indovinare. Vedi sotto. |
| I-08 | ✅ fatto (2026-08-12) | **Non stabilito.** I prefissi E5 sfiorano la soglia solo a doc@1 (p=0,0503), **cambiano segno** a doc@3 e spariscono a doc@5: è il profilo di un effetto nullo con rumore. La model card li richiede; su questo corpus non si vedono. |
| C-06 | ✅ fatto **a due punti** (2026-08-13) | E2B ed E4B su entrambi i dataset. **12B scartato**: 240 s/query misurati, 13,3 ore. **L'affermazione 3 del §0 resta non determinata** — con due punti il divario c'è ed è grande, ma se la curva si appiattisca era proprio ciò che il terzo punto doveva dire. Vedi sotto. |

### C-06 — la curva di scaling, a due punti su tre

**I numeri** (100 query per dataset, `MAX_NEW_TOKENS=1024`, `REASONING_EFFORT=none`, dense top_k=5):

| | **E2B** (5,1B) | **E4B** (8,0B) | Δ |
|---|---|---|---|
| `format_compliance` open_ragbench | 0,8211 | **0,9263** | **+10,5** |
| `format_compliance` ledger | 0,9487 | **1,0000** | +5,1 |
| `citation_precision` ORB (NLI) | 0,7150 | 0,6811 | −3,4 ⚠️ |
| `uncited_claim_rate` ORB | 0,1748 | **0,1261** | |
| `citation_recall` ORB | 0,5976 | **0,6429** | |
| `numeric_citation_precision` ledger | 0,5094 | **0,7283** | **+21,9** |
| latenza p50 ORB | **7,6 s** | 9,4 s | |
| **VRAM** | **1,93 GB** | 3,28 GB | |

**⚠️ Su ORB E2B sembra battere E4B in `citation_precision`. Non lo batte:** non cita il 17,5% delle affermazioni contro il 12,6%, e ha recall più basso (0,598 contro 0,643). **La precisione sale citando di meno** — la trappola per cui C-03 aveva deciso di riportare `uncited_claim_rate` accanto e mai da solo. È anche un confronto **marginale e non appaiato**: i due modelli producono affermazioni diverse, quindi McNemar non si applica.

**I due controlli di coerenza sono passati.** E4B era già stato misurato in C-01 a 200 query: 0,9309 contro 0,9263 qui (scarto 0,0046) e 1,0000 contro 1,0000 su ledger. È il motivo per cui E4B è dentro C-06 anche se i suoi numeri esistevano già — senza, qualunque differenza fra le taglie sarebbe stata attribuibile anche a un cambio d'ambiente in tre giorni di modifiche.

**C-09 si ripaga subito.** Su LEDGER il verificatore numerico mostra il divario fra le taglie a **+21,9 punti**, dove l'NLI — dominato dal proprio pavimento su quel genere — ne mostra 9 (0,2000 → 0,2931). Senza C-09 quella riga della curva sarebbe stata in gran parte una misura dello strumento.

#### Perché il 12B è stato scartato

**240 s/query, misurati due volte** (1→2 record in 240 s; 3→5 in 480 s): **6,7 ore per dataset, 13,3 in totale**. Il precedente esiste: T-02 aveva già escluso il 26B MoE perché non entrava in VRAM, e la curva si era fermata a 12B.

Il conto tornava dalla tabella di T-02 — prefill 33,8 tok/s su ~5.000 token di contesto fa 148 s, più 75 s di generazione a 2,4 tok/s. **Quel calcolo era stato fatto e poi scartato** perché una calibrazione da 3 query aveva risposto 43 s/query. Due stime che differivano di quattro volte, e ho scelto quella comoda invece di indagare la discrepanza. La calibrazione resta inspiegata: 3 query in 113 secondi totali sono incompatibili con i 240 s misurati sulla **stessa identica prima query**.

> **Regola operativa che ne discende:** uno smoke test da 3 query non è una stima. E il ritmo di una run lunga va misurato nei suoi primi minuti, non annunciato e poi lasciato correre.

#### Cosa questo lascia aperto

**L'affermazione 3 del §0 non è determinata.** Dice *«con un retrieval buono la taglia del modello conta molto meno di quanto si creda»*. Su due punti:

- passare da 5,1B a 8,0B — **1,57× i parametri, 1,7× la VRAM** — compra **+10,5 punti** di conformità su ORB e **+21,9** di precisione numerica su LEDGER;
- non è un effetto piccolo, quindi **questi dati non sostengono l'affermazione 3**;
- ma **se la curva si appiattisca fra 8B e 12B era precisamente ciò che il terzo punto doveva dire**, ed è la parte non misurata.

Riportarlo come «taglia conta poco» sarebbe leggere due punti come se fossero tre.

#### Cosa invece questi dati sostengono

**Il genere documentale conta quanto la taglia, e forse di più.** E2B passando da ORB a LEDGER guadagna **12,8 punti**; passare da E2B a E4B su ORB ne vale **10,5**. Cambiare corpus vale più che raddoppiare il modello.

La causa è quella che C-01 aveva già isolato: su open_ragbench il **23% dei chunk contiene già marcatori `[n]`** — sono paper, e i paper citano così — mentre su LEDGER sono **zero**. Il modo dominante di sbagliare, copiare i riferimenti del documento, su LEDGER *non può esistere*. È la terza volta che questo progetto trova il genere come variabile dominante, ed è materia dell'affermazione 2, non della 3.

#### Per completare il terzo punto

```bash
python scripts/eval_citations.py --dataset open_ragbench --model gemma4:12b --limit 100
```

**6,7 ore.** Su LEDGER non ne vale la pena: E4B è già a 1,0000 e il 12B non ha margine per migliorare. Restano validi i vincoli della parte 1 — nessuna variabile d'ambiente, e niente modifiche a `src/` o agli indici rispetto ai numeri qui sopra.

### I-11 — non adottata, e perché il numero che la sosteneva era falso

I-10 aveva stabilito che il tetto a 512 token migliora il **retrieval** (+1,26 punti a doc@1, p=0,0384). Restava da sapere se la risposta si potesse ancora *scrivere*: a `top_k=5` il tetto porta il contesto da **5.243 a 2.030 token mediani, −61%**.

**Sulla generazione, nessun impatto.** Stesse 150 query sui due indici:

| | plain | capped |
|---|---|---|
| formato, appaiato **dopo il parser** | 0,9786 | 0,9786 — **+0,0000**, p=1,0000 |
| formato, grezzo | 0,9500 | 0,9714 — +0,0214, p=0,5078 |
| astensione | 6,0% | 4,0% |
| troncate | 0 | 0 |

L'astensione non sale: il contesto tagliato non fa perdere risposte. Era il controllo che il solo `format_compliance` non avrebbe mostrato, perché le astensioni escono dal suo denominatore.

**E gli undici punti che sembravano il risultato.** `citation_precision` passava da 0,6634 a 0,7745. Dentro il **solo braccio `plain`**, a parità di generazione, l'accettazione cala in modo monotono con la lunghezza della premessa:

```
    65 -   343 token   79,2% accettate   P(entail) mediana 0,932
   346 -   828 token   68,6%                              0,729
   832 -  1721 token   59,8%                              0,554
  1784 - 14632 token   57,8%                              0,529
```

Le premesse di `capped` stanno **tutte** sotto i 515 token, cioè nella fascia dove `plain` accetta il 68-79%. Il suo 77,5% è quello che si prevede applicando la curva di `plain` a premesse corte — **senza alcun miglioramento della qualità delle citazioni**.

> `STACK.md` documentava già la sensibilità alla lunghezza di questo verificatore (correlazione 0,46-0,54 fra numero di finestre e P(entailment) massima). Era scritta, ed è stata dimenticata davanti a un numero che faceva comodo. Riproducibile con `scripts/probe_premise_length.py`.

**La regola che sopravvive a I-11:** `citation_precision` non è confrontabile fra configurazioni che cambiano la lunghezza dei chunk. Vale per qualunque modifica al chunking, non solo per questa.

**La decisione.** Nessun guadagno di qualità contro **618 minuti di re-ingestione e un indice quadruplo, per sempre**. Non adottata.

**Due voci da riconsiderare alla prossima re-ingestione**, perché sono reali e non confuse da niente:

1. **latenza −44% in mediana e −68% in p90** (9,8→5,5 s; 22,5→7,2 s), conseguenza diretta di un contesto più corto;
2. **premesse spezzate 8,1% → 0%**, che *elimina* l'artefatto del massimo su più finestre invece di aggirarlo — un miglioramento dello strumento di misura, non del sistema.

Se una re-ingestione servirà per altro — il passaggio a BGE-M3 è già previsto in `STACK.md` — il tetto va adottato in quell'occasione, perché lì costa zero in più.

### I-10 e I-08 — il tetto di chunking regge, i prefissi no

Misurati insieme su un **indice ridotto** (450 documenti su 997, 9.312 chunk), che è ciò che rende la decisione economica: ~80 minuti di GPU contro i 618 di una re-ingestione completa. Le due varianti condividono l'indice di controllo, quindi separarle sarebbe costato una seconda costruzione per niente.

**1.903 query appaiate**, non 200: il campione contiene documenti interi, quindi ogni query golden i cui documenti rilevanti stanno dentro è valutabile senza reindicizzare nulla.

| criterio | plain → **capped** (I-10) | p | plain → **prefixed** (I-08) | p |
|---|---|---|---|---|
| doc@1 | 0,9038 → **0,9164** | **0,0384** | 0,9038 → 0,9138 | 0,0503 |
| doc@3 | 0,9732 → **0,9811** | **0,0400** | 0,9732 → **0,9716** | 0,7011 |
| doc@5 | 0,9821 → **0,9895** | **0,0336** | 0,9821 → 0,9827 | 1,0000 |

**I-10 regge a ogni profondità**, con la stessa direzione e un'ampiezza coerente: non è una soglia colpita per caso, è lo stesso effetto letto a tre distanze. **I-08 no**: sfiora la soglia solo dove c'è più margine, cambia segno a doc@3 e sparisce a doc@5.

**A 200 query la lettura era invertita.** `prefixed` sembrava il migliore (2 contro 8 discordanti a doc@1) e `capped` nullo (4 contro 5). Con dieci volte i dati l'ordinamento si ribalta — e i dati in più erano già sugli indici costruiti, bastava non limitarsi alle 200 query che avevano *definito* il campione.

> Non è che il campione da 200 fosse impreciso: dava l'**ordinamento sbagliato**. È lo stesso avvertimento che C-01 aveva già registrato — a quella numerosità il tasso complessivo non ha potenza per guidare una decisione — trovato una seconda volta su una domanda diversa.

**Riportate tutte e tre le profondità, sempre.** `doc@5` è saturo (34 fallimenti su 1.903; su LEDGER **1 su 200**, misurato sull'indice completo) e non può distinguere niente; `doc@1` ha cinque volte il margine. Ma scegliere la profondità dopo aver visto quale conviene sarebbe selezione. Ed è servito: a doc@5 `capped` sembrava non rompere **nessuna** query, mentre a doc@1 ne rompe 50 su 1.903 — il documento giusto veniva spinto giù dalla prima posizione restando dentro le prime cinque.

**Perché LEDGER non è stato misurato.** Verificato prima di spendere: a doc@5 l'indice completo di LEDGER è a **0,9950 — un solo fallimento su 200 query**. Con 494 documenti enormi, i primi 20 chunk coprono una mediana di 5 documenti distinti (12 su ORB): qualunque frammento pertinente trascina dentro il documento giusto. Non è che la misura costasse troppo (3h30, misurate): **non era misurabile** con questo criterio. Cinque minuti di controllo hanno risparmiato tre ore e mezza.

**Cosa resta aperto.** `capped` produce **4,05× i chunk** — l'indice quadruplica, e con esso il tempo di ingestione. Se +1,26 punti a doc@1 valgano quel prezzo è la decisione di I-11, e non la decide questa misura: la decide chi paga la re-ingestione. Quel che questa misura toglie dal tavolo è I-09, che questi dati non giustificano.

**Limite dichiarato:** i tassi assoluti sono ottimistici — l'indice ridotto ha metà dei concorrenti della produzione — e non vanno letti come recall. Si legge il delta appaiato, che della riduzione non risente perché è identica dai due lati. I numeri si ri-derivano con `scripts/probe_index_variants.py eval` in due minuti.

### C-09 — due generi, due strumenti di verifica

**Il problema.** `citation_precision` su LEDGER vale 0,3656 e non è interpretabile: il 96,7% delle affermazioni asserisce numeri presi da tabelle OCR, e chiedere a un modello NLI *«questo testo implica quella frase?»* quando la domanda vera è *«cerca la cella giusta e confronta un numero»* non è un'inferenza linguistica. C-08 aveva già escluso che fosse la formattazione.

**Quanto sbaglia lo strumento vecchio**, misurato prima di sostituirlo (`scripts/probe_table_floor.py`). Su claim i cui numeri sono *dimostrabilmente* nel chunk citato — una ricerca di stringa, nessun modello di mezzo:

| | coppie | accettate a soglia 0,5 | P(entailment) mediana |
|---|---|---|---|
| open_ragbench (prosa) | 29 | **58,6%** | 0,580 — sopra soglia |
| ledger (tabelle) | 161 | **28,0%** | 0,276 — ben sotto |

**Chi sbaglia**, misurato prima di scegliere quanto costruire:

```
numero dentro una cella di tabella    126/161
il claim nomina l'etichetta di RIGA    99/126 = 78,6%
colonna (anno) determinabile           98/126
  e il claim la nomina                 88/98  = 89,8%
```

Il generatore cita bene. Il difetto è nello strumento — il che ha reso il verificatore la versione semplice: cercare numeri ed etichette, non capire le tabelle.

**Il risultato, per dataset:**

| dataset | `citation_precision` (NLI) | `numeric_citation_precision` | `numeric_coverage` |
|---|---|---|---|
| open_ragbench | 0,6573 | 0,0000 | **0,0020** (1/496) |
| **ledger** | 0,3656 | **0,7328** | **0,3958** (131/331) |

Su LEDGER il numerico giudica il 39,6% delle coppie e ne accetta il 73,3%, contro il **23,7%** che l'NLI dà sulle stesse. Su open_ragbench giudica **una coppia su 496**: i numeri dei paper stanno nella prosa, non in celle, e lo strumento si rifiuta di giudicare invece di indovinare.

> Quello 0,0000 su ORB **non è un risultato**: è una precisione su un denominatore di uno. La copertura accanto lo dice, ed è la ragione per cui le due chiavi si riportano sempre insieme.

**Il vincolo rispettato.** Le due metriche non finiscono mai nella stessa colonna. Sono definizioni diverse — inferenza linguistica contro ricerca in griglia — e fonderle avrebbe reso i due dataset non confrontabili, che è la trappola che la decisione di OQ-05 doveva evitare. `citation_precision` non è cambiata di una virgola: 0,6573 e 0,3656 restano gli stessi valori registrati il 2026-08-10.

**Perché il 73,3% da solo non prova niente.** Il verificatore accetta secondo lo stesso criterio — etichetta di riga nominata — che la misura di scoping aveva usato per stabilire che il modello cita bene. È circolare. La validazione vera sono i **disaccordi, che si leggono**: 67 casi in cui il numerico dice sì e l'NLI no, e i primi quattro sono citazioni palesemente corrette rifiutate con P(entail) fra 0,07 e 0,21 —

```
"the cost of goods sold ... in 2017 was $8,265.0 million"
   numerico: riga='Cost of goods sold'  colonna='2017'     NLI: 0,138
```

Nell'altra direzione **2 casi soli**, ed entrambi rivelano un limite del numerico, non dell'NLI: righe senza etichetta, e claim troncati da `split_claims` che hanno perso il soggetto — quest'ultimo è un difetto **a monte**, nella segmentazione di C-03.

**Ciò che questo strumento compra non è un numero migliore: è che ogni verdetto dice quale riga e quale colonna ha usato**, quindi si verifica a occhio in due secondi. L'NLI dice 0,138 e non dice perché.

**Un prerequisito più grande del previsto.** Serviva espandere le celle unite nel parser: il **75%** delle tabelle citate usa `colspan≥2` e il **72%** `rowspan≥2`, quasi sempre le stesse. Senza espanderle l'indice di colonna di una riga dati non corrisponde a quello della sua intestazione, e non si può dire a quale anno appartiene un numero. Scrivendo il probe ho riportato **due volte** una limitazione del mio parser come se fosse un difetto del generatore, e le ho corrette entrambe misurando — la seconda volta il campione utile è passato da 12 a 98 casi.

### C-08 — il markup delle tabelle non era la causa

`citation_precision` su LEDGER vale 0,3656 e C-03 l'aveva registrata come non interpretabile. La diagnosi aveva due metà, e C-08 ne ha testata una.

**Il sospetto, quantificato prima di agire** (117 chunk citati nella run C-03): la premessa mediana è per il **26,5%** token di markup `<td>`/`</tr>`, terzo quartile 62,5%, peggiore 77,2%. E il **96,7%** dei claim contiene almeno tre cifre. Nessuno dei due lati della coppia somiglia a ciò su cui un modello NLI addestrato su prosa è stato istruito.

**La misura**, sulle stesse 331 coppie, stesso dump, nessuna rigenerazione:

| premessa | citation_precision | recall | tempo |
|---|---|---|---|
| markup intatto | **0,3656** (121/331) | 0,2815 | 129 s |
| tabelle rese in righe | **0,3263** (108/331) | 0,2222 | 78 s |

Test appaiato per coppia (claim, chunk, marcatore): **35 citazioni perse contro 22 guadagnate, McNemar esatto p = 0,1112**. E la variazione di P(entailment) è simmetrica — mediana **+0,0000**, 132 punteggi scesi e 125 saliti, 74 invariati.

> **Il verificatore è indifferente alla forma superficiale della tabella.** L'ipotesi era che il markup lo portasse fuori distribuzione; se fosse stato così, toglierlo avrebbe spostato i punteggi in una direzione. Li sposta in entrambe, in egual misura.

**Cosa è servito comunque.** La misura era il modo per **falsificare** la spiegazione più semplice, e l'ha falsificata. Ciò che resta è la seconda metà della diagnosi — verificare un'asserzione numerica contro una griglia è una ricerca più un confronto, non un'inferenza linguistica — e non è rimediabile riformattando. Il ROADMAP §8 diceva che costruire un verificatore dedicato *«significherebbe aggirare un difetto rimediabile nel primo strumento»*: ora sappiamo che rimediabile non è, quindi l'obiezione cade. La decisione, con le sue trappole, è in [`open-questions.md`](open-questions.md) OQ-05.

**Il flag resta spento.** Il punto stimato peggiora, anche se non in modo significativo, e non si accende un interruttore per un guadagno che non c'è. Il fatto che la verifica costi il 40% in meno non è una ragione sufficiente.

**Difetto corretto prima di misurare**, con la lezione di C-07 ancora fresca: `_config_hash` di `eval_citation_precision` non conteneva il flag, quindi le due varianti sarebbero finite su disco **sotto lo stesso nome**. Ora `render_tables` entra nell'hash quando è attivo — e nel `config` sempre, anche quando è `False`, perché un campo assente non distingue "spento" da "misurato prima che l'interruttore esistesse".

### C-07 — l'effetto del ragionamento esteso

**La riga, per dataset** (gemma4:latest, T=0, dense top_k=5, 200 query, `MAX_NEW_TOKENS=2048` su entrambi i bracci):

| dataset | ragionamento | conformità grezza | astensione | latenza p50 | token p50 |
|---|---|---|---|---|---|
| open_ragbench | spento | 0,9309 | 0,060 | 9,2 s | **76** |
| open_ragbench | **acceso** | **0,9722** | 0,100 | 19,0 s | **721** |
| ledger | spento | 0,9931 | 0,280 | 9,6 s | 38 |
| ledger | **acceso** | **1,0000** | **0,450** | 16,8 s | 556 |

**Il rumore di fondo, misurato e non assunto.** Due repliche del controllo, stessa configurazione: open_ragbench 0,9309 → 0,9362 (**3 query discordanti su 188**, p=1,0000), ledger 0,9931 → 1,0000 (**1 su 144**, p=1,0000). La generazione a T=0 è quasi deterministica — molto più di quanto il §1 lasciasse temere — quindi un effetto reale ha spazio per emergere, e questo è ciò che rende leggibile tutto il resto.

**Il risultato grezzo sembra positivo.** Su open_ragbench il ragionamento porta +4,44 punti al test appaiato, 10 query migliorate contro 2 peggiorate, **p = 0,0386**. Il verdetto di C-01 passerebbe da "non dimostrato" a PASS. Su ledger, invece, **zero**: identico su ogni query in cui entrambi i bracci rispondono.

**Ma il guadagno è tutto in una violazione sola:**

| violazione (open_ragbench) | spento | acceso |
|---|---|---|
| `spaced_markers` | **0,0426** | **0,0056** |
| `no_citation` | 0,0160 | 0,0111 |
| `out_of_range` | 0,0106 | 0,0111 |
| `comma_list` | 0,0053 | 0,0056 |
| `range` | 0,0053 | 0,0056 |

Il ragionamento corregge `[1] [2]` e nient'altro. È il difetto che C-01 aveva isolato come l'ultimo rimasto, e che un promemoria nel prompt aveva provato a correggere **fallendo** (p=0,167, revertito). Fa quello che la prompt non era riuscita a fare.

**E qui il risultato si ribalta.** `[1] [2]` è esattamente la variante che il parser di C-02 ripara. Confrontando ciò che il sistema *serve* invece di ciò che il modello *genera* — `compare_generations.py --repaired`:

| open_ragbench, 180 query appaiate | spento | acceso | delta | McNemar |
|---|---|---|---|---|
| grezzo | 0,9278 | 0,9722 | +0,0444 | **p = 0,0386** |
| **riparato** | 0,9667 | 0,9722 | **+0,0056** | **p = 1,0000** |

Il parser recupera da solo il 90% della differenza. Ciò che resta — 5 query discordanti su 180, 2 contro 3 — è indistinguibile dal rumore, che sulle stesse 200 query vale 3 discordanti.

> **Conclusione di C-07: il ragionamento esteso non migliora il sistema, migliora una metrica.** Su open_ragbench compra 4,4 punti di conformità *grezza* pagandoli **9,5× i token** e 2,1× la latenza, e il parser di C-02 li produce gratis. Su ledger non compra niente in nessuna delle due letture, e costa 14,6× i token.

**Il costo secondario è più grande del primo.** Con il ragionamento acceso l'astensione su ledger passa da 0,280 a **0,450**: 90 domande rifiutate su 200 invece di 56. Trentaquattro domande rispondibili in più a cui il sistema smette di rispondere, in cambio di zero punti di conformità. Su open_ragbench lo stesso effetto è più piccolo ma nella stessa direzione (0,060 → 0,100).

Nota di metodo: le query astenute **escono dal test appaiato da entrambi i lati**, quindi il guadagno grezzo non è un artefatto del modello che evita le domande difficili — le 12 query discordanti sono tutte query a cui entrambi i bracci hanno risposto.

**Perché `MAX_NEW_TOKENS=2048` e non 1024.** A 1024 il braccio con ragionamento tronca il 50% delle risposte e ne restituisce il 17% vuote: si sarebbe misurato il budget e attribuito al ragionamento. Il controllo non se ne accorge perché non tocca mai il tetto — verificato: output identico a 1024, 2048 e 4096 (`scripts/probe_reasoning.py budget`).

**Sull'interruttore, con documentazione alla mano** (`docs.ollama.com`, `openai/openai.go`, `ai.google.dev/gemma`): il gestore `/v1` accetta cinque valori e mappa `none` su thinking spento; **omettere il campo lascia Ollama ad accendere il ragionamento da sé**, quindi il "ragionamento invisibile" scoperto in C-01 non era un bug aggirato ma il default documentato. Gemma 4 espone il thinking come booleano `enable_thinking`, senza livelli — perciò `medium`, `high` e il campo omesso danno token identici query per query, e l'asse è binario come il ROADMAP lo chiama. Resta non spiegato da nessuna delle due fonti perché `low` si distingua dagli altri tre (888 token mediani contro 993): il probe `levels` è pronto per chiuderlo, e non è sulla strada di C-07.

**Difetto trovato e corretto prima di misurare:** `config_hash` non conteneva `reasoning_effort` né `max_new_tokens`, quindi i due bracci sarebbero finiti su disco **con lo stesso nome**. Cercandolo ne è emerso uno già realizzato: `prompt_hash` copriva solo `SYSTEM`, e i run 3 e 4 di C-01 sono registrati sotto lo stesso `2878488d` pur avendo user prompt diversi. Ora l'hash copre anche il template del messaggio utente, e i due bracci di C-07 hanno hash distinti (`df800f52` / `231c3d2c`).

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

Sottoposti al test appaiato di McNemar sulle stesse query, **nessuno dei cambi di prompt sposta la conformità complessiva in modo significativo**: run2→run3 p=0,210, run3→run4 p=0,167, run2→run4 p=1,000. Il "+4 punti" del run 3 era rumore ed era stato dichiarato come risultato — violazione del §15 corretta in 2c8cf0c.

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

**`prompt_hash` resta `3a50ef63`.** Nessuna modifica al prompt significa che i numeri di C-01 restano validi e che C-04 misurerà su un prompt stabile — che è esattamente il motivo per cui la regola d'ordine del §15 mette C-05 prima di C-04.

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

---

## Fase 5 — Correttezza delle misure

Nata dall'audit del 2026-08-11: le librerie confrontate con la loro documentazione ufficiale. Il fatto e il protocollo di ognuna stanno in [`open-questions.md`](open-questions.md).

| Task | Stato | Note |
|---|---|---|
| I-09 | ❌ **non applicabile** (2026-08-12) | Era condizionata a I-08, che è risultato negativo: i prefissi E5 sfiorano la soglia solo a doc@1 (p=0,0503), cambiano segno a doc@3 e spariscono a doc@5. La deviazione dalla model card resta reale e documentata in OQ-02; il suo costo su questo corpus no. |
| I-11 | ❌ **non adottata** (2026-08-12) | Nessun effetto sulla generazione: formato identico dopo il parser (+0,0000, p=1,0000), astensione non peggiorata. Gli +11 punti di `citation_precision` erano **la lunghezza della premessa, non la qualità delle citazioni**. Prezzo: 618 min di re-ingestione e indice ×4. Due voci da riconsiderare alla prossima re-ingestione, vedi sotto. |
| R-08 | ✅ fatto (2026-08-13) | `modifier=IDF` attivo su tutte e 7 le collection, **in place**. Effetto **opposto nei due dataset**: su open_ragbench guadagna a ogni profondità e a ogni livello (chunk@5 **+3,94**, p<0,0001); su LEDGER porta al **documento** giusto (doc@5 **+27,85**) e **allontana dal chunk** giusto (chunk@5 **−1,31**, p<0,0001). Adottato lo stesso — è una correzione, non un'ottimizzazione — ma il costo su LEDGER è reale e apre OQ-06. Vedi sotto. |
| R-09 | ✅ fatto (2026-08-13) | **Risultato nullo, e si sa perché.** Le query passano da `query_embed()`. Effetto massimo misurato: **4 query discordanti su 10.000**, tutte le p ≥ 0,125. Il motivo è strutturale, non statistico: nell'87–94% dei casi le due codifiche differiscono per un **fattore di scala uniforme**, che nel prodotto scalare non cambia l'ordinamento. Adottato lo stesso. Vedi sotto. |
| R-10 | ✅ fatto (2026-08-13) | **Le tre ipotesi di OQ-01 sono cadute tutte, e la causa è un'altra.** Il **45,9%** del regresso di 17 punti è **richiamo perso da HNSW**: con ricerca esatta `ledger_routed` va da 0,7647 a 0,8471 (857 query recuperate, 33 perse) mentre `ledger` si muove di 0,37. H1 falsificata da un braccio di controllo che il protocollo non prevedeva. **Passo 3 non pagato.** Vedi sotto. |
| R-11 | ✅ fatto (2026-08-13) | `SEARCH_EXACT` e `HNSW_EF` in `config.py`, **spenti di default**. Il guadagno non segue la taglia dell'indice ma il suo **richiamo**: da +0,0000 su open_ragbench a **+0,0846** su `ledger_routed`, dove l'ANN restituisce solo l'84,8% del vero top-5. **Conseguenza principale: il confronto sul routing di R-07 era contaminato** — 8 dei 21,7 punti di regresso su LEDGER erano l'indice, non la pipeline. Vedi sotto. |

**Cosa questa fase non tocca**, verificato: E-04/E-05 non usano retrieval affatto, e la soglia di astensione di C-04 appartiene alla sola modalità `dense` (`threshold_for` restituisce `None` per le altre) — quindi R-08/R-09 non la sfiorano, per progetto e non per fortuna.

### R-08 — l'IDF aiuta un genere e ne danneggia un altro

**Il difetto.** `ensure_collection()` creava `SparseVectorParams()` senza argomenti, e tutte e sette le collection risultavano `modifier=None`. fastembed lascia fuori la componente IDF dai vettori BM25 **di proposito** — dipende dalle statistiche del corpus, che il client non ha — e si aspetta che la fornisca Qdrant a query time. Senza, il punteggio è la sola frequenza di termine: una parola comune pesa quanto una rara. Era BM25 privato della metà che discrimina.

**La correzione è in place, mai delete + create**: i vettori sparsi su disco erano corretti, la metà mancante stava nella configurazione. `update_collection` la aggiunge senza toccare un punto — verificato sul conteggio prima e dopo su tutte e sette.

#### I numeri (test appaiato, McNemar esatto, stesse query e stessi chunk)

| | **open_ragbench** (3.045 query) | | **LEDGER** (10.000 query) | |
|---|---|---|---|---|
| | senza → con IDF | p | senza → con IDF | p |
| `sparse` chunk@5 | 0,8443 → **0,8837** (+3,94) | <0,0001 | 0,0946 → **0,0815** (**−1,31**) | <0,0001 |
| `sparse` chunk@10 | 0,8923 → **0,9376** (+4,53) | <0,0001 | 0,1385 → **0,1188** (**−1,97**) | <0,0001 |
| `sparse` doc@5 | 0,9593 → **0,9846** (+2,53) | <0,0001 | 0,6411 → **0,9196** (**+27,85**) | <0,0001 |
| `sparse` doc@10 | 0,9773 → **0,9941** (+1,67) | <0,0001 | 0,7234 → **0,9622** (**+23,88**) | <0,0001 |
| `hybrid` chunk@5 | 0,8916 → **0,9034** (+1,18) | 0,0022 | 0,4375 → **0,4143** (**−2,32**) | <0,0001 |
| `hybrid` chunk@10 | 0,9442 → **0,9576** (+1,35) | <0,0001 | 0,5747 → **0,5681** (−0,66) | 0,0033 |
| `hybrid` doc@5 | 0,9865 → **0,9924** (+0,59) | 0,0014 | 0,9297 → **0,9550** (+2,53) | <0,0001 |
| `hybrid` doc@10 | 0,9931 → **0,9974** (+0,43) | 0,0002 | 0,9531 → **0,9744** (+2,13) | <0,0001 |

**Su open_ragbench l'IDF vince ovunque. Su LEDGER fa due cose opposte**: porta al documento giusto molto più spesso (+27,9 punti a doc@5 in `sparse`) e al chunk giusto un po' meno spesso (−1,31, e −2,32 dopo la fusione). Non è rumore: 484 contro 353 query discordanti a `sparse` chunk@5, 597 contro 365 a `hybrid`.

**L'ipotesi** — e resta un'ipotesi, non misurata: su LEDGER i token rari sono cifre e identificativi. Con l'IDF dominano, e tirano verso il documento che contiene quella cifra ma verso il chunk che la *nomina*, non verso quello che risponde. Senza IDF domina la frequenza, che premia i chunk che ripetono i termini della domanda. Verificabile leggendo le ~600 query discordanti; non fatto.

**La fusione RRF assorbe lo sparso in entrambe le direzioni**: su ORB il guadagno passa da +3,94 a +1,18, su LEDGER il guadagno documentale da +27,9 a +2,5 e il danno sul chunk da −1,31 a −2,32.

#### Perché è stato adottato lo stesso

Perché **non è un'ottimizzazione, è una correzione**: senza IDF quel ramo non stava misurando BM25, e chiamarlo `--retrieval-mode sparse` era un'etichetta falsa. L'alternativa era conservare un difetto noto per proteggere due punti di `hit@5` su un dataset. Ma il costo su LEDGER è reale, va detto accanto al guadagno, e apre **OQ-06**: l'IDF è un candidato al routing per genere (affermazione 2 del §0), non una scelta globale. Attivarlo per genere sarebbe un cambiamento nuovo con una misura sua — non si fa qui.

#### Come è stata ottenuta la misura

Le run archiviate del 2026-08-07 sono a **200 query** e non salvano i risultati per query: contro di loro si confrontano due medie e nient'altro. **A 200 query l'effetto su open_ragbench è p=0,7266**, cioè invisibile — il campione era 15 volte troppo piccolo. Le stesse 200 query sono state comunque rimisurate, per avere un confronto legittimo con l'archivio (`b1a67360`, `322f1cbf`, `dc481d05`).

Il test vero è `scripts/probe_idf_paired.py`, possibile perché lo stato pre-R-08 è **riproducibile in secondi**: l'IDF vive nella configurazione, si toglie e si rimette. Il probe riproduce esattamente i due numeri già su disco — 0,8750 senza, 0,8850 con — ed è questo che autorizza a credergli.

> **Il modo in cui questo probe è quasi passato senza misurare niente:** la prima versione spegneva l'IDF con `None`, che in `update_collection` significa *«non toccare questo campo»*, non *«azzera»*. Risultato: **zero query discordanti su 200**, e nessun errore da nessuna parte. Due bracci che erano lo stesso braccio. Serve `Modifier.NONE`, e serve rileggere dopo ogni scrittura — che è quello che il probe ora fa.

#### `config_hash`: due misure, due nomi

`_config_hash` non sapeva niente del modificatore, quindi una run `sparse` di oggi si sarebbe chiamata `adb48814` come quella di una settimana fa. Aggiunto `sparse_idf`, **solo** per `sparse` e `hybrid`: ricalcolando tutte le 26 run in `eval/results` con la funzione vecchia e con la nuova, cambiano le 10 sparse/hybrid e **nessuna** delle 16 dense. Due nomi densi sono fissati a letterale nel test, perché orfanare C-06 e la Fase 4 non farebbe fallire nessun altro test.

È l'opposto del caso di `n_queries`, deciso il giorno prima: l'IDF cambia **cosa il sistema calcola**, la numerosità solo con quanta precisione lo osserviamo. Il primo deve spezzare l'identità, la seconda no.

### R-09 — il difetto è reale, l'effetto è nullo, e il perché è aritmetico

**Il difetto.** In BM25 query e documento non sono simmetrici: la query dice **quali** termini contano, il documento dice **quanto** vale ognuno. `Bm25.query_embed` di fastembed lo scrive esplicitamente — *«to emulate BM25 behaviour, we don't need to use weights in the query»*. Noi mandavamo anche le query da `embed()`, la via dei documenti, applicando alla domanda la normalizzazione per lunghezza `b · len / avg_len`: il rapporto fra la lunghezza della **domanda** e la lunghezza media di un **chunk**, due grandezze che non c'entrano niente l'una con l'altra.

Corretti i quattro percorsi query (`retrieve_sparse`, `retrieve_hybrid`, e i due della dashboard). I due percorsi documento restano su `embed()`, che per loro è giusto.

#### Il risultato: niente

| test appaiato | discordanti | p |
|---|---|---|
| ORB `sparse`@5 | **1** / 3.045 | 1,0000 |
| ORB `sparse`@10 | 1 / 3.045 | 1,0000 |
| ORB `hybrid`@5 | 2 / 3.045 | 1,0000 |
| LEDGER `sparse`@5 | **0** / 10.000 | 1,0000 |
| LEDGER `sparse`@10 | 4 / 10.000 | 0,1250 |
| LEDGER `hybrid`@5 | 4 / 10.000 | 1,0000 |

Le run complete lo confermano: le metriche si muovono alla quarta o quinta cifra decimale, e la variazione più grande è `Success@1` su ORB `sparse`, +0,000985 — tre query su 3.045.

#### Perché, e non è «l'effetto è piccolo»

Il punteggio sparso è un **prodotto scalare** fra vettore query e vettore documento. Moltiplicare il vettore query per una costante moltiplica *ogni* punteggio per la stessa costante: **l'ordinamento non cambia**. E la codifica-documento di una domanda è esattamente una costante moltiplicativa ogni volta che nessun termine si ripete — con `tf = 1` per tutti, tutti i pesi vengono uguali.

Misurato, non dedotto:

| | open_ragbench | LEDGER |
|---|---|---|
| stesso insieme di token | **3.045 / 3.045 (100%)** | **10.000 / 10.000 (100%)** |
| pesi uniformi → stesso ordinamento | 2.651 / 3.045 (**87,1%**) | 9.407 / 10.000 (**94,1%**) |
| con un termine ripetuto | 394 (12,9%) | 593 (5,9%) |

Le due codifiche non differiscono **mai** su *quali* token vengono valutati. E nel 87–94% dei casi differiscono solo per un fattore di scala. Nella minoranza restante il riequilibrio è tenue — pesi 1,65 contro 1,88, un rapporto di 1,14 — e cambia l'ordine solo quando due candidati erano già quasi appaiati.

> Non è un effetto piccolo che potrebbe emergere con più potenza statistica. È un effetto **strutturalmente limitato**: per costruzione può toccare solo le query con un termine ripetuto, e nemmeno tutte.

#### Cosa questo autorizza a dire di R-08

Che i guadagni di OQ-03 sono **interamente** l'IDF. Se avessimo corretto le due metà insieme — la strada che il §15 vieta e che sembrava far risparmiare dieci minuti — avremmo attribuito tutto a «OQ-03» e non avremmo mai saputo che la ripartizione è 100 a 0. La misura separata è costata una rimisura, e ha comprato l'attribuzione.

#### Perché è stato adottato lo stesso

Perché la libreria documenta un contratto e noi lo violavamo. Il codice ora fa ciò che dice di fare, e costa zero. **Un risultato nullo qui è informazione**, non lavoro sprecato: dice che questa strada è chiusa e che chi in futuro vedrà lo sparso comportarsi male non deve ricominciare da qui.

#### L'identità si spezza lo stesso

`sparse_query_embed` è entrato nel `config_hash` **anche se l'effetto è nullo**, e la decisione è deliberata: l'appartenenza all'hash si decide da *cosa il sistema è*, non da *quanto grande è risultato l'effetto*. Il criterio opposto è circolare — servirebbe la misura per poter dare un nome alla misura. Due chiavi e non una, perché i tre stati (nessuna correzione, solo IDF, entrambe) esistono davvero su disco e le run IDF-only di stamattina sono un risultato misurato, non un gradino.

### R-10 — OQ-01 risolta a metà, e non da nessuna delle ipotesi in campo

OQ-01 era aperta dal 2026-08-07: il routing peggiora LEDGER di **17 punti** di doc-recall@5, con 1797 query perse contro 94 guadagnate. Tre ipotesi in campo — H1 (il chunk tabella non embedda il proprio heading), H2 (i chunk sono 3–12× più piccoli), H3 (la tabella è isolata dalla prosa). **Sono cadute tutte e tre.**

#### Passo 1 — i fallimenti sono pareggi, non incomprensioni

Il criterio binario del protocollo non copriva il risultato: `doc_R@5` del routed va da **0,7647 a 0,8567** passando da profondità 5 a 20, mentre il generic sta a 0,9678. Quadruplicare la profondità recupera **6 punti su 17**. H2a è un fattore parziale.

La domanda giusta era *dove* sta il documento corretto quando il routing sbaglia. Su 2.353 query fallite: 39,1% entro rango 20, 72,3% entro 100, **27,7% mai trovato**.

Poi tre cose hanno cambiato il quadro.

**Un confondente escluso, nella direzione opposta.** `ledger_routed` ha 4,8× i chunk, quindi i primi 5 potrebbero coprire meno documenti distinti e il doc-recall calare per pura combinatoria. Misurato: il routed copre **più** documenti (3,60 contro 2,95). Vede di più e sbaglia lo stesso.

**Un errore di unità d'analisi.** Le 651 query irrisolte erano state lette come «651 documenti mal rappresentati». LEDGER ha **494 documenti d'oro per 10.000 query**: per documento ne risulta **uno solo** mai trovato. Il guasto è della coppia query-documento.

**Il fatto che rovescia la questione.** Cercando *dentro* il documento d'oro (filtro Qdrant su `doc_id`) si ottiene il punteggio del miglior chunk che avrebbe potuto rispondere:

| | fallite | riuscite |
|---|---|---|
| punteggio del chunk vincente | 0,8619 | 0,8672 |
| punteggio del miglior chunk d'oro | 0,8551 | 0,8664 |
| **distacco** | **+0,0090** | +0,0000 |
| lunghezza del chunk d'oro | 1034 char | 1022 char |
| lettere/carattere | 0,75 | 0,75 |
| `section_path` presente nel testo | 66,4% | 65,3% |

**Nessuna differenza strutturale.** Il chunk giusto perde per nove millesimi. E l'intero top-5 vive dentro **0,0085** di coseno — meno del distacco che causa il fallimento. Concorrenti entro 0,0090 dal primo: media 7,1 su `ledger`, **9,0 su `ledger_routed`**.

> Questo da solo falsifica H2b e H3: se i chunk piccoli o isolati fossero la causa, le query fallite avrebbero chunk d'oro diversi da quelle riuscite. Non li hanno.

#### Passo 2 — il titolo giusto non batte quello sbagliato

Il protocollo pre-registrato dà **+17,33%** (49/150 contro 23/150; 27 query solo con contesto contro 1 solo senza, p<0,0001). Letto da solo sarebbe un risultato positivo.

Ma il passo 1 aveva stabilito che siamo in regime di quasi-pareggio, dove *qualunque* perturbazione consistente ribalta una frazione di casi. Quindi è stato aggiunto un **braccio di controllo** che il protocollo non prevedeva: anteporre un `section_path` **sbagliato**, preso da un altro documento — stessa lunghezza, stesso stile, contenuto senza relazione.

| | | |
|---|---|---|
| senza contesto | 23/150 | 15,33% |
| con contesto **vero** | 49/150 | **+17,33%** |
| con contesto **finto** | 49/150 | **+17,33%** |

Identici. E il confronto appaiato vero-contro-finto: **12 discordanti da una parte, 12 dall'altra, p = 1,0000**. Non pareggiano solo nel totale: ribaltano ognuno una dozzina di query *diverse*. È la firma di una perturbazione casuale.

**H1 è falsificata, e con essa il senso del passo 3.** Le 6–7 ore di GPU avrebbero misurato l'instabilità di un pareggio. Senza il controllo avremmo scritto che il contesto di sezione vale 18 punti sulle query fallite, e sarebbe stato falso.

#### La causa vera — quasi metà è HNSW che non trova

Il passo 1 aveva lasciato una contraddizione. Le 651 query «mai trovate» hanno un distacco **minore** di quelle perse entro 100 — 0,0071 contro 0,0102 — che con una spiegazione basata sulla rappresentazione è esattamente al contrario. E un chunk a 0,0097 dal vincitore, con una manciata di concorrenti dentro quel distacco, dovrebbe stare verso rango 7, non oltre il centesimo.

L'unica spiegazione che regge: **la ricerca non ci arriva**. Qdrant usa HNSW, che è approssimato — percorre un grafo, e in un vicinato denso può non raggiungere candidati che meriterebbero il podio. `ledger_routed` ha 228.331 punti contro 47.110, tutti in una banda di similarità larga 0,0085.

Misurato con la ricerca **esatta**, che il grafo non lo usa affatto (10.000 query, `scripts/probe_ann_recall.py`):

| | approssimata | esatta | Δ | recuperate / perse |
|---|---|---|---|---|
| `ledger_routed` | 0,7647 | **0,8471** | **+8,24** | **857 / 33** |
| `ledger` | 0,9361 | 0,9398 | +0,37 | 42 / 5 |

| divario `ledger` − `ledger_routed` | |
|---|---|
| con ricerca approssimata | **−17,14** |
| con ricerca esatta | **−9,27** |
| **quota imputabile a HNSW** | **7,87 punti = 45,9%** |

Costo: **2,5 ms/query contro 1,4**. Su queste dimensioni la ricerca esatta costa quanto `ef=512` ed è più precisa. Sono parametri di **ricerca**, non di costruzione: nessuna re-ingestione.

#### Cosa resta aperto

**9,27 punti veri**, dopo aver tolto il richiamo perso dall'indice. Su quelli le tre ipotesi originali sono tutte cadute, e ciò che resta in piedi è la descrizione del passo 1: un regime di quasi-pareggio in cui il routing ha moltiplicato i concorrenti a pari merito. Non è ancora una causa azionabile.

**L'adozione di `exact`/`hnsw_ef` non è stata fatta qui**: è un cambiamento nuovo e vuole la sua misura (§15). Proposta come **R-11**.

> **Una lezione sul metodo, non sul routing.** Il protocollo di OQ-01 era stato scritto in anticipo, ed è stato eseguito com'era — cosa giusta. Ma il suo criterio binario non copriva il risultato reale né al passo 1 né al passo 2, e il suo passo 2 misurava, senza saperlo, l'instabilità dell'ordinamento invece del valore del contesto. **Pre-registrare un test protegge dallo scegliere il test dopo aver visto i dati; non protegge dall'aver scelto il test sbagliato prima.** Serve comunque un controllo che dica cosa il test sta misurando.

### R-11 — il guadagno segue il richiamo dell'indice, e R-07 era contaminata

`SEARCH_EXACT` e `HNSW_EF` vivono in `config.py`, collegati ai due percorsi di ricerca da `store.search_params()`. **Spenti di default**, e nel `config_hash` compaiono **solo se accesi**: è la differenza fra una correzione e una scelta. R-08 andava applicata a tutte le run perché senza IDF il ramo sparso non stava calcolando BM25; il default di Qdrant invece è una configurazione legittima, ed è quella in cui è stato misurato tutto il progetto. Cinque hash reali sono fissati a letterale nei test — `bbaaca85`, `5c3c7fa2`, `f178436c`, `e34c99d5`, `eebf9f45` — così un cambio accidentale del default fallisce prima che una misura sbagliata finisca su disco.

#### Non è la taglia, ed è già interessante

| collection | punti | `doc_R@5` approssimata → esatta | Δ |
|---|---|---|---|
| open_ragbench | 18.840 | 0,9681 → 0,9681 | **+0,0000** |
| open_ragbench_routed | 98.312 | 0,9757 → 0,9787 | +0,0030 |
| ledger | 47.110 | 0,8915 → 0,8962 | +0,0046 |
| **ledger_routed** | **228.331** | **0,6744 → 0,7590** | **+0,0846** |

98.312 punti rendono quasi zero, 228.331 ne rendono otto e mezzo: **la taglia da sola non lo spiega**. E nemmeno la densità da sola — `ledger` e `ledger_routed` hanno praticamente la stessa pendenza (caduta dal 1° al 5° di 0,0085 e 0,0075) e guadagni che differiscono di venti volte.

#### Quello che lo predice si misura senza golden set

Il **richiamo dell'indice**: quanta parte del *vero* top-5 la ricerca approssimata restituisce. Si ottiene confrontando ANN ed esatta sulle stesse query — nessun qrel, nessuna etichetta — quindi si può calcolare su qualunque collection **prima** di spenderci una valutazione (`scripts/probe_index_density.py`).

| collection | `recall@5` dell'ANN | top-5 perfetti | guadagno osservato |
|---|---|---|---|
| open_ragbench | 0,9994 | 99,7% | +0,0000 |
| open_ragbench_routed | 0,9860 | 93,5% | +0,0030 |
| ledger | 0,9892 | 95,6% | +0,0046 |
| **ledger_routed** | **0,8484** | **63,9%** | **+0,0846** |

Su `ledger_routed` **più di una query su tre riceve un top-5 sbagliato**, e il 15% del vero top-5 non viene mai restituito.

#### La conseguenza vera: R-07 confrontava anche gli indici

R-07 e OQ-01 confrontano `ledger` (47k punti) con `ledger_routed` (228k). Con ricerca approssimata quel confronto **non misura solo la pipeline**: misura anche quanto richiamo l'indice perde, e ne perde molto di più su quello denso.

| `doc_R@5`, LEDGER | generic | routed | divario |
|---|---|---|---|
| ricerca approssimata | 0,8915 | 0,6744 | **−21,71** |
| ricerca esatta | 0,8962 | 0,7590 | **−13,72** |

**Otto dei 21,7 punti di regresso — il 37% — erano l'indice, non il routing.** Su open_ragbench, dove entrambe le collection hanno richiamo quasi perfetto, il quadro non cambia: il routing guadagna +0,76 con l'approssimata e +1,06 con l'esatta.

> Confrontare due indici di densità diversa con una ricerca approssimata non è un confronto fra pipeline. È un confronto fra pipeline **più** un confronto fra richiami, e i due non si separano guardando la metrica.

#### Perché il default resta spento

Perché è una **scelta**, non una correzione: il default di Qdrant è legittimo, ed è quello in cui è stato misurato tutto il progetto. Accenderlo d'ufficio spezzerebbe l'identità di ogni misura passata per un guadagno che sulle collection generiche va da 0,0000 a 0,0046.

Quello che cambia non è il default ma **una regola di metodo**, aggiunta al §15: quando si confrontano due indici di taglia o densità diversa, la ricerca esatta è obbligatoria — oppure va verificato prima che il richiamo dell'ANN sia equivalente sui due. Costa un minuto con `probe_index_density.py`.

**Cosa questo non dice.** Che la ricerca esatta sia sempre la scelta giusta: è O(n), e a 228k punti costa 2,5 ms/query contro 1,4, ma a dieci milioni il conto è un altro. È il motivo per cui resta un parametro e non una decisione cablata.

---

### Debiti piccoli chiusi il 2026-08-13, prima della Fase 6

Tre cose notate mentre si lavorava ad altro. Non sono task del ROADMAP: sono correzioni a lavoro già mergiato, fatte direttamente su `main` con un commit ciascuna.

**1. `doc_aggregate` fuori dal `config_hash`.** Da R-05 le metriche documentali sono sempre riportate, quindi il flag non cambia più un solo numero — eppure cambiava il **nome** della misura. È lo specchio del difetto corretto da R-08 e R-09: là due misure diverse condividevano un nome, qui una misura sola ne aveva due. Verificato ricalcolando ogni run in `eval/results`: **zero run vive toccate**; `doc_aggregate=true` compare solo in 5 run di `archive/`, che conservano i propri hash per politica e già non si riproducono. Un test asseriva il contrario ed era corretto quando fu scritto — allora il flag aggiungeva davvero le metriche. Invertito, con scritto perché.

**2. `--no-write` su `scripts/eval.py`.** Il gemello su `eval_citations.py` esisteva dal 12 agosto; qui mancava, e durante R-08 uno smoke test è finito in `eval/results/` accanto alle misure vere e ha dovuto essere cancellato a mano. Verificato: 84 file prima e dopo.

**3. `src/` è lint-pulito.** Ultimo `E402` rimosso da `src/index/store.py`. Refactor puro — **1335 test prima e dopo**, che è la verifica che lo fosse davvero. Gli `E402` in `scripts/` restano e appartengono a Q-04.

---

## Fase 6 — Qualità del codice

Lista chiusa di difetti già osservati, non un giro di pulizia. **Gate: nessuna metrica cambia** — `rescore_citations.py` deve restituire gli stessi valori già registrati.

### Il gate, catturato prima di cominciare (2026-08-13)

Un gate che si misura solo alla fine non è un gate: se un numero non torna, non si sa da quando. Quindi il riferimento è stato preso **prima** della prima riga di Fase 6.

**17 dump ricalcolati, 16 combaciano esattamente** (`+0.0000`). Uno no, ed è **preesistente**:

| dump | registrata | ricalcolata | Δ |
|---|---|---|---|
| `20260810_085111_open_ragbench.jsonl` | 0,8854 | 0,8906 | **+0,0052** |

Sono **8 astensioni in entrambi i casi** — non è il rilevatore di astensione. Lo scarto vale esattamente **una risposta su 192**, e la causa è la data: quella run è delle **08:51** del 10 agosto, e il controllo di formato ha ricevuto **cinque commit dopo**, l'ultimo dei quali è C-02. `e438250` in particolare (*«un costrutto che contiene 0 non è un tentativo di citazione»*) è il tipo di correzione che sposta un caso limite.

Non è un difetto: è `rescore_citations.py` che fa il suo mestiere, cioè dire che quel numero fu registrato con uno strumento diverso da quello di oggi. Quella run è comunque superata — i numeri di C-01 in tabella vengono da esecuzioni successive.

> **Quindi il criterio della Fase 6 è: questi stessi valori, non tutti zeri.** 16 a `+0.0000` e quel dump a `+0.0052`. Se a fine fase comparisse un diciassettesimo scostamento, sarebbe il refactor.

| Task | Stato | Note |
|---|---|---|
| Q-01 | ⬜ da fare | `EvalRun` costruito in **5 siti**; `reasoning_enabled` derivato in 4 e ancora scritto `False` a mano in `src/eval/harness.py` — che con `--query-rewrite` usa davvero il modello. |
| Q-02 | ⬜ da fare | L'harness dei baseline salva le risposte per query. Rende il taglio 45%→17% un test appaiato. |
| Q-03 | ⬜ da fare | `scripts/profile.py` adombra il modulo `profile` della stdlib. Ha già rotto un import in C-03. |
| Q-04 | ⬜ da fare | Igiene di import e lint su `scripts/`. **`src/` è già pulito** (vedi sopra); resta solo `scripts/`. |
