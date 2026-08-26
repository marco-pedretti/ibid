#!/usr/bin/env python3
"""T-02: smoke test token/s e VRAM per ogni modello tramite Ollama.

Uso:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --models gemma4:e2b gemma4:latest gemma4:12b gemma4:27b
    python scripts/smoke_test.py --models gemma4:12b  # testa solo uno

Prerequisiti:
    - Ollama in esecuzione (ollama serve, oppure l'app desktop aperta)
    - Modelli già scaricati con: ollama pull <nome>

Output: tabella pronta per docs/hardware.md + JSON grezzo in eval/contamination/smoke_<timestamp>.json
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

OLLAMA_BASE = "http://localhost:11434"

# gemma4:e2b = E2B, gemma4:latest = E4B; gemma4:27b = 26B MoE (~18 GB, potrebbe girare su CPU)
MODELS_DEFAULT = ["gemma4:e2b", "gemma4:latest", "gemma4:12b", "gemma4:27b"]

# Prompt fisso, temperatura 0, finestra 32k — come da ROADMAP §1 e §3.3
# Usa /api/chat con think:false — Gemma 4 è un thinking model, con /api/generate i token
# vengono consumati dal ragionamento invisibile e la risposta risulta vuota
PROMPT = (
    "Spiega in tre frasi, in italiano, cosa si intende per "
    "'retrieval-augmented generation' e perché è utile."
)
NUM_CTX = 32768
TEMPERATURE = 0.0
NUM_PREDICT = 400


def check_ollama() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def list_local_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as r:
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def ollama_ps() -> str:
    try:
        r = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return ""


def generate(model: str) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def parse_ps_for_model(ps_output: str, model_name: str) -> dict:
    """Estrae processor e size da 'ollama ps' per il modello dato."""
    base = model_name.split(":")[0].lower()
    for line in ps_output.splitlines()[1:]:  # salta header
        if base in line.lower() or model_name.lower() in line.lower():
            parts = line.split()
            # Formato: NAME  ID  SIZE  UNIT  PROCESSOR  UNTIL ...
            if len(parts) >= 5:
                # cerca il campo PROCESSOR (100% GPU / 100% CPU / split)
                for i, p in enumerate(parts):
                    if "%" in p and i + 1 < len(parts):
                        size_str = f"{parts[i-2]} {parts[i-1]}" if i >= 2 else "?"
                        processor = f"{p} {parts[i+1]}"
                        return {"size": size_str, "processor": processor}
    return {"size": "?", "processor": "?"}


def benchmark(model: str) -> dict:
    print(f"\n{'='*60}")
    print(f"Modello: {model}")
    print(f"num_ctx={NUM_CTX}  temperature={TEMPERATURE}  num_predict={NUM_PREDICT}")
    print("Generazione in corso...", flush=True)

    t0 = time.monotonic()
    try:
        resp = generate(model)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  HTTP {e.code}: {body[:300]}", file=sys.stderr)
        return {"model": model, "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        print(f"  Errore: {e}", file=sys.stderr)
        return {"model": model, "error": str(e)}
    t1 = time.monotonic()

    eval_count: int = resp.get("eval_count", 0)
    eval_dur_ns: int = resp.get("eval_duration", 1)
    prompt_count: int = resp.get("prompt_eval_count", 0)
    prompt_dur_ns: int = resp.get("prompt_eval_duration", 1)

    gen_tps = eval_count / (eval_dur_ns / 1e9) if eval_dur_ns else 0.0
    prefill_tps = prompt_count / (prompt_dur_ns / 1e9) if prompt_dur_ns else 0.0

    ps_out = ollama_ps()
    ps_info = parse_ps_for_model(ps_out, model)

    response_text: str = (resp.get("message") or {}).get("content", "")

    print(f"  Generazione: {gen_tps:.1f} tok/s  ({eval_count} token, {eval_dur_ns/1e9:.1f}s)")
    print(f"  Prefill:     {prefill_tps:.1f} tok/s  ({prompt_count} token)")
    print(f"  Totale:      {t1 - t0:.1f}s")
    print(f"  Processor:   {ps_info['processor']}  |  Memoria: {ps_info['size']}")
    print(f"  Risposta:    {response_text[:120].strip()!r}...")

    return {
        "model": model,
        "gen_tps": round(gen_tps, 1),
        "prefill_tps": round(prefill_tps, 1),
        "eval_count": eval_count,
        "prompt_eval_count": prompt_count,
        "total_seconds": round(t1 - t0, 1),
        "processor": ps_info["processor"],
        "ollama_size": ps_info["size"],
        "response_preview": response_text[:300],
        "num_ctx": NUM_CTX,
        "temperature": TEMPERATURE,
    }


def print_summary(results: list[dict]) -> None:
    print("\n\n" + "="*60)
    print("RIEPILOGO: incolla in docs/hardware.md")
    print("="*60)
    print()
    print("| Modello | Quantizzazione (Ollama) | Generazione (tok/s) | Prefill (tok/s) | Memoria | Processor |")
    print("|---|---|---|---|---|---|")
    for r in results:
        if r.get("error"):
            print(f"| {r['model']} | n/d | ERRORE | n/d | n/d | {r['error'][:60]} |")
        else:
            quant = "(vedi ollama show)"
            print(
                f"| {r['model']} | {quant} | {r['gen_tps']} | {r['prefill_tps']} "
                f"| {r['ollama_size']} | {r['processor']} |"
            )


def save_raw(results: list[dict]) -> Path:
    out_dir = Path(__file__).parent.parent / "eval" / "contamination"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"smoke_{ts}.json"
    out_file.write_text(
        json.dumps({"timestamp": ts, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="T-02 smoke test modelli")
    parser.add_argument("--models", nargs="+", default=MODELS_DEFAULT)
    args = parser.parse_args()

    if not check_ollama():
        print("Ollama non raggiungibile su http://localhost:11434", file=sys.stderr)
        print("Avvia Ollama e riprova.", file=sys.stderr)
        sys.exit(1)

    available = list_local_models()
    print(f"Modelli locali disponibili: {available}")

    results = []
    for model in args.models:
        if model not in available and not any(model.split(":")[0] in a for a in available):
            print(f"\nSKIP {model}: non trovato localmente. Esegui: ollama pull {model}")
            results.append({"model": model, "error": "non scaricato"})
            continue
        results.append(benchmark(model))

    print_summary(results)

    out = save_raw(results)
    print(f"\nDati grezzi salvati in: {out}")


if __name__ == "__main__":
    main()
