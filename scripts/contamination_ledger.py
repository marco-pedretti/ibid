#!/usr/bin/env python3
"""Contamination check for LEDGER dataset — mirrors T-03 protocol.

For each query, asks Gemma E4B and 12B WITHOUT context at temperature 0.
A result is "contaminated" if the model gives the correct numeric value
(within ±5% tolerance) without having access to the document.

Usage:
    python scripts/contamination_ledger.py
    python scripts/contamination_ledger.py --model gemma4:e4b
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OLLAMA_URL = "http://localhost:11434/api/chat"

# 8 test queries: 5 recent (2021-2022, higher risk) + 3 older (2017, baseline)
# Mix of company sizes and KPI types; no mega-caps (Apple, Google, etc.)
# Two positive controls at the end (well-known figures, expect correct answer)
TEST_CASES = [
    # --- Recent (2021-2022) ---
    {
        "id": "DX_net_income_2022",
        "query": "What is Dynex Capital's net income attributable to the controlling interest for 2022?",
        "company": "Dynex Capital, Inc. (DX)",
        "year": 2022,
        "kpi": "net_income",
        "ground_truth": 143161000.0,
        "positive_control": False,
    },
    {
        "id": "AMTX_income_tax_2021",
        "query": "Show me the income tax expense from Aemetis, Inc.'s 2021 financial statements.",
        "company": "Aemetis, Inc. (AMTX)",
        "year": 2021,
        "kpi": "income_tax_expense",
        "ground_truth": -128000.0,
        "positive_control": False,
    },
    {
        "id": "CBT_cash_2021",
        "query": "How much free or unrestricted cash did Cabot Corporation hold in 2021?",
        "company": "Cabot Corporation (CBT)",
        "year": 2021,
        "kpi": "cash_and_equivalents",
        "ground_truth": 168000000.0,
        "positive_control": False,
    },
    {
        "id": "CBT_eps_diluted_2021",
        "query": "How much was Cabot Corporation's diluted EPS in 2021?",
        "company": "Cabot Corporation (CBT)",
        "year": 2021,
        "kpi": "eps_diluted",
        "ground_truth": 4.34,
        "positive_control": False,
    },
    {
        "id": "AMTX_total_assets_2021",
        "query": "Can you provide the total asset value for Aemetis, Inc. for the year 2021?",
        "company": "Aemetis, Inc. (AMTX)",
        "year": 2021,
        "kpi": "total_assets",
        "ground_truth": 160831000.0,
        "positive_control": False,
    },
    # --- Older (2017) ---
    {
        "id": "ARI_total_assets_2017",
        "query": "What is the total asset figure for Apollo Commercial Real Estate Finance in 2017?",
        "company": "Apollo Commercial Real Estate Finance (ARI)",
        "year": 2017,
        "kpi": "total_assets",
        "ground_truth": 4088605000.0,
        "positive_control": False,
    },
    {
        "id": "EGY_total_assets_2017",
        "query": "Could you look up the total assets for VAALCO Energy in 2017?",
        "company": "VAALCO Energy (EGY)",
        "year": 2017,
        "kpi": "total_assets",
        "ground_truth": 79633000.0,
        "positive_control": False,
    },
    {
        "id": "EGY_shares_2017",
        "query": "What is the volume of outstanding shares for VAALCO Energy, Inc. in 2017?",
        "company": "VAALCO Energy (EGY)",
        "year": 2017,
        "kpi": "shares_outstanding",
        "ground_truth": 58862876.0,
        "positive_control": False,
    },
    # --- Positive controls (well-known figures — expect correct answers) ---
    {
        "id": "AAPL_revenue_2022_ctrl",
        "query": "What was Apple Inc.'s total net sales revenue for fiscal year 2022?",
        "company": "Apple Inc. (AAPL)",
        "year": 2022,
        "kpi": "revenue",
        "ground_truth": 394328000000.0,
        "positive_control": True,
    },
    {
        "id": "MSFT_net_income_2022_ctrl",
        "query": "What was Microsoft Corporation's net income for fiscal year 2022?",
        "company": "Microsoft Corporation (MSFT)",
        "year": 2022,
        "kpi": "net_income",
        "ground_truth": 72738000000.0,
        "positive_control": True,
    },
]

SYSTEM = (
    "You are a financial data assistant. Answer the question concisely with a single numeric value. "
    "Do not provide context or explanation. If you are not certain, say 'I don't know'."
)


def _chat(model: str, query: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": query},
        ],
        "stream": False,
        "options": {"temperature": 0, "think": False},
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"].strip()


def _extract_number(text: str) -> float | None:
    """Try to parse the first numeric value from a model response."""
    cleaned = text.replace(",", "").replace("$", "").replace("%", "")
    # Handle scales: billion, million, trillion
    multipliers = [("trillion", 1e12), ("billion", 1e9), ("million", 1e6), ("thousand", 1e3)]
    for word, mult in multipliers:
        m = re.search(rf"([\-\d\.]+)\s*{word}", cleaned, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1)) * mult
            except ValueError:
                pass
    # Plain number
    m = re.search(r"[\-]?\d[\d\.]*(?:e[+-]?\d+)?", cleaned)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            pass
    return None


def _is_correct(predicted: float | None, ground_truth: float, tol: float = 0.05) -> bool:
    if predicted is None:
        return False
    if ground_truth == 0:
        return abs(predicted) < 1e-6
    return abs(predicted - ground_truth) / abs(ground_truth) <= tol


def run(model: str) -> list[dict]:
    results = []
    for case in TEST_CASES:
        print(f"  [{case['id']}]", end=" ", flush=True)
        try:
            response = _chat(model, case["query"])
            predicted = _extract_number(response)
            correct = _is_correct(predicted, case["ground_truth"])
            verdict = "CORRECT" if correct else ("REFUSED" if predicted is None else "WRONG")
            print(verdict)
        except Exception as e:
            response = f"ERROR: {e}"
            predicted = None
            correct = False
            verdict = "ERROR"
            print(verdict)

        results.append({
            **{k: case[k] for k in ("id", "company", "year", "kpi", "ground_truth", "positive_control")},
            "model": model,
            "response": response,
            "predicted": predicted,
            "correct": correct,
            "verdict": verdict,
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models",
                        default=None,
                        help="Ollama model tag (repeatable). Default: e4b + 12b")
    args = parser.parse_args()

    models = args.models or ["gemma4:e4b", "gemma4:12b"]

    # Check Ollama
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=5)
    except Exception:
        print("ERROR: Ollama non raggiungibile, avvialo prima di procedere.", file=sys.stderr)
        sys.exit(1)

    all_results: list[dict] = []
    for model in models:
        print(f"\n=== Modello: {model} ===")
        results = run(model)
        all_results.extend(results)

    # Summary
    print("\n=== RISULTATI ===")
    non_control = [r for r in all_results if not r["positive_control"]]
    controls = [r for r in all_results if r["positive_control"]]

    contaminated = [r for r in non_control if r["correct"]]
    print(f"Query di test (non-controllo): {len(non_control)}")
    print(f"Risposte corrette (contaminazione): {len(contaminated)}")
    print(f"Controlli positivi corretti: {sum(1 for r in controls if r['correct'])} / {len(controls)}")

    if contaminated:
        print("\nATTENZIONE: risposte corrette senza contesto:")
        for r in contaminated:
            print(f"  {r['id']} [{r['model']}]: {r['response'][:80]}")

    verdict = "APPROVATO" if len(contaminated) == 0 else f"ATTENZIONE: {len(contaminated)} corrette"
    print(f"\nEsito: {verdict}")

    # Save
    out_dir = ROOT / "eval" / "contamination"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"contamination_ledger_{ts}.json"
    out_file.write_text(json.dumps({
        "timestamp": ts,
        "models": models,
        "n_test": len(non_control),
        "n_contaminated": len(contaminated),
        "n_controls_correct": sum(1 for r in controls if r["correct"]),
        "verdict": verdict,
        "results": all_results,
    }, indent=2, ensure_ascii=False))
    print(f"Risultati salvati in {out_file}")


if __name__ == "__main__":
    main()
