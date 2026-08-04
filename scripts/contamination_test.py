#!/usr/bin/env python3
"""T-03: verifica di contaminazione sui dataset candidati.

Per ogni domanda, i modelli vengono interrogati SENZA contesto documentale.
Esito atteso (buono): il modello non conosce la risposta specifica o sbaglia.
Esito da scarto: il modello risponde correttamente — il dataset è contaminato.

Uso:
    python scripts/contamination_test.py --dataset open_ragbench
    python scripts/contamination_test.py --dataset open_ragbench --models gemma4:latest
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

OLLAMA_BASE = "http://localhost:11434"
MODELS_DEFAULT = ["gemma4:latest", "gemma4:12b"]

# Controlli positivi: risposte note — verificano che il modello stia funzionando
POSITIVE_CONTROLS = [
    {
        "id": "control_001",
        "query": "What does the acronym 'RAG' stand for in the context of AI language models?",
        "type": "positive_control",
        "source": "general_knowledge",
        "expected_answer": "Retrieval-Augmented Generation",
    },
    {
        "id": "control_002",
        "query": "What is the capital city of France?",
        "type": "positive_control",
        "source": "general_knowledge",
        "expected_answer": "Paris",
    },
]

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question directly and concisely "
    "based only on your training knowledge. Do not search external sources. "
    "If you do not know the answer, say 'I don't know' clearly."
)


def check_ollama() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def ask_model(model: str, question: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 4096,
            "num_predict": 300,
        },
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return (data.get("message") or {}).get("content", "").strip()
    except urllib.error.HTTPError as e:
        return f"[HTTP ERROR {e.code}: {e.read().decode(errors='replace')[:200]}]"
    except Exception as e:
        return f"[ERROR: {e}]"


def run_test(questions: list[dict], models: list[str]) -> list[dict]:
    results = []
    total = len(questions)

    for i, q in enumerate(questions):
        print(f"\n[{i+1}/{total}] {q['type']} / {q.get('source', '')} "
              f"| doc: {q.get('doc_id', 'n/a')}")
        print(f"  Q: {q['query'][:120]}")

        entry = {
            "id": q["id"],
            "query": q["query"],
            "type": q["type"],
            "source": q.get("source", ""),
            "doc_id": q.get("doc_id", ""),
            "expected_answer": q.get("expected_answer", ""),
            "responses": {},
        }

        for model in models:
            print(f"  [{model}] ", end="", flush=True)
            resp = ask_model(model, q["query"])
            print(f"{resp[:80].replace(chr(10), ' ')}...")
            entry["responses"][model] = resp

        results.append(entry)

    return results


def verdict(response: str, expected: str) -> str:
    """Valutazione euristica — da revisionare manualmente."""
    if not response or "don't know" in response.lower() or "i do not know" in response.lower():
        return "NON_SA"
    # Controllo grezzo: se parole chiave della risposta attesa compaiono nella risposta
    expected_words = set(expected.lower().split())
    resp_words = set(response.lower().split())
    overlap = len(expected_words & resp_words) / max(len(expected_words), 1)
    if overlap > 0.5:
        return "POTENZIALMENTE_CONTAMINATO"
    if overlap > 0.25:
        return "PARZIALE"
    return "SBAGLIATO_O_GENERICO"


def print_summary(results: list[dict], models: list[str]) -> None:
    print("\n\n" + "=" * 70)
    print("RIEPILOGO CONTAMINAZIONE")
    print("=" * 70)

    for model in models:
        print(f"\nModello: {model}")
        print(f"{'N':>3} {'Tipo':<30} {'Verdetto':<30}")
        print("-" * 65)
        for i, r in enumerate(results):
            resp = r["responses"].get(model, "")
            v = verdict(resp, r["expected_answer"])
            qtype = f"{r['type']}/{r['source']}"[:28]
            marker = "⚠️ " if "CONTAMINATO" in v else "   "
            print(f"{i+1:>3} {qtype:<30} {marker}{v}")

    print()
    print("NOTA: 'POTENZIALMENTE_CONTAMINATO' richiede revisione manuale.")
    print("Confronta la risposta del modello con l'expected_answer nel JSON completo.")


def save_results(results: list[dict], dataset: str) -> Path:
    out_dir = Path(__file__).parent.parent / "eval" / "contamination"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"contamination_{dataset}_{ts}.json"
    out_file.write_text(
        json.dumps({"timestamp": ts, "dataset": dataset, "results": results},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="T-03 contamination test")
    parser.add_argument("--dataset", default="open_ragbench",
                        help="Nome del dataset (usato per caricare le domande)")
    parser.add_argument("--models", nargs="+", default=MODELS_DEFAULT)
    parser.add_argument("--questions-file", default=None,
                        help="Percorso al file JSON delle domande (default: eval/contamination/<dataset>_questions.json)")
    args = parser.parse_args()

    if not check_ollama():
        print("Ollama non raggiungibile su http://localhost:11434", file=sys.stderr)
        sys.exit(1)

    questions_file = args.questions_file or (
        Path(__file__).parent.parent / "eval" / "contamination"
        / f"{args.dataset}_questions.json"
    )
    if not Path(questions_file).exists():
        print(f"File domande non trovato: {questions_file}", file=sys.stderr)
        sys.exit(1)

    with open(questions_file, encoding="utf-8") as f:
        dataset_questions = json.load(f)

    # Controlli positivi prima, poi le 16 domande del dataset
    all_questions = POSITIVE_CONTROLS + dataset_questions

    print(f"Dataset: {args.dataset}")
    print(f"Modelli: {args.models}")
    print(f"Domande: {len(POSITIVE_CONTROLS)} controlli positivi + {len(dataset_questions)} dataset = {len(all_questions)} totali")

    results = run_test(all_questions, args.models)
    print_summary(results, args.models)

    out = save_results(results, args.dataset)
    print(f"\nRisultati completi salvati in: {out}")
    print("Revisiona manualmente i casi 'POTENZIALMENTE_CONTAMINATO'.")


if __name__ == "__main__":
    main()
