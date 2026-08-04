"""LLM generation via OpenAI-compatible endpoint (LLM_BASE_URL).

think=False suppresses Gemma 4 reasoning tokens — Ollama passes it through
its OpenAI-compatible layer. Other backends ignore the unknown field.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def generate(
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "think": False,  # Ollama/Gemma4: suppress internal reasoning tokens
        }
    ).encode()

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"LLM HTTP {e.code}: {body}") from e
