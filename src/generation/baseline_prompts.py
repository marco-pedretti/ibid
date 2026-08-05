"""System prompts for generation baselines E-04 (permissive) and E-05 (strict).

Baseline A — permissive: model answers freely from its knowledge.
Baseline B — strict: model is instructed to abstain when not certain.
"""

BASELINE_A_SYSTEM = (
    "Answer the question to the best of your ability.\n"
    "Respond in the same language as the question."
)

BASELINE_B_SYSTEM = (
    "Answer the question ONLY if you are certain the answer is correct.\n"
    "If you are not confident, reply with exactly this phrase: "
    "'I cannot answer without more information.'\n"
    "Do not guess or extrapolate.\n"
    "Respond in the same language as the question."
)

# Heuristic phrases that indicate the model declined to answer.
# Covers English and Italian; checked case-insensitively.
ABSTENTION_PHRASES: tuple[str, ...] = (
    "i cannot answer",
    "cannot answer without",
    "i can't answer",
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "unable to answer",
    "insufficient information",
    "non posso rispondere",
    "non ho informazioni sufficienti",
    "non so rispondere",
    "non lo so",
    "non so",
)
