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
MAX_NEW_TOKENS: int = 1024

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

# Query rewriting (R-03): LLM rewrites the query before embedding.
# Uses LLM_BASE_URL / LLM_MODEL; override here for a dedicated smaller model.
QUERY_REWRITE_MODEL: str = os.getenv("QUERY_REWRITE_MODEL", "")  # "" = use LLM_MODEL

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR: Path = ROOT / "data"
