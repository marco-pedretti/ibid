"""Prompt builder for cited answer generation.

Citation format is enforced here with an explicit example — see ROADMAP §3.2.
The model is never left to decide the format.

The negative examples are not decoration.  They were written from the failures
of the first C-01 measurement (200 queries, open_ragbench, gemma4:latest), where
19 of 22 non-compliant answers had one cause: **the model cited the source
document's own reference system instead of ours.**

    out_of_range   14 answers   [12], [21], [69], [121] — bibliography numbers
                                copied out of the paper.  12 of the 14 cited a
                                number that appears verbatim as [n] in the
                                chunk text.
    no_citation     5 answers   [Corollary 4.5], [D. 2], [Appendix D. Varying
                                fuel prices] — the paper's own structural
                                labels, so no [n] marker at all.

23% of open_ragbench chunks already contain `[n]` markers, because they are
academic papers and that is how papers cite.  A prompt that says "cite with [n]"
without saying which [n] is competing with the document for the same notation.
This is a property of the `academic_pdf` genre, not of the model.

**The output format is decided here, not observed in the UI (U-02).**  Two lines,
added once the chat screen had to draw what the model writes.  Without them the
renderer is tuned to whatever the *current* model happens to emit: gemma4 answers
in prose and echoes the corpus' LaTeX, so `$…$` and plain paragraphs were enough
— but the model is a request parameter, and a larger one that replies with a
Markdown table would arrive as literal pipes on screen.  This is the same rule
already applied to citations: the format is a contract, not a habit we measured.

The rules name only what the corpora actually produce, measured on 1200 chunks:
Markdown headings (100% of `open_ragbench` chunks, 77% of `ledger`), HTML tables
(39% of `ledger`, Mathpix Markdown), and LaTeX (83% of `open_ragbench`).  A
longer list would spend attention on formats nobody has seen.

**The output language (C-05).**  "Respond in the same language as the question"
was carried here from an early refactor and was never verified until C-05.  It
works: on 20 golden queries hand-translated into it/es/fr/de and asked against
the *same* English chunks, 14 of 14 answered questions came back in the language
asked, none mixed two languages, and all 14 still respected §3.2.  Reproduce
with `python scripts/probe_language.py`.

**The abstention string stays English on purpose, and is not a bug to fix.**
The same probe found that all 6 abstentions came back as `Insufficient
information.` whatever the question's language.  That is a protocol token, not
prose: `citation_format.is_abstention` matches it exactly, and a phrase that
varied per language would make the abstention rate depend on which language a
query happened to be written in — a metric moving for a reason that has nothing
to do with retrieval.  Localising it belongs to the UI (Fase 7), which renders
the token; it does not belong in the prompt.
"""

from __future__ import annotations

from src.datasets.schema import Chunk

#: The exact string the prompt asks for when the context is insufficient, and
#: the one the C-04 gate emits when it refuses before generating.  It is a
#: protocol token, not prose — see the note on the output language above — so it
#: lives in one place and both paths use it.
ABSTENTION_ANSWER = "Insufficient information."

SYSTEM = (
    "You are a precise research assistant. Answer the question using ONLY the provided context chunks.\n"
    "After each claim, immediately cite the source chunk(s) with [n] markers.\n\n"
    "CITATION RULES\n"
    "1. Valid markers are ONLY the chunk numbers listed in the context, from [1] upwards.\n"
    "2. The chunk text often contains the source document's own references — "
    "bibliography numbers like [12], or labels like [Corollary 4.5], [Appendix D], [Table 2]. "
    "Those belong to the document, NOT to you. Never copy them into your answer and never cite them.\n"
    "3. Multiple chunks are cited with contiguous markers and no separator: [1][2].\n"
    "4. Cite only chunks that directly support the claim.\n\n"
    "Correct:\n"
    "  The maximum value is 400ms [2][3]. The proposed model outperforms the baseline [1].\n"
    "Wrong:\n"
    "  The maximum value is 400ms [2, 3].     <- comma\n"
    "  The maximum value is 400ms [2] [3].    <- space between markers\n"
    "  The maximum value is 400ms [2]-[3].    <- dash\n"
    "  The maximum value is 400ms [2-3].      <- range\n"
    "  As shown in [Corollary 4.5], ...       <- the document's own label\n"
    "  As shown in [17], ...                  <- the document's own bibliography\n\n"
    "OUTPUT FORMAT\n"
    "Plain prose: no Markdown headings, lists, tables or bold, and no HTML tags, "
    "even when the context contains them.\n"
    "Keep formulas in LaTeX between $...$, as they appear in the context.\n\n"
    "If the context does not contain sufficient information, reply exactly: "
    f"'{ABSTENTION_ANSWER}'\n\n"
    "Respond in the same language as the question."
)


def build_user_message(query: str, chunks: list[Chunk]) -> str:
    """Render the context with each chunk numbered and delimited.

    The chunk number is stated twice — once as a delimiter line and once as the
    valid range at the top — because the alternative was a bare `[1]` prefix
    sitting flush against text that may itself open with `[12]`.
    """
    n = len(chunks)
    parts = [f"--- CHUNK [{i + 1}] ---\n{c.text}" for i, c in enumerate(chunks)]
    context = "\n\n".join(parts)
    valid = "[1]" if n == 1 else f"[1] to [{n}]"
    return (
        f"You are given {n} context chunks. The only valid citation markers are {valid}.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
