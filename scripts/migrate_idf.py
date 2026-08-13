#!/usr/bin/env python3
"""R-08: attiva `modifier=IDF` sugli indici sparsi gia' esistenti.

Non re-ingesta niente. I vettori sparsi su disco sono corretti come sono — la
componente TF e' quella giusta — e fastembed lascia fuori l'IDF *di proposito*,
perche' dipende dalle statistiche del corpus, che il client non ha. La meta'
mancante vive nella configurazione dell'indice, e si aggiunge con
`update_collection`: i punti non vengono toccati.

**Mai delete + create.** I vettori densi di queste collection sono ore di GPU
(open_ragbench e ledger insieme fanno ~66k chunk, le varianti routed ~326k), e
buttarli per cambiare un campo della configurazione sparsa porterebbe via con se'
ogni misura che ci si appoggia, C-06 compresa.

Idempotente: rilanciarlo non fa niente. `--dry-run` dice soltanto cosa farebbe.

Usage:
    python scripts/migrate_idf.py --dry-run
    python scripts/migrate_idf.py
    python scripts/migrate_idf.py --collection open_ragbench --collection ledger
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg  # noqa: E402
from src.index.store import ensure_idf_modifier, get_client  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="R-08: modifier=IDF sugli indici sparsi")
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

    changed = 0
    for name in names:
        info = client.get_collection(name)
        sparse = (info.config.params.sparse_vectors or {}).get("sparse")
        before = getattr(sparse, "modifier", None)
        points = info.points_count

        if str(before).lower().endswith("idf"):
            print(f"  {name:<32} {points:>7} punti  gia' IDF, niente da fare")
            continue
        if args.dry_run:
            print(f"  {name:<32} {points:>7} punti  modifier={before} -> IDF  (dry-run)")
            changed += 1
            continue

        ensure_idf_modifier(client, name)
        # Riletto dal server: che il campo sia scritto lo dice Qdrant, non noi.
        after = (client.get_collection(name).config.params.sparse_vectors or {}).get("sparse")
        now = client.get_collection(name).points_count
        ok = "OK" if points == now else f"!! punti {points} -> {now}"
        print(f"  {name:<32} {points:>7} punti  modifier={after.modifier}  {ok}")
        changed += 1

    verb = "da migrare" if args.dry_run else "migrate"
    print(f"\n{changed}/{len(names)} collection {verb}.")
    if changed and not args.dry_run:
        print("Ora vanno rimisurati --retrieval-mode sparse e hybrid sui due dataset.")


if __name__ == "__main__":
    main()
