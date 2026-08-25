# Stato di avanzamento

Tracciamento dei task di `ROADMAP.md` man mano che vengono completati. Non sostituisce `ROADMAP.md` (che resta la fonte di verità, immutabile in questo file) — qui si registra solo cosa è stato fatto, quando, e con quale verifica. Le **ipotesi non ancora verificate**, col protocollo per verificarle, stanno in [`open-questions.md`](open-questions.md).

**Come è ordinato**, perché tre volte era già derivato: ogni fase ha **una tabella sola**, subito sotto il titolo, con le righe **per identificativo** — è l'ordine in cui un task si cerca. Sotto, una **sezione di dettaglio per task**, nell'ordine in cui il lavoro è stato fatto — che non è quello della tabella, e `ROADMAP.md` §15 dice perché. Un task si registra nella fase in cui il piano lo mette, non in quella durante la quale è capitato di farlo.

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
| I-01 | ✅ fatto (2026-08-05) | Profilatore documenti in `src/profiling/profiler.py`: `DocProfile` dataclass + `profile_from_chunks()` (generico su Chunk objects, raggruppa per `dataset_id`/`doc_id`) + `dataset_summary()` + `format_report()`. CLI in `scripts/profile_docs.py` (supporta `--dataset all`). Report open_ragbench: 997 doc, table density 0.103. Report ledger: 494 doc, table density 0.410 — **4× più alto** → generi confermati diversi. Gate superato: `python scripts/profile_docs.py --dataset all` produce il report per entrambi i dataset (allora si chiamava `profile.py`; rinominato da Q-03). 16+17=33 test unitari (profiler + ledger schema), 79/79 pass totali. Scelta e approvazione secondo dataset: **LEDGER** (`artefactory/ledger-long-context-KPI-QA`, CC-BY-4.0), contamination check superato 2026-08-05 — 0/8 corrette con Gemma 12B senza contesto (log in `eval/contamination/contamination_ledger_20260805_093505.json`). Loader in `src/datasets/ledger.py`: pagine split su `<--- Page Split --->`, tabelle HTML, `qrel_doc_id()` per E-01. |
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
| R-07 | ✅ fatto (2026-08-06), **misura definitiva (2026-08-07)** | Infrastruttura ablation: `scripts/ingest.py --collection-suffix routed` crea `open_ragbench_routed` / `ledger_routed` senza toccare le collection originali; `scripts/eval.py --collection NAME --pipeline-mode routed` valuta su una collection alternativa. `src/eval/harness.py`: parametro `collection` in `run_retrieval_eval()` e `_config_hash()`. 15 test in `tests/test_retrieval_routing_ablation.py`. Re-ingestion completata (618 min GPU, 98.312 chunk ORB + 228.331 chunk LEDGER). **I numeri riportati inizialmente (+4% / −20%, 50 query, profondità 5) erano affetti da due difetti corretti il 2026-08-07** — vedi `eval/results/archive/README.md`. **Misura definitiva sui golden set completi** (dense, profondità 10, `doc_R@5`): open_ragbench 3045 query, generic 0.9681 → routed **0.9757**; ledger 10000 query, generic 0.8916 → routed **0.6744**. Test appaiato di McNemar sul criterio binario *"almeno un documento rilevante nei primi 5 documenti"*, stesse query, `scripts/compare_runs.py`: **open_ragbench +0.76 punti** (71 query a favore di routed contro 48, **p=0.043** — reale ma marginale); **ledger −17.03 punti** (1797 a favore di generic contro 94, **p<0.0001** — schiacciante). **Conclusione: l'affermazione 2 del §0 non è sostenuta.** Il routing non batte la pipeline generica: la migliora in modo trascurabile su un genere (+0.76 punti, appena sopra la soglia di significatività su 3045 query) e la peggiora gravemente sull'altro. Ciò che il progetto dimostra davvero è la necessità della misura **per dataset**: un routing di progettazione plausibile è risultato molto sbagliato su un genere, e una media aritmetica (−8 punti) avrebbe nascosto sia il segno opposto sia il fatto che le due metà hanno forza statistica incomparabile. **Risultato negativo, resta in tabella** (§7). Cause del regresso LEDGER: ipotesi non ancora verificate, protocollo in [`docs/open-questions.md`](open-questions.md) (OQ-01). **In ricerca esatta — l'unico confronto legittimo fra due indici di densità diversa, R-11 — i due numeri sono 0.8962 → 0.7590 e il divario è −13.72**, non −21.71: otto punti erano il richiamo dell'indice. I due numeri qui sopra sono in ricerca approssimata e **non si riproducono più** (OQ-09): rieseguendoli oggi il primo dà 0,7705.

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
| C-06 | ✅ **completo a tre punti** (2026-08-22) | E2B ed E4B su entrambi i dataset (2026-08-13); **12B su open_ragbench** col prompt del 12 agosto, così che fra i punti cambi solo il modello. Dopo il parser di C-02, sulle 91 query che tutti e tre hanno risposto: **0,8681 → 0,9670 → 0,9670**. Il salto c'è una volta sola — E2B→E4B **+9,9 punti, 9 query a 0, p=0,0039** — e poi la curva è **piatta**: E4B→12B **+0,0000**, una query per parte, **p=1,0000**, al doppio della latenza (19,2 s contro 9,4). **L'affermazione 3 del §0 è sostenuta**, e nella forma forte: fra 8B e 11,9B la taglia non conta affatto. I 240 s/query che avevano fatto scartare il 12B erano sbagliati di quindici volte (25,5 misurati). Vedi sotto. |
| C-07 | ✅ fatto (2026-08-12) | **Risultato negativo, e resta in tabella.** Il ragionamento esteso guadagna +4,4 punti di conformità *grezza* su open_ragbench (p=0,0386) e **+0,6 dopo il parser di C-02** (p=1,0000), perché tutto il guadagno è nella variante `[1] [2]` che il parser ripara gratis. Su ledger nessun effetto. Costo: **9,5× i token**, e l'astensione su ledger da 0,280 a 0,450. Vedi sotto. |
| C-08 | ✅ fatto (2026-08-12) | **Risultato negativo: il markup non era la causa.** Rendere le tabelle OCR in righe leggibili porta `citation_precision` su LEDGER da 0,3656 a 0,3263 — 35 citazioni perse contro 22 guadagnate, **p = 0,1112**. Il verificatore è indifferente alla forma della tabella. Flag lasciato spento. La diagnosi che resta è in `open-questions.md`, OQ-05. |
| C-09 | ✅ fatto (2026-08-12) | **`numeric_citation_precision` 0,7328 su LEDGER**, contro lo 0,2374 che l'NLI dà sulle stesse coppie. Copertura 39,6%; su open_ragbench 0,2% — lo strumento si rifiuta di giudicare la prosa invece di indovinare. Vedi sotto. |
| I-08 | ✅ fatto (2026-08-12) | **Non stabilito.** I prefissi E5 sfiorano la soglia solo a doc@1 (p=0,0503), **cambiano segno** a doc@3 e spariscono a doc@5: è il profilo di un effetto nullo con rumore. La model card li richiede; su questo corpus non si vedono. |
| I-10 | ✅ fatto (2026-08-12) | **Effetto reale, piccolo.** Il tetto a 512 token guadagna **+1,26 punti a doc@1** (p=0,0384) su 1.903 query, e regge a tutte e tre le profondità (p=0,038 / 0,040 / 0,034). Costo: **4,05× i chunk**. Vedi sotto. |

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

> **Chiuso da A-01** (2026-08-14). Il percorso di servizio è `src/service/answer.py`, la riparazione è agganciata lì, e `Answer` porta **entrambi** i testi — `raw_text` e `text` — proprio perché il grezzo è quello che C-01 misura.

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

**Rischio pre-esistente trovato per caso:** `scripts/profile.py` fa ombra al modulo stdlib `profile`, che torch importa. Qualsiasi script in `scripts/` che tocchi torch fallisce con un `ModuleNotFoundError: GenerationMixin` che non c'entra niente. `probe_entailment.py` si toglie da solo la propria directory da `sys.path`; la causa resta. — **Risolto il 2026-08-13 da Q-03**: lo script si chiama `profile_docs.py`, e il rimedio locale in `probe_entailment.py` è stato tolto perché non serve più.

### C-05 — Istruzione esplicita sulla lingua di output

**Criterio soddisfatto senza modificare il prompt.** L'istruzione `"Respond in the same language as the question"` c'era già: portata da `e3d6130`, un commit di refactor dell'era T-0x, e **mai verificata**. C-05 non era quindi «aggiungere una riga» ma «dimostrare che quella riga funziona», che è il criterio che il ROADMAP scrive.

**Il baseline, dalle generazioni già salvate.** Su 891 risposte: 873 inglesi, 18 non identificabili (formule, risposte cortissime), **0 miste**. Il difetto non si manifesta sui nostri corpus — ma questo non dimostra niente sull'istruzione, perché entrambi i corpus sono inglesi: una risposta inglese a una domanda inglese è compatibile con un prompt che non dice nulla sulla lingua.

**La prova vera.** 20 query reali del golden, 10 per dataset, tradotte a mano in it/es/fr/de, poste contro **gli stessi chunk inglesi**. Il retrieval gira sulla query inglese originale e poi resta fisso: tradurre anche la query sposterebbe il recupero, e una risposta sbagliata sarebbe un fallimento di retrieval travestito da fallimento di lingua.

| | ledger | open_ragbench |
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

~~**Aperto**: l'harness dei baseline non salva le risposte per query.~~ È il motivo per cui il taglio 45% → 17% resta un'inferenza dai totali invece di un test appaiato, e per cui i tre difetti sopra hanno richiesto di rigenerare le risposte a mano per essere diagnosticati. `citation_harness` ha risolto lo stesso problema in C-01. **1232 test.** — **Chiuso il 2026-08-13 da Q-02**, e **misurato**: `wrong_rate` 0,4500 → 0,1700, **31 query discordanti contro 3**, p<0,0001. Non è più un'inferenza dai totali. Dettagli e le altre due metriche nella sezione Q-02.

---

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

### C-06 — la curva di scaling, e il punto in cui smette di salire

> **Il terzo punto è stato misurato il 2026-08-22, e la curva si appiattisce.**
> Cento domande di `open_ragbench` col 12B, **col prompt vecchio** letto dal
> sidecar del 12 agosto, così che fra i tre punti cambi solo il modello. Sulle 91
> query che tutti e tre hanno risposto, dopo il parser di C-02:
>
> | | `format_compliance` | astensioni | token | latenza p50 |
> |---|---|---|---|---|
> | E2B (5,1B) | 0,8681 | 5 | 74 | 7,6 s |
> | E4B (8,0B) | **0,9670** | 5 | 83 | 9,4 s |
> | 12B (11,9B) | **0,9670** | 9 | 68 | **19,2 s** |
>
> McNemar esatto sulle stesse query: **E2B → E4B +9,9 punti, 9 a 0, p=0,0039**;
> **E4B → 12B +0,0000, una query per parte, p=1,0000**. Non è «un guadagno
> piccolo»: è zero a quattro decimali, e costa il doppio del tempo.
>
> **L'affermazione 3 è sostenuta**, e il resoconto sta in fondo alla sezione. Quel
> che segue è la lettura a due punti, che resta perché diceva una cosa giusta —
> *«se la curva si appiattisca fra 8B e 12B era precisamente ciò che il terzo
> punto doveva dire»* — e perché il modo in cui il 12B era stato scartato è un
> reperto suo.


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

**L'affermazione 3 del §0 non è determinata** — *lettura del 2026-08-13, superata dal riquadro in cima*. Dice *«con un retrieval buono la taglia del modello conta molto meno di quanto si creda»*. Su due punti:

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

#### Il terzo punto, misurato il 2026-08-22

Il comando è quello previsto qui sopra, con un'aggiunta che non c'era e che è tutto
il punto: **`--system-prompt-file`**, per girare col prompt del 12 agosto invece che
con quello in vigore. Senza, fra il secondo e il terzo punto sarebbero cambiate due
cose — il modello e il prompt — e la curva avrebbe parlato di tutt'e due (§15).

```bash
python scripts/eval_citations.py --dataset open_ragbench --model gemma4:12b --limit 100     --system-prompt-file eval/results/generations/20260812_170338_open_ragbench.prompt.txt
```

**2.554 secondi, 25,5 s a domanda.** Non 6,7 ore: il prezzo era sbagliato di
quindici volte, ed è la seconda volta in questa sezione. Il conto e le due
manopole che lo spiegano stanno in [`hardware.md`](hardware.md); qui basta la
regola che ne esce, perché è la stessa già scritta sopra con un termine in più:
**una stima di durata non è una misura finché non è stata cronometrata sullo
strumento vero, nello stato in cui girerà.**

##### La curva

Il confronto è sulle **91 query che nessuno dei tre ha rifiutato**. Le altre nove
escono da tutt'e tre i bracci insieme, non da uno solo: un test appaiato su una
popolazione decisa dal braccio che si astiene di più non è appaiato.

| | grezzo | **dopo il parser** | Δ dal precedente |
|---|---|---|---|
| E2B (5,1B) | 0,8462 | 0,8681 | |
| E4B (8,0B) | 0,9341 | **0,9670** | **+9,9** — 9 query a 0, p=0,0039 |
| 12B (11,9B) | 0,8901 | **0,9670** | **+0,0000** — 1 a 1, **p=1,0000** |

**Il salto c'è una volta sola.** Da 5,1B a 8,0B nove query passano da non
conformi a conformi e **nessuna** va nell'altro verso: un'unanimità, non una
maggioranza. Da 8,0B a 11,9B una query migliora, una peggiora, e i due tassi sono
lo stesso numero a quattro decimali.

Sul grezzo il 12B sembra addirittura **peggiore** di E4B (0,8901 contro 0,9341,
7 a 3, p=0,3438): indistinguibile dal caso, e comunque **il parser di C-02 lo
assorbe interamente**. È la stessa lezione di C-07 — la conformità grezza misura
in parte quanto il modello indovina una convenzione tipografica, e quella parte è
proprio ciò che il parser esiste per non far contare.

##### Due differenze che non sono conformità, e vanno guardate a parte

**Il 12B si astiene di più**: 9 volte su 100 contro 5. C-01 aveva indicato la
disponibilità a dire *«non lo so»* come la cosa che ci si aspetta degradi con la
taglia; qui va **nell'altro verso**, e sono numeri troppo piccoli per dire di più
(9 contro 5 su 100 non è un test).

**E scrive di meno**: 68 token in mediana contro 83. Che è anche il modo in cui
si scopre un'altra cosa — le prove a sei domande fatte quel pomeriggio **col
prompt in vigore** davano 244 e 283 token. Lo stesso modello, sullo stesso corpus,
scrive quattro volte tanto col prompt di U-14. È un effetto del prompt, non della
taglia, e appartiene a D-3.

##### Cosa la curva sostiene, e cosa no

**Sostiene l'affermazione 3 nella sua forma forte.** Non «la taglia conta meno del
previsto»: fra 8,0B e 11,9B, con questo retrieval, **non conta affatto** — a
parità di tutto il resto, e pagando il doppio della latenza.

**Non dice che valga per ogni metrica.** La curva misurata è la conformità di
formato. `citation_precision`, `citation_recall` e `numeric_citation_precision`
sul 12B **non sono state misurate**: richiedono il verificatore NLI su ogni coppia
e sono un'altra run. Il secondo punto della curva le aveva, il terzo no, e
scriverlo è meno costoso che scoprirlo leggendo il README.

**Non dice niente su LEDGER**, dove non è stata fatta e dove non aveva margine:
E4B è già a 1,0000. Il che, per l'affermazione 3, è un modo diverso di dire la
stessa cosa — se il modello piccolo è già al soffitto, quello grande non ha dove
salire.

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

### I-11 — non adottata, e perché il numero che la sosteneva era falso

I-10 aveva stabilito che il tetto a 512 token migliora il **retrieval** (+1,26 punti a doc@1, p=0,0384). Restava da sapere se la risposta si potesse ancora *scrivere*: a `top_k=5` il tetto porta il contesto da **5.243 a 2.030 token mediani, −61%**.

**Sulla generazione, nessun impatto.** Stesse 150 query sui due indici:

| | plain | capped |
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

Il test vero è `scripts/probe_sparse_paired.py` (allora `probe_idf_paired.py`, rinominato da R-09), possibile perché lo stato pre-R-08 è **riproducibile in secondi**: l'IDF vive nella configurazione, si toglie e si rimette. Il probe riproduce esattamente i due numeri già su disco — 0,8750 senza, 0,8850 con — ed è questo che autorizza a credergli.

> **Il modo in cui questo probe è quasi passato senza misurare niente:** la prima versione spegneva l'IDF con `None`, che in `update_collection` significa *«non toccare questo campo»*, non *«azzera»*. Risultato: **zero query discordanti su 200**, e nessun errore da nessuna parte. Due bracci che erano lo stesso braccio. Serve `Modifier.NONE`, e serve rileggere dopo ogni scrittura — che è quello che il probe ora fa.

#### `config_hash`: due misure, due nomi

`_config_hash` non sapeva niente del modificatore, quindi una run `sparse` di oggi si sarebbe chiamata `adb48814` come quella di una settimana fa. Aggiunto `sparse_idf`, **solo** per `sparse` e `hybrid`: ricalcolando tutte le 26 run in `eval/results` con la funzione vecchia e con la nuova, cambiano le 10 sparse/hybrid e **nessuna** delle 16 dense. Due nomi densi sono fissati a letterale nel test, perché orfanare C-06 e la Fase 4 non farebbe fallire nessun altro test.

È l'opposto del caso di `n_queries`, deciso il giorno prima: l'IDF cambia **cosa il sistema calcola**, la numerosità solo con quanta precisione lo osserviamo. Il primo deve spezzare l'identità, la seconda no.

### R-09 — il difetto è reale, l'effetto è nullo, e il perché è aritmetico

**Il difetto.** In BM25 query e documento non sono simmetrici: la query dice **quali** termini contano, il documento dice **quanto** vale ognuno. `Bm25.query_embed` di fastembed lo scrive esplicitamente — *«to emulate BM25 behaviour, we don't need to use weights in the query»*. Noi mandavamo anche le query da `embed()`, la via dei documenti, applicando alla domanda la normalizzazione per lunghezza `b · len / avg_len`: il rapporto fra la lunghezza della **domanda** e la lunghezza media di un **chunk**, due grandezze che non c'entrano niente l'una con l'altra.

Corretti i quattro percorsi query (`retrieve_sparse`, `retrieve_hybrid`, e i due della dashboard). I due percorsi documento restano su `embed()`, che per loro è giusto.

#### Il risultato: niente

| test appaiato | discordanti | p |
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

> **Il +0,0046 di `ledger` è del 13 agosto e oggi vale +0,1257** (OQ-09): il termine di sinistra è sceso a 0,7705, quello di destra non si è mosso di un decimale. La conclusione del paragrafo regge — il guadagno segue il richiamo, non la taglia — ma questa riga è una fotografia datata di un richiamo che nel frattempo è cambiato.

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

> **Lo 0,9892 di `ledger` è del 13 agosto: il 22 vale 0,8356** (OQ-09). Questa colonna misura il richiamo del grafo, ed è esattamente la grandezza che si è mossa — non una proprietà stabile della collection.

#### La conseguenza vera: R-07 confrontava anche gli indici

R-07 e OQ-01 confrontano `ledger` (47k punti) con `ledger_routed` (228k). Con ricerca approssimata quel confronto **non misura solo la pipeline**: misura anche quanto richiamo l'indice perde, e ne perde molto di più su quello denso.

| `doc_R@5`, LEDGER | generic | routed | divario |
|---|---|---|---|
| ricerca approssimata | 0,8915 | 0,6744 | **−21,71** |
| ricerca esatta | 0,8962 | 0,7590 | **−13,72** |

> **La riga «ricerca approssimata» non si riproduce più** (OQ-09): oggi il primo termine è 0,7705. La riga in esatta sì, cifra per cifra. È la ragione per cui da D-4 in poi i numeri di `ledger` si pubblicano in esatta.

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

| Task | Stato | Note |
|---|---|---|
| Q-01 | ✅ fatto (2026-08-13) | `run_config.make_eval_run` è l'unico costruttore. Il difetto vero non era la duplicazione ma ciò che nascondeva: l'harness del retrieval dichiarava `model="retrieval_only"` e `reasoning_enabled=False` **anche con `--query-rewrite`**, cioè quando l'LLM girava davvero — e su disco c'è la run che lo prova. Vedi sotto. |
| Q-02 | ✅ fatto (2026-08-13) | Entrambi gli harness salvano i risultati per query. La prova che serve: `compare_retrieved.py` riproduce **esattamente** i numeri di R-11 (0,9361 → 0,9398, 5 contro 42 discordanti) con uno strumento generico invece di un probe scritto apposta. Vedi sotto. |
| Q-03 | ✅ fatto (2026-08-13) | `scripts/profile.py` → **`profile_docs.py`**. Il difetto era riproducibile in una riga (`import profile` da `scripts/` restituiva il nostro file) e ora `import transformers` da quella cartella funziona. Tolto anche il rimedio locale in `probe_entailment.py`, che curava il sintomo per un file solo lasciando la causa in piedi per gli altri 35. |
| Q-04 | ✅ fatto (2026-08-13) | `ruff check .` **pulito su tutto il repo**. Le 53 segnalazioni erano 3 difetti veri e 50 volte lo stesso: gli script non sono installati, quindi il bootstrap di `sys.path` deve precedere gli import. Soppresso in configurazione — **e dichiarato come soppressione** — con la correzione vera rimandata alla Fase 7. Tolti 101 `# noqa: E402` diventati ridondanti. |
| Q-05 | ✅ fatto (2026-08-13) | `src/providers.py`. Le 3 copie in `src/` e le 2 liste letterali nei probe sono sparite; aggiunti `ROCMExecutionProvider` e `CUDAExecutionProvider` all'ordine di preferenza, **dichiarati e non verificati** (è U-12). Il ripiego su CPU ora **avvisa** invece di degradare in silenzio. Extra opzionali in `pyproject.toml`. Trovato per strada un percorso assoluto cablato in un probe. Vedi sotto. |
| Q-06 | ✅ fatto (2026-08-13) | `src/datasets/registry.py`. Le **14** liste `choices=[...]` scritte a mano sono sparite, e con loro la catena di `if` in `ingest.py` (21 righe → 4) e le due funzioni quasi identiche di `build_golden.py` (→ 1). Nel registro sono finite anche tre cose che erano sparse altrove: `prepare_golden`, `golden_ready_glob`, `build_unanswerable`. Vedi sotto. |

### Il gate, catturato prima di cominciare (2026-08-13)

Un gate che si misura solo alla fine non è un gate: se un numero non torna, non si sa da quando. Quindi il riferimento è stato preso **prima** della prima riga di Fase 6.

**17 dump ricalcolati, 16 combaciano esattamente** (`+0.0000`). Uno no, ed è **preesistente**:

| dump | registrata | ricalcolata | Δ |
|---|---|---|---|
| `20260810_085111_open_ragbench.jsonl` | 0,8854 | 0,8906 | **+0,0052** |

Sono **8 astensioni in entrambi i casi** — non è il rilevatore di astensione. Lo scarto vale esattamente **una risposta su 192**, e la causa è la data: quella run è delle **08:51** del 10 agosto, e il controllo di formato ha ricevuto **cinque commit dopo**, l'ultimo dei quali è C-02. `e438250` in particolare (*«un costrutto che contiene 0 non è un tentativo di citazione»*) è il tipo di correzione che sposta un caso limite.

Non è un difetto: è `rescore_citations.py` che fa il suo mestiere, cioè dire che quel numero fu registrato con uno strumento diverso da quello di oggi. Quella run è comunque superata — i numeri di C-01 in tabella vengono da esecuzioni successive.

> **Quindi il criterio della Fase 6 è: questi stessi valori, non tutti zeri.** 16 a `+0.0000` e quel dump a `+0.0052`. Se a fine fase comparisse un diciassettesimo scostamento, sarebbe il refactor.

### Q-01 — il campo che dichiarava il falso, e il commento che mi ha fermato

**Cinque siti con lo stesso preambolo.** Quattro deducevano `reasoning_enabled` dalla configurazione, il quinto lo scriveva `False` a mano: la forma che prende una duplicazione quando invecchia, con la correzione arrivata ad alcune copie e non a tutte.

**Ma il difetto vero è più profondo della duplicazione.** `make_eval_run` chiede a chi la chiama `llm: str | None`, dove `None` significa *«in questa run non ha girato nessun modello»* — e solo allora ha senso `model="retrieval_only"`, finestra 0, ragionamento spento.

Chiederlo invece di dedurlo dal tipo di harness corregge una dichiarazione falsa: **l'harness del retrieval usa l'LLM quando `--query-rewrite` è attivo** (R-03), e diceva lo stesso di non usarlo. La prova è su disco:

| `20260806_093334_open_ragbench_generic_dense-rewrite.json` | |
|---|---|
| `model` | `retrieval_only` |
| `reasoning_enabled` | `false` |
| cosa era successo | il modello aveva **riscritto ogni query** |

È archiviata e resta com'è. Da ora una run del genere dice il vero.

#### Il commento che ha impedito un cambio di semantica silenzioso

La prima versione della fabbrica calcolava `git_commit()` da sé — comodo, una cosa in meno da passare. Poi ho letto il commento che stava sopra la riga che stavo sostituendo:

> *«captured before the run, not when the EvalRun is built»*

Una run lunga può **finire dopo un commit**, e il valore che serve è quello del codice che ha girato, non quello dell'albero a fine corsa. La mia versione l'avrebbe cambiato senza che nessun test se ne accorgesse. Ora `git_commit` è un parametro, e c'è un test che se ne accorgerebbe.

#### Un test riscritto, perché guardava il posto sbagliato

`test_reasoning_enabled_is_derived_not_asserted` cercava l'espressione della deduzione nel **testo sorgente** di `run_generation_eval`. Spostata la deduzione, il test è fallito **senza che ci fosse alcuna regressione**: segnalava *dove sta il codice*, non *cosa fa*.

Riscritto sul comportamento — cinque valori di `REASONING_EFFORT`, verifica del campo risultante — e ora vale ovunque la deduzione viva.

#### I residui trovati passando di lì

Due difetti che i test di Q-03 e Q-06 non vedevano, trovati a occhio:

- **Q-06**: due script scrivevano la lista dei dataset in una terza forma (`else ["open_ragbench", "ledger"]` in fondo a un `for`), che non era né `choices=` né una ramificazione su `==`. Aggiunto un test più largo, che cerca **la lista** invece delle due forme note — ed è lui che ha trovato il secondo.
- **Q-03**: il rimedio locale che si toglieva `scripts/` da `sys.path` era in **altri sei file**. Q-03 cercava il nome del file, non i posti che lo aggiravano.

> La lezione, per i tre test «guarda il resto del repo» scritti in questa fase: **cercare la *forma* di un difetto ne lascia fuori le varianti.** Meglio cercare la cosa che non deve esistere.

**Gate superato**, output identico al riferimento. Verificata anche una eval vera: `config_hash 5c3c7fa2`, lo stesso di sempre. 1389 test.

### Q-02 — i dump per query, e cosa rendono possibile

**Il difetto ha morso due volte, in due posti diversi.**

Durante E-04/E-05 la diagnosi di tre difetti ha richiesto di **rigenerare a mano le risposte**, perché quelle delle run non esistevano più. E il 2026-08-13, in R-08, il confronto con le run archiviate del retrieval è stato **marginale** — due medie, nessun test — e McNemar è stato possibile solo perché lo stato pre-correzione era riproducibile a comando, togliendo e rimettendo `modifier=IDF`. Una fortuna, non un metodo: la prossima correzione potrebbe non essere reversibile.

**Il meccanismo è quello che C-01 aveva già inventato**, estratto in `src/eval/dump.py` prima di essere copiato una terza volta: append incrementale, suffisso `.partial`, rinomina **solo dopo l'ultimo record**. Le due proprietà che garantisce:

- una run che muore alla query 190 su 200 **non perde le 190**;
- un file troncato **non si confonde con uno finito** — l'esistenza del nome definitivo è la prova che la run è arrivata in fondo. `read_jsonl` rifiuta i `.partial` invece di leggerli in silenzio.

#### La verifica che conta

`scripts/compare_retrieved.py` sulle due run LEDGER (approssimata contro esatta):

| | |
|---|---|
| A, ricerca approssimata | 0,9361 |
| B, ricerca esatta | 0,9398 |
| discordanti | **5 contro 42**, p < 0,0001 |

**Sono esattamente i numeri di R-11**, ottenuti allora con un probe scritto apposta e ora con uno strumento generico che funziona su qualunque coppia di run. Lo script si rifiuta se i due dump non coprono le stesse query, invece di intersecare in silenzio: un test appaiato su una popolazione decisa dalla differenza fra due file non è un test appaiato.

#### Cosa è stato tolto dopo averlo scritto

`doc_ids` era pura derivazione di `chunk_ids` e pesava **circa un megabyte per run** per non dire niente di nuovo; i punteggi sono arrotondati a quattro cifre invece di sei. `query_text` invece resta benché sia nella golden: leggere le query discordanti è la pratica che qui ha ribaltato più di una conclusione — il controllo di R-10, i 67 disaccordi di C-09 — e costringere a un secondo file la rende abbastanza scomoda da non farla.

**Costo su disco, misurato invece che stimato:** 7,1 MB grezzi per una run LEDGER da 10.000 query, **0,80 MB dentro git** (comprime nove volte). Il precedente c'è — le 34 generazioni di C-01 sono committate — e sotto il megabyte a run è il prezzo per rendere confrontabile una run archiviata.

#### Un difetto mio, trovato dai test

Avevo definito la cartella dei dump come costante di modulo derivata da `RESULTS_DIR`. I test sostituiscono `RESULTS_DIR` con una `tmp_path`, ma **una costante calcolata all'import gli sfugge**: sei file veri erano finiti in `eval/results/retrieved/`, scritti dalla suite di test. Ora si deriva al momento della chiamata. E `_shown()` ripiega sul percorso assoluto invece di sollevare — una riga di stampa non deve far fallire una run.

#### E l'altra metà: i baseline

Verificato end-to-end su due run brevi (25 query, prompt permissivo contro severo). Il test appaiato dice **due cose opposte sulla stessa coppia**:

| esito contato | A | B | Δ | discordanti | p |
|---|---|---|---|---|---|
| `correct` | 0,5600 | 0,6000 | +4,0 | 1 contro 2 | **1,0000** |
| `abstained` | 0,0400 | 0,2800 | **+24,0** | 0 contro 6 | **0,0312** |

Guardando i soli totali si direbbe che il prompt severo risponde anche un po' meglio. Il test appaiato dice che quei quattro punti **poggiano su tre query discordanti** e non si distinguono dal caso, mentre la differenza sull'astensione è reale e unanime.

È esattamente la distinzione che i dump esistono per rendere possibile — su 25 query, cioè su uno smoke test, non su una misura.

#### Il 45%→17% è diventato un test appaiato (2026-08-13)

E-04 ed E-05 ri-eseguite su open_ragbench, 100 query per baseline. **I totali riproducono quelli dell'11 agosto a tre decimali** — 0,430/0,120 e 0,410/0,420 — il che è anche una verifica indipendente che la Fase 6 non ha cambiato comportamento.

| esito | A (permissivo) | B (severo) | Δ | discordanti | p |
|---|---|---|---|---|---|
| **`wrong`** — invenzione | 0,4500 | **0,1700** | **−28,0** | **31 contro 3** | **<0,0001** |
| `correct` | 0,4300 | 0,4100 | −2,0 | 9 contro 7 | **0,8036** |
| **`abstained`** | 0,1200 | **0,4200** | **+30,0** | **0 contro 30** | **<0,0001** |

**Il taglio dell'invenzione è reale e quasi unanime**: 31 query in cui solo il prompt permissivo inventa, 3 in cui solo il severo lo fa.

**E non costa correttezza.** Il calo di 2 punti non si distingue dal caso — 9 query contro 7, p=0,80. Prima era un'inferenza dai totali: due percentuali vicine, e nessun modo di sapere se dietro ci fosse churn o stabilità. Ora si sa: c'è churn in entrambe le direzioni, e si annulla.

**Il conto torna esattamente**, ed è la parte che rende leggibile il meccanismo: 30 astensioni in più = 28 invenzioni + 2 risposte corrette. Il prompt severo **converte invenzioni in astensioni**, non risposte corrette in astensioni. L'astensione è unanime (0 contro 30): non c'è una sola query in cui il permissivo si astenga e il severo no.

> È il numero che sostiene l'**affermazione 1 del §0** — i modelli piccoli senza verifica sbagliano in modo sistematico — e ora lo sostiene come test appaiato invece che come confronto fra due medie. È anche ciò che U-04 deve rendere visibile nell'interfaccia.

**24 delle 28 invenzioni diventano esattamente quell'astensione**, e i casi sono la faccia leggibile del numero:

> *«How do changes in effective microbial death rate influence parameters like alpha and beta?»*
> **A**: «The relationship between changes in **effective microbial death rate** and parameters like $\alpha$ (often representing a growth or production rate)…»
> **B**: «I cannot answer without more information.»

Il prompt permissivo non esita: grassetti, LaTeX, e una relazione causale inventata di sana pianta su un contenuto che non ha mai visto. Sono le due risposte affiancate che U-03 deve mostrare, e adesso esistono su disco invece che come aneddoto.

### Q-05 — la cucitura della portabilità, e un probe che funzionava su una macchina sola

**Il blocco era in cinque posti** — `index/embed.py`, `generation/entailment.py`, `retrieval/reranker.py`, più due liste letterali in `probe_entailment.py` — sempre nella stessa forma: *«DirectML se c'è, altrimenti CPU»*.

Non era solo duplicazione. **DirectML esiste solo su Windows**, quindi su Linux quel blocco ripiega sempre su CPU anche con una GPU capace, e finché stava in cinque posti sistemarlo voleva dire cinque modifiche coerenti fra loro. Ora `PREFERRED_ACCELERATORS` nomina anche ROCm e CUDA: **dichiarati, non verificati** — qui si sviluppa su Windows, e provarli davvero è U-12.

> Averli in elenco non li rende testati. Li rende **raggiungibili senza toccare quel file**, che è tutto ciò che una cucitura deve fare.

**Il ripiego adesso si dichiara.** Prima, senza acceleratore, il sistema girava su CPU in silenzio: ~2,4 embed/s contro ~10 (I-07), cioè un'ingestione da 2 ore che ne diventa 8, scoperto a run finita. Ora c'è un `NoAcceleratorWarning` che dice cosa ha trovato, cosa cercava, e quanto costa.

**Tre script forzano CPU di proposito** — tokenizzano soltanto, e caricare un modello su GPU per contare token costa più di quanto renda. Ora lo dicono con `CPU_ONLY` invece che con una lista anonima: è la stessa scelta, ma leggibile come scelta.

#### Il difetto trovato per strada

`scripts/probe_premise_length.py` aveva **due percorsi assoluti cablati** — `os.chdir(r"c:\Users\marco\dev\ibid")` e lo stesso in `sys.path` — residuo di quando era uno script usa-e-getta. Funzionava su **una macchina sola**: per Elia moriva all'import, e nessun test lo copriva perché i probe non ne hanno.

Anche i file che leggeva erano relativi, tenuti in piedi proprio da quel `chdir`. Ancorati a `ROOT`. Verificato lanciandolo **da fuori dal repo**: gira, e riproduce esattamente i numeri di I-11 (79,2% di accettazione nel primo quartile).

**Gate superato**, output identico al riferimento. 1368 test.

### Q-06 — cosa ha cambiato, e il primo passaggio del gate

**Il coupling era tutto ai bordi.** Il nucleo era già agnostico — `Chunk` porta `dataset_id`, il routing va per `doc_genre`, le metriche sono per dataset per contratto (§3.1) — e in tutto `src/` c'erano **16 sole occorrenze letterali** dei due nomi, quasi tutte nei loader, cioè dove devono stare. Il problema era che quattordici script ripetevano a mano la lista di cosa esiste.

**Tre cose sono rientrate da dove erano scappate**: il download del parquet QA di LEDGER (viveva dentro `build_golden.py`), il criterio per sapere se era già stato fatto, e la scelta fra i due costruttori di query senza risposta (viveva dentro un `if` in `build_unanswerable.py`). Sono sapere *sul dataset*, non *sullo script*.

**Due test guardano il resto del repo invece del registro**, ed è il punto: il valore di quel modulo non è che funzioni, è che sia l'unico posto che sa quali dataset esistono. Uno cerca le liste `choices` scritte a mano, l'altro le ramificazioni su `== "open_ragbench"`. Senza, il quindicesimo arriva alla prossima CLI e non se ne accorge nessuno finché non si aggiunge un dataset.

> **`fetch_dataset.py` è stato un commit a parte, e vale la pena dire perché.** Accettava `--dataset`, elencava solo `open_ragbench` fra i `choices`, e poi nominava `open_ragbench` sei volte nel corpo. Non poteva sbagliare — l'unico valore ammesso era anche l'unico implementato — ma l'opzione era decorativa. Collegarlo al registro gli fa **guadagnare** il supporto per ledger, che è un cambiamento di comportamento e non entra nel commit di un refactor. Verificato: `--dataset ledger` riporta 494 documenti e 47.110 chunk, cioè esattamente i punti della collection su Qdrant.

**Gate superato.** `rescore_citations.py` restituisce un output **identico al riferimento riga per riga**, confronto automatico compreso. È il primo dei sei task a metterlo alla prova.

---

## Fase 7 — Servizio e API

Il backend diventa sostituibile dal frontend e viceversa, e può girare su un'altra macchina. **Gate: nessuna metrica cambia, e la CLI continua a funzionare identica.**

