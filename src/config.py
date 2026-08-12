"""All retrieval and inference parameters live here.

An ablation is a loop over config, not a code change — see ROADMAP §3.4.
"""

import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# LLM (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:latest")
LLM_QUANTIZATION: str = os.getenv("LLM_QUANTIZATION", "Q4_K_M")
CONTEXT_WINDOW: int = 32768
TEMPERATURE: float = 0.0
# Overridable because C-07 needs both of its arms at 2048: with reasoning on,
# 1024 is spent thinking before the answer starts and half the generations come
# back truncated (see scripts/probe_reasoning.py). Raising it for the reasoning
# arm alone would change two things at once, so the control moves with it — and
# the control does not notice, since it never reaches the cap at either value.
MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "1024"))

# Gemma 4 is a thinking model. "none" suppresses the reasoning tokens through
# the OpenAI-compatible contract — see src/generation/chat.py for what does and
# does not work on Ollama's /v1. Set to "low"/"medium"/"high" for C-07, which
# measures the effect of extended reasoning. `EvalRun.reasoning_enabled` is
# derived from this value, so it stops being a hardcoded claim.
REASONING_EFFORT: str = os.getenv("REASONING_EFFORT", "none")

# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
# Dense: multilingual-e5-large via fastembed + onnxruntime-directml (AMD RX 6750 XT).
# Windows ML not used: MIGraphX EP requires exact driver and doesn't support GenAI models;
# DirectML (maintenance mode) remains the correct backend for this GPU.
# Target: BAAI/bge-m3 when fastembed PR #602 merges — re-ingest required.
EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
EMBEDDING_BATCH: int = 32  # TODO: provare 64 — I-07 ha girato 122 min con 32; se DirectML scala bene può dimezzare

# Sparse: BM25 via fastembed SparseTextEmbedding (CPU, no GPU needed — statistical model).
# Multilingual (18 language stopword lists), Apache 2.0. Used in R-01 hybrid RRF.
SPARSE_EMBEDDING_MODEL: str = "Qdrant/bm25"

# Dove fastembed tiene i pesi. Il suo default e' `%TEMP%/fastembed_cache`, cioe'
# una cartella che il sistema operativo ha il diritto di svuotare: il 2026-08-12
# Windows ha cancellato la directory `blobs` **durante** I-10, lasciando i
# symlink dello snapshot a puntare nel vuoto. L'indicizzazione era finita, la
# valutazione e' morta su `NO_SUCHFILE` dopo 80 minuti di GPU.
#
# `~/.cache/fastembed` sta accanto a `~/.cache/huggingface`, che nella stessa
# occasione e' sopravvissuta: e' una cache utente, non temporanea.
FASTEMBED_CACHE: str = os.getenv(
    "FASTEMBED_CACHE_PATH", str(Path.home() / ".cache" / "fastembed")
)

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K: int = 5

# Hybrid RRF (R-01): smoothing constant and candidate pool per index.
# Fetch HYBRID_FETCH_K from each of dense and sparse before fusing.
RRF_K: int = 60
HYBRID_FETCH_K: int = 20

# Cross-encoder reranker (R-02): model and candidate pool fed into the reranker.
# RERANK_FETCH_K candidates are fetched from initial retrieval; the reranker
# then scores all of them and returns the top_k best.
RERANKER_MODEL: str = "BAAI/bge-reranker-base"
RERANK_FETCH_K: int = 20

# ---------------------------------------------------------------------------
# Abstention gate (C-04)
# ---------------------------------------------------------------------------
# What a human chooses is the budget: how many *answerable* questions the system
# may refuse. The thresholds below are then derived from data by
# scripts/calibrate_abstention.py — that derivation is what makes the gate
# "decided by code" (ROADMAP §14) rather than a number somebody liked.
#
# 1% and not more, because the gate cannot improve the metric it is measured on:
# on E-02 the model already abstains 35/35 on both datasets. The gate exists as a
# guarantee for models that will not (C-06 runs E2B and E4B), and a guarantee
# should cost as little as possible.
ABSTENTION_BUDGET: float = 0.01

# Derived, per Qdrant collection. Only valid for the retrieval mode below and
# for the embedding model that produced the index: dense cosine scores sit
# around 0.8, RRF fusion scores around 0.02, and one threshold applied to the
# other abstains on everything or on nothing. Re-run the calibration after any
# re-ingestion or embedding change.
ABSTENTION_CALIBRATED_MODE: str = "dense"
ABSTENTION_THRESHOLDS: dict[str, float] = {
    "open_ragbench": 0.7924,
    "ledger": 0.8289,
}

# ---------------------------------------------------------------------------
# Entailment verification (C-03)
# ---------------------------------------------------------------------------
# The verifier behind citation_precision. Replaced mDeBERTa-v3 NLI after the
# measurement in scripts/probe_entailment.py — see STACK.md. MIT, multilingual,
# ships its own ONNX export, binary entailment/not_entailment head.
ENTAILMENT_MODEL: str = "MoritzLaurer/bge-m3-zeroshot-v2.0"

# The model's window is 8194 tokens. Truncation is set just under it.
ENTAILMENT_MAX_LEN: int = 8192

# Premise cap. Below it a chunk is one premise and there is no max-over-windows
# artefact; 96% of chunks are under it. Above it, windowing is cheaper than one
# quadratic pass: 123 ms at 758 tokens, 762 ms at 2951, 19.7 s at 7693.
ENTAILMENT_PREMISE_CAP: int = 4096

# Decision boundary for "supported". Deliberately the model's own natural
# boundary for a binary head, NOT tuned on our data: a threshold fitted on the
# same answers the metric is reported over inflates that metric by construction.
# Calibrating it needs a held-out split and is its own task. At 0.5 the verifier
# is pessimistic — it missed a third of verbatim-copied claims in the floor test
# — so citation_precision reported with it is a lower bound, which is the safe
# direction for a number meant to show the system can be trusted.
ENTAILMENT_THRESHOLD: float = 0.5

# Le premesse LEDGER sono OCR Mathpix: prosa con markup `<table>` dentro, fino al
# 77% dei token della premessa. Con questo attivo il markup diventa righe
# `cella | cella` prima della verifica. Parametro e non costante perche' il
# confronto fra le due varianti deve girare sulle stesse generazioni salvate
# (§3.4: un'ablation e' un ciclo sulla config). Default spento finche' C-08 non
# ha misurato: cambiarlo cambia `citation_precision` gia' riportata.
ENTAILMENT_RENDER_TABLES: bool = os.getenv("ENTAILMENT_RENDER_TABLES", "") == "1"

# Query rewriting (R-03): LLM rewrites the query before embedding.
# Uses LLM_BASE_URL / LLM_MODEL; override here for a dedicated smaller model.
QUERY_REWRITE_MODEL: str = os.getenv("QUERY_REWRITE_MODEL", "")  # "" = use LLM_MODEL

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR: Path = ROOT / "data"
