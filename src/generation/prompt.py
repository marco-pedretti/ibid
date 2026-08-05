"""Prompt builder for cited answer generation.

Citation format is enforced here with an explicit example — see ROADMAP §3.2.
The model is never left to decide the format.
"""

from __future__ import annotations

from src.datasets.schema import Chunk

SYSTEM = (
    "You are a precise research assistant. Answer the question using ONLY the provided context chunks.\n"
    "After each claim, immediately cite the source chunk(s) with [n] markers.\n"
    "Use only contiguous markers like [1][2], never [1,2] or [1-2] or [1 and 2].\n"
    "Cite only chunks that directly support the claim.\n"
    "If the context does not contain sufficient information, reply exactly: "
    "'Insufficient information.'\n\n"
    "Respond in the same language as the question.\n\n"
    "Correct format example:\n"
    "The maximum value is 400ms [2][3]. The proposed model outperforms the baseline [1]."
)


def build_user_message(query: str, chunks: list[Chunk]) -> str:
    parts = [f"[{i + 1}] {c.text}" for i, c in enumerate(chunks)]
    context = "\n\n".join(parts)
    return f"Context:\n{context}\n\nQuestion: {query}"
