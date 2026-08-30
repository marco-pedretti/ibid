"""L'indice `demo`: caricarlo su Qdrant, e dire che e' quello (U-08).

Il file che sta in git lo scrive `scripts/build_demo_index.py`, una volta, su
una macchina che ha l'indice completo. Questo modulo fa il verso opposto e lo
fa **ovunque**: legge `data/demo/`, lo scrive su Qdrant e ci mette sopra un
cartellino. Non serve ne' GPU ne' rete: i vettori sono gia' quelli misurati.

    python -m src.index.demo                    # dentro il container
    python scripts/seed_demo.py                 # lo stesso, da fuori

## Il cartellino, e perche' non basta scriverlo nel README

Le collection si chiamano `open_ragbench` e `ledger` come quelle vere, e deve
essere cosi': se si chiamassero altrimenti, l'interfaccia non le troverebbe e i
sei esempi di `esempi.ts` andrebbero cambiati insieme al modo di avviare. Ma due
collection con lo stesso nome e un ventesimo dei punti sono **il modo perfetto
di misurare la cosa sbagliata**: un `eval.py` lanciato per sbaglio contro questo
server stamperebbe numeri plausibili e falsi.

Quindi il caricamento lascia una collection in piu', `ibid_demo`, senza vettori
e con un punto solo: il manifesto. Da li' `/datasets` sa dire **ridotto**,
l'interfaccia lo scrive, e la protezione qui sotto sa distinguere un server di
dimostrazione da uno con dentro due ore di GPU.

**E' anche cio' che impedisce il guasto peggiore di tutti**: caricare la demo
sopra l'indice vero. Senza cartellino il caricamento si rifiuta di toccare una
collection che esiste gia', perche' non puo' sapere che cosa contiene.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

from src.index.store import _UPSERT_BATCH, ensure_collection, get_client

#: La collection che non e' un indice: e' un cartellino. Senza vettori (Qdrant
#: accetta `vectors_config={}`), un punto solo, il manifesto nel payload.
MARCATORE = "ibid_demo"

#: Dove sta l'indice ridotto dentro il repository, e **dentro l'immagine**: il
#: `Dockerfile` lo copia in `/app/data/demo`, cosi' il percorso e' lo stesso
#: dentro e fuori dal container e questo modulo non deve saperlo. Montarlo, come
#: si faceva fino al 2026-08-30, voleva dire che l'immagine pubblicata non
#: sapeva avviarsi senza una copia del repository accanto.
CARTELLA = Path(__file__).parent.parent.parent / "data" / "demo"


def manifesto(client: QdrantClient) -> dict | None:
    """Il manifesto se questo server e' una demo, `None` se non lo e'.

    **Non solleva quando la collection manca**: la domanda «sei una demo?» ha
    una risposta anche su un server normale, ed e' «no».
    """
    if not client.collection_exists(MARCATORE):
        return None
    punti, _ = client.scroll(MARCATORE, limit=1, with_payload=True, with_vectors=False)
    return punti[0].payload if punti else None


def dataset_ridotti(client: QdrantClient) -> set[str]:
    """I `dataset_id` che su questo server sono l'indice ridotto."""
    m = manifesto(client)
    return {v["dataset_id"] for v in m.get("datasets", [])} if m else set()


def _leggi(cartella: Path, dataset: str) -> tuple[list[dict], np.ndarray]:
    righe = [
        json.loads(r)
        for r in (cartella / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines()
        if r
    ]
    dense = np.load(cartella / f"{dataset}.dense.npy")
    if len(righe) != len(dense):
        raise SystemExit(
            f"{dataset}: {len(righe)} chunk e {len(dense)} vettori. "
            "I due file non vengono dallo stesso `build_demo_index.py`."
        )
    return righe, dense


def carica(
    client: QdrantClient,
    cartella: Path = CARTELLA,
    force: bool = False,
) -> dict:
    """Scrive l'indice ridotto su Qdrant. Restituisce il manifesto caricato."""
    letto = json.loads((cartella / "manifest.json").read_text(encoding="utf-8"))
    gia_demo = dataset_ridotti(client)

    for voce in letto["datasets"]:
        dataset = voce["dataset_id"]
        if client.collection_exists(dataset) and dataset not in gia_demo and not force:
            raise SystemExit(
                f"la collection «{dataset}» esiste gia' su questo server e non porta il "
                f"cartellino «{MARCATORE}»: potrebbe essere l'indice completo, che costa "
                "ore di GPU. Non la tocco.\n"
                "  - per la demo, usa un Qdrant suo: `docker compose --profile demo up`\n"
                "  - se sai cosa stai facendo: --force"
            )

    for voce in letto["datasets"]:
        dataset = voce["dataset_id"]
        righe, dense = _leggi(cartella, dataset)
        t0 = time.perf_counter()

        # Ricreata, non svuotata: cosi' due caricamenti di fila danno lo stesso
        # indice anche se il file e' cambiato di dimensione fra i due.
        if client.collection_exists(dataset):
            client.delete_collection(dataset)
        ensure_collection(client, dataset, dense_size=int(dense.shape[1]))

        for i in range(0, len(righe), _UPSERT_BATCH):
            blocco = righe[i : i + _UPSERT_BATCH]
            client.upsert(
                collection_name=dataset,
                points=[
                    PointStruct(
                        id=i + j,
                        vector={
                            "dense": dense[i + j].tolist(),
                            "sparse": SparseVector(
                                indices=r["sparse"]["indices"], values=r["sparse"]["values"]
                            ),
                        },
                        payload=r["payload"],
                    )
                    for j, r in enumerate(blocco)
                ],
                wait=True,
            )
        print(f"  {dataset}: {len(righe)} chunk in {time.perf_counter() - t0:.1f} s")

    # Il cartellino **per ultimo**: un caricamento interrotto a meta' non deve
    # lasciare un server che si dichiara pronto.
    if client.collection_exists(MARCATORE):
        client.delete_collection(MARCATORE)
    client.create_collection(collection_name=MARCATORE, vectors_config={})
    caricato = {**letto, "caricato": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    client.upsert(
        collection_name=MARCATORE,
        points=[PointStruct(id=0, vector={}, payload=caricato)],
        wait=True,
    )
    return caricato


def main(argv: list[str] | None = None) -> None:
    import src.config as cfg

    ap = argparse.ArgumentParser(description="Carica l'indice `demo` su Qdrant (U-08).")
    ap.add_argument("--data", type=Path, default=CARTELLA, help="la cartella data/demo")
    ap.add_argument("--qdrant-url", default=cfg.QDRANT_URL)
    ap.add_argument(
        "--force",
        action="store_true",
        help="sovrascrive anche collection che non portano il cartellino",
    )
    args = ap.parse_args(argv)

    print(f"indice `demo` -> {args.qdrant_url}")
    caricato = carica(get_client(args.qdrant_url), args.data, force=args.force)
    totale = sum(v["chunk"] for v in caricato["datasets"])
    print(f"pronto: {totale} chunk, embedder {caricato['embedding_model']}")
    print("**indice ridotto**: serve a mostrare, non riproduce nessuna misura.")


if __name__ == "__main__":
    main()
