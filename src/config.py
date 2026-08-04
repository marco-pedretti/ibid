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
EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"  # T-05: fastembed/ONNX (BGE-M3 target when DirectML lands)
EMBEDDING_BATCH: int = 32

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K: int = 5

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR: Path = ROOT / "data"
