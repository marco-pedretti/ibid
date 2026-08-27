#!/usr/bin/env python3
"""U-08: ritaglia dall'indice vero l'indice `demo`, quello che sta in git.

    python scripts/build_demo_index.py --dry-run     # dice cosa prenderebbe
    python scripts/build_demo_index.py               # scrive data/demo/

**Non calcola niente: copia.** I vettori vengono letti da Qdrant, non
rigenerati, e la ragione e' il criterio di U-08 letto per intero. Un builder che
riembeddesse il testo produrrebbe numeri *simili* a quelli misurati, e simile
qui non basta: il terzo esempio di ogni dataset chiude il gate di astensione per
+0,0078 su `ledger`, che e' meno di quanto una versione diversa di
`onnxruntime` sposti uno score. La demo mostra **gli stessi vettori** su cui
sono state prese le misure, oppure mostra un sistema diverso da quello descritto.

Ne segue che questo script gira **una volta**, su una macchina che ha l'indice
completo, e il suo risultato entra nel repository. Chi clona non lo esegue:
esegue `scripts/seed_demo.py`, che non ha bisogno ne' di GPU ne' di rete.

## Cosa entra, e perche' documenti interi

La selezione parte da un vincolo che non e' negoziabile: i chunk dichiarati in
`ui/src/app/esempi.ts`. Se mancassero, il primo clic di chi prova il progetto
finirebbe in un'astensione, il difetto che D-17 ha gia' trovato una volta.

Ma prendere **solo** quei chunk darebbe un corpus a groviera: l'esploratore di
A-07 mostra i documenti per intero, e una citazione aperta su un documento con
tre chunk su venti si legge come un guasto. Quindi l'unita' di selezione e' il
**documento**, non il chunk: si prendono i documenti che contengono i chunk
d'oro, tutti i loro chunk, fino al budget.

I distrattori arrivano gratis da questa scelta, e sono i migliori possibili:
chunk **dello stesso corpus e dello stesso genere**, spesso dello stesso
documento della risposta giusta. Un rumore preso a caso da un altro dataset
renderebbe il recupero piu' facile di quanto sia.

## Cosa NON prova, e va detto

Un indice ridotto **non riproduce nessuna misura**. Con 1.500 punti invece di
18.840 il recupero ha meno concorrenti, quindi trova piu' facilmente; e il BM25
sparso cambia proprio i pesi, perche' l'IDF lo calcola Qdrant sulle statistiche
della collection (R-08). Questo indice serve a **mostrare**, e il manifesto che
lo accompagna lo dichiara: `scripts/seed_demo.py` lo carica su Qdrant come
cartellino, `/datasets` lo riporta, e l'interfaccia lo scrive.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import src.config as cfg
from qdrant_client.models import FieldCondition, Filter, MatchAny
from src.datasets import registry
from src.eval.provenance import load_golden
from src.index.store import get_client
from verify_esempi import esempi_dal_ts

DEMO = ROOT / "data" / "demo"
GOLDEN = ROOT / "eval" / "golden"

#: Quanti chunk per dataset. **Il budget e' in chunk e non in documenti** perche'
#: i due corpus non si somigliano affatto: un paper di `open_ragbench` sta in
#: ~20 chunk, un bilancio di `ledger` in ~113. A parita' di documenti uno dei due
#: peserebbe sei volte l'altro; a parita' di chunk nessuno dei due domina.
BUDGET: dict[str, int] = {"open_ragbench": 700, "ledger": 1100}

#: Quante query d'oro guardare per raccogliere documenti. Non e' il numero di
#: query che finiscono nella demo: e' il pozzo da cui si pescano i documenti
#: finche' il budget non e' pieno.
QUERY_MAX = 300


def _commit() -> str:
    """Il commit da cui esce questo indice. Vuoto se git non risponde."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def documenti_da_prendere(dataset: str) -> tuple[list[str], list[str]]:
    """I documenti candidati, in ordine, e i chunk che non possono mancare.

    L'ordine e' il criterio: **prima i documenti degli esempi**, poi quelli
    delle query d'oro nell'ordine del file. Il file e' stabile, quindi lo e'
    anche questa lista: rieseguire lo script sullo stesso indice da' lo stesso
    indice ridotto.
    """
    obbligatori = [
        a["chunk"] for _, a in esempi_dal_ts().get(dataset, []) if a["esito"] == "risponde"
    ]
    dorate = [q for q in load_golden(GOLDEN / f"{dataset}.jsonl") if q.answerable]
    da_oro = [r.chunk_id for q in dorate[:QUERY_MAX] for r in q.qrels]

    ordine: list[str] = []
    for chunk_id in [*obbligatori, *da_oro]:
        if doc_id_di(chunk_id) not in ordine:
            ordine.append(doc_id_di(chunk_id))
    return ordine, obbligatori