| Task | Stato | Note |
|---|---|---|
| A-01 | ✅ fatto (2026-08-14) | `src/service/` — tre casi d'uso, tre funzioni: `answer()`, `datasets()`, `chunk()`. `scripts/query.py` è passato da *essere* la pipeline a stamparla. Un test verifica il confine invece di affermarlo. **1438 test** (1401 → 1438). |
| A-02 | ✅ fatto (2026-08-14) | La configurazione di richiesta esce da `cfg` globale: `RequestConfig`, immutabile, uno per richiesta. Il criterio — due richieste concorrenti che non si contaminano — è un test con due thread e una barriera. **1475 test**. |
| A-03 | ✅ fatto (2026-08-14) | Il contratto UI ↔ API del §3.5 esiste come tipi (`src/api/schema.py`) e come sequenza di eventi (`answer_stream`). Streaming vero, non finto. La decisione lasciata aperta nel ROADMAP è stata presa e scritta lì. **1556 test**. |
| A-04 | ✅ fatto (2026-08-14) | `/health`, `/datasets`, `/chunk/{chunk_id}`, `/query`, `/query/stream`, `/config`. Il confronto CLI ↔ API che ad A-01 aveva un braccio solo ora li ha entrambi. Query completa da `curl` verificata contro Qdrant e Ollama vivi. **1585 test**. |
| A-05 | ✅ fatto (2026-08-14) | Backend in `docker compose`, `QDRANT_URL` e `LLM_BASE_URL` da ambiente. Immagine costruita e provata contro Qdrant e Ollama sull'host: stessa risposta e stesso verdetto della corsa fuori container. **1607 test**. |
| A-06 | ✅ fatto (2026-08-14) | La dashboard smette di essere un secondo backend: le due copie della pipeline sparite, tutto passa da `dashboard/api_client.py`. Ha prodotto `POST /retrieve`, che dall'API mancava. **1620 test**. |
| A-07 | ✅ fatto (2026-08-14) | **I tre buchi trovati disegnando la Fase 8**: `models` in `Capabilities`, `reasoning_effort` in `QueryRequest`, `GET /documents` e `GET /document/{doc_id}/chunks`. Tutti e tre **additivi**, e un test manda la richiesta minima `{"query": "..."}` per provarlo. Con loro un indice payload su `doc_id`: contare i chunk per documento passa da 2,07 s a 0,025 s. **1659 test**, `ruff check .` pulito, CLI verificata eseguendo la stessa query su `main` e sul branch. Dettaglio sotto. |
| A-08 | ✅ fatto (2026-08-19) | **Il catalogo dei modelli**: `Capabilities` porta famiglia, finestra massima e quantizzazione di ciascuno. La finestra si legge **per pattern** (`*.context_length`), quindi vale per qualunque famiglia — e il massimo non è uno solo: 131.072 per `gemma4:latest`, 262.144 per `gemma4:12b`. **12 test** in più (1690 in tutto). Additivo: `models` invariato. Dettaglio sotto. |

### A-01 — cosa c'era davvero dentro il CLI

Dalla T-05 `scripts/query.py` non era un client: **era** il percorso di servizio. Recupero, gate di astensione, generazione, riparazione dei marcatori e `print` nello stesso file, nella stessa funzione. Finché il consumatore era uno solo, nessuno se ne accorgeva.

Il criterio di A-01 dice *«nessun endpoint contiene logica di pipeline»*, e da solo non basta: se la contiene l'altro consumatore, non c'è niente da confrontare. Quindi la verifica è scritta come test — `scripts/query.py` non importa più `src.index`, `src.retrieval`, `src.generation` — e non come promessa.

**Quattro cose che il risultato deve saper dire, e prima non poteva:**

| stato | perché non era rappresentabile |
|---|---|
| astensione **del gate** vs **del modello** | erano lo stesso booleano, e sono due eventi diversi: uno costa 0 s di GPU, l'altro 11 |
| testo **grezzo** e testo **riparato** | il parser di C-02 cambia ciò che il modello ha scritto; tenerne uno solo perde o la prova o la leggibilità |
| **troncamento** | una risposta tagliata non ha citazioni perché non è arrivata a scriverle — non è un difetto di formato |
| **verdetti non ancora disponibili** | con lo streaming è la norma: il marcatore `[2]` compare prima che il suo verdetto esista (§3.5) |

**La verifica NLI entra nel percorso di servizio.** Girava solo dentro l'harness di C-03: il sistema che si mostra a qualcuno produceva marcatori non verificati, cioè proprio la cosa che l'affermazione 1 del §0 dice di saper misurare. Ora ogni citazione porta il proprio verdetto, e **nessuna viene filtrata** — U-07 chiede che le non verificate siano marcate, non nascoste, e toglierle porterebbe la precisione apparente al 100% per costruzione. Accanto ai verdetti c'è l'elenco delle frasi che non citano niente: è il denominatore nascosto, perché la precisione si alza citando di meno.

**`chunk()` non prende il dataset.** Lo schema del §3 impone `{dataset_id}:{doc_id}:{seq}`, quindi è già dentro l'id — ed è il motivo per cui l'endpoint del ROADMAP si chiama `/chunk/{chunk_id}` e non `/chunk/{dataset}/{chunk_id}`. Chiederlo a parte permetterebbe di passarne uno incoerente con l'id. Un test lega le due convenzioni: se un `chunk_id` smettesse di iniziare col dataset, `dataset_of()` mentirebbe in silenzio.

**`datasets()` legge il registro di Q-06**, e chiede a Qdrant se quegli indici esistono. Senza, il frontend porterebbe la quindicesima copia di quel `choices=[...]`. Tre stati e non due: assente, presente e vuota, presente con N chunk — la collection vuota esiste davvero fra `ensure_collection` e la fine dell'ingestione.

#### Una funzione privata con cinque chiamanti

`_payload_to_chunk` esisteva in due copie identiche e **tre script la importavano attraverso l'underscore**. È la stessa storia di `_RETRIEVERS` prima di R-05: con cinque chiamanti non era privata, era scritta nel posto sbagliato. Ora è `chunk_from_payload` in `src/index/store.py`, accanto alla `upsert` che quel payload lo scrive — le due devono cambiare insieme, o un campo aggiunto sopra sparisce in silenzio al ritorno.

Il test che l'ha trovata non cercava lei: cercava la separazione fra calibrazione e valutazione del gate di astensione, e si è rotto all'import.

#### Due cambi di comportamento, dichiarati

- **Il servizio passa `cfg.REASONING_EFFORT` alla generazione.** Il CLI lo ignorava da prima che quel parametro esistesse: col default `none` non cambia niente, con qualunque altro valore ora obbedisce alla configurazione invece di contraddirla.
- **`--dataset` accetta i dataset del registro**, non più una stringa qualsiasi. La collection arbitraria non si perde — è `--collection`, che era il vero uso di quella libertà (`ledger_routed`).

**Nessuna metrica si muove**: niente di `eval/` passa da qui.

> **Cosa A-01 non ha fatto, e va detto.** Il criterio parla di *«la stessa richiesta dalla CLI e dall'API»*: l'endpoint `/query` non esiste ancora (è A-04), quindi il confronto ha per ora un braccio solo. Il test che li confronta va scritto lì, sulla stessa funzione — non su una seconda pipeline. Restano fuori anche i parametri di retrieval per richiesta (rerank, riscrittura, filtri): sono A-02, che è il posto dove la configurazione smette di passare da `cfg` globale.

### A-02 — quattro categorie, non una

Il task sembra «sposta i parametri dentro un oggetto». Il lavoro vero è stato **decidere quali**, e la risposta è che le costanti di `config.py` non sono la stessa cosa:

| categoria | esempi | può variare per richiesta? |
| **per richiesta** | `top_k`, modalità, reranker, modello, temperatura, tetto di token | sì — è `RequestConfig` |
| **legata all'indice** | `EMBEDDING_MODEL`, `SPARSE_EMBEDDING_MODEL` | **no**: l'indice è stato costruito con lei |
| **di deployment** | `QDRANT_URL`, `LLM_BASE_URL`, `FASTEMBED_CACHE` | **no**: una richiesta non sposta la macchina |
| **calibrata sui dati** | soglie di astensione, entailment, verifica numerica | **no**: sono derivate da misure |

Le ultime tre restano costanti di modulo, e non è che siano rimaste indietro. Il modello di embedding nella richiesta renderebbe **esprimibile una richiesta sbagliata**: interrogare l'indice con un embedder diverso da quello che l'ha costruito restituisce spazzatura *senza errore*. E una soglia scelta da chi chiama permetterebbe di tararla sulla stessa risposta che deve giudicare — la trappola che i commenti di `config.py` passano il tempo a evitare. Una classe di test protegge queste assenze: le presenze si notano quando mancano, un campo aggiunto per comodità no.

**`frozen=True` è la garanzia, non lo stile.** Ciò che nessuno può modificare non può essere modificato *da un'altra richiesta*. E nessun campo ha un default sulla classe: `from_defaults()` resta l'unico posto in tutto il repo che legge quelle costanti, verificato da un test — un default sul campo sarebbe una seconda sorgente di verità, e la prima cosa che farebbe è divergere.

#### Il difetto che nessun test sequenziale trova

Prima, due richieste concorrenti con `top_k` diverso leggevano la stessa costante di modulo. Non si riproduce da soli, non compare in nessuna suite sequenziale: **compare sotto carico**, che è il momento peggiore per scoprirlo.

Il test lo forza invece di aspettarlo: due thread, una barriera che li tiene entrambi dentro il retrieval nello stesso istante, `top_k` 2 contro 5. Poi verifica tre cose diverse — che ogni risposta abbia la propria profondità, che il *retriever* abbia ricevuto la propria configurazione, e che il risultato riporti quella che ha davvero girato.

#### Il percorso si è allungato, quindi i test lo seguono tutto

`search_params()` leggeva `cfg` da sola. Ora i due valori di R-11 arrivano da fuori, e la catena è **config → backend → store → Qdrant**. Una dimenticanza in mezzo non darebbe nessun errore: darebbe una ricerca approssimata dove ne era stata chiesta una esatta — cioè il guasto silenzioso che R-11 esiste per rendere controllabile. Cinque test coprono la catena intera, `hybrid` compreso, dove i rami di ricerca sono due e uno solo sbagliato produrrebbe una fusione fra due ricerche diverse.

#### Cosa il servizio ha guadagnato

Reranker, riscrittura della query e filtro sui metadati ora funzionano **dal percorso di servizio**, non solo dall'harness: erano flag che solo la valutazione sapeva usare. Il gate di astensione legge i punteggi **dopo** il reranker — che è anche il motivo per cui la soglia è calibrata per modalità, e `threshold_for` restituisce `None` fuori da quella calibrata invece di applicare una soglia che non significa niente.

#### Gli harness continuano a leggere `cfg`, ed è corretto

`_config_hash` e `build_config` leggono ancora le costanti di modulo. Non è un residuo: un harness ha **una** configurazione per tutta la sua vita, quindi non c'è una seconda richiesta da cui distinguersi. La regola nasce dalla concorrenza, non dall'estetica — e il test che la fa rispettare elenca i moduli del percorso di servizio, non tutto `src/`.

#### Il gate, e come è stato verificato

Scritto **prima** della prima riga: sette run archiviate vengono rilette da disco, i loro argomenti ricostruiti dalla configurazione che ciascuna dichiara di aver usato, e l'hash ricalcolato. Un `config_hash` è **il nome di una misura**: un refactor che lo cambia rinomina tutto l'archivio in silenzio, perché nessun numero si muove — cambia solo il nome sotto cui è registrato. Le ancore coprono le tre modalità, il reranker e la collection diversa dal dataset; `query_rewrite` e `filter_content_type` non hanno una run su disco, e un test lo dichiara invece di lasciarli sembrare coperti.

Poi la verifica per misura, stesso comando sui due rami:

| | dense R@5 | dense doc_R@5 | hybrid R@5 | hybrid doc_R@5 |
|---|---|---|---|---|
| `main` (prima) | 0,8000 | 0,9600 | 0,8800 | 0,9800 |
| `A-02` (dopo) | 0,8000 | 0,9600 | 0,8800 | 0,9800 |

**Identici su tutte e sette le metriche**, in entrambe le modalità, 50 query su open_ragbench.

#### Uno spostamento puro, per far tornare il verso

`src/eval/retrieval_backends.py` → `src/retrieval/backends.py`. La collocazione descriveva il primo chiamante, non la funzione: una richiesta HTTP che per recuperare dei chunk deve importare il pacchetto di valutazione ha le dipendenze rovesciate. 21 file aggiornati, **stesso numero di test prima e dopo** — che è il controllo che sia stato davvero solo uno spostamento.

> Resta lo stesso problema per `verify_answer`, che vive in `src/eval/citation_metrics.py` ed è funzionalità, non misura. E `dashboard/failure_store.py` ha una **copia** della logica di retrieval invece di usare i backend: è il consumatore che A-06 farà passare dall'API, ed è lì che quella copia deve sparire.

### A-03 — il criterio è «rappresentabile», e non voleva dire «c'è un campo»

Il criterio del task è che ogni stato dell'interfaccia previsto in Fase 8 sia rappresentabile. Preso alla lettera significa una cosa più forte di quanto sembri: **chi consuma deve poterlo distinguere dagli altri senza indovinare.** Un campo che copre tre situazioni non le rappresenta, le nasconde.

Due stati sono stati aggiunti proprio per questo, ed erano entrambi facili da credere deducibili:

| stato | perché non si deduceva |
|---|---|
| «attendo i verdetti» | `citations == []` copre **tre** casi: verifica non chiesta, verifica fatta senza citazioni, verdetti in arrivo. Con lo streaming il terzo è la norma |
| «chi si è astenuto» | il gate costa 0 s di GPU, il modello ~11: un booleano li sommava |

Indovinare sbagliato sul primo significa o un caricamento eterno, o **dichiarare verificata una citazione che nessuno ha guardato**.

#### La decisione che il ROADMAP lasciava aperta

§3.5 diceva: *«La UI deve sapere che il testo verrà sostituito, o lo stream deve essere ritardato fino al parser — perdendo lo streaming. Va scelto, e la scelta va scritta qui.»*

Scelto: **si streamma il grezzo, `answer` lo sostituisce.** Ritardare fino al parser costa lo streaming per intero — la prima parola arriverebbe *dopo* l'ultima, cioè dopo gli ~11 s che U-10 dice esplicitamente di non nascondere con tagli di montaggio.

Ne discende una regola vincolante per la Fase 8, ora scritta nel ROADMAP: **finché `answer` non arriva, i marcatori che scorrono non sono cliccabili.** Renderli attivi prima significherebbe offrire un link a un `[2]` che il parser potrebbe scartare.

#### Lo streaming non poteva essere finto

`chat.py` chiamava sempre con `stream: false`. Con quella sola strada, l'unico streaming possibile era aspettare la risposta intera e poi spezzettarla: **identico dal lato del browser, e falso**.

`generate_stream()` legge il flusso `data: {...}` del contratto OpenAI-compatibile. Due dettagli che valeva la pena scrivere una volta sola: il conteggio dei token arriva **solo** chiedendolo con `stream_options.include_usage`, in un ultimo pacchetto senza `choices`; e il primo pacchetto di molti backend porta solo il ruolo, che emesso come token darebbe alla UI un aggiornamento vuoto.

Verificato contro l'Ollama vivo: **66 delta, il primo a 2,69 s e l'ultimo a 3,37 s.** Se fosse bufferizzato arriverebbero tutti insieme alla fine.

> Il test che conta non è sullo streaming: è l'**equivalenza**. La somma dei pezzi dev'essere la stessa `Completion` della strada non-streaming. È l'unico modo per accorgersi che lo streaming perde qualcosa — un difetto che dal browser si vede come una frase che comincia a metà.

#### Una pipeline sola, di nuovo

Qui il difetto che A-01 aveva tolto stava per rientrare dalla finestra: una funzione che risponde tutta insieme e una che risponde a pezzi sarebbero state **due volte la stessa sequenza**.

Quindi `answer_stream()` è il primitivo e `answer()` è una vista su di esso: `DoneEvent` porta la risposta intera, e la strada non-streaming passa un generatore di un pezzo solo. La prova è che i **42 test di servizio esistenti sono passati invariati** dopo la ristrutturazione — e due test nuovi confrontano le due strade campo per campo, e verificano che i token ricomposti siano esattamente il testo grezzo. Se divergessero, la verifica girerebbe su una risposta diversa da quella che l'utente ha letto.

#### Il braccio nudo esce dalla valutazione

U-03 chiede la stessa query affiancata con e senza RAG. Il braccio nudo esisteva solo dentro l'harness dei baseline. Ora è `rag=False` sulla stessa funzione — **un parametro e non un secondo percorso**, perché con due percorsi ci sarebbero due modi di astenersi, due modi di contare i token e due modi di sbagliare.

Provato da riga di comando sulla stessa query citata nel commit di E-04/E-05:

> **permissivo**: tabelle, LaTeX e una relazione causale inventata di sana pianta
> **severo**: «I cannot answer without more information.»

Senza contesto il parser non tocca il testo (nessun marcatore è valido, li toglierebbe tutti), il gate risulta **inattivo** e non «superato», e ogni affermazione compare nella lista di quelle senza fonte — che è il confronto, non un dettaglio.

#### Due cose che al contratto mancavano

**`ErrorEvent`.** Quando lo stream è cominciato gli header sono già partiti e un 500 non è più spedibile: un errore a metà risposta può solo essere un altro evento. Nasce nello schema e non nel servizio, che continua a sollevare — così un CLI vede la traccia di stack e un browser uno stato disegnabile, senza che nessuno dei due debba fingere. Porta anche lo `stage`, perché la UI possa dire «le fonti ci sono, la risposta no».

**`Capabilities`.** Le modalità di retrieval e i prompt del baseline si leggono dal backend. Senza, il frontend porterebbe la quindicesima copia scritta a mano di quel `choices=[...]` che Q-06 ha appena tolto di mezzo.

#### Il confine, difeso all'orlo HTTP

