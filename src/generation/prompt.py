"""Prompt builder for cited answer generation.

Citation format is enforced here with an explicit example — see ROADMAP §3.2.
The model is never left to decide the format.
"""

from __future__ import annotations

from src.datasets.schema import Chunk

SYSTEM = (
    "Sei un assistente di ricerca preciso. Rispondi alla domanda usando SOLO i chunk di contesto forniti.\n"
    "Per ogni affermazione, cita il/i chunk di provenienza con marcatori [n] immediatamente dopo l'affermazione.\n"
    "Usa solo marcatori contigui come [1][2], mai [1,2] o [1-2] o [1 e 2].\n"
    "Cita solo i chunk che supportano direttamente l'affermazione.\n"
    "Se il contesto non contiene informazioni sufficienti, rispondi esattamente: "
    "'Non ho informazioni sufficienti.'\n\n"
    "Esempio di formato corretto:\n"
    "Il valore massimo è 400ms [2][3]. Il modello proposto supera la baseline [1]."
)


def build_user_message(query: str, chunks: list[Chunk]) -> str:
    parts = [f"[{i + 1}] {c.text}" for i, c in enumerate(chunks)]
    context = "\n\n".join(parts)
    return f"Contesto:\n{context}\n\nDomanda: {query}"
