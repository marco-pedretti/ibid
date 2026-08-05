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
EMBEDDING_BATCH: int = 32

# Sparse: BM25 via fastembed SparseTextEmbedding (CPU, no GPU needed — statistical model).
# Multilingual (18 language stopword lists), Apache 2.0. Used in R-01 hybrid RRF.
SPARSE_EMBEDDING_MODEL: str = "Qdrant/bm25"

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K: int = 5

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR: Path = ROOT / "data"
