"""I-01: document profiler — computes per-document features used by genre routing.

Features derived from Chunk objects (available for any dataset):
  - n_sections, n_chars, has_text_layer
  - table_density, image_density, avg_section_len

Features that require raw PDF analysis (populated by I-06):
  - n_pages (0 = not yet extracted)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from src.datasets.schema import Chunk
from src.profiling.genre import assign_genre

_TABLE_TYPES = {"table", "mixed"}
_IMAGE_TYPES = {"figure_caption", "mixed"}
_TEXT_TYPES = {"text", "mixed"}


@dataclass
class DocProfile:
    doc_id: str
    dataset_id: str
    n_sections: int
    n_chars: int
    has_text_layer: bool
    n_table_sections: int
    n_image_sections: int
    table_density: float    # n_table_sections / n_sections
    image_density: float    # n_image_sections / n_sections
    avg_section_len: float  # n_chars / n_sections
    n_pages: int = 0        # populated by I-06; 0 = unknown
    doc_genre: str = ""     # assigned by I-02


def profile_from_chunks(chunks: Iterable[Chunk]) -> list[DocProfile]:
    """Group chunks by (dataset_id, doc_id) and compute per-document features."""
    groups: dict[tuple[str, str], list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        groups[(chunk.dataset_id, chunk.doc_id)].append(chunk)

    profiles: list[DocProfile] = []
    for (dataset_id, doc_id), doc_chunks in sorted(groups.items()):
        n = len(doc_chunks)
        n_chars = sum(len(c.text) for c in doc_chunks)
        n_table = sum(1 for c in doc_chunks if c.content_type in _TABLE_TYPES)
        n_image = sum(1 for c in doc_chunks if c.content_type in _IMAGE_TYPES)
        has_text = any(c.content_type in _TEXT_TYPES for c in doc_chunks)

        td = n_table / n if n > 0 else 0.0
        asl = n_chars / n if n > 0 else 0.0
        profiles.append(DocProfile(
            doc_id=doc_id,
            dataset_id=dataset_id,
            n_sections=n,
            n_chars=n_chars,
            has_text_layer=has_text,
            n_table_sections=n_table,
            n_image_sections=n_image,
            table_density=td,
            image_density=n_image / n if n > 0 else 0.0,
            avg_section_len=asl,
            doc_genre=assign_genre(td, asl),
        ))
    return profiles


def dataset_summary(profiles: list[DocProfile]) -> dict:
    """Return aggregate statistics for a list of profiles (same dataset_id)."""
    if not profiles:
        return {}
    n = len(profiles)
    return {
        "n_docs": n,
        "total_sections": sum(p.n_sections for p in profiles),
        "total_chars": sum(p.n_chars for p in profiles),
        "pct_with_text": sum(1 for p in profiles if p.has_text_layer) / n * 100,
        "mean_table_density": sum(p.table_density for p in profiles) / n,
        "max_table_density": max(p.table_density for p in profiles),
        "mean_image_density": sum(p.image_density for p in profiles) / n,
        "mean_avg_section_len": sum(p.avg_section_len for p in profiles) / n,
        "mean_sections_per_doc": sum(p.n_sections for p in profiles) / n,
    }


def format_report(profiles: list[DocProfile]) -> str:
    """Format a human-readable tabular report grouped by dataset."""
    if not profiles:
        return "(no documents profiled)"

    from itertools import groupby

    lines: list[str] = []
    def key(p):
        return p.dataset_id

    sorted_profiles = sorted(profiles, key=key)

    for dataset_id, group in groupby(sorted_profiles, key=key):
        grp = list(group)
        s = dataset_summary(grp)
        lines.append(f"\n=== Dataset: {dataset_id} ===")
        lines.append(f"  Documents   : {s['n_docs']}")
        lines.append(f"  Sections    : {s['total_sections']}")
        lines.append(f"  Total chars : {s['total_chars']:,}")
        lines.append(f"  Has text    : {s['pct_with_text']:.1f}%")
        lines.append(f"  Table density (mean / max) : {s['mean_table_density']:.3f} / {s['max_table_density']:.3f}")
        lines.append(f"  Image density (mean)       : {s['mean_image_density']:.3f}")
        lines.append(f"  Avg section len (mean)     : {s['mean_avg_section_len']:.0f} chars")
        lines.append(f"  Avg sections per doc       : {s['mean_sections_per_doc']:.1f}")

        # Top-5 most table-heavy docs
        top_table = sorted(grp, key=lambda p: p.table_density, reverse=True)[:5]
        if top_table and top_table[0].table_density > 0:
            lines.append("\n  Top-5 table-heavy docs:")
            lines.append(f"  {'doc_id':<30} {'sections':>8} {'table_dens':>10} {'img_dens':>8}")
            lines.append("  " + "-" * 60)
            for p in top_table:
                lines.append(
                    f"  {p.doc_id:<30} {p.n_sections:>8} {p.table_density:>10.3f} {p.image_density:>8.3f}"
                )

    return "\n".join(lines)
