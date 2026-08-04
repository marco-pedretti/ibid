"""Data contracts from ROADMAP §3 — do not rename or add fields without updating ROADMAP.md."""

from datetime import datetime

from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_id: str    # "{dataset_id}:{doc_id}:{seq}"
    dataset_id: str  # "open_ragbench" | "vidore_v2" | "demo"
    doc_id: str
    doc_genre: str   # "academic_pdf" | "table_heavy" | "continuous_text"
    pipeline: str    # ingestion pipeline actually used
    section_path: str
    page: int
    bbox: tuple[float, float, float, float] | None
    content_type: str  # "text" | "table" | "figure_caption" | "mixed"
    text: str
    source_uri: str


class EvalRun(BaseModel):
    run_id: str
    timestamp: datetime
    git_commit: str
    config_hash: str
    dataset_id: str
    model: str
    quantization: str
    context_window: int
    temperature: float
    reasoning_enabled: bool
    pipeline_mode: str  # "generic" | "routed"
    metrics: dict[str, float]
