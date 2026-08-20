#!/usr/bin/env python3
"""U-05: allinea `pipeline` nelle collection generiche gia' indicizzate.

Il commit precedente ha corretto i loader: nella modalita' generica non gira
nessuna delle tre pipeline di `src/ingestion`, quindi il campo vale
`PIPELINE_GENERIC` invece di un nome di pipeline che non ha girato. Le
collection costruite prima portano ancora il valore vecchio -- su `ledger`
`table_heavy`, su `open_ragbench` `continuous_text` -- e la targhetta di U-05
mostrerebbe quello.

**Non re-ingesta niente, e non tocca un vettore.** `set_payload` riscrive un
campo su una collection viva, come gli indici payload di A-07 e il modificatore
IDF di R-08. Queste collection sono ore di GPU: un rimedio che chiedesse di
ricostruirle non sarebbe un rimedio.

**Perche' e' sicuro.** Nessuno calcola su `Chunk.pipeline`: si scrive
all'ingestione, si mette nel payload, si rilegge in `ChunkView`. Nessuna
metrica, nessun `config_hash`, nessun `EvalRun` -- che porta `pipeline_mode`, un
campo diverso, scritto dalla CLI di ingestione. Quindi nessun risultato
registrato si sposta, e questa migrazione non e' una misura ripetuta.

**Le collection *routed* non si toccano**, ed e' un rifiuto e non una
dimenticanza: li' il valore e' vero, l'ha scritto il modulo che ha girato
davvero. Lo script lo verifica dal nome e si ferma, perche' il modo piu' facile
di rovinare questo dato e' passargli la collection sbagliata.

Idempotente: rilanciarlo non fa niente. `--dry-run` dice soltanto cosa farebbe.

Usage:
    python scripts/migrate_pipeline_field.py --dry-run
    python scripts/migrate_pipeline_field.py
    python scripts/migrate_pipeline_field.py --collection ledger
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets.registry import dataset_ids
from src.datasets.schema import PIPELINE_GENERIC
from qdrant_client import models

from src.index.store import get_client

#: Il suffisso che marca una collection prodotta dal router (R-06/R-07).
SUFFISSO_ROUTED = "_routed"

#: Quanto si aspetta una scrittura. Vedi la nota accanto a `set_payload`.
TIMEOUT_S = 600


def valori(client, collection: str, campione: int) -> Counter:
    """Quali `pipeline` porta oggi la collection, su un campione."""
    punti, _ = client.scroll(
        collection_name=collection,
        limit=campione,
        with_payload=True,
        with_vectors=False,
    )
    return Counter(p.payload.get("pipeline", "") for p in punti)


def da_migrare(client, collection: str) -> int:
    """Quanti punti **non** hanno gia' il valore giusto. Esatto, non campionato.

    Il campione serve a stampare cosa c'e' dentro; a decidere se c'e' ancora da
    fare serve il conto vero. Con 500 punti su 47.110, «gia' a posto» sarebbe
    una conclusione tratta dall'1% -- e una migrazione che si dichiara finita
    quando non lo e' e' il modo in cui un dato resta sbagliato per sempre.
    """
    return client.count(
        collection,
        count_filter=models.Filter(
            must_not=[
                models.FieldCondition(
                    key="pipeline", match=models.MatchValue(value=PIPELINE_GENERIC)
                )
            ]
        ),
    ).count


def main() -> None:
    p = argparse.ArgumentParser(
        description="U-05: `pipeline` nelle collection generiche"
    )
    p.add_argument(
        "--collection",
        action="append",
        default=None,
        help="collection da migrare (ripetibile; default: le generiche dei dataset noti)",
    )
    p.add_argument("--dry-run", action="store_true", help="dice soltanto cosa farebbe")
    p.add_argument(
        "--campione", type=int, default=500, help="punti letti per il resoconto"
    )
    args = p.parse_args()

    client = get_client(cfg.QDRANT_URL)
    esistenti = {c.name for c in client.get_collections().collections}
    scelte = args.collection or list(dataset_ids())

    for nome in scelte:
        if nome.endswith(SUFFISSO_ROUTED):
            print(
                f"{nome}: RIFIUTATO -- e' una collection routed, li' il valore e' vero"
            )
            continue
        if nome not in esistenti:
            print(f"{nome}: assente, salto")
            continue

        totale = client.count(nome).count
        restano = da_migrare(client, nome)
        if restano == 0:
            print(f"{nome}: gia' a posto ({totale} punti, tutti '{PIPELINE_GENERIC}')")
            continue

        prima = valori(client, nome, args.campione)
        print(
            f"{nome}: {restano} punti su {totale} da cambiare, "
            f"oggi {dict(prima)} -> '{PIPELINE_GENERIC}'"
        )
        if args.dry_run:
            continue

        t0 = time.perf_counter()
        # Senza filtro: **ogni** punto di una collection generica viene dal
        # loader generico, quindi il valore giusto e' lo stesso per tutti. Un
        # filtro qui restringerebbe a cio' che ci si aspetta di trovare, e
        # lascerebbe fuori proprio i casi che non ci si aspettava.
        client.set_payload(
            collection_name=nome,
            payload={"pipeline": PIPELINE_GENERIC},
            # `Filter()` vuoto seleziona **tutti** i punti. Non e' una
            # scorciatoia per non scrivere una condizione: la condizione
            # sarebbe «quelli che hanno il valore vecchio», e restringere
            # cosi' lascerebbe fuori proprio i punti con un valore che non
            # si era previsto di trovare.
            points=models.Filter(),
            wait=True,
            # Il default del client e' cinque secondi, e su `ledger` (47.110
            # punti) la scrittura ne prende di piu': il server la porta a
            # termine, il client molla, e lo script esce con un errore. Una
            # migrazione riuscita che si dichiara fallita e' peggio di una
            # fallita: invita a rilanciarla cercando un guasto che non c'e'.
            timeout=TIMEOUT_S,
        )
        rimasti = da_migrare(client, nome)
        stato = "ok" if rimasti == 0 else f"ATTENZIONE: {rimasti} punti non cambiati"
        print(f"   fatto in {time.perf_counter() - t0:.1f}s -- {stato}")


if __name__ == "__main__":
    main()
