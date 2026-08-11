"""LLM generation via OpenAI-compatible endpoint (LLM_BASE_URL).

Gemma 4 is a thinking model.  Left alone it spends most of its token budget on
reasoning that never reaches `message.content`, so a capped request returns a
truncated answer — or an empty string, with `finish_reason: "length"`.

Suppression has to happen through the OpenAI-compatible contract (STACK.md:
inference is always reached through `LLM_BASE_URL`, never through a
vendor-specific endpoint).  Measured against Ollama 0.32.6 on one long-context
RAG prompt, completion tokens for the same answer:

    "think": false            1410   ignored — not an OpenAI field
    "chat_template_kwargs"    1410   ignored
    "enable_thinking": false  1410   ignored
    "reasoning_effort": "low" 1410   accepted
    "reasoning_effort":"none"  267   works
    (native /api/chat, think=false)  325   works, but is not the /v1 contract

`"think": false` was carried here from the T-02 smoke test, where it was
verified against Ollama's *native* `/api/chat`.  On `/v1/chat/completions` it is
an unknown field and is dropped silently, so every generation since T-05 has
been reasoning invisibly while `EvalRun.reasoning_enabled` recorded False.

**What the documentation says**, checked 2026-08-11 after C-07 turned up
behaviour the table above did not predict.  Ollama's `/v1` handler
(`openai/openai.go`, `FromChatRequest`) accepts exactly five values and rejects
anything else with a 400:

    if !slices.Contains([]string{"high","medium","low","max","none"}, effort) {
        return nil, fmt.Errorf("invalid reasoning value: ...")
    }
    if effort == "none" { think = &api.ThinkValue{Value: false} }
    else                { think = &api.ThinkValue{Value: effort} }

Three things follow, and all three were previously guesses here:

1. Omitting the field leaves `think` nil, and Ollama then **auto-enables**
   thinking on a capable model.  The invisible reasoning above was not a bug
   being worked around — it is the documented default.
2. `"none"` is a documented value that maps to thinking off, not an
   undocumented string that happened to work.
3. The endpoint passes the *level* through as a string.  Whether the level
   means anything is the model's business — and Google's Gemma 4 docs describe
   thinking as the boolean `enable_thinking`, with no graded levels.  So on this
   model the axis is on/off, which is what `scripts/probe_reasoning.py` measured
   independently: `medium`, `high` and the omitted field return byte-identical
   token counts query by query.

`"low"` is the one thing neither source explains: it is distinguishable from the
other three (888 median completion tokens against 993, half the truncations).
"accepted, no effect" in the table above was measured on a single prompt and is
not what a six-prompt probe shows.  Unresolved, and out of C-07's way: the arms
of a binary on/off row are `"none"` and the default-on state, and `"low"` is
neither.

`reasoning_effort` is a parameter rather than a constant because C-07 measures
the effect of extended reasoning on and off, and that is the switch.

Sources:
    https://docs.ollama.com/api/openai-compatibility
    https://github.com/ollama/ollama/blob/main/openai/openai.go
    https://ai.google.dev/gemma/docs/capabilities/thinking
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Completion:
    """A generation together with the evidence of whether it finished.

    `finish_reason == "length"` means the answer was cut off.  Scoring such an
    answer as if it were complete is how 3% of a run silently became empty
    strings that then counted as citation-format failures.
    """

    content: str
    finish_reason: str
    completion_tokens: int

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


def generate_detailed(
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    reasoning_effort: str | None = "none",
) -> Completion:
    """Generate and report how the generation ended.

    Args:
        reasoning_effort: OpenAI-standard reasoning control.  "none" suppresses
            the thinking tokens; None omits the field entirely for backends that
            reject unknown values with a 400.
    """
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"LLM HTTP {e.code}: {body}") from e

    choice = data["choices"][0]
    return Completion(
        content=(choice["message"].get("content") or "").strip(),
        finish_reason=choice.get("finish_reason", ""),
        completion_tokens=int(data.get("usage", {}).get("completion_tokens", 0)),
    )


def generate(
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    reasoning_effort: str | None = "none",
) -> str:
    """Generate and return the answer text only."""
    return generate_detailed(
        base_url, model, system, user, temperature, max_tokens, reasoning_effort
    ).content
