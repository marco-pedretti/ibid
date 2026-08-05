"""LLM-as-judge for generation evaluation (E-04, E-05).

One additional LLM call per response: given the question, the model's
response, and the reference answer, the judge returns CORRECT / WRONG /
ABSTAINED as a single word.
"""

from __future__ import annotations

from src.generation.chat import generate

_JUDGE_SYSTEM = (
    "You are an impartial evaluator.\n"
    "Given a question, a reference answer, and a model's response, "
    "classify the response as CORRECT, WRONG, or ABSTAINED.\n"
    "- CORRECT: the response is factually consistent with the reference answer\n"
    "- WRONG: the response contradicts the reference or makes clearly incorrect claims\n"
    "- ABSTAINED: the model explicitly said it does not know or cannot answer\n"
    "Reply with exactly one word: CORRECT, WRONG, or ABSTAINED."
)


def judge_answer(
    query: str,
    response: str,
    reference: str,
    base_url: str,
    model: str,
    temperature: float = 0.0,
) -> str:
    """Evaluate a response against the reference answer.

    Returns one of: "correct", "wrong", "abstained".
    Falls back to "wrong" on any unexpected verdict.
    """
    user_msg = (
        f"Question: {query}\n\n"
        f"Reference answer: {reference}\n\n"
        f"Model response: {response}"
    )
    raw = generate(
        base_url=base_url,
        model=model,
        system=_JUDGE_SYSTEM,
        user=user_msg,
        temperature=temperature,
        max_tokens=16,
    ).strip().upper()

    if raw.startswith("CORRECT"):
        return "correct"
    if raw.startswith("ABSTAINED"):
        return "abstained"
    return "wrong"
