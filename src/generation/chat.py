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
from collections.abc import Callable, Iterator
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
    except (urllib.error.URLError, OSError) as e:
        raise _irraggiungibile(url, e) from e

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


@dataclass(frozen=True)
class Delta:
    """Un pezzo di risposta mentre arriva, o la fine.

    Una sequenza sola invece di due canali: chi consuma scorre fino a `final` e
    non deve conoscere un secondo protocollo per sapere com'e' andata.  L'ultimo
    elemento non porta testo — porta il verdetto, che prima dell'ultimo non
    esiste.
    """

    text: str = ""
    final: bool = False
    finish_reason: str = ""
    completion_tokens: int = 0


def generate_stream(
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    reasoning_effort: str | None = "none",
) -> Iterator[Delta]:
    """Come `generate_detailed`, ma i pezzi arrivano mentre il modello scrive.

    Serve perche' §3.5 prevede SSE, e senza questo l'unico streaming possibile
    sarebbe **finto**: aspettare la risposta intera e poi spezzettarla. Sembra
    identico dal lato del browser e non lo e' — la prima parola arriverebbe dopo
    l'ultima, cioe' dopo gli ~11 s che il progetto misura come latenza.

    Stesso contratto OpenAI-compatibile del resto del modulo (STACK.md:
    l'inferenza passa sempre da `LLM_BASE_URL`). Due dettagli del formato:

    - il flusso e' `data: {json}` per riga, chiuso da `data: [DONE]`;
    - il conteggio dei token arriva **solo** se lo si chiede con
      `stream_options.include_usage`, e in un ultimo pacchetto senza `choices`.
      Se il backend non lo manda, resta 0: dichiarato assente, non stimato.
    """
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
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
    finish_reason = ""
    completion_tokens = 0
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[len("data:"):].strip()
                if body == "[DONE]":
                    break
                event = json.loads(body)
                if usage := event.get("usage"):
                    completion_tokens = int(usage.get("completion_tokens", 0))
                for choice in event.get("choices", []):
                    if reason := choice.get("finish_reason"):
                        finish_reason = reason
                    if text := (choice.get("delta") or {}).get("content"):
                        yield Delta(text=text)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"LLM HTTP {e.code}: {body}") from e
    except (urllib.error.URLError, OSError) as e:
        raise _irraggiungibile(url, e) from e

    yield Delta(final=True, finish_reason=finish_reason, completion_tokens=completion_tokens)


def collect(deltas: Iterator[Delta]) -> Completion:
    """Uno stream riletto come se non lo fosse.

    Non e' una comodita': e' cio' che rende verificabile che le due strade
    diano la stessa risposta. Un test che confronta `generate_detailed` con la
    somma dei delta e' l'unico modo per accorgersi che lo streaming perde un
    pezzo — un difetto che dal lato del browser si vede come una frase che
    comincia a meta'.
    """
    pezzi: list[str] = []
    ultimo = Delta(final=True)
    for delta in deltas:
        if delta.final:
            ultimo = delta
        else:
            pezzi.append(delta.text)
    return Completion(
        content="".join(pezzi).strip(),
        finish_reason=ultimo.finish_reason,
        completion_tokens=ultimo.completion_tokens,
    )


def _irraggiungibile(url: str, e: Exception) -> RuntimeError:
    """L'errore che vede **chi guarda**, quando il modello non risponde.

    Non e' un caso raro: e' il primo che incontra chi prova la demo. Il profilo
    `demo` di U-08 avvia Qdrant e il backend, non un motore di inferenza,
    quindi su una macchina senza Ollama la prima domanda finisce qui. Prima ci
    finiva come `URLError: <urlopen error [Errno 111] Connection refused>`,
    cioe' un'eccezione di Python in faccia a chi non l'ha scritta:
    **visto davvero**, sull'Arch, al primo clic su una domanda d'esempio.

    Dice tre cose, e servono tutte e tre: dove ha provato, che il resto
    funziona, e quale variabile cambia l'indirizzo.
    """
    motivo = getattr(e, "reason", None) or e
    return RuntimeError(
        f"Nessun modello raggiungibile su {url} ({motivo}). "
        "La ricerca nel corpus funziona lo stesso: per generare le risposte serve un "
        "endpoint OpenAI-compatibile, e l'indirizzo si cambia con LLM_BASE_URL."
    )


def _get_json(url: str, timeout: int) -> dict:
    """Una GET che restituisce JSON, o solleva dicendo dove ha fallito."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"LLM HTTP {e.code}: {body}") from e
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"LLM irraggiungibile su {url}: {e}") from e


def list_models(
    base_url: str,
    timeout: int = 10,
    *,
    fetch: Callable[[str, int], dict] | None = None,
) -> list[str]:
    """I modelli che questo endpoint dichiara di avere, in ordine alfabetico.

    Serve alla UI (A-07): il menu dei modelli deve venire dal backend, perche'
    e' l'unico che sa quali esistono davvero. Un elenco scritto a mano nel
    frontend e' la quindicesima copia di Q-06 -- diverge, e il modello nuovo
    arriva senza che nessuno lo aggiunga.

    **Passa da `LLM_BASE_URL` come tutto il resto del modulo.** Non e' un
    dettaglio di stile: il browser puo' non raggiungere Ollama (in `compose.yml`
    e' dietro `host.docker.internal`, e in un deployment reale e' su un'altra
    macchina), e STACK.md impone comunque l'endpoint OpenAI-compatibile invece
    di quello nativo -- cosi' questa funzione vale anche con vLLM o llama.cpp
    server al posto di Ollama.

    L'ordine e' alfabetico e non quello di arrivo: `/v1/models` di Ollama
    ordina per data di download, che cambia sotto i piedi di chi ha appena
    scaricato qualcosa e fa saltare la selezione in un menu.

    Solleva `RuntimeError` se l'endpoint risponde male: e' un guasto, e chi
    chiama decide se e' fatale. Per l'API non lo e' -- vedi `catalog.models()`.

    Args:
        fetch: la GET, iniettabile. Stessa forma di seam di `answer_stream`, e
            per la stessa ragione: un test che verifica l'ordinamento non deve
            avere bisogno di un server acceso.
    """
    data = (fetch or _get_json)(f"{base_url.rstrip('/')}/models", timeout)
    return sorted(
        str(m["id"]) for m in data.get("data", []) if isinstance(m, dict) and m.get("id")
    )
