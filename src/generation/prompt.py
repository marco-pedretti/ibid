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

**The output format is decided here, not observed in the UI (U-02).**  That rule
stands and is the reason this paragraph exists; what it *decides* was reversed on
2026-08-19 (U-14).  It used to say plain prose — no headings, lists, tables or
bold — and that choice was made because plain prose was what the renderer could
draw.  Deciding a contract from what the consumer happens to support is the
inverse of the rule it was written under.

Two things made the reversal necessary rather than cosmetic.  U-03 puts the same
question in two columns, with sources and without; the bare arm runs on
`baseline_prompts.py`, which has never carried a format rule, so a ban here meant
the two columns differed in *how they were written* as well as in what they had
to work from — the second variable §15 forbids.  And the model is a request
parameter that U-03 put in a menu on screen, which turns the hypothetical warning
this paragraph used to carry ("a larger model replying with a Markdown table
would arrive as literal pipes") into a thing a viewer can now cause with a click.

So the instruction invites the two formats the corpora actually contain, measured
on 1200 chunks: Markdown (headings in 100% of `open_ragbench` chunks and 77% of
`ledger`) and LaTeX (83% of `open_ragbench`).  HTML stays banned, and that is not
an oversight: 39% of `ledger` carries Mathpix HTML tables, the UI does not render
markup it did not parse itself, and a tag echoed into the answer would either
show as text or have to be trusted — which is a decision about injection, not
about typography.

**What did not change is the citation format.**  §3.2 is still contiguous
`[n][m]`, and the markers must survive emphasis: `**[2]**` parses, `[2](...)`
would not, and the rule below says so in the model's own language.  A format
freedom that broke the first claim of §0 would be a bad trade at any price.

**The cost is declared.**  This changes `prompt_hash`, so the 17 citation runs on
disk stop being comparable with anything measured after it — which is precisely
the job of that field.  C-01, C-02 and C-07 get re-measured once the interface is
finished; `baseline_prompts.py` is untouched, so E-04/E-05 stay comparable.

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
    "Use Markdown where it helps the reader: headings, lists, tables, bold, "
    "inline code. Do not use it for decoration.\n"
    "Keep formulas in LaTeX between $...$, as they appear in the context.\n"
    "No HTML tags, even when the context contains them.\n"
    "Citation markers are never inside a link: write **[2]** or [2], never "
    "[2](...).\n\n"
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