def doc_id_di(chunk_id: str) -> str:
    """Il `doc_id` dentro un `chunk_id`.

    Il contratto del §3 e' `{dataset_id}:{doc_id}:{seq}`, e il pezzo di mezzo
    **puo' contenere altri due punti**: si tolgono il primo campo e l'ultimo,
    non si divide in tre.
    """
    return chunk_id.split(":", 1)[1].rsplit(":", 1)[0]


def punti_dei_documenti(client, collection: str, doc_ids: list[str]) -> list:
    """Tutti i punti di quei documenti, vettori compresi, in ordine di chunk_id."""
    fuori: list = []
    for i in range(0, len(doc_ids), 32):
        filtro = Filter(
            must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids[i : i + 32]))]
        )
        offset = None
        while True:
            punti, offset = client.scroll(
                collection,
                scroll_filter=filtro,
                limit=256,
                with_payload=True,
                with_vectors=True,
                offset=offset,
            )
            fuori.extend(punti)
            if offset is None:
                break
    return sorted(fuori, key=lambda p: p.payload["chunk_id"])


def costruisci(dataset: str, dry_run: bool) -> dict:
    client = get_client(cfg.QDRANT_URL)
    ordine, obbligatori = documenti_da_prendere(dataset)
    budget = BUDGET[dataset]

    scelti: list[str] = []
    punti: list = []
    for doc_id in ordine:
        del_documento = punti_dei_documenti(client, dataset, [doc_id])
        if not del_documento:
            continue
        # Il documento entra **intero o per niente**: uno troncato a meta' e'
        # esattamente il corpus a groviera che questa scelta evita.
        if punti and len(punti) + len(del_documento) > budget:
            break
        scelti.append(doc_id)
        punti.extend(del_documento)

    punti.sort(key=lambda p: p.payload["chunk_id"])
    presenti = {p.payload["chunk_id"] for p in punti}
    mancanti = [c for c in obbligatori if c not in presenti]
    if mancanti:
        raise SystemExit(
            f"{dataset}: i chunk dichiarati in esempi.ts non sono entrati: {mancanti}. "
            "Il budget e' troppo stretto, oppure quei chunk non sono nell'indice."
        )

    print(f"  {dataset}: {len(scelti)} documenti, {len(punti)} chunk")
    for c in obbligatori:
        print(f"    esempio presente   {c}")

    voce = {"dataset_id": dataset, "documenti": len(scelti), "chunk": len(punti)}
    if dry_run:
        return voce

    DEMO.mkdir(parents=True, exist_ok=True)
    dense = np.asarray([p.vector["dense"] for p in punti], dtype=np.float32)
    np.save(DEMO / f"{dataset}.dense.npy", dense)

    with (DEMO / f"{dataset}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for p in punti:
            sparse = p.vector["sparse"]
            f.write(
                json.dumps(
                    {
                        "payload": p.payload,
                        # In chiaro: la parte grossa (i densi) sta gia' nel .npy
                        # accanto, e questo file resta leggibile e diffabile.
                        "sparse": {
                            "indices": [int(i) for i in sparse.indices],
                            "values": [round(float(v), 6) for v in sparse.values],
                        },
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    voce["dense_size"] = int(dense.shape[1])
    return voce


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", default=registry.ALL, choices=registry.cli_choices())
    ap.add_argument("--dry-run", action="store_true", help="conta e non scrive")
    args = ap.parse_args()

    print(f"indice completo su {cfg.QDRANT_URL}")
    voci = [costruisci(d, args.dry_run) for d in registry.resolve(args.dataset)]
    if args.dry_run:
        return

    manifesto = {
        "generato": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _commit(),
        # **Il modello, sempre.** Un indice e' legato all'embedder che l'ha
        # prodotto: interrogarlo con un altro restituisce spazzatura *senza
        # errore*, ed e' il guasto piu' difficile da riconoscere di tutti.
        "embedding_model": cfg.EMBEDDING_MODEL,
        "sparse_embedding_model": cfg.SPARSE_EMBEDDING_MODEL,
        "datasets": voci,
    }
    (DEMO / "manifest.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    peso = sum(f.stat().st_size for f in DEMO.iterdir() if f.is_file()) / 1e6
    print(f"\n{DEMO.relative_to(ROOT)}: {peso:.1f} MB")
    print("caricalo con: python scripts/seed_demo.py")


if __name__ == "__main__":
    main()