`QueryRequest` accetta **solo** la configurazione di richiesta della classificazione di A-02. Niente `embedding_model` (l'indice è stato costruito con lui: un altro restituisce spazzatura *senza errore*), niente indirizzi, niente soglie calibrate. Tre test lo tengono chiuso, uno per ragione — perché sono tre ragioni diverse, non una regola sola.

> Perché due insiemi di tipi accanto a quelli del servizio: sono due cose diverse che oggi si somigliano. Quelli del servizio sono la forma in cui la pipeline pensa; questi sono la forma che qualcun altro leggerà fra sei mesi con un client che non abbiamo scritto noi. Se fossero lo stesso oggetto, rinominare un campo interno cambierebbe il contratto pubblico senza che nessuno debba deciderlo.

### A-04 — l'endpoint che non decide niente

Il criterio di A-01 era *«nessun endpoint contiene logica di pipeline»*. Qui si vede se reggeva: gli endpoint sono cinque righe l'uno, perché la pipeline sta in `src/service/` e la forma in `src/api/schema.py`. Un test lo verifica invece di affermarlo — `src/api/main.py` non importa `src.index`, `src.retrieval`, `src.generation`, `src.eval`.

E i test degli endpoint **non hanno bisogno di Qdrant**. Se ne avessero bisogno, direbbero che l'endpoint contiene ancora della pipeline.

#### Il confronto che aspettava dal 14 agosto mattina

A-01 chiedeva *«la stessa richiesta dalla CLI e dall'API produce lo stesso risultato»*, e l'endpoint non esisteva ancora: quel confronto aveva un braccio solo.

Ora ne ha due, e confronta **l'oggetto giusto**. Confrontare le due *risposte* non basterebbe: coinciderebbero anche se le due strade costruissero richieste diverse che per caso danno lo stesso esito. Ciò che va confrontato è la `AnswerRequest` che arriva al caso d'uso — ed è lo stesso tipo da entrambe le parti, perché la pipeline è una sola.

Quattro confronti: richiesta minima, parametri di retrieval, braccio nudo di U-03, parametri di ricerca di R-11. Perché fosse possibile, `scripts/query.py` ha dovuto esporre `build_parser()` e `request_from_args()` — estrarli è ciò che rende il criterio **verificabile** invece che affermato.

#### Quattro decisioni piccole con una ragione ciascuna

**`/health` non interroga Qdrant.** U-09 lo usa per `depends_on: service_healthy`; se rispondesse solo con l'indice acceso, un avvio in cui Qdrant parte dopo si bloccherebbe a vicenda. La domanda «i dati ci sono?» ha già una risposta migliore in `/datasets`, dove `ready` la dà **per dataset**.

**`/chunk/{chunk_id:path}`.** Un `chunk_id` *contiene* i due punti per contratto (`{dataset_id}:{doc_id}:{seq}`); senza `:path` il routing lo taglierebbe al primo. È lo stesso motivo per cui l'endpoint non prende il dataset come secondo parametro: è già lì dentro.

**Tre codici distinti dove sarebbe stato comodo uno.** `404` per un id che non c'è — un link vecchio dopo una re-ingestione è una domanda legittima con una risposta legittima. `400` per un id malformato, e dirlo costa **zero interrogazioni all'indice**. `500` resta il guasto.

**Un valore inesistente è `422`, non `500`.** `RequestConfig` lo rifiutava già da A-03, ma sollevando *dentro* il servizio. Un client che manda `retrieval_mode: "magica"` ha sbagliato lui, e un 500 lo manderebbe a cercare nel posto sbagliato. Gli elenchi restano una tupla sola in `config.py`: cambia solo dove il rifiuto diventa leggibile.

```
{"detail":[{"loc":["body","retrieval_mode"],
            "msg":"retrieval_mode sconosciuto: 'magica' (ammessi: dense, sparse, hybrid)"}]}
```

#### Sullo stream, due cose che si vedono solo in produzione

**Un guasto a metà non butta via ciò che era arrivato.** Un test manda `chunks` e poi solleva: il client riceve `chunks`, poi `error`, e può dire «le fonti ci sono, la risposta no» invece di mostrare una pagina vuota.

**`X-Accel-Buffering: no`.** Un proxy che bufferizza annulla lo streaming **senza rompere niente**: il client riceve tutto insieme alla fine e non ha modo di accorgersi che sarebbe dovuto arrivare a pezzi. È la stessa forma di guasto silenzioso dello streaming finto di A-03, un livello più in là.

#### Il criterio, con `curl`

Contro Qdrant e Ollama vivi, senza frontend:

| | |
|---|---|
| `POST /query` | `The standard deviation of RMSE for Ridge Regression is 0.0226 [1].` — citazione verificata, `p=0,606` |
| `POST /query/stream` | 19 eventi `token`, poi `answer` con `verification_pending: true`, poi `citations`, poi `done` |
| `GET /chunk/...` | `open_ragbench:2412.20245v4:15`, con `doc_genre`, `pipeline`, `bbox: null` dichiarato |
| `rag: false` | `I cannot answer without more information.` — 0 chunk, `gate.active: false` |

> **0,0226 è lo stesso valore del gate della T-05**, per la stessa domanda. Il 4 agosto era la prova che la fetta verticale stava in piedi; oggi arriva su HTTP con la sua citazione verificata a fianco.

`fastapi` e `uvicorn` erano dichiarati in `pyproject.toml` ma non installati in questo Python: installati.

### A-05 — il container *è* la seconda macchina

Il criterio è *«backend su una macchina, Qdrant e LLM su un'altra, **senza modifiche al sorgente**»*. Non si verifica con due macchine: si verifica mostrando che nel sorgente **non c'è niente da modificare**.

E poi si prova. Dal punto di vista del container, l'host è già un altro host — altra interfaccia di rete, altro `localhost`. Backend nel container, Qdrant e Ollama sull'host, stessa domanda della T-05:

```
The standard deviation of RMSE for Ridge Regression is 0.0226 [1].
citazione [1] supportata, p=0,606
```

Identica alla corsa fuori container, verdetto compreso. Per servizi davvero altrove basta l'ambiente, e nessun file cambia:

```
QDRANT_URL=http://10.0.0.5:6333 LLM_BASE_URL=http://10.0.0.7:11434/v1 make api
```

#### Quattro difetti che non si vedevano perché l'immagine non era mai stata costruita

| | |
|---|---|
| `env_file: - .env` | il file non esiste: **`docker compose up` falliva** |
| nessun `.dockerignore` | ogni build spediva **2,3 GB** al demone, quasi tutti `data/` — e nessuno di quei byte serve a un backend che legge da Qdrant |
| `qdrant:latest` | due macchine potevano avere due Qdrant diversi, e un indice è un formato su disco |
| nessun healthcheck su Qdrant | `depends_on: service_healthy` non aveva niente da aspettare |

L'healthcheck di Qdrant merita una nota: usa il **suo stesso binario**, perché quell'immagine non ha né `curl` né `wget`. Un healthcheck che non può girare lascia il servizio `starting` per sempre, e la dipendenza non parte mai — un guasto che si manifesta come «l'avvio si è bloccato», senza errori.

Gli indirizzi ora sono `${VAR:-default}`: i default coprono il caso comune senza impedire l'altro. È la differenza fra un file che *funziona qui* e uno che dichiara **dove** può funzionare.

#### I pesi dei modelli vanno su un volume, e non è ottimizzazione

Sono ~2,5 GB fra embedding, reranker e verificatore NLI. Le tre strade possibili non sono equivalenti:

- **nell'immagine**: 2,5 GB di layer da ricostruire a ogni cambio di codice;
- **senza niente**: 2,5 GB di download a **ogni avvio**, prima della prima risposta;
- **volume**: si pagano una volta.

E il percorso è dichiarato (`FASTEMBED_CACHE_PATH`, `HF_HOME`). Il default di fastembed è `%TEMP%`, che Windows ha già svuotato *durante* I-10 uccidendo una valutazione dopo 80 minuti di GPU. In un container il default è peggio ancora: sparisce a ogni riavvio.

#### Il costo del container, misurato — e la prima misura era sbagliata

Nel container non c'è GPU: embedding, reranker e verificatore girano su CPU. La prima versione di questa sezione riportava così il costo:

| stadio | fuori | dentro |
| retrieval | 2,5 s | 14,4 s |
| verifica | 5,2 s | 21,8 s |

**Erano tempi di prima query, cioè caricamento dei modelli riportato come costo per richiesta.** Il difetto è lo stesso di sempre in questo progetto — una misura presa una volta e generalizzata — ed è comparso in un posto dove il rimedio è ovvio: chiedere tre volte invece di una.

Ripetuto, tre query di fila per arma, la stessa domanda:

| stadio | host (DirectML) | container (CPU) | prima query, container |
|---|---|---|---|
| retrieval | 0,020 s | 0,072 s | 11,0 s |
| verifica | 0,095 s | 0,825 s | 17,1 s |
| **totale** | **~3,0 s** | **~1,7 s** | 37,8 s |

Il totale del container è **più basso** di quello dell'host, il che chiude la questione da solo: la differenza fra GPU e CPU su *una* query è ~0,7 s di verifica e ~0,05 s di recupero. Un embedding e tre coppie NLI non saturano niente — la GPU serve quando il lavoro è in blocco (66k chunk da indicizzare, 3045 query da valutare), non quando è una domanda.

> La generazione misura 2,85 s dall'host e 0,77 s dal container, contro **la stessa Ollama sulla stessa GPU**. Stabile su tre ripetizioni in entrambi i casi, quindi non è rumore. **Non è spiegato**, e non è attribuibile al container: è segnato qui perché un numero stabile che non si sa spiegare è una domanda aperta, non un dettaglio.

Il `NoAcceleratorWarning` di Q-05 è comparso nei log del container esattamente come doveva, dichiarando il ripiego invece di degradare in silenzio. È la prima volta che quel warning serve a qualcuno che non lo stava cercando.

> **Ne segue la regola, e con i numeri veri è più netta: le run di valutazione non si lanciano dal container** — lì il fattore 3–10× su ogni embedding si moltiplica per migliaia di query. **Il servizio sì**, e senza riserve.

#### Perché la GPU nel container non è una configurazione che manca

Verificato, non ricordato, il 2026-08-14:

- **`onnxruntime-directml` non ha wheel Linux.** `pip download --platform manylinux_2_28_x86_64` risponde *«No matching distribution found»*: DirectML è un'API Windows, e il container è Linux.
- **Il container non vede nessun dispositivo GPU**: niente `/dev/dxg`, `/dev/kfd`, `/dev/dri`. Docker Desktop su Windows non li espone per schede non-NVIDIA.
- **ROCm non è una via d'uscita su questa macchina**: la RX 6750 XT è gfx1031, fuori dal supporto ufficiale, e comunque servirebbe `/dev/kfd`.

Due ragioni indipendenti, ciascuna sufficiente. La strada esiste ma è **un'altra macchina**: Linux nativo con NVIDIA (`--gpus all` + `onnxruntime-gpu`) o con una AMD supportata da ROCm. È lo stesso confine di U-12, e l'immagine è predisposta — vedi `GPU_EXTRA` nel `Dockerfile`.

L'acceleratore ONNX resta fuori dall'immagine di proposito: gli extra si escludono a vicenda e dipendono dalla piattaforma (Q-05), e un'immagine che ne cablasse uno girerebbe su **una macchina sola** — cioè il contrario del criterio di questo task.

#### I test guardano i file, non le funzioni

Ventidue, nella forma di Q-06 e A-02: nessun indirizzo cablato in `src/`, gli indirizzi interpolati in `compose.yml`, `data/` ed `eval/` fuori dal contesto di build, il processo non root, Qdrant pinnato.

E uno che protegge una scelta di A-02: **`.env.example` non contiene configurazione di richiesta**. Metterci `TOP_K` o `TEMPERATURE` la renderebbe di nuovo globale, condivisa fra richieste concorrenti — esattamente il difetto appena tolto.

#### Cosa resta dichiarato

**Nessun `uv.lock`.** Due build a distanza di mesi possono risolvere versioni diverse. Per un servizio che si vuole riproducibile il lock è il passo giusto, ed è un task suo.

**L'immagine porta più dipendenze del necessario** — `streamlit`, `datasets`, `pandas` sono in `[project.dependencies]` e servono agli harness, non all'API. Separarle in extra è possibile e non è A-05.

### A-06 — il consumatore esigente ha chiesto una cosa che non c'era

Il ROADMAP diceva perché questo task esiste: *«è il consumatore più esigente che esista già. Se l'API le basta, basterà anche al frontend — e se non le basta, si scopre ora invece che a React scritto.»*

**Non le bastava.** Dall'API mancava la metà che non genera: l'unico modo di vedere dei chunk era `/query`, cioè pagare una generazione. Per un batch del Failure Explorer sarebbero **200 generazioni per un dato che esiste prima di ognuna**.

Da qui `POST /retrieve`, che accetta molte query in una chiamata perché l'embedding è batch per natura: 200 query in un viaggio sono una passata di GPU, 200 viaggi sono 200 passate. È la differenza fra una pagina usabile e una che non lo è — ed è l'unico endpoint di tutta la Fase 7 che non è stato progettato a tavolino ma **chiesto da un consumatore**.

#### Non era un client: era un secondo sistema

La dashboard apriva il proprio client Qdrant, embeddava le query, fondeva con RRF, chiamava il cross-encoder. Due copie della pipeline — `retrieval_probe.py` e `failure_store.py` — accanto a quella del servizio.

E **le copie erano già divergenti**: dopo A-02 la configurazione di richiesta ha smesso di stare in `cfg`, e queste continuavano a leggerla da lì. Il commento in cima a `retrieval_probe.py` diceva che i parametri venivano da `src.config` *«così che quello che vedi qui sia quello che l'eval ha misurato»* — la buona intenzione era scritta, e aveva smesso di essere vera.

Nessun test poteva accorgersene: ognuno verificava la propria copia contro sé stessa.

```
probe(client, query, config)            →  probe(query, config)
evaluate_queries(client, queries, ...)  →  evaluate_queries(queries, ...)
```

> Il `client` che sparisce dalla firma **è il criterio in una riga**: chi interroga Qdrant è il servizio.

#### Il criterio del ROADMAP era un proxy, e si è visto eseguendolo

Era `grep -r "^from src\." dashboard/`. Comodo da controllare, e sbagliato in due direzioni:

| | |
|---|---|
| **troppo largo** | catturava la lettura di `eval/results/` e `eval/golden/` — file sul disco della dashboard, che non stanno dietro nessun endpoint. Soddisfarlo avrebbe richiesto o di ricopiare lo schema di `EvalRun`, o di far servire all'API l'archivio degli esperimenti — e la lista di ciò che la Fase 7 espone è dichiarata **vincolante** |
| **troppo stretto** | `^from src\.` non vede un import annidato dentro una funzione, che è esattamente dove `state.py` teneva il proprio client Qdrant |

Il criterio nuovo dice la cosa che il vecchio approssimava: **la dashboard non deve *eseguire* la pipeline.** I cinque import rimasti hanno la ragione scritta accanto, in un test che fallisce se ne compare un sesto senza che qualcuno l'abbia deciso:

```python
AMMESSI = {
    "src.datasets.schema": "contratto dati del §3, per leggere eval/results/",
    "src.ingestion.ocr_tables": "interpretare markup OCR è un formato, non la pipeline",
    ...
}
```

> È lo stesso movimento di I-07, dove il criterio «< 20 minuti» descriveva un modello che non era quello adottato e fu riscritto con i numeri veri. Un criterio che non sopravvive all'esecuzione va corretto, non aggirato.

#### Il sesto chiamante attraverso l'underscore

`_split_segments` viveva in `pipeline_table_heavy.py`. La importavano in **sei**, di cui quattro fuori dall'ingestione: il verificatore di entailment di C-03, quello numerico di C-09, un probe e la dashboard.

È il caso peggiore della serie iniziata con `_RETRIEVERS` e proseguita con `_payload_to_chunk`: **il verificatore delle citazioni dipendeva da una pipeline di ingestione per leggere una premessa.** Ora è `split_segments` in `ocr_tables.py`, accanto al parser — un modulo che era già stato spostato una volta per la stessa ragione, e che porta scritto in cima *«serve a due cose che non si parlano»*.

Spostamento puro: 1544 test non-dashboard invariati.

#### La vista che era una console di un altro servizio

Collection Stats leggeva la configurazione interna di Qdrant: dimensioni dei vettori, distanze, nomi degli indici sparsi. Era l'amministrazione di un altro servizio — che Qdrant la sua console ce l'ha già, su `:6333/dashboard`.

Ora `/datasets` riporta anche le collection del server con **tre fatti che riguardano questo sistema**: punti, dimensione densa, presenza dell'indice sparso. Non è statistica per curiosità:

- una `dense_size` diversa fra due collection significa che sono state costruite da modelli di embedding diversi, e **non sono confrontabili** — la vista ora lo dice invece di lasciarlo dedurre;
- `has_sparse: false` distingue una collection su cui `hybrid` funziona da una su cui userebbe solo il ramo denso.

#### I test si sono accorciati, ed è la cosa giusta da notare

Verificavano che il probe usasse il vettore denso per `dense`, pescasse più a fondo col reranker, fondesse con RRF in `hybrid`. Cioè verificavano **una copia della pipeline contro sé stessa**.

Quella copia non c'è più, e con lei quei test: il comportamento vive in `test_service_answer.py` e `test_index_search_params.py`, dove c'è un'implementazione sola da verificare invece di due che devono ricordarsi di essere d'accordo.

Quel che resta è ciò che la dashboard fa davvero — chiedere la cosa giusta, e trasformare la risposta nella forma che le viste disegnano — più sette test nuovi sul confine.

#### Provato contro l'API viva

| | |
|---|---|
| `capabilities()` | 2 dataset, 7 collection con punti e dimensioni |
| `probe()` | `open_ragbench:2412.20245v4:15` in testa, score 0,840 |
| A/B `ledger` vs `ledger_routed` | jaccard chunk **0,00**, jaccard doc **0,00** — il caso R-07 per cui quella vista esiste |
| Failure Explorer | 20 query golden in **0,7 s**, in 2 chiamate da 10 |

> Lo `0,00` su entrambi i jaccard non è un difetto: le due collection usano pipeline di chunking diverse, quindi i `chunk_id` non coincidono per costruzione. È esattamente ciò che la vista è costruita per rendere leggibile, ed è la ragione per cui R-07 si misura su `doc_R@5`.

### A-07 — disegnare quattro schermate ha rivelato tre buchi

A-06 ha esercitato **un** consumatore dell'API, non tutti. La bozza d'interfaccia della Fase 8 — quattro schermate disegnate prima di scrivere una riga di React — ne ha rivelati altri tre, ed è lo stesso meccanismo che il ROADMAP aveva previsto per A-06: *«se non le basta, si scopre ora invece che a React scritto.»*

| serve a | mancava | conseguenza se restava |
| il menu dei modelli | `models` in `Capabilities` | una lista scritta a mano nel frontend, cioè la quindicesima copia di Q-06 |
| il toggle «Ragionamento» | `reasoning_effort` in `QueryRequest` | un comando che non ha niente da mandare |
| sfogliare il corpus | `GET /documents`, `GET /document/{doc_id}/chunks` | l'esploratore può solo cercare, mai **mostrare** |

Sta in Fase 7 e non in Fase 8 perché la Fase 8 dice «il frontend non importa niente da `src/`»: mettere modifiche a `src/api/` dentro un task U-xx sarebbe stata la prima violazione di quella regola il giorno dopo averla scritta.

#### Il criterio è che nessuno dei tre tocchi il contratto

Due campi additivi e due endpoint nuovi. `TestContrattoAdditivo` lo verifica in tre punti: la richiesta minima `{"query": "..."}` basta ancora, i sette endpoint di A-04 ci sono tutti, nessun campo è sparito dalla risposta. Cambiare la forma di ciò che qualcosa ha già prodotto è la regola che ha reso caro il §3.2.

#### La lista modelli, e perché la degradazione è una decisione

`chat.list_models()` passa da `LLM_BASE_URL` e dal contratto OpenAI-compatibile come tutto il resto del modulo — non per stile: il browser può non raggiungere Ollama (in `compose.yml` è dietro `host.docker.internal`, e in un deployment reale è su un'altra macchina), e così la stessa funzione vale con vLLM o llama.cpp server al posto di Ollama.

`catalog.models()` restituisce `[]` quando l'endpoint non risponde, **e non solleva**: `/datasets` serve anche i dataset, che con l'LLM non c'entrano niente. È lo stesso difetto per cui `/health` non interroga Qdrant. E la lista resta vuota invece di contenere il modello configurato — aggiungerlo affermerebbe che esiste, che è precisamente ciò che non si è potuto verificare.

L'ordine è alfabetico e non quello di arrivo, perché `/v1/models` di Ollama ordina per data di download: un menu che si riordina da solo fa saltare la selezione a chi ha appena scaricato qualcosa.

#### `reasoning_effort` si poteva vedere, non scegliere

`ConfigView` lo restituiva già. Cioè l'asse che C-07 misura era leggibile a posteriori e non impostabile — un'asimmetria che nessuno aveva notato perché nessun client l'aveva ancora chiesto.

`REASONING_EFFORTS` raccoglie i cinque valori che l'endpoint accetta davvero: non è una scelta nostra, è quello che Ollama verifica in `openai/openai.go` rispondendo 400 a tutto il resto. Un livello inventato diventa così un **422 col nome del campo** invece di un 400 del modello rimbalzato come 500 — cioè un guasto nostro per un errore di chi chiama.

> **La stringa vuota resta fuori dall'elenco** pur essendo trattata come «spento» da `reasoning_enabled`. È raggiungibile solo da `REASONING_EFFORT=""` nell'ambiente, e sul filo produrrebbe proprio il 400 che l'elenco esiste per evitare. Latente, non introdotta qui, e ora scritta accanto alla costante invece che scoperta da chi la incontra.

#### L'indice payload: 80× su una domanda che la UI fa a ogni pagina

`GET /documents` deve contare i chunk per documento. `facet` di Qdrant lo fa lato server ma **richiede un indice payload** su `doc_id`; senza, l'unica strada è scandire i payload.

E la stessa mancanza penalizzava già `get_by_chunk_id`, che sta sul percorso di **ogni citazione cliccata** in U-06. La sua docstring prevedeva questo rimedio da prima che servisse.

| collection | punti | scansione | con indice |
|---|---|---|---|
| `ledger` | 47.110 | 2,07 s | **0,025 s** |
| `ledger_routed` | 228.331 | ~10 s (stimata) | 0,21 s (misurata via API) |

Un indice payload si aggiunge a una collection viva **senza rifare i vettori**, esattamente come il modificatore IDF di R-08 — e per la stessa ragione vale la pena ripeterlo: queste collection sono ore di GPU, e un rimedio che richiedesse di ricostruirle non sarebbe un rimedio.

`ensure_collection` li crea da ora a ogni ingestione. `scripts/migrate_payload_indexes.py` serve alle collection indicizzate prima, e a chi ripristina uno snapshot anteriore ad A-07: **sette collection migrate in 14 s**, conteggi punti invariati, rilanciarlo non fa niente.

#### `DocumentInfo` non porta il genere, ed è una decisione

`doc_genre` e `pipeline` stanno sul chunk perché è lì che sono veri. Metterli sul documento sarebbe un'aggregazione che il dato non garantisce: una collection `_routed` può mescolare pipeline dentro lo stesso documento — ed è esattamente il caso che l'esploratore esiste per mostrare.

Per la stessa ragione `/document/{doc_id}/chunks` restituisce i chunk **in ordine di sequenza**: mostrare come un documento è stato spezzato ha senso solo nella sequenza in cui è stato spezzato, ed è ciò che rende visibile il routing (U-05) a chi sfoglia invece di interrogare. `marker` e `score` valgono 0 su ognuno — qui non c'è stato nessun recupero, e un punteggio inventato farebbe leggere una classifica dove c'è solo una lettura.

#### Il gate

| | |
|---|---|
| `rescore_citations.py` | 16 dump a `+0.0000`, e il solo `+0.0052` preesistente |
| smoke dense 50 query, open_ragbench | R@5 **0,8000** · doc_R@5 **0,9600** · nDCG@10 **0,7051** — identici al riferimento di A-06 |
| suite | **1659 test**, `ruff check .` pulito |
| CLI end-to-end | verificato eseguendo la **stessa query su `main` e su `A-07`**: output identico |

> L'ultima riga merita la nota. La risposta non coincide con quella registrata in A-06 (`…0.0226 [1].`, `OK [1] p=0.606`): con `--top-k 3` il modello ne produce una più lunga, con due citazioni entrambe bocciate dal verificatore. Eseguire lo stesso comando su `main` dà **lo stesso output**, quindi la differenza viene dai flag e dallo stato del modello, non da A-07 — che è ciò che il gate deve accertare. Confrontare due comandi diversi e dichiarare una regressione sarebbe stato l'errore speculare a quello di A-05, dove un tempo a freddo era stato riportato come costo per richiesta.

### A-08 — la finestra di contesto è una proprietà del modello, e si è dovuto misurarlo

Nato da una richiesta di Marco (2026-08-19): far scegliere a chi usa la demo la
dimensione del contesto, come fa lo slider della GUI di Ollama. Tre misure prima
di decidere, perché nessuna delle tre era ovvia.

| verifica | esito |
|---|---|
| `num_ctx` sul contratto OpenAI | **non è fra i campi supportati** — la documentazione elenca `model`, `messages`, `temperature`, `max_tokens`, `reasoning_effort`… e rimanda a un Modelfile |
| mandarlo comunque su `/v1/chat/completions` | **200, e ignorato**: `num_ctx: 4096` e il modello resta caricato a 32768 |
| `PARAMETER num_ctx` in un Modelfile | **ha effetto attraverso l'endpoint OpenAI**: modello derivato a 8192, e una chiamata a `/v1` lo carica a 8192 |
| `/api/ps` come fonte di verità | **inutilizzabile**: elenca solo i modelli *caricati*, e a servizio inattivo risponde vuoto |

La seconda riga è la più importante: un controllo costruito lì **sembrerebbe
funzionare senza fare niente**, che è il difetto peggiore dei due possibili.

Ne segue la forma del task: la finestra viaggia col **nome del modello**, e il
menu dei modelli è già un campo pienamente supportato. Il selettore di contesto
non è quindi una manopola nuova sull'API — è il catalogo.

#### Perché deve leggersi per pattern

Ollama pubblica la finestra sotto una chiave che **contiene il nome della
famiglia**: `gemma4.context_length`, `qwen35.context_length`. Cercarla per nome
avrebbe funzionato su gemma4 e su nient'altro — che è esattamente la domanda che
Marco ha fatto («funzionerà con qualsiasi modello o solo per gemma4?»). Si cerca
per suffisso, e un test lo fissa con due famiglie nella stessa chiamata.

**E il massimo non è uno solo**, misurato sui quattro installati:

| modello | famiglia | finestra max | quantizzazione |
|---|---|---|---|
| `gemma4:latest` | gemma4 | 131 072 | Q4_K_M |
| `gemma4:e2b` | gemma4 | 131 072 | Q4_K_M |
| `gemma4:12b` | gemma4 | **262 144** | Q4_K_M |
| `qwen3.5:latest` | qwen35 | **262 144** | Q4_K_M |

Quindi «solo le finestre compatibili col modello scelto» (U-16) smette di essere
una precauzione e diventa un fatto.

#### La terza volta che incontro lo stesso difetto

Il catalogo porta anche la **quantizzazione**, e non per completezza.
`LLM_QUANTIZATION = "Q4_K_M"` è una costante che finisce in ogni `EvalRun`, ed è
vera oggi per tutti e quattro **per coincidenza**. È la stessa forma di
`context_window` (D-14) e di `reasoning_enabled` prima di loro — che
`run_config.py` documenta come «una dichiarazione che nessuno verificava, e per
un periodo è stata falsa in ogni run». Tre campi della stessa famiglia,
dichiarati e mai letti; il catalogo li rende leggibili tutti e tre.

#### La chiamata nativa, e dove sta

`/api/show` è l'API nativa di Ollama, e il vincolo di STACK.md dice che
**l'inferenza** passa da un endpoint OpenAI-compatibile perché il repo giri anche
su vLLM o llama.cpp. Questa non è inferenza: è **scoperta**, e degrada a «non lo
so» ovunque non esista — allora il catalogo torna a essere la lista di nomi che
era prima, con `context_max: None`, e chi legge non offre una scelta che non può
sostenere. È lo stesso schema di `catalog.models()` che restituisce `[]` invece
di inventare.

Sta in `catalog.py` e non in `chat.py` di proposito: quel modulo è il contratto
OpenAI, e mettergli dentro una chiamata nativa lo renderebbe il posto dove la
regola si aggira invece di quello dove è scritta.

#### Additivo, e verificato che lo sia

`models` resta `list[str]` con gli stessi valori — ora derivati dal catalogo. Il
test di A-07 è stato **esteso invece che adattato**: il suo criterio è proprio
che quella forma non cambi, quindi continua a guardarla, e due test nuovi
coprono il catalogo e il caso del motore muto.

**1690 test Python** (10 nuovi sul catalogo, 2 sugli endpoint), 183 Vitest,
typecheck verde, tipi TypeScript rigenerati.

---

## Fase 8 — Interfaccia

| Task | Stato | Note |
|---|---|---|
| U-00 | ✅ fatto (2026-08-14) | Scheletro `ui/`: Vite 8 + React 19 + TypeScript 7 + Tailwind 4, client SSE scritto a mano, temi, i18n IT/EN, `/datasets` all'avvio. **19 test Vitest** + 15 test Python sul contratto generato. `npm run typecheck && npm test && npm run build` verdi; catena provata contro l'API viva. Dettaglio sotto. |
| U-01 | ✅ fatto (2026-08-14) | Selettore dataset nella corsia laterale del mockup, scelta ricordata in `localStorage` e **validata** contro `/datasets`. La regola di selezione è in funzioni pure: **9 test Vitest** in più (28 in tutto), senza jsdom. Provato contro l'API viva: `open_ragbench` 18.840 e `ledger` 47.110 chunk. Dettaglio sotto. |
| U-02 | ✅ fatto (2026-08-14) | Schermata di chat con **pannello fonti sempre visibile** (nel telaio, non nella chat): otto stati, uno per evento del §3.5, macchina a stati in un reducer puro con **16 test** (44 lato Vitest). Marcatori inerti finché non arriva `answer`. I valori di `abstention` ora sono generati come i tipi. Esempi dello stato vuoto presi da `eval/golden`. Provato contro l'API viva su una query d'oro reale. **Rendering LaTeX** con KaTeX, regola dei delimitatori misurata: 49 falsi positivi tolti su 49, zero formule vere perse. Dettaglio sotto. |
| U-03 | ✅ fatto (2026-08-19) | **La barra di composizione e il confronto affiancato**: i quattro controlli del mockup (RAG, ragionamento, modello, «Avanzate») e la stessa domanda rilanciata a RAG invertito in due colonne. Il secondo braccio riparte dalla configurazione *che ha girato*, non dalla barra — §15 dentro l'interfaccia. **3 test Vitest** in più (155 in tutto), e ogni controllo si apre sul valore in vigore letto da `/config`. Dettaglio sotto. |
| U-04 | ✅ fatto (2026-08-20) | **Il prompt del modello senza fonti si sceglie dentro quella colonna**: due pastiglie — «risponde comunque» e «si astiene» — che rifanno **quella colonna sola**, con l'altra ferma a fare da paragone. È il 45%→17% di E-04/E-05 su una domanda singola invece che in una tabella. Il braccio nudo diventa un campo dello stato: ricavarlo da `config` faceva scambiare di posto le due colonne mentre una si rifà. **10 test Vitest** in più (214 in tutto). Dettaglio sotto. |
| U-05 | ✅ fatto (2026-08-20) | **Come il documento è stato riconosciuto e come è stato tagliato**, sulla scheda della fonte: `tabelle → taglio generico`, con l'accento solo quando una pipeline è stata scelta per il genere. Prima però il campo andava reso vero: i loader generici scrivevano il nome di una pipeline che **non aveva girato** — terza volta di quella famiglia dopo `reasoning_enabled` e `context_window`. Migrazione di payload su 65.950 punti, senza re-ingestione. **6 test Vitest** in più (225) e 2 Python (1711). Dettaglio sotto. |
| U-06 | ✅ fatto (2026-08-20) | **L'esploratore del corpus**: i documenti, com'è stato spezzato quello aperto — una tessera per chunk, larga il doppio dove c'è una tabella — e il chunk scelto **per intero**, che è la ragione del task: la scheda ne mostra due righe e il chunk può essere lungo 6.302 caratteri. Nessun campo nuovo: `/documents` e `/document/{id}/chunks` esistevano dal A-04 e non li aveva mai chiamati nessuno. Il PDF non c'è su nessuno dei due corpus, e si dichiara. **11 test Vitest** in più (236). Dettaglio sotto. |
| U-07 | ✅ fatto (2026-08-17) | Ogni citazione porta il **proprio verdetto**, sul marcatore in mezzo alla prosa e sulla scheda della fonte, e **nessuna è nascosta**. Cinque stati per il marcatore e sei per la scheda, distinti da glifo, colore e parola insieme (§12). Le frasi senza citazione sono sottolineate dove stanno. La corrispondenza frase↔marcatore è in funzioni pure: **38 test Vitest** in più (116 in tutto). Provato contro l'API viva su `open_ragbench` e `ledger`. Dettaglio sotto. |
| U-13 | ✅ fatto (2026-08-17) | **Conversazione nuova e cronologia locale**: l'elenco nella corsia, persistenza in `localStorage`, e il ricaricamento riapre una conversazione *nuova*, con la cronologia accanto. Cosa si ricorda e come si rilegge è in funzioni pure: **17 test Vitest** in più (147 in tutto). Cancellare la cronologia c'è, a due tempi, ed è il primo posto in cui la palette ha un rosso — `danger`, solo per ciò che distrugge. Due giri di revisione. Dettaglio sotto. |
| U-14 | ✅ fatto (2026-08-19) | **Markdown e LaTeX nella risposta**: il prompt li invita invece di vietarli, e l'interfaccia li disegna — come **intervalli sul testo grezzo**, così verdetti per frase e frasi scoperte restano allineati. **15 test Vitest** in più (172 in tutto). Debito dichiarato: `prompt_hash` cambia, C-01/C-02/C-07 da rimisurare. Dettaglio sotto. |
| U-15 | ✅ fatto (2026-08-19) | **Con quali parametri e' stata data ogni risposta**: la configurazione che ha girato si rilegge nella conversazione, e fra una domanda e l'altra si vede cosa è cambiato. **Nessun campo nuovo**: `ConfigView` era già dentro ogni risposta e già nel deposito da U-13. **11 test Vitest** in più (183 in tutto). Dettaglio sotto. |
| U-16 | ✅ fatto (2026-08-19) | **Modello e contesto, due selettori**: il primo elenca i modelli, il secondo le finestre che quel modello regge — e compare solo quando ce n'è più di una. Nessuna convenzione sui nomi: il raggruppamento passa da `parent_model`. Con `scripts/model_sizes.py` che crea le taglie. **15 test Vitest** in più (198 in tutto). Dettaglio sotto. |
| U-17 | ✅ fatto (2026-08-20) | **Il testo indicizzato**: la colonna di mezzo dell'esploratore ha due viste dello stesso documento — la mappa dice quanto sono grandi i pezzi, il testo dice cosa c'era nel punto in cui uno è stato tagliato — con le cuciture visibili e la selezione condivisa. **51 test Vitest** in più (287). Dettaglio sotto. |
| U-18 | ✅ fatto (2026-08-20) | **La corsia si comprime**: un comando accanto al marchio la riduce a una striscia di 48 px e la riporta larga, e la scelta vale al prossimo avvio. Nella striscia restano i due comandi e le tre tendine; la cronologia no, e il suo bottone riapre la corsia dicendo perché. **8 test Vitest** in più (295). Dettaglio sotto. |
| U-19 | ✅ fatto (2026-08-21) | **La pagina «Che cos'è»**: cosa fa il progetto, le tre affermazioni del §0 col verdetto che hanno oggi, cosa la demo non è, e chi l'ha fatta. Raggiungibile dalla corsia in tutti e due gli stati, in IT/EN. **Nessuna metrica scritta a mano**: i numeri non ci sono, e la pagina dice dove sono. **2 test Vitest** in più (300). Dettaglio sotto. |
| U-20 | ✅ fatto (2026-08-21) | **L'avvio guidato**: cinque passi, e ognuno **circonda con un alone la zona di cui parla** — le fonti, la colonna delle risposte, la barra sotto il campo, il dataset nella corsia, «Che cos'è». Il velo scurisce e sfoca il resto ma **non intercetta il puntatore**: si scrive e si manda con la guida aperta, e la lingua si cambia dalla scheda. Si salta con un comando, non torna, e il deposito ricorda il passo. **25 test Vitest** in più (325). Dettaglio sotto. |
| U-21 | ✅ fatto (2026-08-21) | **Il telefono**: sotto una soglia **derivata dalle colonne** (200 di corsia + 390 di lavoro + 272 di fonti = 862 px) il telaio ha una colonna sola, e le due laterali diventano due strati che si aprono sopra il lavoro — la corsia da sinistra, le fonti da destra, con quante ne sono arrivate scritte sul comando. Il confronto si impila, l'esploratore diventa un affondo in due schermate, e la scheda della guida smette di finire sul campo in cui si scrive. **10 test Vitest** in più (335). Dettaglio sotto. |

### U-00 — il contratto esiste in due linguaggi, e uno dei due si genera

«Il frontend non importa niente da `src/`» è la regola giusta: un frontend che importasse la pipeline non ne sarebbe un consumatore, sarebbe un **secondo posto in cui la pipeline vive**. Ma ne segue che il contratto del §3.5 va scritto due volte, e due elenchi scritti a mano divergono — la lezione di Q-06, in TypeScript. Peggio: la seconda copia diverge *in silenzio*, perché nessun test Python guarda dentro `ui/`.

Quindi `ui/src/api/types.ts` **non si scrive**: lo produce `scripts/gen_api_types.py`, e `tests/test_ui_types.py` fallisce se il file committato non è ciò che il generatore produce oggi. Un campo aggiunto ad `AnswerResponse` senza rigenerare rompe la suite **Python** — si scopre prima di arrivare al browser, e senza che serva Node per accorgersene. Provato togliendo a mano `truncated` dal file: due test falliscono.

**Gli eventi SSE non sono modelli pydantic**, ed è il punto delicato: `to_wire()` costruisce i payload a mano, quindi è l'unico pezzo di contratto in cui togliere un campo non romperebbe nessun tipo Python. Il generatore perciò non lo legge, lo **esegue**: i nomi dei campi vengono dal dizionario che finisce davvero sul filo.

Due proprietà che il tipo fa rispettare meglio di un test: in `QueryRequest` solo `query` è obbligatorio — cioè il criterio di A-07 verificato dal compilatore a ogni chiamata invece che una volta sola — e le liste di `Capabilities` restano `string[]` e non letterali, perché un valore nuovo lato server deve **arrivare** al frontend, non romperlo.

#### `EventSource` non serviva, e non averlo è una decisione

`/query/stream` è una `POST` e l'`EventSource` del browser fa solo `GET`. Accettare anche `GET` per poterlo usare costringerebbe a serializzare quindici parametri in query string, e a dichiarare cacheabile una richiesta che accende una GPU.

La conseguenza vera però è un'altra: **`EventSource` riconnette da solo**, ed è esattamente ciò che non deve accadere. Rilanciare una generazione da ~11 s produce una risposta *diversa*, e il testo cambierebbe sotto agli occhi di chi legge senza che nessuno l'abbia chiesto. Su caduta si mostra il parziale marcato incompleto, con un «Riprova» esplicito.

Il parser sta su due livelli, e la divisione non è estetica: `frames()` è trasporto puro (byte → riquadri) e si prova senza rete, `events()` aggiunge il contratto (JSON, nomi noti). Chi legge un test fallito deve poter distinguere un bug di parsing da una divergenza dall'API.

**I 13 test non provano «legge un evento»**: provano i modi in cui la rete consegna i byte — riquadro spezzato a metà riga, due nello stesso pacchetto, un carattere UTF-8 tagliato a cavallo di due pacchetti, `\r\n`, `data` multiplo, commenti. E il riquadro incompleto a stream caduto, che viene **scartato**: non è un riquadro corto, è un riquadro che non è arrivato.

Un nome di evento sconosciuto viene saltato e segnalato, non tradotto in `error`: il server non ha segnalato un guasto, e inventarne uno mostrerebbe all'utente un errore che nessuno ha commesso. Un `data` che non è JSON invece solleva — lì il contratto è rotto davvero.

#### Il proxy non bufferizza, ed è stato misurato, non supposto

Il backend non ha CORS e resta senza: in produzione API e UI stanno dietro la stessa origine, e aprirla per comodità di sviluppo sarebbe una decisione di sicurezza presa per sbaglio. In sviluppo ci pensa il proxy di Vite. Ma un proxy che bufferizza **non rompe niente**: consegna tutto insieme alla fine, e il client non ha modo di accorgersi che sarebbe dovuto arrivare a pezzi.

| stessa query, `top_k 3` | `chunks` | primo token | `done` | token |
|---|---|---|---|---|
| attraverso il proxy | 0,27 s | 3,01 s | 6,82 s | 41 |
| diretto su `:8000` | 0,22 s | 2,99 s | 6,80 s | 41 |

> **La prima misura era sbagliata, e vale più della seconda.** Attraverso il proxy il primo tentativo dava primo token a **20,19 s** e 14 token addensati in 0,2 s — che si legge come «il proxy bufferizza». Era la richiesta a freddo: Ollama stava caricando i pesi. Rimisurata a caldo, la differenza sparisce. È la trappola di A-05 un'altra volta, e la regola che la disinnesca è sempre quella del §15: un confronto è un confronto solo se i due lati differiscono in **esattamente** una cosa.

`chunks` a 0,27 s contro il primo token a 3,01 s è anche la conferma numerica della decisione presa disegnando: il pannello fonti si apre su `chunks`, non a risposta finita. L'attesa si riempie invece di premiare.

#### Le decisioni piccole che non sono di stile

**Il tema si stampa prima della prima pittura**, da tre righe in `index.html`, non da React: montare il componente e poi cambiare sfondo produce un lampo bianco su tema scuro. E con `data-theme` **sempre** presente su `<html>`, la variante CSS è una condizione sola invece di tre stati, e il toggle vince sul sistema in entrambi i versi. «Sistema» resta però una scelta viva: il listener sulla media query non si stacca, perché chi la lascia così vuole che la pagina cambi a finestra aperta.

**Nessun webfont.** U-08 chiede `--profile demo` in meno di due minuti *senza rete*, e un font da CDN è una richiesta di rete al primo caricamento.

**Nessuna libreria i18n.** Due lingue e un dizionario piatto sono trenta righe, e `Record<Chiave, string>` fa fallire **la compilazione** su una chiave mancante — prima e meglio di qualsiasi test. E che la lingua dell'interfaccia non arrivi mai all'API non è una regola da ricordare: `QueryRequest` non ha un campo lingua, quindi non c'è modo di mandarla.

**`/datasets` ha tre stati e non due.** «Sto contattando» non è «è rotto»: mostrare subito l'errore per poi toglierlo fa lampeggiare un guasto che non c'era. E la lista modelli vuota resta un non-guasto, com'è in A-07 — i dataset non dipendono dall'LLM.

#### Licenze, e l'unica copyleft dell'albero

Lette dai `package.json` in `node_modules`, non dedotte: 56 pacchetti MIT, 4 Apache-2.0, 3 ISC, 1 BSD-3-Clause, **2 MPL-2.0**. Le due sono `lightningcss` e il suo binario per piattaforma, tirati dentro da Tailwind 4.

MPL-2.0 è copyleft **a livello di file**: obbliga a mantenere sotto MPL i file di quella libreria se modificati e ridistribuiti, e non si propaga al progetto che la usa. Non è nella lista vietata (GPL / AGPL / LGPL-static), è una dipendenza di build che non finisce nel bundle servito, e il CSS che produce è un output, non un'opera derivata dei suoi sorgenti. Registrata in `STACK.md` perché la regola dice di **segnalare**, non di valutare in silenzio.

#### Il gate

| | |
|---|---|
| suite Python | **1674 test** (erano 1659), `ruff check .` pulito |
| suite frontend | **19 test** Vitest, `tsc` senza errori, `vite build` verde |
| catena viva | `/datasets` attraverso il proxy â†’ 4 modelli, `open_ragbench` 18.840, `ledger` 47.110, 7 collection |
| stream vivo | 41 token in 5 eventi distinti, tempi indistinguibili da quelli diretti |

> Node non era installato quando U-00 è cominciato. La metà che non ne aveva bisogno — generatore, tipi, test di deriva — è stata fatta e committata prima, invece di scrivere lo scaffold alla cieca: qui un file che non si è mai visto compilare sarebbe stata l'unica cosa consegnata senza la verifica che la accompagna.

### U-01 — la scelta è derivata, e un indice vuoto si vede ma non si sceglie

Il criterio è «cambio dataset senza riavvio», e la parte difficile non è il menu: è decidere **cosa significa scegliere** quando il server elenca un dataset che non si può interrogare, o quando il browser ricorda un id che non esiste più.

**Tre decisioni, e nessuna è di comodità.**

| situazione | cosa fa il frontend | perché non l'alternativa |
| dataset elencato con `ready: true` ma zero chunk | compare nella lista, disabilitato, col motivo scritto | nasconderlo direbbe che non esiste; lasciarlo scegliere farebbe leggere come ignoranza del modello ciò che è assenza di dati — ogni domanda tornerebbe un'astensione |
| id ricordato che `/datasets` non elenca più | si butta e si ripiega sul primo interrogabile | un id in `localStorage` **è** una costante del backend scritta mesi fa, ed è esattamente ciò che U-00 vieta al frontend di portarsi dietro |
| nessun indice pronto | `null`, e il selettore lo dice | fingere una selezione manderebbe ogni query contro una collection vuota. È la condizione normale di chi ha appena clonato il repo |

`ready` e `n_chunks` restano separati perché il §3.5 li ha separati apposta: una collection che esiste ed è vuota è uno stato reale, diverso dall'assenza.

**La regola sta in funzioni pure, fuori da React.** Non è pulizia architetturale, è l'unico modo di provarla: i test girano in ambiente `node`, e ciò che vive dentro un componente richiederebbe jsdom più una libreria di rendering — due dipendenze da giustificare in `STACK.md` per verificare una condizione che qui è una `if`. Nove test in più, 28 in tutto lato Vitest.

**Nessun `useEffect` che sincronizza.** L'id selezionato è *derivato* a ogni render da `sceltaIniziale(lista, ricordato)`: quando le capabilities arrivano la scelta si risolve da sola, e quando il dataset ricordato sparisce dal server ripiega senza che nessuno debba accorgersene. Un effetto che scrivesse stato in risposta ad altro stato avrebbe due sorgenti di verità e almeno un render in cui non concordano. Si ricorda **solo la scelta esplicita**, mai il ripiego: salvarlo lo trasformerebbe in una decisione che l'utente non ha preso, e al prossimo avvio con l'indice tornato pronto vincerebbe sul dataset giusto.

#### Il selettore: prima il `<select>` nativo, poi una tendina nostra

Il disegno è quello di `docs/ui-mockup.html` — nome a sinistra, conteggio a destra, bordo sottile — ma il controllo sotto è un `<select>` reso trasparente e steso sopra il disegno. Tastiera, ruolo ARIA, chiusura al clic fuori e voci disabilitate arrivano dal browser: sono le quattro cose che un menu fatto in casa sbaglia quasi sempre, e riscriverle non costerebbe un componente, costerebbe un difetto di accessibilità. Il mockup non disegna mai la lista aperta, quindi lasciarla al sistema non tradisce nessuna decisione presa.

> **Sostituito la sera stessa, su richiesta: le tendine di sistema non piacevano.** La decisione resta registrata perché è ciò che stabilisce il **debito** del cambio: quelle cinque cose non si perdono, si riscrivono. `Selettore.tsx` implementa il pattern `listbox` — il fuoco resta sul bottone, `aria-activedescendant` indica la voce evidenziata, frecce/Invio/Escape/Home/Fine funzionano, Escape riporta il fuoco al bottone e Tab non lo intrappola — e la navigazione (saltare le disabilitate, girare in tondo, restituire `-1` quando **tutte** lo sono, senza cui il ciclo non finisce) sta in `lista.ts` con 13 test, senza DOM.

L'animazione ha due tempi diversi di proposito: aprire è la risposta a un gesto (150 ms `ease-out`, parte veloce e si posa), chiudere toglie di mezzo (110 ms `ease-in`, non fa aspettare per una cosa già decisa). Un pannello che entra ed esce con la stessa curva sembra sempre in ritardo in uscita. Sono transizioni CSS, quindi la regola globale `prefers-reduced-motion` le azzera tutte. Effetto collaterale gradito: le icone tornano dentro la lista del tema, che erano state tolte solo perché un `<option>` nativo accetta esclusivamente testo.

**Il selettore ha tre stati dove uno solo sarebbe stato più semplice e falso**: «contatto il backend» non è «nessun indice pronto» — la seconda frase accusa l'ingestione di non essere stata fatta, e detta mentre la risposta è ancora in volo è un'accusa falsa. E col backend caduto il motivo sta già nella colonna accanto: ripeterlo nel selettore darebbe la colpa ai dati invece che al servizio.

#### La corsia laterale, e cosa non c'è ancora

Lingua e tema scendono dalla testata di U-00 alle pastiglie in fondo alla corsia, come nel mockup: sono impostazioni dell'applicazione, non della pagina, e quando la colonna centrale diventerà la chat una testata dove metterle non ci sarà. Il tema è una **tendina**, non un bottone che cicla: con tre stati un bottone che gira nasconde le opzioni — non si vede quante sono, non si sa dove si finisce, e chi non ha ancora capito che «sistema» esiste può scoprirlo solo cliccando finché non ricompare, cioè imparando l'interfaccia per tentativi. Il caret `▾` non è decorazione: nel mockup distingue la pastiglia che apre un menu (`.tg.menu`) da quella che commuta e basta, ed è il modo in cui tema e lingua si dichiarano diverse. La lingua resta un bottone perché con **due** stati si vedono entrambi e un clic porta all'altro: una tendina di due voci farebbe fare due gesti dove ne basta uno. Il nome dello stato sta accanto al glifo perché «sistema» non è deducibile da un simbolo, ed è proprio quello che va capito — è l'unico che continua a cambiare da solo.

La cronologia e il pulsante «Esplora il corpus» del mockup restano fuori finché non aprono qualcosa. È la stessa regola che la bozza applica a sé stessa nella didascalia del toggle «Prompt»: un comando che gira a vuoto è lo stesso difetto di un campo che il servizio ignora.

La colonna centrale mostra collection, punti, dimensione densa e presenza dei vettori sparsi del dataset scelto. Non è un segnaposto: è ciò che rende il criterio **verificabile**, perché «cambio senza riavvio» si vede solo se qualcosa cambia sotto gli occhi. Quando arriverà la chat, quei dati prenderanno il loro posto sotto «Dettagli della run», che il §12 vuole comunque sempre leggibili.

Provato contro l'API viva attraverso il proxy: `open_ragbench` 18.840 chunk, `ledger` 47.110, quattro modelli, sette collection. `npm run typecheck && npm test && npm run build` verdi, e i 15 test Python sul contratto generato restano verdi perché il contratto non è stato toccato.

> **Un guasto raccolto per strada.** Avviare `python scripts/dev.py` con l'output rediretto su file lo faceva morire prima ancora di partire: su Windows `sys.stdout` prende `cp1252` quando non è una console, e la freccia `→` sollevava `UnicodeEncodeError`. In terminale non si vedeva — si vede solo in un log o in CI. Il messaggio è tornato ASCII invece di forzare l'encoding: un avvio che dipende da come è configurata la console è un avvio che funziona per caso.

### U-02 — «visibile in ogni stato» è un vincolo di struttura, non di grafica

Il criterio dice che la lista documenti è visibile **senza interazione, in ogni stato dell'interfaccia**. Letto alla lettera decide dove vive il pannello: non dentro la chat, ma dentro il telaio, accanto a essa. Uno stato in cui la chat non c'è — backend che non risponde, nessun dataset pronto — è comunque uno stato, e un pannello figlio della chat sparirebbe proprio lì.

Da questo discende anche l'assenza di un selettore di modalità: non c'è un «modo documenti» e un «modo risposta» da alternare. Le fonti stanno sempre a destra, la sintesi sempre al centro, e non c'è niente da scegliere per vedere l'una o l'altra. Prima della prima domanda la colonna non è vuota: dice cosa comparirà, e quando.

#### Otto stati, uno per evento

Il §3.5 manda sei eventi in un ordine che **è** il contratto. L'interfaccia deve sapere cosa disegnare dopo ognuno, e la tabella è il task:

| evento | riga di stato | corpo |
| *(richiesta partita)* | `cerco nel corpus…` | scheletro a tre righe |
| `chunks` | `3 fonti · il modello sta scrivendo…` | scheletro a due righe, **pannello fonti pieno** |
| `token` | `scrivo… · marcatori non ancora attivi` | testo che cresce, marcatori spenti |
| `answer` | `testo definitivo · controllo le citazioni…` | testo riparato, marcatori accesi |
| `citations` | `verdetti arrivati` | invariato (i verdetti sono U-07) |
| `done` | `retrieval 0,02 s · generation 11,4 s · …` | pallino fermo, verde |
| `error` | `interrotto · generation` | **parziale conservato** + avviso + «Riprova» |
| *(«Ferma»)* | `fermata · resta la risposta parziale` | parziale conservato, nessun avviso |

Otto e non «carica / non carica» perché chi guarda deve poter distinguere se il ritardo è il retrieval, il modello o la verifica. Trenta secondi senza articolazione si leggono tutti come un blocco.

La macchina a stati sta in un reducer puro ([conversazione.ts](ui/src/app/conversazione.ts)), non nel componente, e per la stessa ragione di U-01: i test girano in ambiente `node`. **16 test** — 44 in tutto lato Vitest — e non provano «legge un evento», provano i casi che a mano non si riescono a riprodurre.

**Tre decisioni che quei test fissano.**

- **`answer` sostituisce il testo, non lo continua.** Durante lo stream si accumula il grezzo; `answer` porta il testo dopo la riparazione dei marcatori, ed è quello che si deve leggere. Da lì un token in ritardo viene ignorato: appenderlo scriverebbe in coda a una risposta già chiusa, ed è un guasto che si vede solo con una rete lenta.
- **Il parziale non si butta mai.** Su `error`, su caduta del trasporto e su «Ferma» restano fonti e testo ricevuti. Una risposta interrotta è un dato.
- **Tre esiti distinti dove uno solo sarebbe comodo:** `error` del server (che dice *cosa*), caduta del trasporto (che non lo dice, e `stage: "trasporto"` lo dichiara invece di inventarlo), «Ferma» (che non è un guasto ma una decisione di chi guarda). Mostrarli uguali manderebbe a cercare un guasto chi ha solo premuto un pulsante.

E `verificate` resta separato da `citazioni` vuote: senza, «verificata, nessuna citazione» e «verdetti non disponibili» sarebbero la stessa lista vuota — che è esattamente la distinzione su cui poggerà U-07.

#### I marcatori sono inerti finché `answer` non arriva

È una regola del §3.5, non una scelta grafica. Mentre i token scorrono, `[2]` compare **prima** che il suo verdetto esista e prima che il parser abbia potuto normalizzarlo: disegnarlo subito come riferimento valido significherebbe promettere per una decina di secondi qualcosa che nessuno ha ancora controllato. Spenti sono grigi e sottolineati a puntini; accesi diventano accento su fondo accento.

Si riconosce solo la forma contigua `[n]`, la stessa che il parser accetta. Se il modello scrive `[2, 3]` qui non si accende niente, esattamente come non si accende nel backend: **un'interfaccia più generosa del contratto mostrerebbe come citazione ciò che il contratto ha scartato.**

#### Anche i valori di `abstention` si generano

«Non ho trovato niente» (gate di C-04) e «il modello non se l'è sentita» sono due risposte diverse, e mostrarle uguali cancellerebbe proprio ciò che il gate misura. Distinguerle richiede i tre valori di `abstention` — `""`, `"retrieval"`, `"model"` — che stanno in `src/service/answer.py`.

Scriverli a mano in TypeScript sarebbe la costante del backend che U-00 vieta al frontend. Quindi li emette `scripts/gen_api_types.py` come `export const ABSTENTION`, e un test in più li lega ai simboli Python: cambiarli senza rigenerare rompe la suite **Python**, non il browser.

#### Gli esempi sono query d'oro vere, e vincolano U-08

Si **leggono nella lingua dell'interfaccia e partono in quella del corpus**: sotto la traduzione compare la query vera, in mono, così si vede prima di cliccare invece di scoprirla dopo nella propria domanda. Tradurre anche il testo mandato farebbe rispondere in italiano su un corpus inglese, con le citazioni a sostenere un testo tradotto — e sarebbe il primo clic di chi prova il progetto a produrlo.

I tre esempi dello stato vuoto vengono da `eval/golden/*.jsonl`, per dataset, tranne il terzo di ogni coppia che è **fuori dal corpus di proposito**: l'unico modo di mostrare che il sistema si astiene è fargli una domanda senza risposta, e nasconderla renderebbe la demo una pubblicità.

> **Vincolo su U-08, scritto ora perché lì sarà tardi.** Nel profilo `demo` l'indice conterrà solo i chunk d'oro di ~30 query. Se questi esempi non sono fra quelle, il primo clic di chi prova il progetto finisce in un'astensione. [esempi.ts](ui/src/app/esempi.ts) è il vincolo, non un suggerimento.

#### Cosa non c'è, e non per dimenticanza

Targhette `pipeline`/`doc_genre` sulle schede (U-05), verdetti per citazione (U-07), toggle RAG (U-03), prompt del baseline (U-04), parametri avanzati, cronologia. Ognuno arriva col proprio criterio e col proprio test; anticiparli significa consegnarli senza la verifica che li accompagna.

Un debito invece è reale e va detto: i quattro dati dell'indice che U-01 mostrava nella colonna centrale — collection, punti, dimensione densa, vettori sparsi — sono usciti di scena quando la chat ha preso quel posto. Devono tornare sotto «Dettagli della run», che il §12 vuole sempre leggibile e che non esiste ancora.

#### Il LaTeX, e perché la regola comoda era sbagliata

`open_ragbench` sono paper e `ledger` è Mathpix Markdown: la matematica non è un caso limite, è il contenuto. Misurato prima di scrivere il rendering:

| | risposte di riferimento | chunk veri |
| `open_ragbench` | 452 formule `$…$` su 2000 | 83% con `$…$`, 50% con `$$`, 65% con comandi LaTeX, **100% comincia con un titolo Markdown** |
| `ledger` | 0 | 48% con `$…$` (ma è **valuta**), 39% con tabelle in **HTML**, 77% con titoli |

**La regola comoda è sbagliata, e si sapeva solo misurandola.** «Accetto `$…$` solo se contiene un comando LaTeX» eviterebbe di scambiare due prezzi per una formula, ma **125 coppie su 452 (28%) non hanno nessun segnale**: sono variabili singole — `$o$`, `$n$`, `$p(y, o, u)$`. Butterebbe via un quarto della matematica vera.

Si usa la regola stretta dei delimitatori (niente spazio dopo l'apertura né prima della chiusura, nessuna cifra subito dopo, nessun attraversamento di riga vuota), che però da sola non bastava sui chunk: nelle tabelle HTML di `ledger` `<td>` non ha spazi, e due importi in celle diverse si chiudevano a vicenda. **49 falsi positivi su 600 chunk.** Le due difese possibili, contate sugli stessi 1200 chunk:

| guardia | falsi tolti (`ledger`) | formule vere perse (`open_ragbench`) |
| **contiene un tag HTML** | **49 / 49** | **0 / 22.150** |
| tetto di 120 caratteri | 26 / 49 | 275 |

Separazione perfetta contro separazione mediocre, e in tutti e due i versi. La guardia riconosce un **tag**, non un `<` qualunque: `$a < b$` resta matematica.

> **Il corpus finanziario ne aveva bisogno quanto i paper, e non per la stessa ragione.** Alla domanda sul capex di Sherwin-Williams il modello ha risposto `Capital expenditures ... were $(303.8)$ million dollars [1]`: riecheggia i delimitatori Mathpix del documento anche attorno a una cifra di bilancio. Senza rendering, quella stringa si legge così com'è — ed era esattamente il difetto segnalato.

**Una formula incompleta resta testo.** Mentre i token arrivano, `$\frac{a}` non ha ancora la chiusura: comporla disegnerebbe un errore rosso per mezzo secondo a ogni formula che si sta scrivendo. La proprietà cade fuori dalla segmentazione, non è un caso speciale.

**Gli estratti passano da `perAnteprima`**: via i cancelletti dei titoli e i tag delle tabelle. Senza, l'anteprima più frequente in assoluto comincia con `####` e quella di un bilancio è fatta di `</td><td>`. È una riduzione per una scheda alta due righe, non una modifica del dato — chi aprirà la fonte con U-06 deve vedere il chunk com'è stato indicizzato.

**Cosa non si renderizza, e perché.** Tabelle Markdown, grassetti e liste **nella risposta**: nelle risposte di riferimento sono zero, e nelle due risposte osservate dal vivo pure. Un parser Markdown completo entrerebbe anche in conflitto col §3.2, che accetta come citazione solo `[n]` contiguo — `[1]` è sintassi di link in Markdown. Se un giorno il modello dovesse rispondere con una tabella, si vedrà come testo grezzo: brutto, ma leggibile e senza inventare struttura che il contratto non riconosce.

`katex` 0.18.4 (MIT) è **l'unica dipendenza che finisce nel bundle servito**, e porta i propri font: +260 kB di JS e +190 kB di font, emessi da `vite build` come file locali — nessuna richiesta a un CDN, quindi U-08 resta avviabile senza rete. È una deroga dichiarata al «tutti font di sistema» del §12, e la ragione è la stessa per cui i simboli sono disegnati e non scritti: un carattere risolto dal sistema è diverso su ogni macchina, e una formula lo è in modo molto più visibile di un caret. `trust: false` resta il default e resta scritto: senza, `\href` darebbe a un testo **generato dal modello** un modo per iniettare markup.

#### Il formato si decide nel prompt, e lascia una misura in sospeso

Il rendering descritto sopra era tarato su ciò che **gemma4** scrive: prosa e il LaTeX del corpus. Ma il modello è un parametro della richiesta, e uno diverso che rispondesse con una tabella Markdown arriverebbe come pipe letterali sullo schermo. Quindi due righe in `SYSTEM` — prosa piana, niente Markdown né HTML, formule fra `$…$` — che nominano solo i tre formati misurati sui 1200 chunk. Un test tiene la sezione entro quattro righe: l'attenzione del modello serve alle citazioni.

**Markdown pieno è stato valutato e scartato, e non per estetica.** In CommonMark `[2][3]` è un *reference link*: un renderer Markdown standard non disegna due marcatori, cerca una definizione di link chiamata `3`. La forma contigua che il §3.2 impone è esattamente quella che Markdown reinterpreta, e l'unica uscita sarebbe tokenizzare i marcatori **prima** del Markdown — cioè una seconda implementazione del contratto di citazione, che è ciò che il §3.2 esiste per impedire.

Le tabelle sarebbero peggio del disordine che risolvono: la verifica di C-03 è **a livello di frase**, e una riga di tabella non è una frase. Una risposta con una tabella di KPI verrebbe fuori più bella e **meno verificata** — celle senza citazione, o citazioni che il verificatore non sa attribuire. È barattare la prima affermazione del §0 per un bordo. E c'è una ragione di sostanza sotto la meccanica: una tabella generata **fonde** numeri presi da chunk diversi in una struttura che il modello ha inventato, cioè nasconde proprio il punto in cui la tracciabilità si perde.

Il grassetto inline resta possibile in futuro — dieci righe, nessuna dipendenza, `**` non collide con `[n]` — ma va aggiunto come cambiamento **isolato**, con la sua misura: gli asterischi finiscono nel testo che `claims.py` spezza in frasi e che l'NLI giudica. Oggi il guadagno sarebbe comunque piccolo: le risposte misurate sono di due-quattro frasi, e l'unico accento che serve ce l'ha già il marcatore acceso.

> **Debito saldato il 2026-08-21 (D-1/D-2), e il numero è cambiato.** Il test d'ancora aveva fatto ciò per cui era scritto: saltare invece di mentire. Rimisurato col prompt in vigore, `open_ragbench` dopo il parser di C-02 fa **0,9628** — non il 98% di prima, che valeva per `3a50ef63`. L'ancora ora punta alla run nuova e il test non salta più. Dettaglio in fondo, «D-1 e D-2».

#### Provato contro l'API viva

Una query d'oro vera (`open_ragbench`, `top_k 3`), attraverso il proxy:

| | |
|---|---|
| eventi | `chunks` ×1, `token` ×128, `answer` ×1, `citations` ×1, `done` ×1 |
| fonti | 3 chunk dallo stesso documento, score 0,875 / 0,862 / 0,855 |
| citazioni | 3 verdetti, tutti `supported`, 0 frasi non citate |
| tempi | retrieval 4,75 s · generation 19,16 s · verification 6,42 s · **total 30,32 s** |

> **Quei tempi sono a freddo e non vanno confrontati con nessun altro numero.** Era la prima query dopo l'avvio: il retrieval include il caricamento del modello di embedding, la generazione il caricamento dei pesi. A caldo, in U-00, la stessa catena dava primo token a 3,01 s. È la trappola di A-05 per la quarta volta, e la regola che la disinnesca è sempre quella del §15 — un confronto è un confronto solo se i due lati differiscono in **esattamente** una cosa.

Suite Python **1675 test verdi**; `npm run typecheck && npm test && npm run build` verdi.

### U-07 — l'unità del verdetto è la coppia, non il marcatore

Il criterio dice: *«una citazione non verificata da C-03 è distinguibile da una verificata senza aprire nulla, e nessuna delle due è nascosta»*. Sembra una richiesta grafica. Non lo è: contiene una domanda a cui bisogna rispondere prima di disegnare qualsiasi cosa — **dato il `[3]` che sta in mezzo alla risposta, di quale verdetto si tratta?**

Perché l'unità che C-03 misura non è il marcatore, è la **coppia (frase, chunk citato)**. Lo stesso `[3]` può comparire in tre frasi e reggerne due. Un verdetto per marcatore aggregherebbe esattamente la granularità che l'affermazione 1 del §0 esiste per misurare — «la precisione di citazione **a livello di frase** è misurabile» — quindi ogni **occorrenza** nel testo porta il verdetto della frase in cui sta, e due `[3]` nella stessa risposta possono avere due colori diversi.

#### Le frasi non si ritagliano, si ritrovano

Per sapere in quale frase sta un'occorrenza serve sapere dove finiscono le frasi. La strada breve è riscrivere `split_claims` in TypeScript: una regex sul terminatore, dieci righe. È anche precisamente ciò che U-00 vieta — la seconda copia di una regola del backend diverge **in silenzio**, perché nessun test Python guarda dentro `ui/`.

L'API manda già le frasi (`citations[].claim`, `uncited_claims`), quindi il frontend cerca **dove stanno** invece di dove andrebbero tagliate. Se il backend cambia il modo di spezzare, questo modulo continua a dire il vero senza sapere che è cambiato.

Il solo dettaglio del backend che resta necessario conoscere è che quelle frasi arrivano **senza i marcatori** — `strip_markers`, perché il modello NLI non ha mai visto indici fra quadre e non fanno parte di ciò che la frase afferma. Quindi la ricerca avviene su una copia del testo a cui i marcatori sono stati tolti, tenendo una mappa verso le posizioni vere.

| caso | regola |
|---|---|
| marcatore dentro `[da, a)` della frase | il caso normale: `Il valore è 400ms [2][3].` |
| marcatore in un buco fra due frasi | appartiene alla **seguente**: il backend spezza sul bianco *dopo* il terminatore, quindi un `[2]` scritto dopo il punto apre la frase successiva |
| marcatore oltre l'ultima frase | appartiene all'ultima: è la coda di una risposta troncata, senza punto finale |

Le tre righe sono una sola condizione in codice — «la prima frase che finisce dopo di lui» — e non un albero di casi. Una frase che non si ritrova resta `null` e il suo verdetto vive solo sulla scheda: **non si inventa una posizione**, perché un verdetto posato sulla frase sbagliata è peggio di un verdetto che manca.

#### Cinque stati, e nessuno è l'assenza di un altro

È la lezione del §3.5 sui tre significati di una lista vuota, applicata al singolo marcatore.

| stato | quando | veste |
| `inerte` | prima di `answer` | punteggiato, `muted`, nessun glifo |
| `attesa` | testo definitivo, verifica in corso | **accento** + punto |
| `sostenuta` | il chunk sostiene la frase | `ok` + spunta |
| `nonSostiene` | il chunk non la sostiene | `warn` + croce |
| `nonVerificata` | nessun verdetto per questa coppia | `wait` + casella vuota |

`nonVerificata` è lo stato che il criterio nomina per nome, e ha **due cause vere e diverse**: `verify` spento nella richiesta, oppure una frase più corta di `MIN_CLAIM_CHARS` — sotto la quale «il chunk sostiene questo?» non è una domanda con una risposta, e il backend non produce la coppia. Senza questo stato entrambe si leggerebbero come «sostenuta», che è l'errore peggiore possibile qui.

`statoVerifica` risolve un caso che a mano non si nota: fra `citations` e `done`, `verificate` è ancora `false` — arriva con `done` — e leggerlo lì direbbe «non verificata» di una risposta i cui verdetti sono appena arrivati. In quella finestra l'unica prova che la verifica ha girato sono i verdetti stessi.

#### Una divergenza dichiarata dal mockup

Nel mockup un `[1]` verificato resta **accento** (`.mk.viva`) e solo quello che non regge diventa ocra (`.mk.dubbia`). Con cinque stati sullo schermo quella scelta non sta in piedi: un marcatore sostenuto accento e uno non verificato accento sarebbero indistinguibili, cioè il criterio di U-07 mancato. La bozza non modellava lo stato «non verificata», e infatti non aveva il problema.

L'accento resta però fuori dai verdetti veri, come vuole il §12 — *«un verdetto colorato con l'accento smette di essere un verdetto e diventa decorazione»* — e sopravvive dove la domanda non è un verdetto: sul marcatore in `attesa`, dove la domanda è «è un riferimento valido?» e da `answer` in poi la risposta è sì. Nella pastiglia della scheda lo stesso stato è `wait`, perché lì la domanda è «qual è il verdetto?» e non c'è ancora.

#### Glifo, colore e parola insieme, scritti come una tabella

Il §12 lo chiede, e la ragione non è di stile: chi non distingue l'ocra dal verde vedrebbe due pastiglie identiche, e qui la differenza fra le due **è la tesi**. La corrispondenza sta in un `Record` e non in una catena di `if`, così aggiungere uno stato significa aggiungere una riga con tutte e tre le cose — non esiste il caso di uno stato che ha il colore e non la parola.

Sul marcatore in mezzo alla prosa ci stanno solo i primi due; la parola sta nell'`aria-label` (per chi ascolta, glifo e colore non arrivano: la parola è l'unica cosa che resta) e nel **riepilogo sotto la risposta**, che nomina i marcatori che non reggono e conta le frasi scoperte. Il glifo del riepilogo è lo stesso che sta sul marcatore, così quella frase fa anche da legenda senza esserne una.

E l'ultima riga del riepilogo è la tesi, nell'interfaccia e non solo nel README: *una citazione che non regge è il dato, non un errore, e la precisione si alza citando di meno.* Senza scriverlo, un fondo ocra si legge come un guasto — l'esatto contrario di ciò che U-07 esiste per dire. Per la stessa ragione `warn` non è rosso, ed è una decisione già scritta in `index.css` da U-00.

#### Il numero accanto alla parola cambia con quante frasi citano la fonte

Con **una** citazione è il punteggio di implicazione: un «non sostiene» a 0,49 e uno a 0,02 sono due cose diverse, e senza il numero il verdetto sembra categorico dove invece c'è una soglia. Con **più** citazioni è il conteggio, perché allora il punteggio riguarda una frase sola e mostrarlo da solo farebbe credere che riguardi tutte.

Quando i verdetti sulla stessa fonte non concordano la pastiglia dice `misto` col conteggio — `1 su 3 non sostiene` — e non una media: una media di verdetti opposti non dice niente. È anche il caso che dimostra perché il glifo da solo non basta, e infatti `misto` porta la croce (qualcosa non regge, e non va attenuato) mentre la distinzione la fa la parola.

**«Non citata» non è un verdetto** e non va colorata come tale: è un chunk che il recupero ha portato e che la risposta non ha usato. Resta nel pannello — U-02 vuole le fonti visibili in ogni stato — ma dire «sostiene» o «non sostiene» di qualcosa che nessuno ha affermato sarebbe inventare un giudizio.

#### Due cose che si sono spostate

**Le frasi senza citazione sono uscite dal pannello fonti** e sono tornate dove stanno: sottolineate nella risposta. U-02 le aveva messe in fondo alla colonna perché non c'era un altro posto, ma una frase che non cita niente non è una fonte, e in 272 px prendeva lo spazio delle fonti vere. Nel testo si legge **dove** manca la citazione, che è l'unica cosa che serve saperne.

**`segmenta` ora dice anche da dove viene ogni segmento.** Non era un extra rimandabile: annotare il testo vuol dire posare qualcosa su una posizione, e l'offset **non era ricostruibile da fuori** — un segmento `inline` può venire da `$…$` (due caratteri di delimitatore) o da `\(…\)` (quattro), quindi chi riceve i segmenti non può sommare le lunghezze. Lo sa solo chi ha tagliato. È entrato come refactor puro: 78 test, gli stessi di prima, con le posizioni asserite invece che dedotte.

L'ordine fra i due passaggi è deciso e conta: **`segmenta` prima, annotazione dentro i suoi pezzi.** Al contrario, un `$x[3]$` — un indice fra quadre dentro una formula, che in un corpus di paper esiste — verrebbe spezzato a metà e la formula non si comporrebbe più. La matematica ha la precedenza perché un suo errore rompe il disegno, mentre un marcatore mancato resta leggibile.

#### Il verdetto NLI da solo era il verdetto sbagliato su `ledger`

Questo non era nel piano: è uscito dalla prova dal vivo, ed è la ragione per cui la prova dal vivo si fa.

Alla domanda sul capex di Sherwin-Williams il verdetto era `non sostiene`, punteggio 0,208. Stampando anche il campo `numeric` — che c'è nel contratto dal §3.5 e che la pastiglia non guardava:

| | NLI (C-03) | numerico (C-09) |
| `ledger`, capex Sherwin-Williams | **non sostiene** 0,208 | **sostiene** |
| `open_ragbench`, RMSE `[1]` | non sostiene 0,467 | `not_applicable` |
| `open_ragbench`, RMSE `[2]` | non sostiene 0,183 | `not_applicable` |

Il 222,8 **sta nella tabella citata**. Il verdetto NLI è sbagliato, e lo è per una ragione già scritta in `entailment.py`: su `ledger` **il 96,7% dei claim è numerico**, e un modello NLI addestrato su prosa non verifica un'asserzione numerica contro una tabella. È letteralmente perché C-09 esiste.

Quindi mostrare solo `supported` avrebbe dato per verdetto ciò che il progetto stesso documenta come debole lì — su metà dei dataset, e nel punto dove U-07 promette che il verdetto si legge senza aprire niente. Non è ampliamento di scopo: è il criterio.

**Si mostrano entrambi**, che è anche ciò che `schema.py` dichiara del campo (*additivo, non sostituisce `supported`*). Due pastiglie, non una scelta fra le due: scegliere sarebbe decidere in codice quale verificatore ha ragione, e quella è una misura, non un `if`.

- La seconda pastiglia **non porta un punteggio**: C-09 confronta cifre, non produce una probabilità, e uno 0 direbbe il falso.
- `not_applicable` **non produce nessuna pastiglia**: è il caso normale su un corpus di paper, e un'etichetta che compare quasi sempre non informa.
- La parola dice **cosa ha guardato** — «la tabella lo conferma» — e non il nome del verificatore: «numerico» richiederebbe una legenda, la tabella no.

E cambia il **titolo** del riepilogo. Se tutte le non sostenute sono confermate dal numerico, «non tutte le citazioni reggono» è la frase sbagliata: non è la citazione a non reggere, sono i due verificatori a non concordare. Il titolo diventa quello, il tono passa da attenzione a neutro, e il glifo è un `≠`. Un titolo che dicesse il contrario metterebbe in bocca all'interfaccia un giudizio che il progetto ha già misurato falso.

#### Provato contro l'API viva, sui due corpus

Non per vedere se disegna: per verificare che il presupposto del ritrovamento — *la frase che l'API manda è una sottostringa del testo, a marcatori tolti* — sia vero su ciò che Gemma scrive davvero e non solo nei casi che ho scritto io.

| | `open_ragbench` | `ledger` |
| risposta | 2 frasi, 2 marcatori | 1 frase, 1 marcatore |
| coppie verificate | 2 | 1 |
| frasi ritrovate nel testo | **2 / 2** | **1 / 1** |
| verdetti NLI | `[1]` non sostiene 0,467 · `[2]` non sostiene 0,183 | `[5]` non sostiene 0,208 |
| verdetti numerici (C-09) | `not_applicable` su entrambe | **`sostiene`** — e vedi sopra |
| tempi | retrieval 4,06 s · generation 19,33 s · verification 5,93 s | retrieval 0,17 s · generation 15,89 s · verification 9,05 s |

> **La prima riga di tempi è a freddo, la seconda a caldo, e non si confrontano.** Il retrieval a 4,06 s include il caricamento del modello di embedding; a caldo la stessa domanda costa 0,17 s. È la trappola di A-05 per la quinta volta.

Il caso `ledger` è più interessante di quanto sembri: la risposta è `... were $(222.8)$ million dollars [5].` — il modello riecheggia i delimitatori Mathpix del documento attorno a una cifra di bilancio. La frase citata attraversa quindi una formula, il testo si spezza in tre segmenti, e il `[5]` sta nell'ultimo: lo span della frase si ritaglia sui segmenti e il verdetto arriva dove deve. Era il caso che la macchinaria dei ritagli esisteva per non sbagliare.

E i dati sono anche una piccola dimostrazione della tesi del §0: delle tre citazioni prodotte dal vivo **nessuna regge secondo l'NLI**, con punteggi fra 0,18 e 0,47 — e una delle tre regge invece secondo il verificatore numerico. Sono i numeri che C-01 misura in grande, visibili sullo schermo senza aprire niente, e il disaccordo fra i due verificatori è visibile insieme a loro: che è precisamente ciò che U-07 chiedeva, e un po' più di quanto chiedesse.

`npm run typecheck && npm test && npm run build` verdi, **116 test Vitest**.

### U-13 — «sopravvive a un ricaricamento» non è la stessa cosa di «la lettura sopravvive»

Il criterio chiede due cose e mezza: cominciare una conversazione nuova senza ricaricare, una cronologia che sopravvive al ricaricamento, e la **dichiarazione** che è locale a questo browser. La terza è quella che si dimentica, perché è la sola che non si nota mancando.

**Dove sta la dichiarazione.** Prima era una riga sotto l'elenco, «Solo in questo browser.», e alla revisione era il rilievo giusto: vera, e scollegata da ciò di cui parlava — una frase che comincia con «solo» non dice *cosa* sta solo qui. Adesso la sezione si chiama **«Cronologia locale»** e il suggerimento sul nome porta la frase intera. Il criterio resta soddisfatto perché la parola è sempre sullo schermo — dichiarata, non dedotta — e la spiegazione non occupa cinque righe di una corsia larga 200 px.

**Quale conversazione era aperta non si ricorda, ed è la correzione più interessante delle tre revisioni.** L'avevo salvata (un campo `corrente`) ragionando che altrimenti la cronologia sopravvive al ricaricamento ma la lettura no. Marco l'ha ribaltata, e ha ragione: chi apre `ibid` lo fa per **chiedere qualcosa**, quindi ritrovarsi in fondo a una conversazione di ieri mette un clic davanti al caso frequente per risparmiarne uno a quello raro. Ora si riapre sempre su una conversazione nuova, e tornare indietro è una voce della corsia.

Il campo non viene più scritto invece di essere scritto e ignorato — un dato che nessuno rilegge invecchia peggio di un dato assente — e **non è servita una `VERSIONE` nuova**: un deposito più vecchio porta ancora `corrente`, che viene ignorato senza far scartare niente. È la stessa proprietà per cui la versione esiste solo per le rotture vere, e questa è la prima volta che si è vista funzionare.

**Una risposta rimasta a metà torna sigillata.** Chiudendo la scheda durante gli ~11 s di generazione, nel deposito c'è `fase: "scrittura"`: al ricaricamento il pallino pulserebbe per sempre in attesa di uno stream che non esiste più. `interrompi` la porta dove sta «Ferma» — lo stream è finito senza che il server dicesse niente, il parziale resta, e il «Riprova» che U-02 aveva già scritto per l'altro caso funziona anche per questo.

Non è teorico: la scrittura è ritardata di 400 ms, e il retrieval da solo ne prende ~0,3 s, quindi **la domanda finisce nel deposito prima del primo token**. Chiudendo a metà si ritrova la domanda, non un buco.

| quando si scrive | perché |
|---|---|
| 400 ms dopo l'ultimo cambiamento | durante la generazione lo stato cambia a ogni token: scrivere subito serializzerebbe tutta la cronologia ~30 volte al secondo |
| non durante lo stream | i token arrivano più vicini del ritardo, quindi una risposta costa **una** scrittura, quella che parte quando smettono |

**Un campo aggiunto dopo prende il suo default.** Le risposte salvate si rileggono come `{ ...inizio(), ...salvata }`. `Risposta` cresce a ogni task — U-05 la targhetta pipeline, U-06 i link profondi — e un numero di versione che scartasse la cronologia a ogni campo nuovo la scarterebbe praticamente sempre. `VERSIONE` resta per una rottura vera, cioè un campo che cambia significato. I quattro controlli di tipo dopo la fusione non sono paranoia generica: sono esattamente i campi su cui l'interfaccia **itera**, e un `chunks` che non è un array fa cadere il pannello fonti.

**Se non ci sta, si scrive meno.** `localStorage` solleva `QuotaExceededError` quando l'origine è piena, e ignorarlo darebbe una cronologia che da un certo punto in poi non cambia più: le conversazioni nuove sparirebbero a ogni ricaricamento senza un motivo visibile. Si sacrificano le più vecchie, che è ciò che il tetto di venti fa comunque, solo prima del previsto. Uno scambio porta con sé **le fonti intere** — è ciò che rende un pannello fonti ricostruibile invece di vuoto — quindi si misura in decine di KB.

#### Il pulsante che il ROADMAP chiede è una voce dell'elenco

Il §12 elenca «pulsante Nuova conversazione, elenco delle conversazioni». Il mockup invece mette *«Nuova conversazione» come prima voce attiva della cronologia*, e l'ho consegnata così — un pulsante che dice «Nuova conversazione» sopra una voce attiva che dice «Nuova conversazione» sono due controlli con le stesse parole, uno sull'altro.

**Alla revisione era il difetto opposto** (Marco, 2026-08-17): come riga era leggibile ma piatta, e la voce più usata della corsia aveva lo stesso peso della meno usata. Ha quindi la forma delle azioni della corsia, quella che nel mockup ha «Esplora il corpus» (`.bottone-esplora`): accento su fondo accento tenue, e al passaggio si riempie d'accento come il bottone d'invio della chat — la forma diceva che era un comando, ma restava immobile sotto il puntatore, che è ciò che fa dubitare che sia cliccabile. E il timore che l'aveva resa una voce sparisce da sé — con la forma di un'azione non è più una voce, quindi la conversazione vuota non ne ha una e non c'è niente da confondere. Il `+` resta, ed è ciò che la distinguerà da «Esplora il corpus» quando saranno una sopra l'altra.

Una conversazione vuota non si ricorda comunque: nel deposito non finiscono conversazioni senza domande, quindi la cronologia non si riempie di righe senza nome.

#### Le voci non sono `disabled`, e non è una svista

Non si cambia stanza mentre il modello parla: lo stream scrive in **una** conversazione, e andarsene lascerebbe dei token ad arrivare in una stanza che nessuno sta guardando. La via d'uscita c'è e si vede — è «Ferma», e lascia il parziale dov'è.

Ma un elemento `disabled` non riceve gli eventi del puntatore, quindi il suggerimento che spiega *perché* non risponde non si aprirebbe: cioè l'unica informazione utile in quei secondi. Le voci restano quindi bottoni veri con `aria-disabled`, il tono attenuato, e la guardia vera nel provider — dove sta anche il resto della regola «una generazione per volta».

#### Due cose decise qui e non dal criterio

**Riaprendo si torna anche sul corpus.** Il `dataset_id` della prima domanda viaggia con la conversazione: senza, la domanda seguente in un filo su `ledger` cadrebbe su `open_ragbench` perché il selettore era rimasto lì, e nel filo non ci sarebbe niente a dirlo. Non si aggiorna mai dopo la prima: riscriverlo direbbe che risposte già date vengono da un corpus che non le ha prodotte.

**Cancellare la cronologia c'è, e a due tempi.** Non era nel criterio né nel mockup, e l'avevo lasciata come debito dichiarato — poi la prima cosa che è servita provando è stata togliere quaranta conversazioni di test, che senza un comando si toglievano solo svuotando `localStorage` dal browser. Non un `confirm()` del browser (colori del sistema operativo in mezzo a un'interfaccia che ha i propri: lo stesso difetto del `title` nativo) e non un clic solo, perché non c'è nessun server che ne tenga una copia — è precisamente ciò che «locale» significa. Il secondo clic entro quattro secondi, poi il comando si disarma da sé. Va via anche la conversazione aperta: cancellare tutto tranne l'unica cosa visibile non sarebbe cancellare tutto.

**E il rosso è entrato nella palette** (seconda revisione), che finora non ce l'aveva: `danger` non è un `warn` più acceso, è il colore di ciò che distrugge. Colorare «cancella» con l'ocra dei verdetti avrebbe dato lo stesso segnale a un rilievo — una citazione che non regge, che il §0 dice essere il dato — e a un'azione irreversibile. È l'unico posto dove compare. Il comando è un cestino disegnato con le cinque regole di `Icona.tsx`, solo icona col nome nell'`aria-label`, e quando è armato la domanda «Cancellare tutto?» prende il posto del nome della sezione: un'icona che cambia colore dice che è cambiato qualcosa, non cosa.

`npm run typecheck && npm test && npm run build` verdi, **147 test Vitest**.

### U-03 — la barra intera, e un confronto che cambia una cosa sola

Il ROADMAP dava a U-03 un solo controllo. Contandoli, il mockup ne mette **cinque**
sotto il campo e solo due avevano un ID: RAG (U-03) e il prompt del baseline (U-04).
Ragionamento, menu dei modelli e «Avanzate» stavano nel disegno, nelle decisioni del
§12 e persino nell'API — `reasoning_effort` e `models` esistono perché A-07 li ha
aggiunti *guardando questa barra* — ma in nessun posto con un criterio. È la situazione
della cronologia prima che diventasse U-13, e sono stati accorpati qui (2026-08-19):
la barra la costruisce U-03, ed è il primo task che ne ha bisogno.

#### Il confronto è un layout, e il §15 dentro l'interfaccia

«Affiancate, dalla stessa query, nella stessa sessione» non si ottiene con due messaggi
consecutivi: si leggono uno dopo l'altro, e la domanda in mezzo si dimentica. Il toggle
della barra decide la **prossima** domanda; il confronto è un'azione su una risposta
**già data**, che la rilancia col RAG invertito.

Da cosa riparte è la decisione che conta. Non dalla barra — rilanciare con le opzioni
correnti metterebbe nelle due colonne anche un modello diverso o un `top_k` cambiato nel
frattempo, e il confronto direbbe «guarda cosa fa il RAG» mostrando l'effetto di tre
cose. Riparte da `ConfigView`, cioè da ciò che ha girato, e inverte un campo solo.

Il test conta le chiavi: `Object.keys(stessaConfigurazione(c))` deve coincidere con
`Object.keys(c)`. Un campo aggiunto al contratto e dimenticato lì uscirebbe dal
confronto **in silenzio**, cioè diventerebbe esattamente la seconda variabile che quella
funzione esiste per impedire.

Ne segue che il comando compare solo su una risposta **conclusa**: da che parte va
ciascuna colonna lo dice `config.rag`, e senza `config` non si saprebbe da quale braccio
si parte. Una colonna intitolata a caso è peggio di un comando assente.

#### La colonna nuda non dice «sbagliato»

Il mockup ci aveva scritto «Plausibile, e sbagliato». È vero del suo esempio e non di
ogni risposta: senza fonti non si può *sapere* se è giusta — ed è esattamente il punto.
L'avviso dice ciò che si sa, cioè che non c'è niente da aprire.

Nel confronto il pannello fonti laterale sparisce e le fonti stanno **dentro** la
colonna. Non è un'eccezione al criterio di U-02: averle da una parte e non dall'altra è
l'argomento della schermata, e una colonna sola di fianco mostrerebbe le fonti di uno
dei due bracci senza dire di quale.

#### «Come configurato» era un'opzione, ed è stato l'errore della prima stesura

Ogni menu si apriva su una voce «come configurato» che significava *non lo mando,
decidi tu*. Il ragionamento sembrava solido: `Capabilities` elenca i valori **ammessi**
e non quelli **configurati**, quindi preselezionare il primo dell'elenco avrebbe scritto
sopra la scelta del deployment una scelta che nessuno aveva fatto — e l'ordine è
alfabetico, quindi il primo non ha rapporto con niente.

Marco l'ha rifiutato alla revisione: il default dev'essere **una delle opzioni vere**,
selezionata e marcata. Aveva ragione, e la conclusione è più secca di quanto sembri: il
servizio quei valori li pubblica. `GET /config` restituisce l'intero `ConfigView` in
vigore, esiste da A-04, ed **era già nel client** (`api.config`, scritta in U-00) senza
che nessuno la chiamasse. L'interfaccia dichiarava di non sapere una cosa che aveva a
disposizione.

Non è servito toccare il contratto — il che è rilevante, perché un campo nuovo in
`Capabilities` sarebbe stata una modifica a `src/api/` dentro un task U-xx, cioè la
violazione che A-07 esiste per aver evitato.

Ne segue una semplificazione invece di una complicazione: **tutto parte esplicito**,
l'eccezione non esiste più. E ciò che è stato spostato dal predefinito diventa accento,
che è l'unica cosa che «Avanzate» chiuso poteva nascondere.

Elenco modelli vuoto ≠ elenco assente: A-07 restituisce `[]` quando non raggiunge
`LLM_BASE_URL`. Ma il **nome** del modello configurato si sa lo stesso, da `/config`, e
la pastiglia attenuata lo porta dentro: ciò che manca non è sapere chi risponde, è
poterlo cambiare. Attenuata e non `disabled`, che non riceve il puntatore e chiuderebbe
la bolla che spiega: la lezione delle voci di cronologia in U-13.

#### I due numerici non sono campi, sono manopole

`top_k` e `hnsw_ef` erano due `<input type="number">`. Le frecce native sono diverse su
ogni browser, non appartengono al vocabolario di pillole della barra, e lasciavano
scrivere un campo **vuoto** — uno stato che il valore non ha. Ora sono una pastiglia con
− e +, cifre in mono, e il segno che riporta al predefinito quando ci si è allontanati:
una manopola senza ritorno costringe a ricordare da dove si era partiti, che è
esattamente ciò che «marcato come predefinito» esiste per evitare.

`null` resta raggiungibile solo dove è un valore vero: `hnsw_ef` non impostato significa
lasciar decidere l'indice, ed è il predefinito di questo servizio — si legge `auto`, non
uno spazio bianco.

#### Il ragionamento è l'unico comando che dichiara il proprio costo

Acceso/spento e non cinque livelli — cinque livelli sono un'ablation, cioè il lavoro
della dashboard — e i due capi sono quelli su cui **C-07 ha misurato**, `none` e `high`,
perché il suggerimento porta i numeri di quella misura e un interruttore che mandasse un
livello diverso li farebbe descrivere un'altra cosa. Sul modello l'asse è davvero
binario: `low` produce già lo stesso ragionamento di `high` (1410 token contro 267).

Parte **spento**, e per una volta il predefinito non è «il modo migliore» ma il modo
misurato: acceso compra +0,6 punti di conformità pagando 9,5× i token e trentaquattro
astensioni in più su 200. Il suggerimento lo scrive. Sta lì perché il progetto misura
anche ciò che non conviene, e nasconderlo dietro un interruttore muto sarebbe la prima
volta che una misura resta fuori dalla UI perché è scomoda.

I due valori sono del server e stanno scritti nel frontend, quindi hanno la verifica
accanto: se `Capabilities` smette di offrirli il comando **sparisce** invece di mandare
un 422 — un guasto nostro presentato come un errore di chi clicca.

#### Niente della barra si ricorda oltre la sessione

È l'unica decisione di stato che la barra contiene. Il dataset si ricorda perché è una
preferenza — su quale corpus sto lavorando. «RAG spento, `top_k` 20, ragionamento
acceso» non è una preferenza, è un **esperimento**, e ritrovarlo ancora impostato domani
è il modo in cui un risultato si legge come il prodotto. Un ricaricamento riporta la
barra al modo in cui il progetto è pensato per funzionare, che è anche quello in cui è
stato misurato. Stessa lettura di U-13: il caso frequente vince sul raro.

`npm run typecheck && npm test && npm run build` verdi, **155 test Vitest**. Una revisione.

### U-14 — la regola sul formato si rovescia, e il markdown entra come intervalli

Nato da una domanda di Marco (2026-08-19): col RAG spento gemma4 tende a scrivere
in markdown — meglio tenerlo anche col RAG acceso, o sopprimerlo?

La domanda conteneva una premessa da correggere: **la UI non aveva mai reso il
markdown.** `Testo.tsx` disegnava LaTeX con KaTeX e i marcatori di citazione,
niente altro, quindi col RAG spento sullo schermo comparivano gli asterischi
crudi. Non c'era una caratteristica da tenere: c'era da decidere cosa farne.

#### Perché i due bracci differivano

Non il modello: il prompt. `SYSTEM` (RAG acceso) diceva *«Plain prose: no Markdown
headings, lists, tables or bold»*; `BASELINE_A_SYSTEM` (RAG spento) è di due righe
e una regola di formato non l'ha mai avuta.

Il divieto da un lato solo rendeva il confronto di U-03 **una schermata a due
variabili**: la colonna con le fonti in prosa piana per contratto, quella nuda
libera di formattare. È esattamente ciò che il §15 vieta, e non me ne ero accorto
costruendola.

#### La regola non è cambiata, è cambiato ciò che decideva

`prompt.py` dice *«il formato si decide qui, non si osserva nella UI»*, e quella
regola resta — è anzi la ragione del rovesciamento. La prosa piana era stata
scelta perché era ciò che il renderer sapeva disegnare, cioè decidendo un
contratto **da ciò che il consumatore supporta**: l'inverso della regola sotto cui
era stata scritta.

E l'avvertimento ipotetico che quel file portava — *«un modello più grande che
rispondesse con una tabella Markdown arriverebbe come pipe letterali»* — non è più
ipotetico da quando U-03 ha messo il menu dei modelli sullo schermo.

L'HTML resta vietato, e non per simmetria: il 39% di `ledger` porta tabelle HTML
di Mathpix, la UI non disegna markup che non ha analizzato lei, e un tag
riecheggiato nella risposta sarebbe una decisione sull'iniezione, non sulla
tipografia. Stessa ragione per cui i link non si rendono: un riferimento che
nessuno può aprire, dentro una risposta senza fonti verificabili, è l'opposto
della tesi.

#### Il vincolo che decide tutta la forma del codice

I verdetti per frase e le frasi scoperte arrivano dal backend come **posizioni
dentro ciò che il modello ha scritto**, e la matematica è già segmentata sugli
stessi offset. Un parser che restituisse una stringa ripulita — senza asterischi,
senza cancelletti — sposterebbe ogni indice a valle del primo simbolo tolto, e la
sottolineatura di «questa frase non cita niente» finirebbe su un'altra frase. Un
errore invisibile in revisione e sistematico in esecuzione.

Quindi `markdown.ts` non toglie niente: dice **dove** c'è enfasi, **dove** i
caratteri di sintassi vanno nascosti, e come il testo si divide in blocchi. I
caratteri spariscono per ultimi, in `visibili`, quando ogni altro intervallo è già
stato calcolato.

Due precedenze che a mano si sbagliano, e hanno il loro test: il codice vince
sull'enfasi (dentro `` `a*b*c` `` gli asterischi sono un identificatore), e
l'underscore vale solo fra confini di parola (`dataset_id` non è un corsivo — in
un corpus di paper e bilanci quegli identificatori ci sono davvero). E un test
fissa che `**[2]**` lascia `[2]` intatto: il §3.2 è la prima affermazione del §0,
e il grassetto non deve nasconderlo.

#### I titoli non crescono di corpo

Un `##` reso come un titolo grande darebbe alla risposta **senza fonti** una
gerarchia visiva che quella con le fonti non ha — e il confronto di U-03 esiste
per mettere in dubbio proprio quella colonna. Rendere il markdown ha un costo che
va nominato: grassetti ed elenchi puliti fanno sembrare più autorevole l'unica
risposta che nessuno può verificare. Si paga in parte togliendo la gerarchia: un
titolo si legge come tale per peso e spaziatura, non per dimensione.

#### Il debito, dichiarato

Cambiare `SYSTEM` cambia `prompt_hash`: le **17 run di citazioni** a disco (2 hash
distinti) smettono di essere confrontabili con quelle successive. È il lavoro di
quel campo — rendere visibile una rottura che altrimenti sarebbe silenziosa — e
C-01, C-02 e C-07 si rimisurano a interfaccia finita, per decisione di Marco.
`baseline_prompts.py` non è toccato: non ha mai avuto una regola di formato,
quindi è già «invitato», ed E-04/E-05 restano confrontabili.

**Cosa non è provato**, e va detto: il livello puro ha 15 test suoi, ma la
composizione fra markdown, marcatori e verdetti non è verificata da un test —
`ui/` non ha jsdom, per scelta di U-00. Si guarda a schermo.

> **Saldato il 2026-08-24 (D-8).** La composizione è uscita da `Testo.tsx` in
> `composizione.ts`, che restituisce una lista di pezzi invece di nodi e quindi
> ha 18 test suoi. U-00 non è stata riaperta: quello che si prova è **quali
> pezzi, dove, con che veste**; le classi e KaTeX restano un giudizio a schermo.
> In fondo a questo quaderno, in *D-8*.

`npm run typecheck && npm test && npm run build` verdi, **172 test Vitest**;
1678 test Python passano col prompt nuovo.

### U-15 — la configurazione era già salvata, mancava di essere letta

Proposto da Marco (2026-08-19): le conversazioni dovrebbero ricordare anche i
parametri con cui sono state lanciate, e fra una domanda e l'altra dovrebbe
vedersi cosa è cambiato — come una nota che «si vede a malapena», col peso di
«Invio per mandare».

**Il dato c'era già, e non da oggi.** `Risposta.config` porta il `ConfigView`
che ha *davvero* girato — non quello chiesto — e arriva con l'evento `done` del
§3.5; `cronologia.ts` lo serializza da U-13 senza che nessuno l'avesse messo lì
per questo. Nessun campo nuovo nel contratto, nessuno nel deposito, nessuna
`VERSIONE` da alzare: mancava solo di essere mostrato.

È la **seconda volta in due giorni** che la cosa da fare era chiedere a un dato
che c'era già: la prima è stata `/config` in U-03, che era nel client dai tempi
di U-00 senza che nessuno lo chiamasse. Vale la pena notarlo come abitudine da
prendere — prima di aggiungere un campo, guardare cosa il contratto già dice.

Ora che quel giro è visibile ha anche un test invece di essere vero per caso:
`cronologia.test.ts` verifica che `config` sopravviva a serializzazione e
rilettura.

#### Si mostra la differenza, non la configurazione

Quattordici campi ripetuti sotto ogni domanda sarebbero un muro che nessuno
legge, e ciò che serve sapere è *cosa è cambiato da prima*. La prima riga di una
conversazione si confronta con i **predefiniti del servizio**, che `/config`
pubblica: una conversazione in cui non si è toccato niente lo dice in tre parole
invece che in quattordici.

E la prima riga dice **con cosa è partita**, non da cosa si è allontanata:
`partita con rag no · top_k 12` si legge, `partita con rag sì → no` no — è una
freccia che punta a un valore che quella conversazione non ha mai avuto. Che i
campi siano elencati *è* già il segnale che differiscono dai predefiniti. Le
righe successive tengono la freccia, perché lì il valore di prima c'è stato.

#### La differenza copre tutto il contratto, non i controlli della barra

Un parametro cambiato lato server fra due domande è esattamente ciò che questa
riga esiste per non far sparire. Prendere le chiavi da `dopo` la rende
automatica: un campo aggiunto domani a `ConfigView` compare da solo, senza che
nessuno debba ricordarsi di aggiungerlo anche qui.

I nomi dei campi restano quelli del server — `retrieval_mode`, `top_k` —
esattamente come i tempi nella riga di stato: tradurli vorrebbe dire tenere un
elenco di chiavi del backend nel frontend, e una chiave nuova comparirebbe senza
nome.

#### Tre casi che a mano si sbagliano

| caso | cosa fa | perché |
| `config` assente | non scrive niente | interrotta, caduta o in corso: `config` viene con `done`. «Non si sa cosa ha girato» non è «non è cambiato niente», e tacere è l'unico dei due che non afferma il falso |
| una risposta interrotta **in mezzo** | il confronto la salta all'indietro | un «Ferma» non ha toccato nessun parametro: dire «tutto cambiato» dopo quel gesto sarebbe falso |
| nessuna differenza | non c'è riga (tranne la prima) | una nota che c'è sempre smette di essere letta — la stessa regola del riepilogo dei verdetti |

#### La riga compare premendo invio, non a generazione finita

Prima correzione di Marco. `Risposta.config` dice cosa ha girato e arriva con
`done`, cioè dopo ~11 s: la riga compariva quindi solo a cose fatte, e diceva
cosa era cambiato **dopo** che la risposta l'aveva già subito.

Ma cosa è stato **chiesto** si sa nell'istante in cui si preme invio.
`Scambio.chiesto` lo porta, ed è un secondo campo e non una sostituzione: quasi
sempre i due coincidono, e quando non coincidono è il server ad aver deciso
altrimenti — un fatto che si vuole poter vedere, non appianare. Si mostra
`config` appena c'è e `chiesto` nel frattempo, quindi al passaggio non si vede
niente.

**`campiRichiesta` è derivata da `configChiesta`, non parallela**, ed è la parte
che conta: ciò che si mostra come chiesto e ciò che parte sul filo sono lo stesso
oggetto letto due volte. Due funzioni separate si sarebbero allontanate al primo
campo aggiunto alla barra, e la riga avrebbe dichiarato una configurazione
diversa da quella mandata — un errore che nessuno vedrebbe, perché il valore
sbagliato sarebbe *plausibile*. Un test lo fissa campo per campo.

Un deposito scritto prima non ha `chiesto`: vale `null`, la riga tace, nessuna
`VERSIONE` da alzare.

#### Il peso è quello di una nota a margine

Mono, 10 px, attenuato, sopra la domanda. **Non è un messaggio della
conversazione**: non ha bolla né mittente, perché non l'ha detto nessuno — è una
nota su come è stata prodotta la riga sotto. Un riquadro di sistema fra due
domande spezzerebbe la lettura del filo per dire una cosa che nel caso comune è
«niente è cambiato».

Sopra la domanda e non sotto la risposta: dice con cosa quella domanda è stata
eseguita, e leggerlo dopo averne letto l'esito sarebbe scoprire le regole a
partita finita. La configurazione **intera** sta nel suggerimento, che è il posto
dove la si va a cercare — ed è un dato, quindi si apre subito (140 ms).

`npm run typecheck && npm test && npm run build` verdi, **183 test Vitest**.

### U-16 — due manopole sopra un nome solo

> **Aggiornamento del 2026-08-24: le manopole sono tornate una.** Con A-09 la
> finestra di contesto non è più una scelta dell'interfaccia — la decide il
> motore, da come è avviato — quindi il secondo selettore è stato **tolto**, e
> con lui `catalogo.ts` e i suoi 21 test: il menu dei modelli elenca ora ciò che
> il motore elenca, senza raggruppare per genitore. Quello che resta di questa
> sezione descrive un comando che non c'è più; si tiene perché il ragionamento
> sul *perché* non si deducono i nomi resta valido, ed è la ragione per cui
> togliere quel codice non ha lasciato buchi. Dove la cosa si dice a chi guarda:
> il suggerimento del menu dei modelli, e un limite in più nella pagina «Che
> cos'è» — *«quanto testo entra nel modello non lo decide ibid»*.

Chi usa la demo sceglie **il modello** e **quanto contesto**, indipendentemente,
perché sono due domande diverse: *chi risponde* e *quanto testo gli entra*. Che
sotto la coppia sia un singolo nome nel catalogo di Ollama è un dettaglio
dell'implementazione, e non affiora: il primo selettore elenca `gemma4:e2b`, non
`gemma4:e2b-8k` accanto a `gemma4:e2b-32k`.

**Il raggruppamento non interpreta i nomi.** Ogni voce derivata porta il proprio
`parent`, che il motore dichiara (A-08). Dedurre `gemma4-8k` → `gemma4`
spezzando una stringa sarebbe una convenzione dentro l'interfaccia, e le
convenzioni si rompono il giorno in cui qualcuno chiama un modello diversamente
— c'è un test con una taglia chiamata `taglia-corta`, cioè un nome che nessuna
convenzione riconoscerebbe.

Attenzione a una trappola vicina: **raggruppare per `family` sarebbe sbagliato**.
`gemma4:e2b` e `gemma4:12b` hanno la stessa famiglia e sono due modelli diversi;
per famiglia si sarebbero fusi in una voce sola.

#### Il secondo selettore compare solo quando c'è una scelta

Se quel modello ha una finestra sola — perché nessuno ne ha create altre, o
perché il motore non pubblica il catalogo — un menu da una voce non è un
controllo: è un'etichetta che gli assomiglia. Sparisce, come sparisce il
ragionamento quando l'asse non c'è.

E senza catalogo si continua a scegliere il modello: `daNomi` costruisce la
stessa forma dalla lista piatta. Su un server più vecchio di A-08, o su un motore
che non è Ollama, si perde la scelta della finestra e non quella del modello.

**Le taglie offerte sono solo quelle che il modello regge.** Il massimo non è uno
solo — 131.072 per `gemma4:e2b`, 262.144 per `gemma4:12b` — quindi non esiste una
lista valida per tutti. Una taglia che compare e poi fallisce è peggio di una che
non compare: fa scoprire il limite dopo l'attesa, e per giunta come un errore
invece che come un vincolo. Senza un massimo noto si offre tutto, perché
nascondere per un limite non dichiarato sarebbe inventare un vincolo.

#### Cambiare modello tiene la finestra

Chi confronta due modelli sulla stessa domanda sta cambiando **una** cosa:
ripartire dal default gliene cambierebbe due sotto le mani, che è il §15 rotto
dentro un menu. `conModello` sceglie la finestra più vicina a quella che si
aveva fra quelle che il nuovo modello ha.

#### Chi crea le taglie

`scripts/model_sizes.py`, e non un campo della richiesta — la ragione è misurata
in A-08. Riceve le taglie, non le indovina: restringerle a quelle che la macchina
regge è **X-05**, rinviato di proposito. Rifiuta una taglia oltre il massimo
dell'architettura, perché altrimenti la creerebbe e il menu non la mostrerebbe,
lasciandola invisibile e non spiegata.

Il suffisso `-8k` è per chi legge `ollama list`, **non** per il programma: il
raggruppamento passa da `parent_model`. Se fosse il nome a decidere, rinominare
un modello a mano lo scollegherebbe dal suo gruppo in silenzio.

Provato per intero: `262144` su `gemma4:e2b` viene rifiutato (regge 131.072),
`8192` crea `gemma4:e2b-8k`, e il catalogo lo rilegge con `parent='gemma4:e2b'` e
`context=8192`. `ollama create` da un modello già scaricato riusa i blob, quindi
non scarica e non duplica i pesi.

**198 test Vitest** (15 nuovi sul catalogo), 1699 Python, typecheck e build verdi.

#### Cinque correzioni alla revisione, e la piu' utile e' la prima

**«L'utente non dovrebbe occuparsi di questo.»** Le taglie sono modelli derivati,
e chiedere a chi guarda di crearli significava che il selettore non esisteva
finché non aveva letto la documentazione giusta. `--assicura` è idempotente e la
chiama `scripts/dev.py` a ogni avvio. **Non la chiama il servizio**, ed è una
decisione: `LLM_BASE_URL` può puntare a un motore condiviso o su un'altra
macchina, e un backend che scrivesse modelli nel registro di qualcun altro a ogni
avvio modificherebbe lo stato di chi non ha chiesto niente.

**La scala arriva al massimo del modello, e la cautela di partenza era falsa.**
Si era fermata a 32k temendo che una finestra troppo grande facesse *fallire* la
generazione. La documentazione di Ollama dice il contrario: quando la cache delle
chiavi non entra in VRAM, il motore sposta parte del modello in RAM di sistema e
continua — molto più lento, non rotto. Quindi il costo è un rallentamento, e un
rallentamento **si vede**: la riga dei tempi lo mostra a ogni risposta.
Nascondere una scelta per un costo visibile toglie proprio la misura che il
progetto esiste per far vedere.

**I pioli sono nostri, il tetto no — e mancava un pezzo.** `context_max` si
leggeva già dal motore, ma la scala era una lista fissa che veniva solo tagliata:
un modello il cui massimo non cade su una potenza di due non avrebbe mai visto la
propria finestra più grande. Oggi non si notava — i quattro installati hanno
massimi di 128k e 256k, che *sono* pioli — e sarebbe stato il difetto che si
scopre con un modello nuovo e sembra un guasto di quel modello.

**Via la voce «non fissata».** Il modello base non scrive `num_ctx`, quindi la
finestra la sceglie il servizio e il numero non lo sappiamo: in un menu di misure
era l'unica voce che non era una misura. Nessuna riscrittura dell'etichetta la
rendeva meno vaga, perché il problema era la voce. Si parte da **32k**, la
finestra con cui il progetto misura, e su un modello che non ce l'ha si prende la
più vicina e non la più grande — la più grande sarebbe la più lenta. La scelta
guardata dall'hardware è X-05, dove quella voce torna come *una misura decisa
dalla macchina* invece che come un'incognita.

**Il predefinito si calcola come il valore di partenza.** La pastiglia si apriva
in accento — il tono che qui significa «qualcuno ha mosso questo» — e il menu
marcava predefinita la taglia da 8k. Causa: `finestraDi` sul modello base non
trova niente, perché il base non è più una finestra, e ripiegava sulla prima
dell'elenco. Ora è lo stesso `risolvi` a decidere le due cose, che è la stessa
disciplina per cui `campiRichiesta` è derivata da `configChiesta`.

#### Una regressione, trovata misurando

Con sedici modelli `/datasets` è passato a **38 secondi** — misurato sul processo
vivo — perché `model_catalog()` chiedeva `/api/show` una volta per modello, in
fila, ~2 s l'una. È la prima chiamata che il frontend fa all'avvio: la pagina
sarebbe rimasta quaranta secondi in «Contatto il server…», che nessuno legge come
lentezza.

| | |
|---|---|
| prima | 35,2 s |
| in parallelo, a freddo | **6,3 s** |
| con la cache, a caldo | **2,0 s** |

Servono tutti e due: la cache da sola avrebbe nascosto il costo alla seconda
volta invece di toglierlo. Un fallimento **non** si memorizza — un motore muto
adesso può rispondere fra un minuto — e un test fissa anche l'ordine, perché un
menu che si riordina da solo fa saltare la selezione a chi ha appena scelto.

### U-04 — la seconda variabile è nella colonna, non nella barra

`baseline_prompt` esisteva nell'API da A-03 — il commit si intitola «il servizio
risponde anche senza contesto (U-03, U-04)» — validato, pubblicato in
`Capabilities`, applicato in `answer.py`, e non raggiungibile da nessuna parte
dell'interfaccia. È il caso opposto a quello di U-16, dove mancava il dato:
qui il dato c'era, mancava il posto dove chiederlo.

Il posto è uno solo, e il §12 lo diceva già: **dentro la colonna senza fonti**.
Col recupero acceso il prompt non è una scelta di nessuno — è quello che impone
il formato delle citazioni, ed è ciò che C-01 misura. Spento, i due prompt sono i
bracci di E-04 ed E-05. Metterlo nella barra sotto il campo avrebbe dato una
manopola che nel caso normale non fa niente.

#### Cosa fanno, non come si chiamano

Le pastiglie dicono «risponde comunque» e «si astiene». «Permissivo» e «severo»
sono i nomi delle due run, e stanno nel suggerimento insieme al numero che le ha
misurate: invenzione dal **45% al 17%**, corrette invariate (p=0,80), su 100
domande di `open_ragbench`.

Due pastiglie e non un interruttore. «Severo» acceso farebbe di «permissivo» la
sua assenza, e permissivo non è l'assenza di niente: è un prompt che dice
*rispondi comunque*. Su un asse i due capi si vedono insieme — è la stessa
ragione per cui `top_k` non è un interruttore.

#### Il §15, un giro più stretto

Il confronto di U-03 cambia il RAG e tiene fermo tutto il resto. Questo cambia
**come è stata posta la domanda** e tiene fermo anche il RAG: parte da
`stessaConfigurazione` della risposta nuda e sovrascrive un campo solo. E rifà
**una colonna sola** — quella con le fonti resta dov'è, a fare da paragone
mentre l'altra si rigenera.

#### Il difetto che il rilancio ha scoperto

Da che parte andasse ciascuna colonna si ricavava da `data.config.rag`: la
risposta di partenza sta dalla parte che il suo `rag` dice, l'altra è quella
lanciata dal confronto. Funziona finché nessuno rifà una delle due.

Rilanciando la colonna nuda il suo `config` torna `null` fino a `done` — cioè
sparisce **proprio il dato da cui si leggeva la posizione**. Per gli ~11 s della
generazione le due colonne si sarebbero scambiate di posto, in una schermata il
cui unico scopo è dire quale delle due ha visto le fonti. Non è un caso di bordo:
è il caso normale di U-04.

La correzione è che il braccio nudo si decide **all'apertura** e diventa un campo
dello stato, e che `conBraccio` riceve quale braccio riscrivere invece di
rileggerlo da uno stato che lo stream sta cambiando. Due test lo fissano; sono
quelli che avrebbero fallito prima.

#### Chiesto e girato, di nuovo

Quale prompt sta girando nella colonna nuda si legge con la regola di U-15: ciò
che ha girato quando si sa (`config.baseline_prompt`), ciò che è stato chiesto
mentre non si sa ancora. Senza, il selettore tornerebbe indietro da solo appena
premuto e salterebbe al valore giusto undici secondi dopo. Il verso conta —
`config` per primo — perché è l'unico dei due che può smentire il controllo, ed è
esattamente quando deve farlo.

#### Non riscrive il filo

Chiedendo col RAG già spento, la colonna nuda **è** la risposta già data. Lì si
rifà la copia del confronto, e la conversazione tiene quella che era stata data
davvero: una risposta già letta non cambia sotto gli occhi di nessuno. Il
confronto è un banco — vive accanto al filo, e chiudendolo sparisce.

#### La colonna nuda viene più bella, ed è metà fenomeno e metà artefatto

Osservato alla revisione: «risponde comunque» produce la risposta **più lunga e
meglio impaginata delle due** — titoli, righe orizzontali, una formula in
display — mentre quella con le fonti sta in due paragrafi. Cioè la più
convincente delle due è quella che non si può controllare.

Metà è il fenomeno che la schermata esiste per mostrare, e metà no. Il braccio
con le fonti porta «Use Markdown where it helps the reader… **Do not use it for
decoration**» e l'obbligo di dire solo ciò che sta nei chunk; quello nudo gira su
`baseline_prompts.py`, che è letteralmente *«Answer the question to the best of
your ability»* — **nessuna** regola di formato. È lo scarto che il docstring di
U-14 aveva già nominato («the second variable §15 forbids») e che il rovesciamento
del formato ha ristretto senza chiudere.

Chiuderlo del tutto significa toccare `baseline_prompts.py`, che rende E-04/E-05
non più confrontabili: si perderebbe il 45%→17% che il suggerimento di questa
stessa schermata cita. Non si scambia una misura per una colonna più sobria — è
**D-16**, da decidere misurando insieme a D-3.

Quello che si è cambiato è l'avviso, che diceva solo metà della cosa. «Non si può
controllare» lascia l'impressione estetica a lavorare indisturbata; ora dice
anche il meccanismo — *niente la obbliga a fermarsi dove finiscono i documenti* —
che vale in lunghezza e in impaginazione insieme, ed è vero per costruzione
invece che per una misura non ancora fatta.

#### Un numero da solo non è una formula

Seconda cosa vista alla revisione, su `ledger`: il modello scrive `$(222.8)$
million dollars` e la cifra usciva in Computer Modern in mezzo alla prosa. Cioè
un **quarto ruolo tipografico** accanto ai tre del §12 — e per giunta su un
corpus dove `$` è il simbolo della valuta e le parentesi vogliono dire
«negativo».

Misurato prima di toccare la regola, sulle risposte di riferimento e con lo
stesso taglio del frontend:

| | coppie `$…$` accettate | di cui soli numeri |
| `open_ragbench` | 717 | **11** |
| `ledger` | 0 | 0 |

Gli undici sono `2010`, `0.47`, `0.33`, `0.01`, `0`, `198.088`, `357.856`,
`[-1,1]`, `(1,2,3)`, `0.874(0.006)` — cifre che un paper ha incorniciato per
abitudine, e nessuna perde qualcosa a essere scritta nel carattere del testo
intorno. La regola è **stretta di proposito**: basta una lettera, un comando, un
apice o un `=` perché resti matematica. `448^{2}`, che è nel corpus, non la
sfiora.

**I delimitatori spariscono invece di restare a vista.** Era la trappola della
correzione ovvia: dire «non è matematica» e basta avrebbe stampato `$(222.8)$`
con i dollari scritti, cioè avrebbe mostrato *il modo in cui il modello ha
sbagliato* invece del numero che ha detto. Il segmento parte da `da: i + 1`, così
la `$` non appartiene a nessun segmento e nessuno la disegna — lo stesso effetto
dei `nascosti` del markdown, ottenuto dove i caratteri di sintassi sono già in
mano a chi taglia.

**E il prompt non c'entra**, che era l'ipotesi comoda. Cercata nei dump di
generazione già su disco: la frase identica — `were $(222.8)$ million dollars
[5]` — è nel dump del **12 agosto**, e il prompt archiviato accanto non ha
nessuna sezione OUTPUT FORMAT, né la riga sul LaTeX che U-14 ha aggiunto il 19.
Il comportamento precede di una settimana la regola a cui verrebbe naturale
darne la colpa.

Tirando quel filo è uscita una cosa più grande delle parentesi in carattere
sbagliato, ed è diventata **OQ-07**: nei bilanci il segno di un numero appartiene
al prospetto e non alla grandezza — `222.8` nella tabella riassuntiva, `(222.8)`
nel rendiconto, stesso documento — quindi una cella copiata in prosa può
invertire ciò che afferma **mentre la citazione resta corretta**. Il 17,9% delle
celle numeriche di LEDGER è fra parentesi, e nel 43% dei documenti la stessa
grandezza compare in tutte e due le forme. Nessuna delle due metriche di
citazione vede questa classe di errore: quella numerica conferma perché il valore
c'è, e il «no» dell'NLI non è un segnale perché su tabelle nega anche i claim
corretti (OQ-05). Misura riproducibile con `scripts/probe_sign_convention.py`,
protocollo e trappole nella voce.

#### Un esempio dello stato vuoto non funziona

Terza cosa vista alla revisione, e non è di U-04: la seconda domanda proposta per
`ledger` — *«What is the accounts receivable for Company The Sherwin-Williams in
2017?»* — si astiene. Il numero c'è (`NYSE_SHW_2017`, `Accounts receivable, less
allowance | 2,104,555`), i chunk d'oro sono dichiarati nel golden set, e in
contesto al modello arrivano le relazioni di certificazione e le lettere agli
azionisti. **«Insufficient information» è la risposta corretta**: il guasto è nel
recupero, ed è OQ-06 alla lettera — documento giusto, chunk sbagliato,
modulistica promossa.

Il difetto non è quella domanda, è come sono stati scelti gli esempi. `esempi.ts`
li prende da `eval/golden` perché «il primo clic non deve finire in
un'astensione»: la premessa è vera, la conclusione no. Su `ledger`, col default,
il chunk giusto è nei primi 5 nel **20,7%** dei casi mentre il documento giusto
c'è nell'**89,2%** — quindi una query d'oro presa a caso ha circa una
probabilità su quattro di funzionare. Dei quattro esempi rispondibili, `dense` ne
prende due in posizione 1, uno in posizione 5 e uno per niente: sono esattamente
le probabilità.

Registrato come **D-17** invece di correggerlo qui: sostituire un esempio è una
decisione su cosa la demo racconta, e va fatta misurando i candidati. Con una
trappola scritta accanto — `hybrid+rerank` prenderebbe tutti e due gli esempi di
`ledger`, ed è la configurazione che vince sui due dati su cui la si guarda.

#### Due cose emerse di lato

**La pastiglia esce dalla barra.** Quattro costanti di stile in `ui/pastiglia.ts`:
questo controllo è un comando dello stesso vocabolario, e ridisegnarselo era il
difetto già visto col caret in U-16 — stessa forma presa da un'altra misura, che
diverge alla prima correzione. Commit separato, 204 test prima e 204 dopo.

**`npm run format:check` era rosso, e non per lo stile.** `core.autocrlf=true`
riscrive i fine riga in CRLF al checkout, e prettier col suo default (`"lf"`) li
segnalava tutti: quattro file, nessuno dei quali aveva un problema visibile nel
diff. `endOfLine: "auto"` prende come giusto il fine riga che il file già ha, ed
è l'unica regola che regge in un repo condiviso fra Windows e Linux senza
`.gitattributes`. Piccola correzione a U-03, che il formattatore l'ha introdotto.

**214 test Vitest** (10 nuovi), 1709 Python invariati, typecheck, build e
`format:check` verdi.

### U-05 — la targhetta non si poteva disegnare finché il campo mentiva

Il criterio è «rende visibile il routing», e il dato per farlo c'era già:
`ChunkView` porta `doc_genre` e `pipeline` dal A-04, con un docstring che dice
testualmente di portarli **per U-05**. Ha retto per un giorno, il tempo di
guardare cosa contengono.

#### Un campo dichiarato che nessuno verificava, il terzo

Il contratto del §3 diceva `pipeline: str  # ingestion pipeline actually used`.
I due loader generici scrivevano un'altra cosa:

```python
ledger.py         pipeline = doc_genre
open_ragbench.py  pipeline = "table_heavy" if doc_genre == "table_heavy" else "continuous_text"
```

In tutti e due i casi il codice spezza a mano — una pagina per chunk, una sezione
per chunk — e i moduli `pipeline_*.py` non vengono mai chiamati. Letto
sull'indice vivo, 2000 punti per collection:

| collection | `doc_genre` | `pipeline` | punti |
|---|---|---|---|
| `ledger` | table_heavy | **table_heavy** | 47.110 |
| `ledger_routed` | table_heavy | **table_heavy** | 228.331 |
| `open_ragbench` | academic_pdf | continuous_text | 18.840 |
| `open_ragbench_routed` | academic_pdf | structured_hierarchical | 98.312 |

Su LEDGER il campo diceva **la stessa cosa nelle due modalità**, ed era falso in
quella generica. Una targhetta dipinta da lì avrebbe mostrato lo stesso valore
col routing acceso e spento, sul dataset dove il routing conta di più — cioè
avrebbe fallito il proprio criterio pur sembrando funzionare.

È la terza volta: `reasoning_enabled` (falso in ogni run per un periodo),
`context_window` (D-14), questo. La forma è sempre la stessa, e qui il motivo per
cui è potuto restare sbagliato stava scritto in un commento di `router.py`:
sosteneva che l'harness leggesse il campo per taggare gli `EvalRun`. Non lo legge
nessuno. **Niente calcola su `Chunk.pipeline`** — si scrive, si mette nel
payload, si rilegge in `ChunkView`.

#### Quella stessa cosa ha reso la correzione economica

Se nessuno calcola su quel campo, correggerlo non sposta nessun risultato
registrato e non chiede di ricostruire un indice: `set_payload` riscrive un campo
su una collection viva, come gli indici payload di A-07 e il modificatore IDF di
R-08. 65.950 punti, nessun vettore toccato, verificato col conto esatto e non a
campione:

| | punti | non-`generic` dopo |
| `open_ragbench` | 18.840 | 0 |
| `ledger` | 47.110 | 0 |
| `open_ragbench_routed` | 98.312 | intatti |
| `ledger_routed` | 228.331 | intatti |

Le *routed* le rifiuta dal nome, e il rifiuto è il punto: lì il valore è vero,
l'ha scritto il modulo che ha girato davvero.

Due cose imparate eseguendola, e sono nello script. Su `ledger` la scrittura
supera i cinque secondi di timeout del client: il server la portava a termine e
lo script usciva con un errore — **una migrazione riuscita che si dichiara
fallita invita a rilanciarla cercando un guasto che non c'è**. E «già a posto»
era deciso su 500 punti campionati, cioè sull'1% di `ledger`; ora è un `count`
con filtro, e la stessa funzione verifica anche l'esito.

#### La targhetta

`tabelle → taglio generico`, sotto la testata della scheda, dove sta
`section_path`: è una proprietà del documento da cui la fonte viene, non un
giudizio su di essa, quindi non va in fondo accanto ai verdetti.

**Le due metà insieme.** La pipeline da sola non dice in base a cosa è stata
scelta; il genere da solo non dice cosa se n'è fatto. Il routing è la freccia.

**Due vocabolari separati**, anche dove una parola coincide: `table_heavy` come
genere è «fatto di tabelle», come pipeline è «spezzato tenendo le tabelle
intere». Su `open_ragbench` un documento `table_heavy` finisce su
`continuous_text`, perché lì le tabelle sono Markdown — quindi non è un'identità,
è una decisione. Una mappa condivisa avrebbe accettato `academic_pdf` come nome
di pipeline, che non lo è.

**L'accento solo quando una pipeline è stata scelta per il genere.** Col routing
spento tutti i documenti ricevono lo stesso taglio, e cinque targhette accese
identiche su cinque schede smettono di essere lette. Il genere invece cambia da
scheda a scheda anche lì.

#### Il limite, dichiarato

Oggi la demo **non instrada mai**: `/datasets` pubblica solo le due collection
generiche, e le `_routed` esistono in Qdrant senza essere raggiungibili. Quindi
la seconda metà della targhetta è costante, e ciò che si vede è che il routing
non è in gioco. È vero e non è tutto ciò che il criterio vorrebbe — registrato
come **D-18**, perché è una scelta di perimetro che non era scritta da nessuna
parte.

> **Aggiornamento del 2026-08-24: non è più un rinvio, è la decisione.** D-18 è
> stato chiuso scegliendo di **non** offrire le collection instradate — in
> ricerca esatta il routing perde 13,72 punti su `ledger` — quindi la targhetta
> resta costante per costruzione, e dice il vero su ogni risposta che la demo
> produce. Il ragionamento sta in fondo a questo quaderno, in *D-18*.

### U-06 — la fonte è il chunk intero, e il PDF non c'è affatto

Il criterio dice «da una citazione si raggiunge la pagina della fonte», e la
parola *pagina* non si poteva prendere alla lettera. Guardato prima di
cominciare:

| | `open_ragbench` | `ledger` |
| PDF su disco | **nessuno** — solo il JSON degli articoli | nessuno — solo il Markdown di Mathpix |
| `page` | sempre `0` | reale (0…N) |
| `bbox` | `null` | `null` |
| `source_uri` | `https://arxiv.org/abs/…` | `ledger:NYSE:SHW:2017` |

L'overlay non è scoperto solo perché I-06 è rinviato: **un PDF non c'è proprio**.
La seconda riga del criterio lo prevede — *«dichiararlo, non simularlo»* — e la
colonna di destra lo scrive invece di disegnare un riquadro grigio che promette
qualcosa.

Quello che si può raggiungere è **il chunk intero**, ed è la metà che conta. La
scheda del pannello ne mostra due righe; il chunk che risponde alla domanda sui
crediti di Sherwin-Williams è lungo **6.302 caratteri**. Controllare una
citazione vuol dire leggerli tutti.

#### Terza volta che il dato c'era già

`/documents`, `/document/{id}/chunks` e `/chunk/{id}` esistono dal A-04; A-07 ha
creato gli indici payload apposta (2,07 s → 0,025 s); `client.ts` li avvolge da
U-00 con un commento che dice «(U-06)». **Non li aveva mai chiamati nessuno** —
come `/config` prima di U-03 e `Risposta.config` prima di U-15. Il costo
misurato: l'elenco di `ledger` è 494 documenti, 21 KB, 0,35 s; il documento più
grande è 261 chunk, 523 KB, 0,46 s. Si chiedono solo aprendo l'esploratore, non
all'avvio.

#### La mappa

Una tessera per chunk, larga il doppio dove c'è una tabella. **La larghezza porta
l'informazione insieme al colore**, non il colore da solo: è la regola dei
verdetti di U-07. Due documenti dello stesso corpus danno due mappe diverse, e
quella è l'affermazione 2 del §0 senza una tabella di numeri.

Non si poteva disegnare prima di U-05: fino a ieri il campo `pipeline` diceva il
nome di una pipeline che non aveva girato.

#### La legenda diceva una cosa vera dell'altro indice

Scritta com'era nel mockup — «tabella · mai spezzata» — era **falsa
sull'indice generico**: lì i chunk sono una pagina intera e la tabella dentro non
è stata protetta da nessuno, ci è capitata. Sarebbe stata la stessa
dichiarazione non verificata che U-05 aveva appena tolto dal campo, rimessa due
giorni dopo in una legenda. Ora sono due etichette scelte da `taglioPerGenere`,
la stessa funzione che decide l'accento sulla targhetta.

#### Due modi di arrivarci, nessuno dei due un comando in più

«Esplora il corpus» sotto il selettore del dataset, perché apre una vista su
*quel* dataset — il docstring del telaio lo aspettava: *«arriverà con la
schermata che apre»*. E il **nome del documento** sulla scheda della fonte, che
era già ciò che si guarda per sapere da dove viene una risposta: su una colonna
larga 272 px un bottone in più sarebbe stato il primo a essere tolto.

#### Un rinominamento per un difetto vero

`app/corpus.tsx` è diventato `app/esploratore.tsx`. Due file con lo stesso nome e
due estensioni si risolvono per ordine di preferenza del bundler: l'import di
`usaCorpus` prendeva `corpus.ts`, che non lo esporta, e il typecheck lo ha detto
subito — ma in un caso meno fortunato avrebbe preso il modulo sbagliato in
silenzio. Il repo non lo faceva mai: `chat.tsx` sta accanto a `conversazione.ts`.

### U-17 — le cuciture sono il contenuto, e il nome dice cosa si sta guardando

**Si chiama «il testo indicizzato» e non «il documento»**, ed è il punto del task: il PDF non ce l'abbiamo (U-06), e ciò che si può mettere in fila sono i chunk. Oggi le due cose coincidono, e non per fortuna: nell'indice generico **non c'è nessuna sovrapposizione** fra chunk adiacenti — misurato — quindi i pezzi partizionano il documento esattamente. In una collection instradata non sarebbe più vero: un quarto delle coppie condivide fino a **586 caratteri**, e una lettura continua li mostrerebbe due volte. Il nome regge anche quel giorno, la vista no, e sta scritto dove serve (D-18 — chiuso il 2026-08-24 decidendo di **non** offrirle nel selettore, quindi dal menù quel giorno non arriva; dall'API, che accetta `collection`, sì).

**Le cuciture sono il contenuto, non un difetto.** Vedere dove un taglio è caduto — in mezzo a una frase, prima di una tabella, dopo un titolo — è la tesi del progetto applicata al corpus: la mappa dice che i pezzi sono disuguali, questa dice cosa c'era nel punto in cui uno è stato staccato. La cucitura sta **sopra** il chunk e non fra due, così porta il nome di quello che apre e il primo taglio si vede come gli altri.

**Due misure hanno deciso due cose, e una ha tolto lavoro.** Comporre il documento più lungo di `ledger` — `NASDAQ_LOOP_2017`, 457.565 caratteri in 147 chunk — costa **29 ms**: si disegna tutto insieme, e la finestra sui pezzi visibili, l'unica cosa che avrebbe potuto far crescere il task, non serve. Alzare il minimo di un tratto della mappa da 3 a 10 px costa **l'1,1%** della mappa nel documento peggiore e niente negli altri: la proporzione si viola di proposito, perché a tre pixel era più fedele e alcuni pezzi restavano invisibili.

`Leggibile` esce da `Contenuto` in un commit suo, senza cambiare cosa disegna: lo usano il chunk singolo e il documento intero, che sono la stessa cosa a due scale.

### U-18 — nella striscia resta ciò che un simbolo sa dire per intero

**La griglia del telaio è uscita dalle classi prima che servisse.** Con due larghezze di corsia e il pannello fonti che va e viene le combinazioni sono quattro, e che la colonna di lavoro guadagni *davvero* i 152 px della corsia chiusa è una somma: o si calcola o si spera. `corsia.ts` la calcola, e i test controllano la cosa che l'errore facile sbaglia — che le tracce restino tante quante erano. Una colonna nascosta con `visibility`, o lasciata lì a larghezza zero, supera l'ispezione a occhio e lascia la traccia dov'era.

**La regola che ha deciso cosa entra nella striscia.** Ci sta ciò che un simbolo sa dire per intero: i due comandi (nuova conversazione, esplora il corpus) e le tre scelte fra poche voci con un nome ciascuna (dataset, lingua, tema) — perché il pannello che si apre è largo quanto le voci, non quanto il bottone che lo apre. La cronologia è l'unica che non regge: il titolo di una voce è già la prima domanda troncata a ~28 caratteri, e troncarlo a un glifo non lascerebbe un titolo, lascerebbe una fila di righe uguali. Il suo bottone **riapre la corsia**, e la bolla dice perché invece di lasciarlo scoprire cliccando.

**Due cose si perdono, e sono scritte dove capitano.** Il nome del dataset non ha più una presenza fissa sullo schermo — resta nell'`aria-label` e nel pannello, col pallino d'accento, a un gesto solo, che è lo stesso che serviva prima per vedere gli altri. Il nome del tema esce dalla pastiglia ma non dalle sue tre voci, che sono il posto dove «sistema» si spiega davvero. Entrambe le perde chi ha scelto di chiudere la corsia.

**Non si anima, ed è una scelta.** Interpolare la traccia da 200 a 48 px vuol dire rifare l'impaginazione della conversazione a ogni fotogramma — mandare a capo il testo, ricollocare le pastiglie dei marcatori, ridisegnare i verdetti — cioè lo stesso costo per cui `Suggerimento` vieta lo `scale` sul testo. Una transizione che scatta è peggio di nessuna transizione: dice che il programma sta faticando.

**Il marchio non rimpicciolisce con la corsia** (correzione di Marco, e ha ragione per la ragione che il componente aveva già scritta in testa a sé stesso: una corsia che cambia larghezza fra due schermate è il difetto più visibile che un'interfaccia possa avere, e un marchio che cambia corpo fra due stati è lo stesso difetto in piccolo). I 19 px non stanno nei 34 fra i due margini — «ibid» in Georgia ne misura ~32 — quindi quella riga annulla il margine e si prende tutti e 48.

Le sigle della lingua **si impilano** invece di sparire: mostrare tutte e due le posizioni e quale è viva è l'unica cosa che quel bottone fa meglio di una tendina, e affiancarne una sola l'avrebbe trasformato nel bottone che cicla criticato tre funzioni più sotto.


### U-19 — la pagina che spiega, e i numeri che non ci sono

Il criterio ne ammetteva due, di strade: i numeri del README, da una fonte sola, **oppure nessuno**. Vale la seconda, e la ragione è una data: le misure delle tre affermazioni valgono per un prompt che U-14 ha cambiato, e rifarle è D-1, D-2, D-3. Una copia scritta a mano in questa pagina resterebbe ferma a quelle vecchie senza dirlo — e una pagina che spiega il progetto è l'ultimo posto in cui ci si può permettere un numero che era vero l'altro ieri. La pagina lo **dichiara** invece di simularlo: «i numeri non stanno qui, stanno nelle tabelle del repository, l'unico posto in cui vengono rifatti quando cambia qualcosa».

**Le tre affermazioni portano un verdetto, con la grammatica dei verdetti.** Stesso glifo, stesso tono, stessa pastiglia con cui `Verdetto` giudica una citazione — perché è lo stesso gesto: dire se una cosa regge, e dirlo anche quando non regge. La 1 regge; la **2 non regge**, in ocra, dentro la pagina che presenta il progetto; la 3 è «non decisa», che non è un modo gentile di dire no — manca la misura, e manca *detto*. Nasconderle avrebbe reso questa pagina una pubblicità, cioè il contrario di ciò per cui il progetto esiste.

**Chi ha risposto e su quale corpus sono un limite, non una scheda tecnica** (correzione di Marco). La pagina aveva una tabella «cosa sta girando adesso» con sei righe di configurazione, ed è stata tolta: quei valori si leggono già nella barra sotto il campo e in «Dettagli della run», dove servono perché lì si sta lavorando, e ripeterli qui trasformava metà di una pagina di prosa in una scheda tecnica. Le due cose che il criterio chiede per nome restano, dentro «cosa questa demo non è»: *non è un panorama — a ogni domanda risponde un modello solo, su un corpus solo, adesso questi due*. È l'unica cosa che quelle altre due viste non dicono, cioè che sono **una**.

I due nomi arrivano comunque vivi da `/config` e da `/datasets`, mai scritti a mano — è il punto in cui è più facile mentire senza volerlo: un nome di modello copiato in una stringa resta lì quando il servizio ne carica un altro. La regola sta in `app/scheda.ts`, dove si prova senza un browser, ed è A-07 irrigidito dalla frase unica: **o si sanno tutte e due, o la frase è un'altra**. Una frase sola col trattino al posto di un nome sarebbe l'affermazione mancata, detta più piano.

**Dice che la demo gira con la ricerca esatta**, come il piano chiede — è l'unico punto in cui non è configurata come la valutazione — e sta anche lei nell'elenco dei «non è», dove appartiene: su un indice fitto l'approssimazione salta qualcosa, e una dimostrazione mostrerebbe quel difetto credendo di mostrare il recupero. La valutazione può permettersi un difetto noto, una dimostrazione no.

**In fondo c'è chi l'ha fatto** (chiesto da Marco insieme alla correzione sopra). Non è cortesia: un banco di prova che pubblica misure negative chiede di essere creduto, e la firma è metà di ciò che lo rende credibile — la pagina appena sopra dice che una affermazione non regge e una non è decisa, e dirlo senza dire chi lo dice chiede fiducia a nessuno in particolare. Sta in fondo e non in cima perché viene dopo il merito: prima cosa fa, cosa regge e cosa no, poi chi lo dice. Con la licenza, e col fatto che insieme al codice ci sono il piano, le tabelle e le domande ancora aperte.

**Ci si arriva dalla corsia, su una riga sua.** Non accanto a lingua e tema: misurato, i tre affiancati chiedono 185 px dove la corsia ne ha 175 — ma non era solo lo spazio. Lingua e tema commutano un valore e restano dove sono; questo apre una schermata, quindi ha la forma di «Esplora il corpus», che è l'altro comando che fa la stessa cosa. Nella striscia resta il solo glifo, come per gli altri.

**Una misura sola per i comandi della corsia** (seconda correzione di Marco, sulla riga in fondo: «è tutto formattato non allineato, di misure diverse»). Non era colpa del bottone nuovo: misurati, i sette controlli della corsia — tutti larghi uguale e incolonnati — avevano **sette altezze e tre raggi**. Corsia larga 34 / 33,3 / 36 / 33,3 / 27 / 25 px con raggi 7 / 8 / 7 / 8 / 5 / 5; striscia 30 / 34 / 34 / 34 / 34 / 42 / 26 con raggi 6 / 7 / 8 / 7 / 8 / 5 / 5. Ogni comando aveva preso la sua misura dal proprio contenuto invece che da una regola, e differenze da mezzo pixel a nove non si leggono come una gerarchia: si leggono come un errore.

La regola, adesso dichiarata: **un comando è alto 34 px** in tutte e due le corsie (nella striscia senza eccezioni — la lingua stava a 42 perché impila due sigle e la scatola seguiva); **un'impostazione è alta 26 px** nella corsia larga, così lingua e tema restano più piccole dei comandi come nel mockup ma uguali fra loro; **il raggio è 7 px ovunque**, quello che il mockup già usa sul dataset e su «Nuova conversazione». In più: il gruppo in fondo aveva un `px-1` che lo rientrava di quattro pixel rispetto al resto della colonna, ed è via; e il tema prende la larghezza che avanza, così la riga finisce dove finiscono i comandi sopra.

`MISURA` esce da `Chat.tsx` e diventa `ui/misura.ts` in un commit suo, senza cambiare comportamento: la misura di lettura è una proprietà dell'occhio, non di una schermata, e due tetti diversi nella stessa applicazione sarebbero due misure di lettura per lo stesso lettore.

### D-1 e D-2 — la conformità delle citazioni col prompt in vigore

Due run da 200 domande, una per corpus, mai aggregate. `gemma4:latest` (E4B,
Q4_K_M, ctx 32768), T=0, dense, `top_k` 5, `prompt_hash 53a5e756` — quello che
U-14 ha messo in vigore. Le 17 run precedenti valevano per `3a50ef63`.

**I numeri, per dataset**, grezzi e dopo il parser di C-02, contro le due run del
12 agosto misurate con lo stesso strumento:

| dataset | | grezza | dopo `parse()` | valutate | astensioni |
|---|---|---|---|---|---|
| **open_ragbench** | prompt vecchio | 0,9263 | 0,9579 | 95 | 5,0% |
| | **prompt in vigore** | **0,9255** | **0,9628** | 188 | 6,0% |
| **ledger** | prompt vecchio | 1,0000 | 1,0000 | 81 | 19,0% |
| | **prompt in vigore** | **0,9664** | **0,9732** | 149 | 25,5% |

`open_ragbench` non raggiunge lo 0,95 di C-01 — e non lo raggiungeva neanche
prima. Non è una regressione, è lo stesso numero: va detto ogni volta che lo si
cita.

**Il confronto non è appaiato**, e questo è il limite che lo governa: codice
diverso, numerosità diversa, prompt diverso. Tre differenze dentro una misura
sola, ed è esattamente perché D-3 esiste. Queste due run dicono **dove si sta**,
non perché. → **D-3 lo ha chiuso il 2026-08-22**, sezione in fondo.

> **Le differenze erano quattro, non tre.** Fra il 12 e il 21 agosto è cambiato
> anche l'indice approssimato di `ledger` (OQ-09), quindi i due bracci non hanno
> ricevuto lo stesso contesto: identico su 72 query delle 100 in comune,
> completamente diverso su 20. **Misurato dopo, la quarta non morde**: sulle 75
> valutate in entrambe la conformità è 1,0000 da tutt'e due le parti, 17 delle
> quali con contesto diverso, e le astensioni passano da 19 a 18. Il calo di
> `ledger` viene dalle query 101–200 — i quattro rifiuti con parole proprie di
> D-19 — non dal recupero. Il conto è nella coda di D-4, in fondo.

#### Il calo di `ledger` non è ciò che la previsione diceva

La previsione rinviata da U-14 era che il markdown avrebbe prodotto risposte
«più belle e meno verificate», e l'argomento erano **le tabelle**: una riga di
tabella non è una frase, quindi la verifica di C-03 non la sa attribuire.

Guardando le risposte: su 337 valutate nei due corpus col prompt nuovo, le
tabelle generate sono **zero**. Come erano zero col prompt vecchio. Ciò che è
cambiato davvero è la forma minuta:

| | elenchi | grassetto |
|---|---|---|
| `open_ragbench` vecchio → nuovo | 8 → **63** | 9 → **33** |
| `ledger` vecchio → nuovo | 4 → **33** | 1 → 2 |

E i cinque fallimenti di `ledger` non hanno niente a che vedere col markdown:
uno è `[1] [2]` con lo spazio, che il parser ripara; gli altri **quattro sono
rifiuti scritti con parole proprie** invece che con la stringa esatta che il
prompt impone — «The provided context does not contain the operating income
figure for Barnwell Industries, Inc. for the year 2017.» Non essendo nell'elenco
di `ABSTENTION_PHRASES` non contano come astensioni, quindi entrano fra le
valutate e falliscono per `no_citation`. **Sono l'intero calo**: senza di loro
`ledger` sarebbe a 0,9931. È registrato come **D-19**, perché la scelta fra le
due letture tocca anche E-04/E-05, che condividono quell'elenco.

Quindi la previsione di U-14 **non è confermata come era scritta**, e non è
nemmeno smentita: il fenomeno che temeva non si è presentato affatto su questi
due corpus, mentre la forma delle risposte è cambiata molto. Distinguere il
merito dal caso è il lavoro di D-3, che ora ha un'ipotesi più affilata di
quando è stato scritto.

#### Due cose viste passando

`out_of_range` torna su `open_ragbench` in 4 risposte su 188: marcatori come
`[16][17][18][19]`, `[30]`, `[34]` con cinque chunk in contesto. È la causa
dominante che C-01 aveva ridotto da 19 a 4 — il modello che copia la
**bibliografia del paper** invece del nostro sistema di riferimenti — e a 4 è
rimasta. Il parser le scarta tutte e quattro, perché puntano fuori dal contesto.

Le astensioni salgono su tutti e due i corpus, e su `ledger` di sei punti e
mezzo (19,0% → 25,5%). Su un corpus dove il chunk giusto è nei primi 5 nel 20,7%
dei casi è un dato sul **retrieval** più che sul formato, e riguarda C-04 e
D-17: va letto accanto alla conformità, non dentro.

#### Cosa cambia nel repository

L'ancora di `config_hash` per C-01 punta alla run di D-1 invece che a quella del
12 agosto. Dal 19 agosto quel test **saltava** — correttamente, perché il suo
hash include il prompt e il prompt era cambiato — e per due giorni non ha
protetto niente. Ora i **1712 test passano e nessuno salta**: era l'unico.

Le generazioni sono a disco accanto ai risultati, col prompt che le ha prodotte.
Sono ciò da cui D-3 e D-19 ripartono senza toccare la GPU: `measure_repair.py` e
`rescore_citations.py` lavorano sui file, non sul modello.

#### Il costo vero, per chi pianifica D-3

Il piano stimava 65–70 minuti a run. Le due insieme ne hanno prese **156**, dalle
12:12 alle 14:48. Il ritmo non è costante: 17,5 s a domanda nella prima metà di
D-1, 28,7 s nella seconda, con la scheda che rallenta sotto carico continuo — non
per risposte più lunghe (87 token mediani contro 81) e non per uno spill di VRAM,
che è stata verificata piena per tutta la run. **22 s a domanda** è la media da
usare per stimare: D-3 sui due corpus è una sessione da ~2 h 30.

Una nota operativa che vale la pena non riscoprire: se il processo di eval carica
l'embedder ONNX **prima** che Ollama carichi il modello, quello che resta di VRAM
non basta e il modello finisce in parte sulla CPU — misurato, **123 s a domanda**
invece di 22. Si evita scaldando il modello prima di lanciare la run.

### U-20 — una guida che indica, e non impedisce niente

Il criterio chiede quattro cose, e tre sono vincoli sulla **forma**: si salta con
un comando solo, non torna dopo un ricaricamento, non impedisce di fare la prima
domanda mentre è aperta, e dichiara di essere locale a questo browser.

La prima forma era una striscia in cima alla colonna di lavoro — non una finestra
modale, perché la terza richiesta escludeva il velo che copre tutto. Marco l'ha
guardata e ha chiesto altro: «qualcosa di più interattivo, che indichi le zone
dell'interfaccia». È la forma che l'avvio guidato ha adesso, e la richiesta era
giusta: una striscia di testo dice *che* le fonti compaiono a destra; un alone
attorno alla colonna delle fonti lo **mostra**, e la differenza è tutta lì.

#### Il velo c'è, scurisce e sfoca, e non chiude niente

L'obiezione che aveva fatto scartare l'overlay è che di solito un overlay *è* il
modo in cui una guida dice «adesso non puoi fare altro» — cioè esattamente ciò
che il criterio vieta. La risposta è che il velo sia un peso visivo e non una
porta: tutto lo strato è `pointer-events: none` tranne la scheda, che ha due
bottoni. Si scrive nel campo, si manda, si clicca un esempio, si cambia dataset,
con la guida aperta e l'alone acceso. Un velo che dicesse il contrario di ciò che
il programma fa sarebbe una bugia disegnata.

Il primo velo scuriva soltanto, e piano (0,16 sul chiaro). Marco l'ha voluto più
deciso, ed è diventato **due cose insieme**: lo scuro sale a 0,34 e 0,58, e si
aggiunge una sfocatura di 3 px. Non è ridondanza — lo scuro abbassa il contrasto
di ciò che sta intorno, la sfocatura gli toglie la **forma**, ed è la forma che
porta l'occhio a leggere una parola invece di guardare dove gli si sta indicando.
Con lo scuro da solo la conversazione accanto resta perfettamente leggibile, solo
più spenta.

Quella richiesta ha però cambiato il meccanismo. Il velo era l'**ombra** da 9999
px dell'alone: elegante, un elemento solo, buco e contorno impossibili da
scollare. E incompatibile con la sfocatura, perché un'ombra scurisce ciò che le
sta sotto ma non lo sfoca — per sfocare serve un elemento che *stia sopra*. Con
quattro rettangoli attorno alla zona si otterrebbe, al prezzo di quattro
sfocature rifatte a ogni fotogramma mentre si spostano. Adesso è **uno strato
fermo, ritagliato**: la sfocatura si calcola su qualcosa che non si muove mai, e
a muoversi è solo la forma che lo ritaglia.

Da cui `buco()`, e la ragione per cui ha **sempre dieci vertici**: `clip-path`
interpola solo fra poligoni con lo stesso numero di punti, e un ritaglio che ne
avesse quattro quando la zona tocca un bordo farebbe saltare il velo proprio nei
passaggi in cui la zona attraversa lo schermo. Il perimetro esterno e il buco
sono quindi sempre entrambi presenti, anche degeneri — ed è un test.

#### Le quattro zone si dichiarano da sé

L'altra obiezione — quella con cui questa forma era stata scartata la prima volta
— è che una guida che evidenzia regioni dello schermo si disallinea in silenzio
il giorno in cui l'impaginazione cambia. Vale per le guide che cercano le regioni
con un selettore CSS scritto altrove. Qui a dichiarare la zona è **chi la
disegna**: `<aside {...zona("fonti")}>`, e `zona()` prende un `Passo["id"]`,
quindi una zona scritta storta non compila. È la sola parte del meccanismo che si
poteva sbagliare in silenzio, ed è la sola che valeva la pena chiudere.

E se il nodo non è sullo schermo — schermata diversa, pannello assente —
**l'alone non si disegna affatto** e la scheda si mette in basso al centro. La
guida dice una cosa in meno, non una cosa falsa.

Le cinque zone: il pannello fonti; la colonna in cui le risposte compaiono (non
il verdetto di una frase, che sarebbe più preciso e **impossibile al primo
avvio**, quando di frasi non ce n'è nessuna); la fila di pastiglie sotto il campo;
il blocco del dataset nella corsia, che è una zona sola nei due stati della
corsia; e il bottone «Che cos'è», che l'ultimo passo nomina. Ogni passo porta
anche il glifo della sua zona.

**Il passo sulla barra è arrivato dopo**, chiesto da Marco. Ogni pastiglia ha già
il suo suggerimento a passaggio del puntatore; quello che mancava era dire che
quella fila esiste e cosa decide — e che la configurazione che ha girato **resta
scritta sopra ogni risposta**, che è U-15 e non si scopre da soli. La zona è la
fila, non il pannello «Avanzate» che si apre sopra: quello è un ripiano che
compare quando lo si chiede, e un alone attorno a qualcosa che di solito non c'è
spiegherebbe una cosa diversa a seconda del momento.

Il suo glifo è la freccia dell'invio, cioè il bottone immediatamente sopra quella
fila: quei controlli non decidono la risposta che si sta leggendo, decidono come
partirà la prossima. Un glifo nuovo — tre manopole, la forma con cui si dice
«impostazioni» dappertutto — sarebbe stato più preciso e più rischioso: a 13 px
una manopola è un punto con un trattino, e le cinque regole in testa a `Icona.tsx`
esistono perché un simbolo che non regge alla sua misura si vede solo dopo averlo
messo.

**Il confronto affiancato non prende un passo**, ed è la stessa regola vista
dall'altro lato: quel comando compare *dentro* una risposta, e al primo avvio di
risposte non ce n'è nessuna. Un alone attorno al vuoto, o attorno a una zona che
comparirà dopo, sarebbe la guida che indica una cosa che non c'è. Stesso motivo
per la cronologia, che al primo avvio è un elenco vuoto.

#### L'aritmetica sta fuori da React, come per le bolle

`ui/riflettore.ts` decide dove va l'alone e dove va la scheda, e si prova in
`node` senza un DOM: è l'unica parte che può dare un risultato **sbagliato**
invece che brutto — una scheda mezza fuori schermo, un alone attorno al vuoto.
È la stessa divisione di lavoro che `Suggerimento` ha con `collocazione.ts`, da
cui questo modulo **legge le due costanti** invece di ridichiararle: distanza fra
una cosa e la sua spiegazione, margine oltre il quale si è fuori finestra.

La regola vera è una sola — **non coprire ciò che si sta indicando** — e da lì
vengono tre gradini.

Il primo: l'ordine dei lati è `destra, sinistra, sotto, sopra`, e vince il primo
in cui la scheda ci sta **per intero**. Non «il lato con più spazio», che è la
regola delle bolle: una bolla di tre parole sta quasi ovunque, una scheda con un
titolo e due frasi no. L'ordine porta i bersagli agli estremi a spiegarsi tutti
sopra la colonna di mezzo: quelli della corsia col fianco destro libero, quello
delle fonti ripiegando a sinistra perché a destra il posto non c'è.

Il secondo gradino **è arrivato dopo**, e da una cosa vista: al passo sulla
colonna delle risposte la scheda copriva troppo di ciò che stava evidenziando.
Quella zona cade fra i due casi previsti — è alta quanto la finestra, quindi
sopra e sotto non c'è niente, e ai fianchi c'è meno di quanto la scheda chiede —
e finiva `dentro`, cioè con la spiegazione appoggiata sopra la cosa spiegata. Ora
in quel caso si prende il lato più capiente e la si **accosta al bordo**, purché
ne resti fuori almeno la metà: sporge sulla zona di quello che manca, e copre un
bordo invece del mezzo. Sotto quella soglia si torna dentro, perché una scheda
accostata che copre comunque quasi tutta la zona la copre **in mezzo**, che è
peggio che coprirla in fondo.

Il terzo, `dentro`, resta per il caso in cui non c'è un bersaglio e la zona è la
finestra intera: lì non c'è nemmeno un bordo. La scheda va in basso, dove non
copre ciò che sta sopra.

**Si converte al confine**, come sempre da quando esiste lo `zoom` sulla radice:
`getBoundingClientRect` e `innerWidth` arrivano in px di finestra, `left` e `top`
si scrivono in px di disegno, e senza dividere per `scala()` l'alone si
allontanerebbe dal bersaglio esattamente del fattore di zoom — il difetto già
pagato una volta dalla bolla del suggerimento.

#### Il movimento è lungo apposta

360 ms per l'alone, il velo e la scheda — **una durata sola per le tre cose**, e
non tre valori accordati a occhio: si spostano insieme e sono una cosa sola, e se
il bordo arrivasse prima del velo si vedrebbe l'alone acceso su un fondo ancora
scuro, che è l'impressione esatta di un programma che fatica.

Sono lunghi per questa interfaccia, dove una tendina ne prende 150, ed è voluto:
questo movimento non è un controllo che risponde a un clic, è un indicatore che
**porta l'occhio** da una parte all'altra dello schermo, e a 150 ms non lo si
segue — lo si ritrova già arrivato, che è come non averlo mosso. La curva decelera
fino quasi a fermarsi, così la parte che si vede meglio è l'ultimo terzo del
tragitto: è dove si sta guardando quando finisce. Chi ha chiesto meno movimento lo
ottiene comunque dalla regola globale `prefers-reduced-motion`, che azzera ogni
durata.

La scheda si rimisura anche **cambiando lingua**, e non è uno scrupolo: cambia
il testo, quindi la sua altezza, quindi dove va messa — senza, passando a EN
resterebbe ancorata all'angolo di prima e crescerebbe verso il basso, nel caso
`dentro` uscendo dalla zona che spiega.

La scheda scivola **solo dopo essere comparsa**: alla prima collocazione sta
ancora a (0, 0) invisibile, e con la transizione già accesa il primo disegno
sarebbe un volo in diagonale dall'angolo in alto a sinistra — il difetto classico
di qualunque cosa che si posiziona dopo essersi misurata. E il suo testo ha
un'altezza minima di quattro righe, quanto il passo più lungo: senza, la scheda
cambierebbe altezza a ogni «Avanti», e cambiando altezza si ricolloca — quindi
scivolerebbe anche in verticale per una ragione che non ha niente a che vedere con
la zona che sta indicando.

#### Due decisioni che si vedono solo se si sbagliano

**Si rimisura di continuo invece di ascoltare gli eventi giusti.** Le cose che
spostano un bersaglio qui sono quattro: la finestra che cambia, una colonna che
scorre, il pannello fonti che compare, la corsia che si comprime. L'ultima
**sostituisce il nodo** invece di ridimensionarlo, quindi un `ResizeObserver` su
ciò che si è trovato smette di parlare proprio quando servirebbe. Un giro ogni
100 ms che rilegge la zona e aggiorna lo stato solo se è cambiata costa una
misura su un elemento, dura quanto la guida, e non lascia casi scoperti.

**La lingua si cambia dalla scheda** (chiesto da Marco). Il selettore in corsia
era già cliccabile — il velo lascia passare il puntatore — ma è scurito, sfocato
e piccolo: è esattamente ciò che la guida sta dicendo di non guardare. Chi apre il
programma e non legge l'italiano deve poter cambiare lingua *prima* di decidere se
questa spiegazione gli interessa, non dopo averla saltata. Stessa grammatica della
pastiglia in corsia — tutte e due le sigle visibili, quella viva in accento — ma
non lo stesso componente: quello è dimensionato sulla griglia della corsia e ha già
due varianti, e una terza lo farebbe servire un posto per cui non è stato fatto.
Ciò che non può divergere è il modo di dire la stessa cosa, e sono tre righe.

I tre bottoni del piede hanno un'**altezza dichiarata**: presa dal contenuto
venivano fuori di 25, 26 e 24 px, e una differenza di un pixel non si legge come
una gerarchia — si legge come un errore. È la lezione che la corsia ha già pagato
in U-19.

**Escape non salta la guida**, ed è una deroga alla regola che vale nel resto
dell'interfaccia. Lì Escape chiude ciò che si è aperto sopra il contenuto — una
tendina, una bolla — e quelle cose si riaprono. Qui la stessa pressione
prenderebbe una decisione **definitiva**, e due dei quattro passi indicano una
zona che contiene una tendina: chi la chiude con Escape si ritroverebbe la guida
via per sempre senza averlo chiesto.

#### Ciò che non è cambiato passando da una forma all'altra

I quattro passi, il loro ordine — quello in cui le cose compaiono guardando una
risposta nascere — e il fatto che l'ultimo nomini «Che cos'è». È la risposta alla
domanda che il criterio non fa: se la guida non torna mai più, chi voleva
rileggerla va in una pagina che si apre quando si vuole, invece che in qualcosa
che si ripresenta a chi l'ha già letto. La guida è transitoria per costruzione, e
nomina ciò che è permanente.

**Si ricorda il passo, non solo che è finita.** Costa lo stesso e paga due volte:
sopravvive a un ricaricamento — ed è metà del criterio — ma soprattutto
all'aprire «Che cos'è» o l'esploratore, che smontano la colonna della chat e con
lei qualunque stato tenuto in React. Arrivare al passo 3, aprire la pagina che il
passo 4 nomina e ritrovarsi al passo 1 sarebbe la guida che punisce chi le dà
retta.

**Il verso sicuro qui è l'opposto di quello di `corsia.ts`.** Un deposito storto
riparte dal primo passo e non dalla fine: il caso da proteggere è chi la guida non
l'ha mai vista. Nella corsia era il contrario, perché lì il caso da proteggere era
non perdere una colonna. Due default opposti, e nessuno dei due è «quello sicuro»
in astratto.

**Chi in questo browser ha già una cronologia non la vede affatto.** La chiave
`ibid.avvio` è nuova: senza questa regola, il primo avvio dopo U-20 avrebbe accolto
con un tour chi usa la demo da settimane. Una cronologia non vuota è l'unica prova
disponibile che la prima volta è già passata, e vale come una guida saltata —
perché lo è. Ma se il deposito dice qualcosa, comanda lui. Per la stessa ragione il
passo si scrive **anche al primo disegno** e non solo al primo clic.

**«Salta» e «Avanti» hanno la stessa veste, e nessuna è d'accento.** L'unico
bottone pieno dell'interfaccia è «Invia»: una guida che chiama più forte del campo
in cui si scrive starebbe chiedendo di essere letta prima che si faccia la cosa per
cui si è aperta la pagina. Fra i due non c'è nemmeno un primario — chi salta e chi
prosegue fanno due scelte legittime.

**Lo stato vuoto tace la propria riga finché la guida c'è**, perché è la versione
in una frase di ciò che i primi due passi dicono per esteso.

E la quarta richiesta del criterio — dichiarare di essere locale a questo browser
— sta nella scheda e non in un suggerimento, allo stesso posto in cui sta quella
della cronologia di U-13: è una promessa sul dato, non una nota d'aiuto. Dice
tutte e due le cose in una riga, perché sono la stessa promessa vista da due lati:
*«Puoi chiedere mentre è aperta. Saltata una volta non torna, e la scelta resta in
questo browser come la cronologia.»*

### U-21 — una colonna sola, e le altre due a un gesto

Il criterio: a **390 px** si fa una domanda, si legge la risposta coi verdetti e si
apre una fonte, **senza scorrimento orizzontale**; e vale ancora quello di U-02 —
la lista documenti resta **raggiungibile in ogni stato**, non necessariamente
affiancata. Sono due parole diverse, ed è tutta lì la forma di questa tappa.

**Il problema era una somma, non un'impressione.** Le due colonne laterali hanno
una misura fissa — 200 px la corsia, 272 il pannello fonti — e la colonna di lavoro
prende il resto. Dentro 390 px quelle due chiedono già 472, cioè più dello schermo:
non è un'impaginazione stretta, è un'impaginazione impossibile.

**La soglia si deriva, non si sceglie.** È la larghezza sotto la quale la colonna
di lavoro riceverebbe meno di 390 px, cioè meno di quanto ne riceve sul telefono su
cui il criterio si misura: `200 + 390 + 272 = 862`. Un numero tondo preso a occhio —
768, 1024 — sarebbe la misura del dispositivo di qualcun altro; questa è la misura
delle colonne che il progetto ha, e cambiandone una il numero si sposta da solo. Un
test lo dice come invariante e non come cifra: *finché è larga, la colonna di lavoro
non riceve meno di un telefono*.

**Due forme e non tre.** Un gradino in mezzo — corsia affiancata, fonti no — si
immagina facilmente, e costa un terzo posto in cui mettere il comando che apre le
fonti e un terzo insieme di stati da tenere giusti. Le larghezze che riceverebbe
sono proprio quelle in cui la colonna di lavoro è già stretta, ed è lì che darle
tutto lo schermo conviene di più. Chi da `larga` in giù vuole più spazio ha già la
corsia che si comprime (U-18).

**La forma non dipende né dalla corsia chiusa né dalla schermata aperta**, e sono
due deroghe rifiutate apposta. La corsia chiusa vale 152 px, abbastanza da far
rientrare le fonti: legarci la soglia vorrebbe dire che comprimendo la corsia
compare una colonna di fonti, cioè che un comando fa due cose diverse a seconda
della finestra. E la soglia conta il pannello fonti anche dove non c'è —
l'esploratore, «Che cos'è» — perché altrimenti la corsia si ritirerebbe in un
cassetto aprendo una schermata e tornerebbe chiudendola. Il telaio è l'unica cosa
di questa interfaccia che non deve muoversi.

#### Raggiungibile, non affiancata

A colonna sola le due laterali **non spariscono e non si nascondono**: escono dalla
griglia e diventano due strati sopra il lavoro. La traccia non resta lì a larghezza
zero — è lo stesso difetto che `corsia.ts` evitava chiudendo la corsia a 48 px
invece che a 0 — e infatti `colonne()` a `stretta` restituisce una traccia sola.

**La larghezza di uno strato è quella della colonna che sostituisce**, 200 e 272, e
non una frazione dello schermo. Tutte le misure di quelle due colonne sono state
accordate su quei numeri — i titoli di conversazione troncati a ~28 caratteri, il
nome del documento in 272 px — e dargliene di diverse qui vorrebbe dire tenere due
impaginazioni per lo stesso componente, di cui una non si guarda mai.

**Il velo è un bottone.** Chiudere toccando fuori è un comando, e un comando ha un
nome che si può leggere e un fuoco su cui si arriva col tasto di tabulazione. È lo
stesso token dell'avvio guidato — e lì non intercettava il puntatore perché la guida
non doveva impedire niente, mentre qui **deve**: sotto c'è roba coperta, e cliccare
alla cieca aprirebbe cose che non si vedono.

**Gli strati si animano, e U-18 aveva deciso il contrario.** Non è un
ripensamento: là il costo era rifare l'impaginazione della conversazione a ogni
fotogramma, perché a interpolare era una traccia della griglia. Qui uno strato sta
*sopra* il lavoro, si sposta con una `transform`, e sotto non si rimpagina niente.
Il movimento in più serve: da quale bordo arriva è l'unica cosa che dice dove torna
quando si chiude. 220 ms, non i 360 della guida — quello è un indicatore da
seguire, questo è un pannello che risponde a un dito e deve essere già arrivato.

**Una testata compare solo qui**, e in tutta la Fase 8 non ce n'era mai stata una:
nelle colonne non serve, perché il marchio sta in cima alla corsia e le fonti sono
già sullo schermo. Porta tre cose e nient'altro — il comando che riapre la corsia,
il marchio, e dove c'è una risposta di cui parlano le fonti. Non è il posto in cui
accumulare i comandi della schermata sotto: una testata che cambia contenuto
passando da una schermata all'altra sarebbe il difetto della corsia che cambia
larghezza, un piano più su.

**Sul comando delle fonti c'è il conteggio**, e non è un ornamento. Il pannello
affiancato si riempie *mentre la risposta nasce* — misurato in U-02: 0,27 s contro
3,01 s — ed è metà della ragione per cui U-02 lo voleva sempre visibile. Chiuso
dentro un foglio quel riempirsi non si vede più, e le fonti tornerebbero a essere
una funzione da andare a cercare. Il numero è la parte di quel segnale che sta in
una testata.

**Il cassetto si chiude su ciò che cambia schermata, e non su ciò che cambia
un'impostazione.** Nuova conversazione, una voce di cronologia, l'esploratore, «Che
cos'è»: quei quattro portano da un'altra parte, e lasciare il cassetto aperto sopra
la cosa appena aperta è fare il gesto a metà. Dataset, lingua e tema no: si cambiano
*per* guardare quello che c'è sotto, e chiudersi addosso costringerebbe a riaprire
per cambiare la seconda cosa. A dichiararlo è chi naviga — `usaChiudiCassetto()` —
che è la stessa forma di `zona()` in U-20. Il contesto sta in un file suo per non
fare un anello: lo provvede il telaio, ma a leggerlo sono i comandi della corsia,
che il telaio importa.

E nel cassetto lo stesso bottone **non «comprime» la corsia: la chiude**. Dire
altro sarebbe promettere una striscia di comandi che a colonna sola non esiste.

#### Le altre due schermate

**Il confronto si impila.** Affiancate le due risposte si leggono con un colpo
d'occhio; impilate si leggono una dopo l'altra, che è meno — ma restano **la stessa
pagina**, sotto la stessa domanda, e scorrere da una all'altra non chiede di
decidere niente. Due linguette invece ne nascondono una dietro un clic e la fanno
tornare a essere una seconda risposta in un filo: cioè esattamente i «due messaggi
consecutivi» che quella schermata esiste per non essere. A scorrere è il
contenitore e non le due sezioni, perché due riquadri di scorrimento dentro uno
schermo alto quanto uno solo danno mezzo schermo a testa.

**L'esploratore diventa un affondo di due schermate**, e non tre riquadri impilati.
L'elenco dei documenti è una cosa che si interroga — 494 voci su `ledger` — e messo
sopra la mappa costringerebbe a scorrerlo tutto ogni volta per tornare al documento
che si sta già leggendo. Le altre due invece si impilano davvero, perché sono la
stessa cosa vista da due distanze: la mappa dice dove sono caduti i tagli, il
dettaglio dice cosa c'è dentro quello scelto, e sceglierne uno sulla mappa riempie
il riquadro che gli sta appena sotto. I manici non ci sono, e non è una perdita:
servivano a spartire una larghezza fra tre colonne. Il contesto guadagna
`lascia()` — per risalire da un documento non basta sceglierne un altro — e accanto
al comando che risale c'è il nome del documento, che è l'unica cosa che dice **da
dove** si sta risalendo ora che l'elenco non è sullo schermo.

#### Quello che U-20 non poteva sapere

Due regole della guida portavano la scheda **esattamente sul campo in cui si
scrive**, cioè rompevano il criterio di U-20 («non impedisce di fare la prima
domanda») proprio sullo schermo su cui U-21 si misura.

La prima: `dentro` significava «in basso», per non coprire ciò che l'alone sta
indicando. Ragionamento giusto finché la zona è una colonna in mezzo a uno schermo
largo; su un telefono la zona che finisce `dentro` è **la colonna di lavoro
intera**, e in fondo a quella c'è sempre il campo. Fra il coprire l'inizio di ciò
che si indica e il coprire il campo, si copre l'inizio.

La seconda: il gradino «accostata al bordo» valeva su tutti e quattro i lati.
Misurato su 390 × 844, con la conversazione che finisce cento pixel sopra il fondo,
accostarsi «sotto» dava alla scheda i 78 px liberi più 72 presi dal campo. Ci si
accosta **solo di fianco**, dove quel che sporge finisce sul margine dello schermo;
sopra e sotto la colonna di lavoro non c'è margine, ci sono la testata e il campo.

E `collocaScheda` riceve `null` quando quel passo non ha un bersaglio su questo
schermo, invece di una finta zona grande quanto la finestra: a colonna sola due dei
cinque passi parlano di cose che stanno nel cassetto, quindi il caso è diventato
normale invece che raro — e passarlo com'è è ciò che permette alla funzione di
distinguerlo.

**Nessun passo nomina più una posizione.** «Il pannello a destra», «da qui si cambia
corpus»: a dire dov'è la cosa c'è l'alone, che la circonda; il testo dice che cos'è.
Una guida che indica il posto sbagliato è peggio di una che non indica.

#### Cosa non è cambiato

Il `zoom` a scalini di `index.css` non entra in questa storia, e si può provarlo:
la soglia più alta è 862 px e il primo scalino sta a 1.400, quindi in tutta la
banda in cui questa decisione si prende px di finestra e px di disegno sono la
stessa cosa. La conversione si fa lo stesso — «si converte al confine» resta la
regola — ma dimenticarla non potrebbe cambiare la forma del telaio.

#### I suggerimenti, e i due casi del tocco

Erano stati dati per scoperti — «si aprono al passaggio del puntatore, e su un
dito non si aprono affatto» — e la metà buona di quella frase era falsa. Su un
**dato** il tocco funzionava già da U-02: `Suggerimento` distingue il clic del
mouse dal tocco guardando se al momento del clic il puntatore è ancora sul
bersaglio, e su un tocco non lo è mai. Un punteggio, un marcatore, un `chunk_id`
non hanno nessun comando sotto, quindi il tocco non ha altro da significare e
apre la bolla.

**Dove sotto c'è un comando, no**, e lì il difetto c'era davvero: il tocco è già
preso — manda la domanda, cambia dataset, apre l'esploratore — e non può anche
voler dire «spiegami». Con una cosa da fare e due da dire, quella che si perde è
sempre la spiegazione: la bolla compariva un istante e spariva insieme alla
schermata che l'aveva aperta.

Lì la domanda si fa quindi **tenendo premuto** (450 ms, la soglia che iOS e
Android usano già: il gesto o è quello che chi tocca ha in mano, o non è niente).
Il clic che chiude la pressione non arriva al comando, e la bolla non se ne va
quando il dito si alza — un `pointerleave` arriva subito dopo il `pointerup`, e
chiudere lì vorrebbe dire non averla mai mostrata. Se ne va al tocco successivo,
ovunque cada, o con Escape.

**Non è una modalità che si accende sotto una certa larghezza**, ed è la
correzione che vale più del resto: si guarda `pointerType`, cioè **il gesto**,
non lo schermo. Un portatile con lo schermo a tocco non ha un passaggio sopra
nemmeno a 1.600 px, e un mouse in una finestra stretta ce l'ha eccome. La
distinzione fra i due casi non è un interruttore nuovo: è `fuoco`, che già
esiste e già significa «dentro c'è qualcosa che prende il fuoco», cioè un
comando.

Resta scoperta la **scoperta**: nessun segno dice che tenendo premuto si ottiene
qualcosa, esattamente come sul desktop nessun segno dice che fermandosi sopra si
ottiene qualcosa — `cursor-help` è tutto, e su un dito non c'è un cursore. È il
prezzo di una spiegazione che non occupa posto quando non serve, ed è lo stesso
prezzo che il `title` nativo fa pagare da trent'anni.


### D-3 — il prompt di U-14 non costa conformità, e adesso c'è il metro per dirlo

Il debito chiedeva una cosa che D-1 e D-2 non potevano dare: non i numeri di
oggi, ma il confronto **appaiato** fra i due prompt sulle stesse domande. Quattro
run da 200 domande, due per corpus, stesso codice, stesso giorno, stesso stato
del motore; `--limit` prende le prime N rispondibili in ordine di golden set e il
golden set non si tocca da E-02, quindi fra i due bracci cambia il **prompt e
basta**. Il vecchio si rilegge dal sidecar del 12 agosto e torna a `3a50ef63`,
l'hash registrato allora: stessi byte, stesso `prompt_hash`.

**McNemar esatto**, sulle query che entrambi i bracci hanno risposto — solo le
discordanti portano informazione:

| dataset | | delta | discordanti | p |
|---|---|---|---|---|
| **open_ragbench** | grezzo | −0,0106 | 6 vs 4 su 188 | 0,75 |
| | dopo `parse()` | −0,0106 | 2 vs 0 | 0,50 |
| **ledger** | grezzo | +0,0069 | 1 vs 2 su 145 | 1,00 |
| | dopo `parse()` | +0,0138 | 0 vs 2 | 0,50 |

Nessuna differenza significativa, e **i segni non concordano fra i due corpus**:
il prompt nuovo perde un punto su `open_ragbench` e ne guadagna uno su `ledger`.
Due direzioni opposte della stessa dimensione sono il modo in cui il rumore si
presenta quando lo si guarda due volte.

#### La linea di rumore, che è la parte nuova

Il §15 vieta di dichiarare un miglioramento senza confrontarlo con la linea di
rumore, e per la generazione quella linea **va misurata**, non assunta zero: il
modello campiona, quindi la stessa configurazione girata due volte non si
riproduce domanda per domanda. Finora D-3 non ce l'aveva. Ora sì, perché il
braccio col prompt in vigore esiste in due copie — il 21 e il 22 agosto:

| dataset | replica dello stesso prompt | delta | discordanti |
|---|---|---|---|
| **open_ragbench** | 0,9149 → 0,9255 | **+0,0106** | 0 vs 2 su 188 |
| **ledger** | 0,9730 → 0,9662 | **−0,0068** | 1 vs 0 su 148 |

**L'effetto attribuito al prompt è grande esattamente quanto l'effetto di rifare
la stessa run**: 1,06 punti contro 1,06 su `open_ragbench`, 0,69 contro 0,68 su
`ledger`. Non è una coincidenza fortunata, è cosa vuol dire «non distinguibile»
quando lo si misura invece di dedurlo da un p-value.

#### I due nulli non sono lo stesso nullo, e la differenza conta

La replica cambia **2 risposte su 188**; il prompt ne cambia **10**, cinque volte
tante. La generazione a temperatura 0 è quasi deterministica anche fra giorni e
stati del motore diversi — più di quanto si potesse dire prima di avere la
replica — quindi quelle 10 sono davvero del prompt.

Ma le cambia **in due direzioni**: 6 peggiorano e 4 migliorano. Il prompt di U-14
non è inerte: sposta **quali** risposte sono conformi, non **quante**. Dire che
il formato nuovo non fa niente sarebbe falso; dire che non costa conformità è
ciò che i numeri sostengono, ed è l'unica delle due frasi che va nel README.

#### La previsione, e come va scritta adesso

L'argomento registrato prima di U-14 diceva che il markdown pieno avrebbe reso le
risposte *«più belle e meno verificate»* — celle senza citazione, e tabelle che
**fondono** numeri presi da chunk diversi in una struttura inventata dal modello,
cioè nascondono proprio il punto in cui la tracciabilità si perde. Quella
previsione **non si è avverata**, ed era già rimasta senza il suo meccanismo: D-1
e D-2 avevano trovato **zero tabelle generate** su 337 risposte valutate.

Va detto per intero, però: non è stata confutata l'idea che una tabella generata
sia meno verificabile di una frase — quella resta vera, e la verifica di C-03 è
ancora a livello di frase. È stata confutata la previsione che **questo prompt**,
su **questi due corpus**, avrebbe prodotto quelle tabelle. Il §7 tiene i
risultati negativi in tabella, e questo è un risultato negativo per una
previsione che avevo ragione di prendere sul serio.

#### Cosa è costato, e cosa si è imparato sul costo

Il ROADMAP stimava **2 h 30** per i due corpus a 22 s a domanda. Il tempo vero è
stato **50 minuti** per il primo giro e ~1 h per il secondo, a 8,6–10 s a
domanda. La differenza non viene da una manopola: viene dal fatto che le run del
21 agosto giravano a 21 s a domanda con il motore in uno stato che oggi
sappiamo riconoscere — vedi `docs/hardware.md`, «il confonditore». Le stime di
costo delle run che restano (D-4, l'affermazione 3) vanno riviste al ribasso in
proporzione, ma **solo dopo averlo verificato su una di esse**, non per analogia.


### D-19 — un rifiuto con parole proprie è un'astensione, ma solo dove ci sono le guardie

Il prompt chiede la stringa esatta `Insufficient information.`; su `ledger` tre o
quattro risposte per run rifiutano a modo loro — *«The provided context does not
contain the operating income figure for Barnwell Industries, Inc. for the year
2017.»* — e finivano contate come `no_citation`. Erano **l'intero divario** fra
0,9730 e 0,9931.

Le due letture erano tutt'e due difendibili: il modello ha disobbedito a
un'istruzione esatta, oppure ha rifiutato e basta. Ha vinto la seconda, per un
motivo che riguarda cosa la metrica dice di misurare: **una citazione mancante in
un rifiuto non è un difetto di citazione.** Contarla tale fa sì che
`citation_precision` misuri l'obbedienza al formato, che è un'altra affermazione
e ha già la sua metrica.

#### Il presupposto del debito era sbagliato, e la misura l'ha corretto

Il debito diceva: *«`ABSTENTION_PHRASES` è lo stesso elenco di E-04/E-05, quindi
allargarlo sposta anche quelle»*. Sposta molto meno di così, perché la lista è
una ma **i rilevatori sono due, con guardie diverse**:

| | dove | condizioni |
|---|---|---|
| `citation_format.is_abstention` | C-01, **e anche E-04/E-05** | frase **+ nessun marcatore + ≤200 caratteri** |
| `generation_harness.is_abstained` | baseline di generazione | **solo la frase** |

E-04/E-05 passa dal rilevatore **guardato**, non da quello nudo. Misurato sui
suoi dump: allargare la lista condivisa avrebbe cambiato **zero** risposte —
40/95 e 49/95 invariati — perché tutte e dieci quelle che contengono una frase
nuova **portano anche un marcatore**: il modello rifiuta *e* cita i chunk che ha
guardato. La sola guardia sui marcatori le esclude tutte.

L'unico effetto fuori dal percorso di citazione sarebbe stato sui baseline di
generazione: **una risposta su 250**, e per giunta un **falso positivo** — una
risposta lunga che risponde davvero e che nomina di sfuggita ciò che il contesto
non contiene.

#### Cosa è stato fatto

Una tupla separata, `SELF_WORDED_REFUSALS`, in `citation_format.py` e **non** in
`baseline_prompts.py`. La legge `has_abstention_phrase`, quindi arriva a
`is_abstention` e alle sue due guardie; non arriva a `is_abstained`, che non ne
ha. Le due liste differiscono perché i due rilevatori chiedono cose diverse — non
perché una sia rimasta indietro.

**Le frasi da sole sarebbero troppo larghe**, ed è esattamente il punto: «does
not contain» compare in molte risposte che rispondono. Sono usabili solo dietro
le guardie, e il test che fissa il caso è quello di Hain Celestial — risponde,
cita, e *poi* dice cosa manca per un altro anno.

#### I numeri, ricalcolati senza GPU

`rescore_citations.py` rilegge i dump e non riscrive mai un `EvalRun`
archiviato: i file in `eval/results/` restano ciò che fu misurato con lo
strumento del giorno, e la differenza è una correzione dichiarata invece di una
riscrittura silenziosa.

| run | registrata | ricalcolata | esito |
|---|---|---|---|
| `20260822_083237_ledger` | 0,9796 | **1,0000** | FAIL → **PASS** |
| `20260822_100304_ledger` | 0,9730 | **0,9931** | FAIL → **PASS** |
| `20260822_075435_open_ragbench` | 0,9255 | 0,9305 | FAIL |
| `20260822_092232_open_ragbench` | 0,9149 | 0,9198 | FAIL |

`ledger` passa la soglia di C-01 in tutt'e due i bracci. `open_ragbench` no, e
non la passava neanche prima: va detto ogni volta che si cita quel numero.

#### D-3 non cambia conclusione, e si può dimostrare invece che sperarlo

D-19 cambia lo strumento con cui D-3 era stato misurato poche ore prima. Rifatto
il confronto appaiato con la regola nuova:

| | vecchio | con D-19 |
|---|---|---|
| `open_ragbench` | A 0,9255 → B 0,9149, discordanti 6v4, p=0,7539 | A 0,9305 → B 0,9198, discordanti **6v4**, p=**0,7539** |
| `ledger` | A 0,9793 → B 0,9862, discordanti 1v2, p=1,0000 | A 1,0000 → B 0,9930, discordanti 1v0, p=**1,0000** |

La ragione strutturale è che McNemar legge **solo le coppie discordanti**, e una
risposta riclassificata come astensione era non conforme in tutt'e due i bracci,
cioè concordante: toglierla sposta i tassi e non il test. Su `ledger` una lo era
davvero — i discordanti passano da 1v2 a 1v0 — e il p resta 1,0000.

Il delta di `ledger` cambia segno, da +0,0069 a −0,0070. Vale la pena notarlo
perché è la miglior illustrazione di cosa significhi un nullo: **la direzione di
una differenza non distinguibile dal rumore non è un'informazione**, e chi la
citasse come «il prompt nuovo è leggermente meglio/peggio» starebbe leggendo il
rumore.


### D-7 — un numero senza la sua scala non è un dato

La pastiglia mostrava `0,717`. Il verdetto in parole c'era già accanto
(«sostiene»), quindi non era illeggibile — ma il numero, che è la parte che
dice *quanto*, non aveva niente contro cui essere letto. Il precedente era in
casa da sempre: `GateView` spedisce `threshold` accanto al proprio `score`.

**Due campi, perché sono due domande diverse.** `CitationView.threshold` sta
accanto al punteggio perché chi disegna la pastiglia non deve cercare la scala
in un altro oggetto; `ConfigView.entailment_threshold` sta nel registro della
run perché quel valore fa parte di cosa è girato, e `ConfigView` esiste per dire
esattamente quello.

**Non viene da `RequestConfig`, e la differenza è il punto.** Ogni altro campo
di `ConfigView` è ciò che la richiesta ha chiesto o ciò che il servizio ha
deciso al posto suo; questo è una costante del modulo, e `ConfigView.of` lo
dichiara con `_NON_DALLA_RICHIESTA` invece di lasciarlo dedurre al `getattr` che
riempie gli altri.

#### L'assenza è protetta, e il test guarda la cosa giusta

Una soglia scelta da chi chiama si potrebbe tarare **sulla stessa risposta che
deve giudicare**, ed è il modo esatto in cui `citation_precision` smette di
significare qualcosa. Quindi `QueryRequest` non la accetta, e un test lo fissa.

Il test guarda i **campi dichiarati**, non un errore di validazione: il modello
ignora gli extra invece di rifiutarli, quindi oggi una soglia inviata cade da
sola. Ciò che va impedito è che qualcuno la aggiunga domani, e solo la lista dei
campi lo vede.

Sul lato frontend la stessa assenza aveva un guardiano già esistente da non
rompere: `stessaConfigurazione` copia **tutti** i campi di `ConfigView` in un
rilancio di confronto, e un test conta le chiavi — un campo che non venisse
copiato uscirebbe dal confronto in silenzio, cioè diventerebbe la seconda
variabile che il §15 vieta. La soglia non si può copiare, quindi la rete
avrebbe dovuto rompersi. Invece di allentarla c'è ora `NON_RICHIEDIBILI`: la
sottrazione è dichiarata, il conteggio resta esatto, e **non copiarla è sicuro
per la ragione precisa per cui non è richiedibile** — è una costante, quindi
vale identica nei due bracci per costruzione, e il §15 parla di ciò che varia.

#### La scala entra nelle parole, non in un secondo numero

La pastiglia è un chip monospazio da 10 px che porta già glifo, verdetto,
punteggio e a volte un conteggio. Un altro numero lì dentro sarebbe una cosa da
decifrare, ed è l'errore già pagato una volta col conteggio `n/m` — due valori
diversi nello stesso posto senza etichetta. La spiegazione invece è **già
attaccata al punteggio**, in due modi insieme: la bolla per chi guarda,
`aria-describedby` per chi ascolta. È lì che una scala serve.

> «...il controllo dice: sostiene, 0,717 contro una soglia di 0,50.»
> «Sostiene se arriva a 0,50.»

**Due decimali per la soglia e tre per il punteggio.** Il punteggio è una misura
e i suoi millesimi distinguono un 0,499 da un 0,502; la soglia è una decisione
presa a numero tondo, e darle tre cifre suggerirebbe una precisione che non ha.

**La soglia viaggia dalla citazione fino a `EsitoScheda`** invece di essere una
costante del frontend. È il divieto di U-00: una copia scritta qui resterebbe
giusta finché qualcuno non cambia quella vera, e allora l'interfaccia direbbe la
propria al posto della sua. Un test la mette a **0,75** apposta, perché con 0,5
da tutte e due le parti le due implementazioni sarebbero indistinguibili.

E la nota che stava in `strings.ts` — *«la soglia non è scritta qui di
proposito: servirebbe un campo nel contratto, come `GateView.threshold`»* — se
n'è andata, che è il modo in cui un debito dichiarato si chiude.


### D-5 — la configurazione che ha girato smette di essere un mistero

Il §12 lo prometteva — *«restano sempre leggibili in "Dettagli della run", così
la configurazione che ha girato non è mai un mistero»* — e U-03 lo chiedeva come
criterio. Non esisteva: i quattro dati dell'indice erano usciti di scena quando
la chat ha preso la colonna centrale, e i parametri di «Avanzate» non
ricomparivano da nessuna parte.

**È per risposta, non per sessione**, ed è la decisione che ha determinato la
forma. Modello e opzioni si cambiano fra una domanda e l'altra, quindi «cosa ha
girato» è una proprietà dello **scambio**: il comando sta sotto la sua risposta,
accanto a «Confronta». Un pannello sempre presente avrebbe mostrato solo
l'ultima, e i parametri di uno scambio più vecchio non si sarebbero più potuti
rileggere — che è il difetto che il debito descriveva, spostato di un metro.

**È uno strato in tutte e due le forme del telaio**, e non una quarta colonna.
U-21 usa gli strati a colonna sola perché lì *sostituiscono* qualcosa; questo non
sostituisce niente. È un riferimento che si consulta e si chiude, e una colonna
permanente per qualcosa che si guarda due volte a sessione toglierebbe spazio
alla conversazione tutte le altre volte.

#### Un campo che mancava sul filo, e perché era il momento di accorgersene

`Answer.collection` esiste da sempre, con scritto accanto perché: *«la soglia di
astensione è calibrata per collection, non per dataset; riportarla è ciò che
rende il risultato ricostruibile.»* Lo stream però la lasciava cadere, e il
frontend poteva solo dedurla dal `dataset_id`.

È una deduzione **giusta quasi sempre e sbagliata quando conta**: `ledger` e
`ledger_routed` sono due indici dello stesso `dataset_id`, e «su cosa hai
cercato» avrebbe dato la stessa risposta a due run diverse. Il caso non è
ipotetico neanche dopo D-18 — che ha deciso di non offrirle nel **selettore**
(2026-08-24) — perché `QueryRequest.collection` le accetta comunque: la demo non
le propone, l'API ci risponde. Il
default è `""` e non il dataset — vale prima che la risposta finisca e sulle
risposte già in cronologia, che sono lo stesso caso: **non si sa**. Metterci il
dataset avrebbe indovinato giusto quasi sempre, che è il modo in cui un difetto
del genere sopravvive.

#### Quali campi si mostrano è una decisione, e sta fuori dal componente

`dettagli.ts` non disegna niente: dice quali campi, in che gruppi e in che
ordine. Sta lì perché è la parte che si può sbagliare **senza che si veda**: un
campo dimenticato non lascia un buco sullo schermo, lascia un'interfaccia che
sembra completa.

La rete è un test che conta — *ogni campo di `ConfigView` compare esattamente una
volta* — ed è lo stesso meccanismo di `stessaConfigurazione` per il confronto:
aggiungere un campo al contratto **rompe il test** invece di sparire in silenzio.
Per la stessa ragione l'elenco è esplicito e non `Object.keys(config)`: un ciclo
sulle chiavi darebbe righe nuove da solo, con l'etichetta mancante e il valore
grezzo, cioè inventerebbe interfaccia.

I gruppi sono le tre domande che uno si fa guardando una risposta e non
fidandosi: **dove** ha cercato, **come** ha cercato, **chi** ha scritto. La
verifica sta col resto della generazione perché è l'ultimo passo di quel
percorso, non un quarto argomento.

#### Le due bugie possibili erano tacere

`hnsw_ef` vale `null` quando lascia decidere Qdrant e `filter_content_type` vale
`""` quando non filtra niente: sono **scelte**, e una cella vuota si legge come
il contrario, cioè come un dato che manca. Si scrivono «predefinito», che copre
tutti e due i casi perché sul filo sono diversi e qui significano la stessa cosa.

E quando la risposta non dice su quale indice ha cercato, la sezione dell'indice
**non si disegna vuota**: una collection scritta senza i suoi numeri sembrerebbe
un indice vuoto, che è un'affermazione e falsa. Si dichiara assente, con la
ragione — salvata prima che il dato esistesse, oppure quella collection non c'è
più — perché tacere sarebbe corretto ma muto: chi guarda vedrebbe due sezioni
invece di tre senza sapere perché.

#### Due cose piccole, per il verbale

`Strato` è uscito da `Telaio.tsx` in un commit suo, **senza toccare niente
d'altro**: 338 test prima, 338 dopo, che è il controllo che dice che era davvero
un refactor. U-21 lo aveva scritto per la corsia e le fonti; D-5 lo riusa, e il
componente non è cambiato perché non doveva — sa entrare da un bordo e lasciarsi
chiudere, e quale dei casi stia servendo non è affar suo.

C'è un'**icona nuova**, `Chiudi`, e non è `Indietro`: una freccia dice «torna da
dove sei arrivato», cioè promette una navigazione. Un foglio non porta da nessuna
parte — si toglie di mezzo, e sotto c'è quel che c'era già.

### D-4 — la sessione di fine fase, e il reranker che fa una cosa sola

Otto configurazioni, due corpus, golden set completi — 3.045 query per
`open_ragbench`, 10.000 per `ledger` — **tutte in ricerca esatta**, per la ragione
scritta nella coda qui sopra. `top_k` 5, profondità 10, `pipeline_mode: generic`.

Le sei senza rerank sono girate il 22 agosto (8 minuti in tutto), le due col
rerank il 23 (**6 h 04**). Stesso percorso di recupero: fra i due giorni l'unica
differenza in `src/retrieval`, `src/index`, `harness.py`, `metrics.py` e
`config.py` è una funzione **aggiunta** a `embed.py` che nessuno di quei percorsi
chiama — verificato col diff prima di spendere le sei ore, perché otto
configurazioni misurate su codice diverso non sono otto configurazioni.

#### I numeri

| `open_ragbench` | nDCG@10 | Success@1 | RR@10 | R@5 | `doc_R@5` |
|---|---|---|---|---|---|
| dense | 0,7184 | 0,5448 | 0,6655 | 0,8279 | 0,9681 |
| sparse | 0,7855 | 0,6263 | 0,7370 | 0,8837 | 0,9882 |
| hybrid | 0,8004 | 0,6345 | 0,7450 | **0,9044** | **0,9954** |
| dense+rerank | 0,7873 | 0,6548 | 0,7469 | 0,8716 | 0,9829 |
| **hybrid+rerank** | **0,8053** | **0,6594** | **0,7593** | 0,8939 | 0,9915 |

| `ledger` | nDCG@10 | Success@1 | RR@10 | R@5 | `doc_R@5` |
|---|---|---|---|---|---|
| dense | 0,2465 | 0,2647 | 0,3833 | 0,2112 | 0,8962 |
| sparse | 0,0272 | 0,0291 | 0,0517 | 0,0214 | 0,8837 |
| hybrid | 0,1564 | 0,0986 | 0,2254 | 0,1287 | **0,9129** |
| **dense+rerank** | **0,2792** | **0,3110** | **0,4342** | **0,2473** | 0,8911 |
| hybrid+rerank | 0,2570 | 0,3056 | 0,4170 | 0,2274 | 0,9023 |

**La configurazione migliore dipende dal genere, ed è la quarta volta in questo
progetto.** Su `open_ragbench` vince `hybrid+rerank`, su `ledger` vince
`dense+rerank` — e su `ledger` la fusione, che sul corpus accademico è la scelta
più forte, è la **peggiore** delle due strade col rerank. Un'unica riga nel README
non esiste.

#### Il reranker fa una cosa sola, e la fa sempre

Test appaiati sulle stesse query, McNemar esatto (`compare_retrieved.py`).

**Success@1 — il chunk giusto al primo posto. Migliora ovunque:**

| | senza → con rerank | discordanti | |
|---|---|---|---|
| ORB dense | 0,5458 → **0,6542** | 534 a 204 | p < 0,0001 |
| ORB hybrid | 0,6207 → **0,6588** | 401 a 285 | p < 0,0001 |
| LED dense | 0,2642 → **0,3107** | 1615 a 1150 | p < 0,0001 |
| LED hybrid | 0,1421 → **0,3052** | **2201 a 570** | p < 0,0001 |

Quattro casi su quattro, e la riga più grande è **+16,3 punti**. Non c'è
ambiguità: mettere il candidato giusto in cima è precisamente ciò che un
cross-encoder sa fare, e lo fa su tutti e due i generi.

**`doc_R@5` — il documento giusto fra i primi cinque. Peggiora dove il recupero
era già buono:**

| | senza → con rerank | discordanti | |
|---|---|---|---|
| ORB dense | 0,9642 → **0,9806** | 63 a 13 | p < 0,0001, **vince il rerank** |
| ORB hybrid | 0,9924 → 0,9898 | 15 a 23 | p = 0,2559, **indistinguibile** |
| LED dense | 0,9398 → 0,9335 | 157 a 220 | p = 0,0014, **vince senza** |
| LED hybrid | 0,9566 → 0,9424 | 118 a 260 | p < 0,0001, **vince senza** |

La regola che le quattro righe disegnano: **dove c'era margine il reranker lo
prende, dove non ce n'era può solo rimescolare** — e rimescolando perde. Su ORB
dense partiva da 0,9642 e guadagna; su ORB hybrid partiva da 0,9924 e il
movimento sparisce nel rumore; su `ledger`, dove il documento giusto c'era già nel
94–96% dei casi, toglie mezzo punto e un punto e mezzo, e tutte e due le volte è
reale.

#### È lo specchio esatto di OQ-06

Quella domanda aperta descrive l'IDF su `ledger`: **porta al documento giusto e
allontana dal chunk giusto** (doc@5 +27,85, chunk@5 −1,31). Il reranker sullo
stesso corpus fa **l'opposto**: chunk@5 da +5,74 a +15,34, doc@5 da −0,63 a −1,42.

Due meccanismi diversi, lo stesso corpus, le stesse due metriche, e il segno
scambiato. Il che dice una cosa che nessuno dei due direbbe da solo: su `ledger`
**`doc_R@5` e la precisione a livello di chunk non sono due misure della stessa
cosa, sono due obiettivi in tensione.** Una domanda nomina un'azienda e un anno; i
documenti candidati sono tutti bilanci di quell'azienda; scegliere *quale pagina*
risponde è un problema diverso dallo scegliere *quale documento*, e migliorare il
secondo non implica migliorare il primo.

Per la generazione conta il chunk — è quello che finisce in contesto — quindi la
scelta è `dense+rerank`. Ma il prezzo va scritto accanto, non nascosto in una
media.

#### Il rerank salva la fusione su `ledger`, e questo dice cos'era rotto

`hybrid` su `ledger` senza rerank ha Success@1 a **0,0986**: praticamente non
mette mai il chunk giusto per primo. Col rerank va a **0,3056**, tre volte tanto,
e più di qualunque altra configurazione tranne `dense+rerank`.

Eppure `hybrid` senza rerank ha il **miglior `doc_R@10` non-rerank del corpus**
(0,9335). I due fatti insieme dicono che RRF su `ledger` produce un **insieme**
di candidati buono e un **ordinamento** pessimo: il chunk giusto è lì dentro, in
posizione sbagliata. È esattamente il difetto che un cross-encoder ripara, ed è la
ragione per cui il guadagno più grande delle otto configurazioni sta lì.

#### Il costo, e cosa la regola dei primi minuti ha e non ha comprato

| | query | durata |
|---|---|---|
| ORB dense+rerank | 3.045 | 40 min 43 s |
| LED dense+rerank | 10.000 | 2 h 13 min |
| ORB hybrid+rerank | 3.045 | 41 min 59 s |
| LED hybrid+rerank | 10.000 | 2 h 27 min |
| | | **6 h 04** |

Lo smoke da 200 query sulla combinazione più cara, fatto prima di lanciare, aveva
dato **0,69 s a query**; la media vera è **0,89**. Il preventivo era corto del
21%.

**Ed è comunque servito**, perché è la seconda cifra che conta: la stessa regola,
non applicata, aveva prodotto in questo progetto un preventivo sbagliato di
quindici volte (il 12B) e uno di cinque (T-02). Cronometrare i primi minuti compra
**l'ordine di grandezza, non il 20%** — e va scritto così, perché una regola che
promette più di quel che dà si smette di usare la prima volta che delude.


### D-4 (coda) — i numeri di LEDGER si riscrivono in ricerca esatta

D-4 doveva essere una sessione di misura e ha trovato un reperto: **l'indice
approssimato di `ledger` non è più quello di nove giorni fa** (OQ-09). Il
contenuto è intatto — la ricerca esatta restituisce le stesse sei cifre del 13
agosto, metrica per metrica — ma il grafo HNSW naviga peggio, e con la ricerca
approssimata `doc_R@5` passa da 0,8915 a **0,7705**.

Da qui la decisione, presa nel commit del ramo: **D-4 gira in ricerca esatta**, e
i numeri di `ledger` nel quaderno si riscrivono con quelli.

#### Le sei configurazioni senza rerank, nelle due ricerche

Dodici run piene su `b1ffe32`, tre modalità per due corpus, una volta in ANN e una
in esatta. Golden set completi: 3.045 query per `open_ragbench`, 10.000 per
`ledger`, profondità 10, `top_k` 5, `pipeline_mode: generic`.

| | | nDCG@10 | `doc_R@5` | `doc_R@10` | R@5 | Success@1 |
|---|---|---|---|---|---|---|
| **open_ragbench** | `dense` | 0,7184 | 0,9681 | 0,9777 | 0,8279 | 0,5448 |
| | `sparse` | 0,7855 | 0,9882 | 0,9941 | 0,8837 | 0,6263 |
| | `hybrid` | **0,8004** | **0,9954** | **0,9974** | **0,9044** | **0,6345** |
| **ledger** | `dense` | **0,2465** | 0,8962 | 0,9159 | **0,2112** | **0,2647** |
| | `sparse` | 0,0272 | 0,8837 | 0,9231 | 0,0214 | 0,0291 |
| | `hybrid` | 0,1564 | **0,9129** | **0,9335** | 0,1287 | 0,0986 |

Su `open_ragbench` questi sono **anche** i numeri in ANN: le due ricerche danno
sei metriche identiche a sei decimali su tutte e tre le modalità. Su `ledger` no,
e la differenza cade esattamente dove c'è un grafo di mezzo:

| `ledger` | ANN | esatta | Δ |
|---|---|---|---|
| `dense`, `doc_R@5` | 0,7705 | **0,8962** | **+0,1257** |
| `hybrid`, `doc_R@5` | 0,8740 | **0,9129** | +0,0389 |
| `sparse`, `doc_R@5` | 0,8837 | 0,8837 | **identico** |

`sparse` è identico perché l'indice sparso non passa da HNSW. È il controllo
interno della tabella: se il divario fosse contenuto dell'indice invece che
navigazione, si vedrebbe anche lì.

#### Cosa vuol dire riscriverli, e cosa si compra

Poco, in valore. Il `doc_R@5` denso pubblicato il 13 agosto era 0,8915 e diventa
0,8962; l'nDCG@10 era 0,2422 e diventa 0,2465. Quattro millesimi, tre.

**Quello che si compra non è precisione, è che i numeri si riproducano.**
Rieseguire oggi la riga in ANN dà 0,7705 e nessun campo del risultato spiega
perché; rieseguire la riga in esatta dà le stesse sei cifre di nove giorni fa, e
le darà anche dopo la prossima riorganizzazione dei segmenti.

#### Le righe già pubblicate, e come vanno lette

Nessuna è stata cancellata. Le misure in ANN sono vere — sono state fatte, con
quell'indice — ma **non si riproducono più**, e chi le rieseguisse oggi troverebbe
altro senza sapere perché. Accanto a ognuna c'è ora la nota che lo dice.

| dove | il numero in ANN | in esatta | |
|---|---|---|---|
| R-07 (sopra) e OQ-01 | `ledger` generic 0,8916 → routed 0,6744, −17,03 pt appaiati | 0,8962 → 0,7590, **−13,72** | l'esatta era già stata misurata da R-11; lì il numero in ANN è metà del confronto e resta dov'è |
| R-11, *«non è la taglia»* | `ledger` 0,8915 → 0,8962, **+0,0046** | oggi lo stesso guadagno vale **+0,1257** | il segno regge, la grandezza no |
| R-11, richiamo dell'indice | `ledger` 0,9892 del vero top-5 | oggi **0,8356** | è la misura che il reperto ha spostato, ed è la causa di tutte le altre |

#### Le run di generazione del 21 e 22 agosto sono girate sull'indice cambiato

E questo tocca **D-1, D-2, D-3 e D-19**, che hanno confrontato il prompt in vigore
con le due run del 12 agosto. Fra i due bracci non è cambiato solo il prompt: è
cambiato anche il recupero, che è precisamente ciò che il §15 vieta.

Misurato invece che assunto, sulle **100 query** che le due run di `ledger`
condividono:

| | |
|---|---|
| contesto identico | 72 su 100 |
| contesto completamente diverso | 20 su 100 |
| astensioni | 19 → 18 (7 contro 6 discordanti) |
| `format_compliance` sulle 75 valutate in entrambe | **1,0000 → 1,0000**, di cui 17 con contesto diverso |

Il recupero è cambiato per **un quarto** delle domande e la conformità non si è
mossa di una risposta. Il calo di `ledger` che D-1 registra (1,0000 → 0,9664)
viene quindi dalle query 101–200, che il 12 agosto non erano state fatte — ed è
esattamente ciò che D-19 ha poi identificato: **quattro rifiuti scritti con parole
proprie**, non un effetto del recupero.

Resta un difetto di metodo che non si cancella riportandolo bene: quel confronto
aveva due variabili, e che la seconda non mordesse si è saputo **dopo**. È il
motivo per cui il passo 3 di OQ-09 è `probe_ann_recall.py` prima di ogni run che
pubblichi numeri in ANN — un minuto, contro il rischio di scoprire a cose fatte
che i due bracci non erano confrontabili.

#### Cosa questa coda non riscrive

**Le due configurazioni col rerank**: sono girate il 23 agosto e stanno nella
sezione qui sopra. Il vincolo che teneva aperto il ramo — le otto configurazioni
sullo stesso percorso di recupero — è stato verificato col diff invece che
assunto: fra il commit delle sei e quello delle due, `src/retrieval`, `src/index`,
`harness.py`, `metrics.py` e `config.py` differiscono per una funzione **aggiunta**
a `embed.py` che nessuno di quei percorsi chiama.

**I numeri di `open_ragbench`**: non c'era niente da riscrivere. ANN ed esatta
danno le stesse sei cifre, che è il motivo per cui il reperto è di `ledger` e non
del progetto.

### D-17 e U-23 — una lista che dichiarava una cosa che nessuno aveva verificato

`esempi.ts` diceva: *«sono query d'oro vere, prese da `eval/golden`, perché il
primo clic di chi prova il progetto non deve finire in un'astensione»*. La
premessa era vera e la conclusione no, e lo scarto fra le due è tutto il task:
**una query d'oro ha dei qrels, non la garanzia che il recupero li trovi.**

Misurato adesso, con la configurazione con cui la demo parte (`dense`, `top_k` 5):
su `ledger` solo il **35%** delle query d'oro porta il proprio chunk nei primi
cinque. Una presa a caso ha circa una probabilità su tre.

#### Cosa ha trovato la verifica

Il debito aveva ragione, e i numeri esatti sono questi:

| esempio | ANN | esatta |
|---|---|---|
| ORB — approccio MLMM e RMSE | 1 | 1 |
| ORB — indipendenza posizione/classe | 1 | 1 |
| LED — spesa in conto capitale di Sherwin-Williams 2017 | 5 | 5 |
| LED — crediti verso clienti di Sherwin-Williams 2017 | **mai** | **mai** |

Ma ne ha trovato anche uno che il debito non sapeva, ed è il più serio: **i due
esempi "fuori corpus" non chiudevano il gate.** 0,8225 contro una soglia di
0,7924 su `open_ragbench`, 0,8417 contro 0,8289 su `ledger`.

L'astensione che la demo mostrava era vera, ma **per la ragione sbagliata**: a
deciderla era il modello che scriveva *«Insufficient information»*, non la soglia
calibrata di C-04. Sono due meccanismi diversi e il §15 ne preferisce uno in modo
esplicito — *«la soglia di astensione e il formato di citazione si decidono in
codice, mai lasciati al modello»*. La demo stava dimostrando l'altro.

#### Il criterio, e perché è doppio

Ogni esempio adesso dichiara **cosa deve succedere**, ed è `atteso` nel file:
il `chunk_id` e la posizione, oppure che il gate si chiuda e con quanto margine.
Il tipo è un'unione, quindi un esempio nuovo **non si può aggiungere senza dire
quale dei due casi è** — che è la stessa forma di rete di `dettagli.ts` in D-5.

`scripts/verify_esempi.py` lo controlla contro l'indice vero, **in ricerca
approssimata e in esatta**. Le due servono tutt'e due perché il default oggi è
l'ANN, il ROADMAP prevede che la demo giri in esatta, e `make dev` e il profilo
`demo` potrebbero non coincidere: un esempio che regge in una sola delle due si
rompe a seconda di come lo si avvia.

> Un controllo che si accontentasse di *«ha trovato qualcosa»* passerebbe anche
> il giorno in cui trova un chunk **diverso** da quello previsto — e su `ledger`,
> dove i bilanci della stessa azienda si somigliano molto, quel giorno arriva.
> Per questo si verifica il chunk dichiarato e non un qrel qualsiasi.

Lo script **legge il TypeScript** invece di tenere una copia dell'elenco: due
elenchi da allineare a mano sono un elenco solo che ogni tanto mente, ed è
letteralmente il difetto da cui nasce questo task. Il parser è rigido apposta —
conta gli esempi, pretende che ogni `query` abbia il suo `atteso` — così un
cambio di forma del file lo fa **fallire** invece di fargli controllare meno di
quello che deve.

#### I nuovi esempi, e come sono stati scelti

`--cerca DATASET` propone query d'oro **verificate**, ordinate per posizione
peggiore fra le due ricerche. I due di `ledger` vengono da lì e arrivano **in
posizione 1 in tutt'e due**; i due di `open_ragbench` erano già a posto e non si
toccano — l'unica cosa che serviva era guardarli.

Per i «fuori corpus» il criterio è più stretto: devono **chiudere il gate**. Ed è
qui che è saltato fuori un fatto che vale oltre la demo:

> **Su `ledger` cambiare anno non basta.** Quattro domande della forma «stessa
> azienda, un anno che il corpus non ha» passano tutte il gate. A chiuderlo è
> l'**azienda** assente: Microsoft chiude, il 2024 di Sherwin-Williams no.

È **OQ-10**, perché la spiegazione candidata è che la soglia sia stata calibrata
su una popolazione che non somiglia al caso vero — le non rispondibili di E-02
sono costruite incrociando i corpus, cioè sono lontanissime.

Fra i candidati che chiudono, la scelta è andata al **margine**, non alla
bellezza: sette domande accademiche inventate per `open_ragbench` stavano fra
−0,025 e +0,007 dalla soglia, cioè o passavano o ci andavano così vicino da non
reggere il prossimo cambio d'indice. Ha vinto una query d'oro non rispondibile di
E-02, a **+0,0227**. Su `ledger` la domanda su Microsoft sta a +0,0078: è più
stretto, è accettato perché quella domanda ha la stessa forma dei due esempi
buoni — e il margine è **scritto nel file**, così lo script avvisa quando si
dimezza invece di scoprirlo quando sparisce.

#### Due reti invece di una

Lo script ha bisogno di Qdrant e dell'indice vero, quindi non gira nella suite.
`esempi.test.ts` copre l'altra metà, quella che si vede senza accendere niente:
tre esempi per dataset, **uno solo** fuori corpus e in fondo all'elenco, il chunk
dichiarato che appartiene al dataset giusto, il margine positivo, e il testo
inglese identico alla query che parte — perché i due stanno uno sopra l'altro
nello stato vuoto, e se differissero chi legge in inglese vedrebbe una domanda e
ne manderebbe un'altra.

#### Cosa questo lascia a U-08

I `chunk` dichiarati sono ora **esattamente ciò che l'indice ridotto del profilo
`demo` deve contenere**. Prima il vincolo era scritto a parole in un commento;
adesso è un elenco di sei identificatori che uno script sa leggere.

### D-18 — le collection instradate restano fuori dall'interfaccia

**Deciso il 2026-08-24. È una chiusura per decisione, non per lavoro fatto: il
codice non cambia di una riga.**

Il debito era scritto come una domanda di presentazione — *offrire
`open_ragbench_routed` e `ledger_routed` raddoppierebbe l'elenco dei corpus con
due voci che sono varianti dello stesso, e va deciso come si presentano* — e
dava per scontata la risposta: che si presentano. Il ROADMAP arrivava a dire che
D-18 era **«l'unica cosa che rende l'affermazione 2 visibile invece che solo
scritta»**. La decisione è l'altra: non entrano.

#### La ragione è un numero, non un gusto

In ricerca esatta — l'unico confronto legittimo fra due indici di densità
diversa, ed è il §15 dopo R-11 — il routing **perde 13,72 punti** di `doc_R@5`
su `ledger` e ne guadagna **1,06** su `open_ragbench`. Sul genere per cui la
pipeline instradata è stata scritta a mano, quella pipeline recupera **peggio**.

Un elenco di corpus che offre due strade non le sta descrivendo: le sta
dichiarando alternative alla pari. Chi prova il progetto non ha modo di sapere
quale delle due è peggio, e la demo non glielo può dire, perché **mostra una
risposta per volta e non sa confrontare niente**. Il risultato sarebbe una
scelta in più che non decide nulla, con metà delle risposte prese dal braccio
che recupera meno.

#### «Visibile» non era la parola giusta

L'argomento originale — renderlo visibile è ciò che lo rende confutabile — vale
quando il reperto è positivo. Qui è negativo, ed è il reperto più interessante
del progetto: confutarlo significa **rifare la misura**, cioè R-07 con
`compare_runs.py`, i due bracci sulla stessa riga e McNemar appaiato accanto.
Quella è la sede, e c'è già. Un menù a tendina non è un esperimento; mettercelo
avrebbe spostato un risultato dalla tabella dove si legge a un posto dove si
può solo aneddotare.

#### Cosa si perde, detto per intero

La targhetta di U-05 resta costante su «taglio generico»: si vede che il routing
**non** è in gioco, non lo si vede all'opera. Era già annotato in U-05 come
limite dichiarato, e da oggi è una scelta invece che un rinvio.

#### Cosa non cambia, ed è più di quanto sembri

- **Le due collection restano su Qdrant.** Sono il secondo braccio di R-07, cioè
  l'unica misura che decide l'affermazione 2: cancellarle libererebbe 2,1 GB e
  costerebbe la riproducibilità di un numero che finisce nel README.
- **Restano fuori dalle Release** (U-08), come già deciso: servono a chi
  riproduce, e chi riproduce ingerisce.
- **L'API le raggiunge ancora.** `QueryRequest.collection` le accetta, e
  `/datasets` le elenca già oggi nel campo `collections` — che è il motivo per
  cui vale la pena correggere la formulazione del debito: non è `/datasets` a
  pubblicare solo le generiche, è il **registro dei dataset**, e il selettore
  dell'interfaccia si costruisce da quello. `collections` esiste per chi
  ispeziona (A-06, la dashboard) e continua a vederle. Quindi non si toglie
  niente: si smette di **offrirle**, che è una cosa diversa e reversibile con un
  elenco.

#### Un effetto collaterale sulla ricerca esatta, che va scritto

Il §12 chiedeva che la demo girasse con `SEARCH_EXACT` acceso, e l'argomento
forte era proprio l'esposizione: con l'ANN, `ledger_routed` restituisce l'84,8%
del vero top-5 e più di una query su tre riceve un top-5 sbagliato (R-11), per
cui la demo avrebbe fatto vedere il routing **più il difetto dell'indice** — di
otto punti peggiore del vero. Fuori dall'interfaccia, quel rischio sparisce
insieme alla ragione.

La scelta resta comunque, per un argomento più debole e non nullo: **OQ-09**.
Sulle generiche la ricerca esatta sposta le metriche fra 0,0000 e 0,0046 e costa
2,5 ms contro 1,4 — niente in tutti e due i sensi — ma l'ANN di `ledger` ha reso
dodici punti in meno a configurazione identica, da solo, sotto un task che non
lo toccava, e la ricerca esatta riproduce bit per bit. Una dimostrazione che
qualcuno riavvia fra sei mesi ha più bisogno di quella garanzia di quanta ne
abbia la valutazione, che i propri numeri li rifà. **Non è ancora in
`compose.yml`**: resta lavoro di U-08, adesso con la sua ragione aggiornata
accanto.

### D-8 — la composizione esce dal JSX, e l'incrocio diventa provabile

Il debito era vecchio di dieci giorni e diceva già come si saldava: *«estrarre
la composizione in una funzione pura che restituisce intervalli invece di
nodi»*. Quello che è cambiato il 2026-08-24 non è la soluzione, è il momento: la
**tappa 3 è Q-07**, il refactor dell'interfaccia, e il suo gate dice *«il numero
di test Vitest non cala e nessuna schermata cambia comportamento»*. Su
[`Testo.tsx`](../ui/src/ui/Testo.tsx) quel gate era **vuoto** — 422 righe, il
file dove il refactor ha più da guadagnare, e nessun test a dire che il
risultato è lo stesso.

#### Le parti avevano i loro test, l'incrocio no

`markdown.ts` prova gli intervalli di enfasi e sintassi, `matematica.ts` il
taglio fra prosa e TeX, `verdetti.ts` quale verdetto tocca a quale occorrenza.
Sono tre elenchi di intervalli **sullo stesso testo**, e le decisioni difficili
stanno tutte in come si sovrappongono. Erano scritte nei commenti, con la loro
ragione, e verificate guardando lo schermo:

1. **La matematica taglia per prima.** Le annotazioni entrano dentro i suoi
   pezzi di prosa, non viceversa: `$x[3]$` — un indice fra quadre dentro una
   formula, che in un corpus di paper esiste — verrebbe spezzato a metà dal
   marcatore, e la formula non si comporrebbe più. Un errore di matematica rompe
   il disegno, un marcatore mancato resta leggibile.
2. **Gli intervalli si ritagliano, non si scartano.** Una frase scoperta che
   contiene una formula sta a cavallo di due segmenti, e una che attraversa due
   celle di tabella è lo stesso caso: metà sottolineatura è leggibile, nessuna
   no.
3. **I caratteri di sintassi spariscono all'ultimo passo.** Toglierli prima
   sposterebbe gli offset di ogni altro intervallo — ed è la ragione per cui
   `markdown.ts` restituisce posizioni invece di testo ripulito.

#### La lista è piatta, e non è un dettaglio

`composizione.ts` restituisce `Pezzo[]`: testo con la sua veste, marcatore,
formula, ognuno col proprio offset nel grezzo. Il disegno **annida** — un tratto
in grassetto e sottolineato sta dentro due involucri — e la lista no: un pezzo
porta le due cose insieme.

È una scelta contro l'istinto, e la ragione è Q-07. Un albero di nodi renderebbe
i test una descrizione della **struttura HTML**, cioè proprio la cosa che il
refactor ha il diritto di cambiare: cambierebbe l'annidamento e i test si
dovrebbero riscrivere, che è il modo in cui un test smette di essere un vincolo
e diventa un costo. La lista piatta descrive **cosa si legge e come**, che è
quello che non deve cambiare.

È la stessa mossa di `dettagli.ts`, che dice quali campi e in che gruppi senza
sapere che aspetto avranno, e per la stessa ragione: è la parte che si può
sbagliare **senza che si veda**.

#### Provati a mutazione, prima di essere creduti

I diciotto test sono passati **alla prima esecuzione**, che è esattamente la
condizione in cui un test non ha ancora dimostrato niente: può passare perché il
codice è giusto, o perché la sua asserzione non tocca il codice. Quindi sono
stati rotti apposta, uno per decisione:

| mutazione | test caduti |
|---|---|
| l'annotazione che non sta tutta dentro il tratto viene scartata | 3 |
| il segmento di prosa perde l'offset del proprio inizio | 4 |
| i caratteri nascosti non si saltano | 2 |

Tre minuti, e sono la differenza fra una suite e una decorazione. È la stessa
cautela che il §15 chiede alle misure — non dichiarare un miglioramento senza la
linea di rumore accanto: finché non lo si è visto fallire, non si sa che cosa
sia il test a tenere fermo.

#### Cosa questo **non** prova, detto per intero

Che l'interfaccia sia provata. Le classi, KaTeX, il componente del marcatore e
tutto ciò che ha un aspetto restano verificabili solo guardando: `ui/` non ha
jsdom, e la scelta di U-00 **non è stata riaperta** — il debito indicava questa
strada proprio per non doverla riaprire. Quel che ora si prova è **quali pezzi,
dove, con che veste**, cioè il calcolo. Il disegno resta un giudizio.

#### Cosa lascia a Q-07

Un gate che su quel file non è più vuoto: 376 test, e la parte che il refactor
toccherà di sicuro è la metà che adesso è misurata. Il refactor puro e i test
stanno in **due commit separati**, così che il primo dimostri da solo ciò che
dichiara — 358 test prima, 358 dopo.

### A-09 — la finestra la imposta il motore, e ventidue modelli se ne vanno

Segnalato da Marco il 2026-08-24, e non come un difetto del progetto: *«quando
voglio usare ollama indipendentemente ci sono ora un sacco di profili, uno per
ogni modello e contesto — non è una bella cosa da lasciare sul pc di qualcuno
che ha voluto provare il progetto»*. Su questa macchina erano **22 voci su 30**
in `ollama list`, e `ollama list` ripete la taglia del modello base a ogni riga:
a occhio, duecento GB di roba altrui. I blob sono condivisi e il disco non se ne
accorge; chi apre l'elenco sì.

#### Prima di cercare un rimedio, verificare che il difetto fosse ancora quello

A-08 aveva deciso il 19 agosto che la finestra viaggia col **nome del modello**,
dopo aver misurato che `num_ctx` mandato a `/v1/chat/completions` riceve *200 e
nessun effetto*. Cinque giorni non sono molti, ma la decisione andava
riverificata prima di essere aggirata:

- la documentazione di Ollama elenca i campi accettati da `/v1/chat/completions`,
  e la finestra non c'è;
- la PR che gliela aggiungeva è stata **chiusa dai maintainer** — *«non segue la
  spec di OpenAI: la API di OpenAI non permette di impostare la lunghezza del
  contesto»* — e la richiesta d'origine è chiusa con lei;
- la strada indicata al suo posto è, testualmente, il Modelfile.

**A-08 aveva ragione, e continua ad averla.** Quello che nessuno aveva
guardato è che la finestra si può impostare da un'altra parte: non nella
richiesta, ma nel **motore**.

#### La misura che ha deciso tutto

`OLLAMA_CONTEXT_LENGTH` non era stata considerata. Provata il 2026-08-24 senza
toccare il servizio di Marco — un secondo server sulla porta 11435, `OLLAMA_NOPRUNE=1`
per non fargli toccare i blob, una domanda da un token su `gemma4:e2b` **base**
attraverso `/v1`:

```
gemma4:e2b   1.9 GB   100% GPU   CONTEXT 32768
```

Nessun modello derivato. Poi, la stessa domanda al server vero, sempre sul
modello base — e qui è arrivata la cosa che il debito non stava cercando.

#### Le run giravano a 32k per fortuna

Anche il server di Marco, **senza nessuna variabile impostata**, dà 32768. Non è
una sua configurazione: `OLLAMA_CONTEXT_LENGTH` non è impostata da nessuna parte
(solo `OLLAMA_FLASH_ATTENTION=1`, messa a mano il 22). È il default automatico di
Ollama 0.32.15, che sceglie fra **4k, 32k e 256k** guardando la memoria.

Quindi ogni `EvalRun` scriveva `context_window: 32768` e la finestra vera era
32768 — **per coincidenza**. Su una macchina più piccola sarebbe stata 4096, e
con cinque chunk in contesto quella differenza non è un dettaglio di
registrazione: è una run che tronca senza dirlo, e un file di risultati che
dichiara il contrario.

Era già scritto, parola per parola, in **D-14**: *«oggi il numero è vero perché
il default di questo modello coincide, ma è una coincidenza, non una misura»*.
Il debito era stato registrato il 19 agosto e catalogato come cosmetico. Non lo
era.

#### Cosa è cambiato

**La finestra si imposta sul motore.** `OLLAMA_CONTEXT_LENGTH=32768`, dichiarata
in `STACK.md` accanto a `OLLAMA_FLASH_ATTENTION=1` — che nel frattempo non era
documentata in nessun `.md`, e vale un fattore quattro sul prefill del 12B. Sono
le due cose che il repo non può garantire da sé, perché stanno nel processo che
serve i modelli, e adesso stanno scritte dove le si cerca.

**La finestra si misura.** `EvalRun.context_window` è letta da `/api/ps`, l'unico
posto dove quel numero esiste. La misura la prende chi ha appena fatto girare il
modello — i tre harness — e non la fabbrica: `/api/ps` sa rispondere solo di un
modello **caricato**, e una chiamata dentro `make_eval_run` sarebbe una richiesta
HTTP per ogni `EvalRun` costruito. Misurato mentre lo scrivevo:
`test_generation_baseline` passava da **1,1 a 49,6 secondi**, e la suite intera
da 47 a 184. Il tempo era il sintomo; il difetto era che l'esito di quei test
avrebbe cominciato a dipendere da quale modello era caricato sulla macchina di
chi li lancia. Da lì `tests/conftest.py`, che fissa la regola per tutta la suite:
**nessun test parla col motore acceso**.

**`make dev` non crea più niente.** Al posto delle taglie, una riga sola e solo
quando serve: silenzio se la finestra attiva è quella dichiarata, il numero vero
se è diversa, dove si imposta se non si sa — che è il caso normale a un avvio,
perché `/api/ps` elenca i modelli caricati e all'inizio non ce n'è nessuno.

**Le taglie restano, sotto `ibid/` e a richiesta.** Sono ancora l'unico modo di
rendere la finestra *scegliibile* (U-16), quindi non si buttano: `ibid/gemma4-e2b:32k`
invece di `gemma4:e2b-32k`. Verificato che un namespace regge tutto il giro —
risponde su `/v1/chat/completions` a CONTEXT 32768, compare in `/v1/models`, e
conserva `parent_model: gemma4:e2b`, quindi il raggruppamento di U-16, che passa
dal genitore e non dal nome, non cambia di una riga. E riusa il blob del modello
base: **stesso ID** della taglia creata col nome vecchio.

#### `--pulisci`, e cosa non tocca

È l'unico comando del progetto che cancella qualcosa dalla macchina di chi lo
lancia, quindi elenca prima, spiega che i blob restano dove sono, e chiede
conferma. Senza terminale la risposta è **no**: un comando che cancella non
interpreta il silenzio come un sì.

Riconosce **solo** ciò che questo script avrebbe creato, coi due nomi che ha
usato — `ibid/...` e `<base>-32k` — e mai un modello senza genitore, che non è
una taglia ma dei pesi scaricati. Su questa macchina la differenza è concreta e
c'è un test che la fissa: propone le 22 giuste e lascia stare
`Qwen3.8-27B-IQ3-32k`, che è derivato, ha una finestra, ed è di Marco.

#### Cosa resta aperto

Una metà di D-14, ed è di contratto: il JSON non distingue «32768 misurato» da
«32768 creduto». Distinguerli vuol dire aggiungere un campo a `EvalRun`, cioè
toccare il §3 — e non si fa di passaggio, in coda a un altro task. Intanto chi
costruisce un `EvalRun` senza misura ottiene il valore dichiarato **e un avviso
su `stderr`**, che è il minimo che separi le due cose.

E una nota che vale per il futuro: delle **tre** variabili del motore che ormai
contano — finestra, flash attention, tipo di cache KV — il risultato ne registra
una sola. È **D-20** vista da un altro lato.

### Q-07 — la lista chiusa, scritta prima di aprire un file

Il criterio del task non parla di codice, parla di metodo: *«lista chiusa di
difetti scritta prima di toccare un file, ognuno con la prova che esiste»*. È la
regola con cui la Fase 6 si è tenuta finita, ed è qui perché un refactor senza
un bordo non finisce: finisce quando ci si stanca, e quello che resta a metà è
peggio di quello che c'era prima.

Quindi prima il censimento, e questo commit non tocca una riga di `ui/`.

#### Cosa il censimento **non** ha trovato

Vale la pena dirlo per primo, perché era l'ipotesi di partenza e si è rivelata
falsa. La logica dentro il JSX — il difetto grosso, quello che rende un file
impossibile da provare — **è già stata pagata**: l'ultima l'ha chiusa D-8 il
giorno prima. [`chat.tsx`](../ui/src/app/chat.tsx) è cablaggio, e il calcolo che
gli serve sta in `conversazione.ts`, provato; la geometria dell'esploratore sta
in `mappa.ts`, provata; le ventinove icone sono tutte usate.

Quel che resta non è struttura sbagliata: è **ripetizione e residuo**. Sette
voci, e nessuna di loro cambia cosa fa una schermata.

#### Le sette

| # | difetto | la prova |
|---|---|---|
| 1 | Sei depositi, sei `try/catch`, tre convenzioni di nome | `localStorage` è aperto in sei posti indipendenti — `avvio.ts`, `corsia.ts`, `Corpus.tsx`, `i18n.tsx`, `theme.tsx`, `scelta-dataset.ts` — ognuno col suo `try/catch` e lo stesso commento riscritto sei volte. Solo `cronologia.ts` prende il deposito **per parametro**, ed è l'unico di cui si prova il fallimento per quota |
| 2 | `PASTIGLIA` definita tre volte, con tre valori diversi | `pastiglia.ts`, `Telaio.tsx`, `Verdetto.tsx`. Il modulo esiste apposta per impedirlo, e lo dice la sua stessa intestazione |
| 3 | Due tabelle, due misure | `Corpus.tsx` disegna mono 10,5 px coi bordi pieni, `Testo.tsx` 12,5 px col bordo solo sotto. Stesso oggetto sullo schermo, due serie di numeri, nessuna delle due sa dell'altra |
| 4 | `Strato` è due cose diverse nella stessa cartella | il pannello che entra da un bordo (`Strato.tsx`) e uno strato della guida (dentro `Avvio.tsx`). Non hanno niente in comune tranne la parola |
| 5 | Ventisette `export` che nessuno importa | `AVANZATE`, `ATTRIBUTO`, `parolaDelVerdetto`, `Braccio`, `Veste`, `Segmento`… Nemmeno un test li nomina: il bordo del modulo dichiara pubblico ciò che è privato |
| 6 | Venti stringhe morte, dieci chiavi per due lingue | `app.tagline`, `nav.chat`, `nav.explore`, `index.*`: resti di una barra di navigazione e di un pannello indice che non esistono più, e non sono nemmeno costruite dinamicamente |
| 7 | `Corpus.tsx` a 871 righe, il doppio del secondo file | diciannove componenti, di cui tre disegnano cose generiche. Non è un difetto di dimensione: è che le tre colonne dell'esploratore e i mattoni di disegno stanno nello stesso file |

#### Le due voci che hanno un giudizio dentro

Cinque si eseguono senza decidere niente. Due no, e sono state discusse prima.

**La tabella (3) non si unifica all'aspetto, si unifica al codice.** Sono due
cose diverse davvero — un chunk del corpus e la risposta del modello — e
imporre a una l'aspetto dell'altra sarebbe **cambiare una schermata**, cioè
esattamente ciò che il gate vieta. Quello che si unifica è l'implementazione:
un disegno solo con due densità dichiarate, e i pixel restano quelli di prima.

**Spezzare un file (7) è la mossa che si fa più spesso senza guadagnarci.** Tre
file da 290 righe non valgono più di uno da 871 se poi si leggono sempre
insieme. Qui si sposta solo ciò che **non parla dell'esploratore** — un mattone
generico che sta lì per caso — e le tre colonne restano dove sono, perché sono
una cosa sola.

#### Cosa succede a ciò che si trova dopo

Va nel registro dei debiti, non dentro il task. La lista è chiusa: è quello che
significa la parola nel criterio.

#### Cinque saldate, e la prova che il refactor è puro

| # | difetto | come si è chiuso |
|---|---|---|
| 1 | sei depositi | `app/deposito.ts`: `CHIAVI`, `ricordato`, `ricorda`, e il `Deposito` iniettabile che `cronologia.ts` aveva già |
| 2 | `PASTIGLIA` per tre | non si unifica — sono **tre forme diverse**: restano `pastiglia.ts`, `CELLA`, `RIQUADRO` |
| 4 | `Strato` per due | quello della guida diventa `SopraTutto` |
| 6 | venti stringhe morte | via, e con loro l'intestazione «non ancora in uso» che ormai stava sopra roba in uso |
| 7 | `Corpus.tsx` a 871 righe | escono `Leggibile.tsx` e `Modo.tsx`: 871 → 722 + 133 + 43 |

Il caso più istruttivo è il **2**. La lista lo chiamava «duplicazione», e non lo
era: `pastiglia.ts` è una pillola da 11 px che si preme, quella di `Telaio.tsx`
un rettangolo da 7 px di raggio, quella di `Verdetto.tsx` un riquadro mono con
`tabular-nums` che non si preme affatto. Unificarle avrebbe cambiato dei pixel —
proprio ciò che il gate vieta. **Si separano i nomi, non le forme**, e ognuno
prende la parola che la sua parte di codice usava già in nota: la stessa nota di
`Telaio.tsx` parlava di «una colonna di celle da 34».

Del **7** vale la parte che *non* si è fatta. `Targa`, `Voce` e `Attesa`
sembrano mattoni generici e sono rimasti dov'erano: li usa solo l'esploratore, e
un modulo condiviso con un consumatore solo è un'astrazione in cerca di un
secondo. Le tre colonne, allo stesso modo, restano insieme — tre file da 240
righe che si leggono sempre in fila non valgono più di uno da 720.

#### Due si sono dissolte al contatto, e il perché conta più di loro

**La voce 5 diceva «27 export che nessuno importa». Ne restano tre.** Il conto
veniva da una domanda sbagliata — *chi mi nomina in un altro file?* — mentre
quella giusta è *sono raggiungibile da una firma esportata?*. Ventitré di quei
ventisette lo sono: `Frame` è il tipo di ritorno di `frames`, `ChunksPayload` un
ramo di `Evento`, `Veste` un campo di `Pezzo`. Nessuno li importa **oggi**, ma
sono la superficie nominabile di ciò che il modulo pubblica: toglierne l'`export`
darebbe un `Pezzo` pubblico con un campo di tipo innominabile — un difetto vero
al posto di uno immaginario.

**La voce 3, le due tabelle, non si è fatta affatto.** La lista prometteva «un
disegno solo con due densità dichiarate», e sul codice quella frase non regge:
`Testo.tsx` costruisce `<thead>` e `<th>` e riempie le celle con intervalli
composti, `Leggibile.tsx` non promuove nessuna riga a intestazione — perché
l'OCR di `ledger` non produce `<th>`, misurato su 2.758 tabelle — e passa
`colSpan`/`rowSpan` al browser. Un componente che portasse tutt'e due sarebbe più
complicato dei due che sostituisce, e la richiesta era *meno* complessità, non
meno righe. Ciò che davvero condividono è il contenitore che scorre: due `div`,
con classi diverse. Non si estrae un componente per questo.

Un censimento che non sopravvive al contatto col codice **in due voci su sette**
non è un censimento sbagliato: è quello che succede a una lista scritta prima di
aprire i file, ed è il prezzo della regola. Il prezzo è basso perché entrambe le
volte si è pagato con una riga di spiegazione invece che con un refactor
inutile.

#### Tre voci in più, dichiarate

A lista chiusa Marco l'ha riaperta: *«fai tutto quello che ritieni necessario,
l'obiettivo è rendere il codice pulito sia per capirlo che per complessità vera
e propria»*. Riaprirla su richiesta dell'autore è legittimo; farlo in silenzio
no, quindi ogni commit dice di essere fuori lista.

**L'ottava è l'unica che tocca qualcosa che si può rompere.** Tre callback di
`chat.tsx` — la domanda, il confronto, il prompt rifatto — ripetevano a mano la
stessa cerimonia, e la riga che conta è l'ultima:

```
void guida(...).finally(() => {
  if (controller.current === ctrl) { controller.current = null; setOccupato(false); }
});
```

Senza quel confronto, uno stream annullato che finisce **dopo** che ne è partito
un altro spegne l'occupato del nuovo: il campo si riapre e «Ferma» si spegne
mentre il modello sta ancora parlando. Tre copie a mano di un invariante di
concorrenza sono tre occasioni di scriverlo giusto due volte su tre, e la terza
non si vede finché non capita. Adesso è `avvia`, ed è la stessa ragione per cui
`guida` esisteva già.

La **nona** e la **decima** sono la stessa forma copiata: l'esploratore e «Che
cos'è» — le due pagine che si aprono sopra la conversazione — scrivevano due
volte le stesse quaranta righe, bottone «indietro» compreso, con la sua stringa
di classi lunga ottantuno caratteri; e i due comandi di corsia che cambiano
schermata la scrivevano quattro volte, due per comando. Da lì `Pagina.tsx`
(`Pagina`, `Ritorno`, `Collegamento`) e due costanti in `Telaio.tsx`. Anche qui
la scelta di dove fermarsi è la stessa della tabella: i due comandi di corsia
restano **due bottoni con una forma in comune** e non diventano un componente,
perché intorno differiscono — uno porta la zona della guida, l'altro un margine —
e un componente che prendesse anche quelle sarebbe una configurazione a sette
manopole.

#### La prova che nessuna schermata è cambiata

Il gate chiede due cose e una era facile da mostrare: **355 → 365** test, e le
dieci in più sono i casi del deposito, provati a mutazione prima di essere
creduti (lettura non protetta: 1 caduto; `null` scritto come parola: 1;
due `CHIAVI` uguali: 1; scrittura non protetta: 2).

L'altra metà — «nessuna schermata cambia comportamento» — in un frontend senza
jsdom è di solito un giudizio. Qui c'è un fatto: **il CSS costruito da questo
ramo è byte per byte identico a quello di `main`**. Tailwind genera il foglio
leggendo le stringhe di classe che trova nel codice, quindi due fogli identici
sono due insiemi di classi identici — e questo ramo ha toccato **ventun file** e
mille e cento righe senza spostare una classe. Il confronto costa due `npm run
build` e un `diff`, e il modo di farlo è un `git worktree` sul commit di
partenza.

Non prova tutto: la struttura del DOM, gli attributi, l'ordine dei nodi restano
fuori. Ma la classe di difetto che un refactor d'interfaccia produce più spesso —
una classe persa nello spostamento — quella è coperta, e prima non lo era.

#### Cosa lascia aperto

**D-22**, trovato e non saldato di proposito: la pillola del mockup esiste in due
misure — 11 px in `pastiglia.ts`, 10 px in `Modo.tsx` — e perché siano due non
risulta da nessuna parte. Unificarle cambia dei pixel, cioè il gate; va deciso
guardando, che è l'unico modo.

E resta vero ciò che D-8 diceva un giorno prima: quel che si prova di `ui/` è
**il calcolo**, non il disegno. `Pagina`, `Ritorno`, `Modo` e `CELLA` non hanno
un test e non possono averlo finché U-00 non si riapre. Ciò che è cambiato oggi
è che sbagliarli si vede in un `diff` del foglio di stile invece che in una
schermata aperta per caso.

### D-22 — quattro bottoni tornano nella famiglia, e il metodo di ieri mostra il suo limite

Nato da Q-07 e chiuso il giorno dopo, su richiesta di Marco: *«uniforma quei 4
bottoni»*. Sono le due coppie dell'esploratore — «Com'è stato spezzato» /
«Il testo indicizzato» nella colonna di mezzo, «Leggibile» / «Grezzo» sul chunk
scelto — e sono le uniche pillole dell'interfaccia che non venivano da
`pastiglia.ts`.

**La prova che erano parenti stava nello stato acceso.** `border-accent
bg-accent-soft text-accent`, identico carattere per carattere ai sei controlli
della barra; tutto il resto divergeva — 10 px contro 11, `text-muted` contro
`text-ink-2`, nessun fondo contro `bg-surface`. Una divergenza che sta tutta a
riposo e nessuna da acceso non è un disegno diverso: è una copia ritoccata.

**Prende `FORMA` e non `PASTIGLIA`**, e la differenza non è di gusto:
`PASTIGLIA` porta `pl-[7px] pr-2.5`, asimmetrici apposta per chi ha un glifo
davanti al testo. Questi non ce l'hanno. I margini interni sono quelli del
selettore del prompt di `Confronto.tsx`, che è l'altra pillola senza glifo — e
il modulo prevedeva già questa variazione, con due dei suoi sei siti che la
usano. Dopo il cambio la forma senza glifo è **una sola** in tutta
l'interfaccia.

#### Il CSS identico, qui, non prova niente

Vale la pena scriverlo perché ieri quello stesso confronto era la prova
principale di Q-07. Questo cambio è **visivo per costruzione** — quattro
bottoni cambiano misura — e il foglio costruito resta **byte per byte lo
stesso**: tutte le utility in gioco (`text-[11px]`, `bg-surface`, `text-ink-2`,
`px-2.5`, `py-1`) erano già usate altrove, quindi Tailwind le emetteva già.

Il confronto fra fogli vede una classe **persa**, non una classe **cambiata**.
È esattamente la classe di difetto che un refactor produce — uno spostamento
che si porta via una classe — e non è affatto quella che produce un ritocco.
Un metodo che ieri era una prova, oggi è muto: e saperlo vale quanto averlo.

### Tre ritocchi chiesti a vista, e due pixel che erano un meccanismo

Marco guarda il pannello «Avanzate» e la corsia dopo Q-07 e chiede tre cose
piccole. Due si esauriscono in una riga; la terza ha aperto un difetto di
geometria che c'era da sempre e che nessuno poteva vedere prima, e vale la pena
scriverla perché è la ragione per cui `pastiglia.ts` adesso **dichiara
un'altezza**.

#### Le tre richieste

1. **`Riordino` si chiama `rerank`.** È il nome del campo che parte sul filo e
   che compare in ogni `EvalRun` a disco: una traduzione onesta serviva a
   nessuno. Cambiato anche in «Dettagli della run» e in inglese, dove diceva
   «Reranking» — una manopola sola non può avere tre nomi in due lingue.
2. **Il numero fra i due segni.** `top_k` e `hnsw_ef` mettevano il ritorno al
   predefinito *in mezzo*, fra il valore e il più.
3. **Si esce dall'esploratore da dove ci si è entrati**: il comando che porta a
   una schermata è anche quello che ne riporta indietro, e nuova conversazione
   o una voce di cronologia riportano al filo.

Della terza vale la pena dire che **non era una funzione nuova**: la regola sta
già in `chat.tsx`, per il confronto, con queste parole — *«le tre azioni della
corsia riportano al filo… cambiare conversazione lasciando aperte due colonne
che parlano di una domanda dell'altra sarebbe la peggiore delle due uscite»*.
Non arrivava alle due pagine per una ragione di struttura: `ProvvedeEsploratore`
e `ProvvedePresentazione` stanno **dentro** `ProvvedeChat`, e un provider non
legge i contesti dei suoi figli. Quindi lo dichiara chi naviga, come per
`usaChiudiCassetto` — da cui `pagine.ts`, che ne è il gemello.

#### Due correzioni a vista sulla stessa manopola

La seconda richiesta è costata tre tentativi, ed è istruttivo perché nessuno dei
due sbagliati era assurdo.

Il primo spostava il ritorno **dopo** il più: il numero finiva in mezzo, sì, ma
i due segni finivano al centro e la pillola restava con un buco a destra. I
segni sono i comandi della manopola, e il loro posto è nella curvatura.

Il secondo li rimetteva ai bordi e centrava il numero con uno **specchio** —
diciotto pixel vuoti a sinistra, a bilanciare il posto del ritorno a destra.
Corretto in geometria, sbagliato in economia: la pillola arrivava a 103 px e il
pannello andava a capo. **Trentasei pixel riservati a un bottoncino che quasi
sempre non c'è.**

La terza sposta il ritorno fuori dalla manopola, accanto al nome del campo:
riguarda il campo, non il numero, e lì lo spazio è già libero perché la colonna
è larga quanto la pillola sotto. Manopola a tre pezzi, 67 px — più stretta di
com'era prima dei ritocchi.

#### Il disallineamento: tre cause, in ordine di quanto erano invisibili

Poi Marco dice che le voci del pannello non sono allineate, «e forse c'è anche
una differenza di scala». Di scala non c'era niente; il resto erano tre cose.

**Le altezze erano due.** Un menu era alto quanto la sua riga di testo — 11 px
per l'interlinea 1,5, più margini e bordi: **26,5** — e il numero a passi quanto
i suoi bottoncini da 18: **24**. Il pannello allinea le colonne in basso, quindi
quei 2,5 px diventavano due altezze di etichetta. Adesso l'altezza sta in
`FORMA`, dichiarata: 26 px per ogni pastiglia dell'interfaccia. È la lezione che
`Telaio.tsx` aveva già scritto sulle celle della corsia — *due controlli
affiancati che differiscono di due pixel non si leggono come due misure, si
leggono come un errore* — e le è arrivata sei giorni dopo, da un'altra parte del
codice.

**I margini orizzontali erano storti su quattro pillole.** `PASTIGLIA` ha
`pl-[7px] pr-2.5`, stretto a sinistra **apposta** per chi porta un pallino
davanti al testo. Se lo prendevano anche quattro pillole che un glifo non ce
l'hanno: `dense` stava a 7 px dal bordo e il caret a 10 dall'altro. Adesso
prendono `FORMA` con `px-2.5`, e `PASTIGLIA` resta a **un solo uso**, quello per
cui esiste.

**E la terza non era una misura, era un meccanismo.** Con le altezze pari le
pastiglie combaciavano, ma i nomi sopra i due menu restavano un pixel e mezzo
più in alto. La pastiglia è `inline-flex`, cioè **in linea**, e il selettore la
metteva dentro un `<div class="relative">`, che dispone i figli come testo: il
bottone si posava su una riga insieme allo strut del carattere ereditato. La sua
linea di base sta a ~18 px dal bordo di sopra, sotto gliene restano otto, e la
discendente dello strut ne chiede di più — riga alta ~27,6 px per una pastiglia
di 26, con l'avanzo **sotto**. In un riquadro isolato non lo vede nessuno; in
una riga di quattro colonne allineate in basso, l'avanzo fa combaciare le
pastiglie e alza le etichette.

`relative flex`, e la riga di testo non esiste più. Vale per **tutti** i
selettori — dataset, tema, modello — che avevano lo stesso avanzo da sempre,
senza che nessuno lo notasse: perché lì nessuno stava in fila con qualcos'altro.

#### Cosa ne resta come regola

Le prime due cause si trovano leggendo il codice; la terza no — richiede di
sapere che `inline-flex` dentro un contenitore di blocco genera una riga di
testo, e di andarla a cercare. La difesa che il progetto ha già trovato due
volte è la stessa: **dichiarare l'altezza invece di dedurla**. Dove è dichiarata
il difetto non nasce, perché non c'è niente da dedurre.


### U-11 — il README, e la vetrina che deve dire d'aver perso

`README.md` in italiano, `README.en.md` accanto, 237 righe ciascuno, rimando
reciproco in cima. La divisione era già decisa nel piano di chiusura: il
progetto è scritto in italiano — ROADMAP, questo file, i commenti nel codice —
e un README inglese davanti a un quaderno italiano prometterebbe una cosa che
il repo non mantiene. Il README inglese lo **dichiara**, invece di lasciarlo
scoprire a chi clicca il primo link.

#### Il criterio chiedeva due cose che erano la stessa cosa

Alla lettera: *le tre affermazioni compaiono ciascuna con la tabella per
dataset che la sostiene*, **e** *la sezione limiti nomina i risultati negativi
invece di ometterli*. Sembrano due requisiti indipendenti, e non lo sono:
**l'affermazione 2 è un risultato negativo**. Metterla fra i limiti avrebbe
soddisfatto la seconda metà violando la prima, e avrebbe consegnato una vetrina
di due terzi del progetto.

Sta quindi nel corpo, allo stesso livello delle altre due, col titolo che porta
❌ accanto ai due ✅, e con la tabella che la smentisce. Con due righe che non
sono decorazione: **otto dei ventidue punti di regresso erano il richiamo
dell'indice** e non la pipeline, e **le tre ipotesi sulla causa sono cadute
tutte**. Senza quelle due, il −13,72 è un aneddoto sulla sfortuna; con quelle,
è una misura di cui si sa cosa contiene.

#### Nessuna riga aggregata, in nessuna tabella

Il §3 vieta di mediare fra generi documentali, e il README è l'unico file del
repo dove quel divieto **non ha un test che lo protegga**. Applicato a mano,
tabella per tabella: ognuna ha due righe, e dove il lettore si aspetterebbe una
conclusione unica il testo dice che non esiste — *«una riga sola non esiste»*
per la configurazione di recupero, *«l'asimmetria fra 20% e 97% non è una
proprietà dei corpus»* per la confabulazione.

È anche la ragione per cui `citation_precision` e
`numeric_citation_precision` compaiono su due righe della stessa tabella e non
in due colonne: sono definizioni diverse, e affiancarle come colonne avrebbe
suggerito che si sommano.

#### L'avvio racconta ciò che parte oggi

`make up`, `make ingest`, `make dev`, più le due manopole di Ollama che valgono
un fattore quattro sul prefill. Il profilo `demo` — il modo in cui il progetto
si consegnerà — sta in una nota sola, dichiarato come non ancora attivo perché
gli manca l'indice committato di U-08.

La scelta è quella ovvia detta per intero: **un README che si apre con un
comando che non parte mente alla prima riga**, e chi lo prova smette di credere
anche al resto della pagina. Quando U-08 atterra, quella sezione si accorcia
invece di allungarsi.

#### Cosa il task non ha consegnato

- **Lo screenshot**, che il criterio nomina. Serve una cattura vera
  dell'interfaccia e ha senso farla insieme al video di **U-10**; un
  segnaposto rotto in una vetrina è peggio della sua assenza.
- **La descrizione «About» del repo**, che il §1 rende obbligatoria. Si imposta
  su GitHub e non vive in nessun file.
