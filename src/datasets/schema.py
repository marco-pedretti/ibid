"""Data contracts from ROADMAP §3 — do not rename or add fields without updating ROADMAP.md."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

#: Il valore di `Chunk.pipeline` quando **nessuna pipeline ha girato**.
#:
#: La modalita' generica e' il termine di paragone di R-07: si prende l'unita'
#: che il documento offre gia' -- una pagina per `ledger`, una sezione per
#: `open_ragbench` -- e non si applica nessuna delle tre pipeline di `ingestion`.
#: Non e' un'assenza di dato: e' cio' che ha prodotto quel chunk, e detto cosi'
#: la targhetta di U-05 mostra una differenza dove una differenza c'e'.
#:
#: La parola e' quella di `EvalRun.pipeline_mode` (`"generic" | "routed"`) e non
#: una seconda: le due dicono la stessa cosa a due livelli diversi -- la run e il
#: chunk -- e due vocabolari per lo stesso fatto divergono al primo che cambia.
PIPELINE_GENERIC: str = "generic"


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
    config: dict[str, Any] = Field(default_factory=dict)  # retrieval flags, see eval/run_config.py
    metrics: dict[str, float]
