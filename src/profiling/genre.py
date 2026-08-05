"""I-02: doc_genre assignment from document profile features.

Three genres map to three ingestion pipelines (I-03/I-04/I-05):
  "table_heavy"    → pipeline_table_heavy      (tables as atomic units)
  "academic_pdf"   → pipeline_structured_hier  (section-aware chunking)
  "continuous_text"→ pipeline_continuous_text   (paragraph + overlap)

Thresholds are module-level constants so they are easy to locate and adjust,
but they are NOT retrieval parameters — they live here, not in config.py.

Accuracy verified in I-02 on 50 sampled documents (25 per dataset):
  open_ragbench → expected "academic_pdf"  | ledger → expected "table_heavy"
  Combined accuracy: 45/50 = 90.0% — see docs/progress.md for details.
"""

from __future__ import annotations

# --- Threshold: table_density → "table_heavy" ---
#
# Chosen from the empirical gap between the two datasets (measured in I-01):
#   open_ragbench  mean=0.103  median=0.074  →  10.6% of docs exceed 0.25
#   ledger         mean=0.410  median=0.410  →   5.9% of docs fall below 0.25
#
# 0.25 sits roughly in the middle of this gap and minimises combined error
# (10.6% FP on open_ragbench + 5.9% FN on ledger → 90.0% combined accuracy).
# A lower value (e.g. 0.20) would mis-route 19% of ORB papers; a higher one
# (e.g. 0.30) would mis-route 11% of ledger annual reports.
# The 4 open_ragbench outliers above the threshold are papers whose JSON
# representation happens to be dominated by benchmark-result tables — routing
# them through the table_heavy pipeline is arguably correct for their content.
TABLE_HEAVY_THRESHOLD: float = 0.25

# --- Threshold: avg_section_len → "academic_pdf" vs "continuous_text" ---
#
# Measured on the two datasets:
#   open_ragbench  mean=5950 chars  median=4188 chars  (long structured sections)
#   ledger         mean=3674 chars  median=3624 chars  (shorter, table-interleaved)
#
# 1000 chars ≈ 150–200 words — enough to distinguish a structured section
# (abstract, methods, discussion) from a short news paragraph or legal clause.
# This threshold is provisional: we do not yet have a pure "continuous_text"
# dataset (novels, news, legal text) to calibrate it against. It will be
# revisited when a third dataset is added (see ROADMAP §2).
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
