#!/usr/bin/env python3
"""A-07: crea gli indici payload su `chunk_id` e `doc_id` gia' esistenti.

Non re-ingesta niente, e non tocca un vettore. Un indice payload si aggiunge a
una collection viva -- esattamente come il modificatore IDF di R-08, e per la
stessa ragione vale la pena ripeterlo: queste collection sono ore di GPU, e un
rimedio che richiedesse di ricostruirle non sarebbe un rimedio.

**Perche' servono.** Sono i due percorsi in cui il progetto interroga l'indice
senza un embedding in mano:

    chunk_id   ogni citazione cliccata (U-06) passa da `get_by_chunk_id`
    doc_id     l'esploratore del corpus: quali documenti, e i chunk di uno

Senza indice, entrambe scandiscono i payload. Misurato il 2026-08-14 su
`ledger` (47.110 punti): "quali documenti ci sono e con quanti chunk" passa da
2,07 s a 0,025 s. Su `ledger_routed` (228.331 punti) la scansione sarebbe
dell'ordine dei 10 s, cioe' una pagina inusabile.

Da questo commit `ensure_collection` li crea a ogni ingestione: questo script
serve alle collection **indicizzate prima**, e a chi ripristina uno snapshot
prodotto prima di A-07.

Idempotente: rilanciarlo non fa niente. `--dry-run` dice soltanto cosa farebbe.

Usage:
    python scripts/migrate_payload_indexes.py --dry-run
    python scripts/migrate_payload_indexes.py
    python scripts/migrate_payload_indexes.py --collection ledger
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.index.store import PAYLOAD_INDEXED_FIELDS, ensure_payload_indexes, get_client


def main() -> None:
    p = argparse.ArgumentParser(description="A-07: indici payload su chunk_id e doc_id")
    p.add_argument("--collection", action="append", default=None,
                   help="collection da migrare (ripetibile; default: tutte)")
    p.add_argument("--dry-run", action="store_true",
                   help="elenca soltanto, non modifica niente")
    args = p.parse_args()

    client = get_client(cfg.QDRANT_URL)
    names = args.collection or sorted(c.name for c in client.get_collections().collections)
    if not names:
        print("Nessuna collection su", cfg.QDRANT_URL)
        return

    print(f"Campi indicizzati: {', '.join(PAYLOAD_INDEXED_FIELDS)}\n")
    toccate = 0
    for name in names:
        info = client.get_collection(name)
        punti = info.points_count or 0
        presenti = set(info.payload_schema or {})
        mancanti = [c for c in PAYLOAD_INDEXED_FIELDS if c not in presenti]

        if not mancanti:
            print(f"  {name:<32} {punti:>7} punti  gia' completo")
            continue
        if args.dry_run:
            print(f"  {name:<32} {punti:>7} punti  da creare: {', '.join(mancanti)}  (dry-run)")
            toccate += 1
            continue

        t = time.perf_counter()
        aggiunti = ensure_payload_indexes(client, name)
        durata = time.perf_counter() - t

        # Riletto dal server: che gli indici ci siano lo dice Qdrant, non noi.
        dopo = set(client.get_collection(name).payload_schema or {})
        ora = client.get_collection(name).points_count or 0
        mancano_ancora = [c for c in PAYLOAD_INDEXED_FIELDS if c not in dopo]
        esito = "OK" if punti == ora and not mancano_ancora else f"!! punti {punti} -> {ora}"
        print(f"  {name:<32} {punti:>7} punti  creati {', '.join(aggiunti)} "
              f"in {durata:.2f}s  {esito}")
        toccate += 1

    verbo = "da migrare" if args.dry_run else "migrate"
    print(f"\n{toccate}/{len(names)} collection {verbo}.")
    if toccate and not args.dry_run:
        print("Nessuna misura cambia: gli indici payload non toccano i vettori "
              "ne' i punteggi di ricerca.")


if __name__ == "__main__":
    main()
