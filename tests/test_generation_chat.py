"""Tests for src/generation/chat.py — the request payload and the reply shape.

The bug these exist to prevent: a field that the server silently ignores.
`"think": false` was sent on every request since T-05 and dropped by Ollama's
OpenAI-compatible endpoint, so the model reasoned through its whole token
budget while `EvalRun.reasoning_enabled` recorded False and answers came back
empty.  A no-op field is invisible without a test that names it.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation import chat
from src.generation.chat import Completion, generate, generate_detailed


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _reply(content="ok", finish_reason="stop", completion_tokens=7):
    return _FakeResponse(json.dumps({
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"completion_tokens": completion_tokens},
    }).encode())


def _capture(**kwargs):
    """Call generate_detailed and return (sent_payload, result)."""
    seen = {}
    reply_kwargs = kwargs.pop("_reply", {})

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["payload"] = json.loads(req.data)
        return _reply(**reply_kwargs)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = generate_detailed(
            base_url="http://x/v1", model="m", system="S", user="U", **kwargs
        )
    return seen, result


class TestPayload:
    def test_reasoning_effort_is_sent_by_default(self):
        seen, _ = _capture()
        assert seen["payload"]["reasoning_effort"] == "none"

    def test_reasoning_effort_can_be_raised(self):
        # C-07 flips this to measure the effect of extended reasoning.
        seen, _ = _capture(reasoning_effort="high")
        assert seen["payload"]["reasoning_effort"] == "high"

    def test_reasoning_effort_omitted_when_none(self):
        # Some OpenAI-compatible backends reject unknown values with a 400.
        seen, _ = _capture(reasoning_effort=None)
        assert "reasoning_effort" not in seen["payload"]

    def test_no_vendor_specific_think_field(self):
        # `think` is Ollama's native-API field. On /v1 it is dropped silently,
        # which is worse than not sending it: it looks like reasoning is off.
        seen, _ = _capture()
        assert "think" not in seen["payload"]

    def test_temperature_and_max_tokens_passed_through(self):
        seen, _ = _capture(temperature=0.0, max_tokens=1536)
        assert seen["payload"]["temperature"] == 0.0
        assert seen["payload"]["max_tokens"] == 1536

    def test_streaming_off(self):
        seen, _ = _capture()
        assert seen["payload"]["stream"] is False

    def test_messages_in_order(self):
        seen, _ = _capture()
        assert [m["role"] for m in seen["payload"]["messages"]] == ["system", "user"]

    def test_url_is_the_chat_completions_path(self):
        seen, _ = _capture()
        assert seen["url"] == "http://x/v1/chat/completions"

    def test_trailing_slash_in_base_url(self):
        with patch("urllib.request.urlopen", side_effect=lambda req, timeout=None: _reply()) as m:
            generate_detailed(base_url="http://x/v1/", model="m", system="S", user="U")
        assert m.call_args[0][0].full_url == "http://x/v1/chat/completions"


class TestCompletion:
    def test_finish_reason_surfaced(self):
        _, c = _capture(_reply={"finish_reason": "length"})
        assert c.finish_reason == "length"
        assert c.truncated

    def test_stop_is_not_truncated(self):
        _, c = _capture()
        assert not c.truncated

    def test_completion_tokens_surfaced(self):
        _, c = _capture(_reply={"completion_tokens": 267})
        assert c.completion_tokens == 267

    def test_empty_content_is_empty_string_not_none(self):
        # A thinking model that used the whole budget returns content: null.
        # Returning None here would crash the format checker instead of being
        # counted as the empty answer it is.
        _, c = _capture(_reply={"content": None})
        assert c.content == ""

    def test_content_is_stripped(self):
        _, c = _capture(_reply={"content": "  hello  "})
        assert c.content == "hello"

    def test_missing_usage_does_not_crash(self):
        def fake_urlopen(req, timeout=None):
            return _FakeResponse(json.dumps({
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            }).encode())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c = generate_detailed(base_url="http://x/v1", model="m", system="S", user="U")
        assert c.completion_tokens == 0


class TestGenerateWrapper:
    def test_returns_the_text_only(self):
        with patch("urllib.request.urlopen", side_effect=lambda req, timeout=None: _reply("hi")):
            out = generate(base_url="http://x/v1", model="m", system="S", user="U")
        assert out == "hi"
        assert not isinstance(out, Completion)

    def test_http_error_is_reraised_with_the_body(self):
        import urllib.error

        def boom(req, timeout=None):
            raise urllib.error.HTTPError("http://x", 400, "Bad", {}, io.BytesIO(b"nope"))

        with patch("urllib.request.urlopen", side_effect=boom), \
             pytest.raises(RuntimeError, match="LLM HTTP 400"):
            generate(base_url="http://x/v1", model="m", system="S", user="U")


class TestModelloIrraggiungibile:
    """U-08: cosa vede chi prova la demo senza un motore di inferenza acceso.

    **Visto davvero**, il 2026-08-27 sull'Arch: il profilo `demo` avvia Qdrant e
    il backend, non un LLM, e il primo clic su una domanda d'esempio finiva in
    `URLError: <urlopen error [Errno 111] Connection refused>` stampato nella
    pagina. Le fonti erano arrivate, quindi il sistema funzionava: a mancare era
    solo la frase che lo dicesse.
    """

    ERRORE = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    def _rifiuta(self, *a, **k):
        raise self.ERRORE

    def test_la_generazione_dice_dove_ha_provato_e_cosa_funziona(self, monkeypatch):
        monkeypatch.setattr(chat.urllib.request, "urlopen", self._rifiuta)
        with pytest.raises(RuntimeError) as e:
            chat.generate_detailed(
                "http://host.docker.internal:11434/v1", "gemma4:latest", "sistema", "ciao"
            )
        messaggio = str(e.value)
        assert "http://host.docker.internal:11434/v1/chat/completions" in messaggio
        assert "LLM_BASE_URL" in messaggio, "dire quale variabile cambia l'indirizzo"
        assert "ricerca nel corpus funziona" in messaggio, "dire cosa continua a funzionare"

    def test_anche_lo_stream_lo_dice(self, monkeypatch):
        """Le due strade sono due `urlopen` diversi, e la demo usa **questa**."""
        monkeypatch.setattr(chat.urllib.request, "urlopen", self._rifiuta)
        with pytest.raises(RuntimeError) as e:
            list(
                chat.generate_stream("http://127.0.0.1:11434/v1", "gemma4:latest", "sistema", "ciao")
            )
        assert "Nessun modello raggiungibile" in str(e.value)

    def test_niente_gergo_di_python_nel_messaggio(self, monkeypatch):
        """Il difetto era proprio questo: un'eccezione di Python in faccia a chi
        non l'ha scritta."""
        monkeypatch.setattr(chat.urllib.request, "urlopen", self._rifiuta)
        with pytest.raises(RuntimeError) as e:
            chat.generate_detailed(
                "http://127.0.0.1:11434/v1", "gemma4:latest", "sistema", "ciao"
            )
        for gergo in ("URLError", "urlopen error", "Traceback"):
            assert gergo not in str(e.value), gergo
