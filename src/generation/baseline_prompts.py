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
#
# The "access" family was added on 2026-08-11 from real output, after the E-02
# runs of E-04/E-05 reported that the model invented an answer to 35 of 35
# unanswerable financial questions.  It had refused all 35 — every single time
# with a phrasing this list did not contain:
#
#     I do not have access to specific, real-time financial data ...
#     I do not have real-time access to specific, historical financial ...
#     I do not have access to external databases or ...
#
# On the answerable path the mistake was invisible, because a response the
# heuristic misses still goes to the LLM judge, which returns "abstained".  The
# unanswerable path has no reference to judge against and counted them as
# invented instead.  A backstop that hides a hole in the primary check is worth
# knowing about: the hole is only exposed where the backstop is absent.
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
    "do not have access",
    "don't have access",
    "do not have real-time access",
    "don't have real-time access",
    "non posso rispondere",
    "non ho informazioni sufficienti",
    "non so rispondere",
    "non lo so",
    "non so",
)
