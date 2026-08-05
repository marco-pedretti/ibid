"""I-02: doc_genre assignment from document profile features.

Three genres map to three ingestion pipelines (I-03/I-04/I-05):
  "table_heavy"    → pipeline_table_heavy      (tables as atomic units)
  "academic_pdf"   → pipeline_structured_hier  (section-aware chunking)
  "continuous_text"→ pipeline_continuous_text   (paragraph + overlap)

Thresholds are module-level constants so they are easy to locate and adjust,
but they are NOT retrieval parameters — they live here, not in config.py.

Accuracy verified in I-02 on 50 sampled documents (25 per dataset):
  open_ragbench → expected "academic_pdf"  | ledger → expected "table_heavy"
  Combined accuracy: see docs/progress.md
"""

from __future__ import annotations

# A page/section is table-dominated if this fraction or more of its
# peer pages in the same document contain HTML tables or Markdown tables.
TABLE_HEAVY_THRESHOLD: float = 0.25

# Below the table threshold, documents with long sections are academic PDFs
# (structured papers with abstracts, methods, references, etc.).
ACADEMIC_SECTION_LEN_THRESHOLD: float = 1000.0  # avg chars per section


def assign_genre(table_density: float, avg_section_len: float) -> str:
    """Return the doc_genre string for a document given its profile features.

    Args:
        table_density:    fraction of sections/pages containing tables (0–1)
        avg_section_len:  mean character count per section/page

    Returns:
        One of "table_heavy", "academic_pdf", "continuous_text"
    """
    if table_density >= TABLE_HEAVY_THRESHOLD:
        return "table_heavy"
    if avg_section_len >= ACADEMIC_SECTION_LEN_THRESHOLD:
        return "academic_pdf"
    return "continuous_text"
