"""Quali dataset esistono, e cosa serve sapere di ognuno (Q-06).

Prima di questo file la risposta era sparsa: `choices=["open_ragbench", "ledger",
"all"]` scritto a mano in **14 script**, una catena di `if dataset_id == ...` in
`ingest.py`, un dizionario `_LOADERS` in `profile_docs.py`, e due import
espliciti in `build_golden.py`. Aggiungere un terzo dataset significava scrivere
il suo loader — che è il lavoro vero e inevitabile — e poi toccare quattordici
file per dirlo in giro.

Il nucleo era già agnostico: `Chunk` porta `dataset_id`, il routing va per
`doc_genre` e non per dataset, le metriche sono già per `dataset_id` per
contratto (§3.1). Il coupling stava tutto ai bordi, ed è quello che questo
modulo raccoglie.

**Non è un plugin system.** Non c'è scoperta automatica, non si caricano moduli
per nome, non esiste un formato di manifesto: è un dizionario, e aggiungere una
voce è una riga. Vale la stessa ragione per cui non c'è un framework di
orchestrazione (§14) — la generalità si compra quando serve, non prima.

## Aggiungere un dataset

1. `src/datasets/<nome>.py` con la stessa forma degli altri due: `DATASET_ID`,
   `REPO_ID`, `download()`, `iter_chunks()`, `iter_chunks_routed()`.
2. Un caricatore del golden set in `golden.py`, che restituisca `GoldenQuery`.
3. Una voce in `REGISTRY`, qui sotto.

Nessuno script va toccato: leggono tutti da qui.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from src.datasets import golden, ledger, open_ragbench, unanswerable
from src.datasets.schema import Chunk


@dataclass(frozen=True)
class DatasetSpec:
    """Tutto ciò che il resto del repo deve sapere di un dataset.

    I campi sono callable e non nomi di funzione da risolvere a runtime: un
    errore di battitura diventa un `ImportError` all'avvio invece di un
    `KeyError` a metà di un'ingestione da due ore.
    """

    dataset_id: str
    repo_id: str
    #: Percorso del corpus **dentro** la cartella del dataset. Serve a due cose:
    #: capire se il download è già stato fatto, e profilare i documenti sorgente.
    corpus_subpath: tuple[str, ...]
    download: Callable[[Path], Path]
    iter_chunks: Callable[[Path], Iterator[Chunk]]
    iter_chunks_routed: Callable[[Path], Iterator[Chunk]]
    load_golden: Callable[[Path], list]
    #: Cosa scaricare prima di poter costruire il golden set, se serve. LEDGER
    #: tiene query e qrel in un parquet separato dal corpus; open_ragbench li ha
    #: gia' accanto ai documenti e qui mette `None`. Sta nel registro e non in
    #: `build_golden.py` perche' e' sapere sul dataset, non sullo script.
    prepare_golden: Callable[[Path], Path] | None = None
    #: Come riconoscere che `prepare_golden` e' gia' stato fatto.
    golden_ready_glob: str | None = None
    #: Le query senza risposta di E-02, che si costruiscono in modo diverso per
    #: ogni corpus: servono domande plausibili ma non rispondibili, e cosa sia
    #: plausibile dipende dal dominio.
    build_unanswerable: Callable[[Path], list] | None = None

    def dataset_dir(self, data_dir: Path) -> Path:
        return data_dir / self.dataset_id

    def corpus_dir(self, data_dir: Path) -> Path:
        return self.dataset_dir(data_dir).joinpath(*self.corpus_subpath)

    def chunks(self, data_dir: Path, pipeline_mode: str = "original") -> Iterator[Chunk]:
        """I chunk secondo la pipeline richiesta.

        `pipeline_mode` è la stessa distinzione binaria del §3.3 — "routed" usa
        il router per genere, qualunque altra cosa usa la pipeline unica.
        """
        d = self.dataset_dir(data_dir)
        return self.iter_chunks_routed(d) if pipeline_mode == "routed" else self.iter_chunks(d)

    def golden_is_ready(self, data_dir: Path) -> bool:
        """`True` se non c'e' niente da scaricare prima di costruire il golden."""
        if self.prepare_golden is None or self.golden_ready_glob is None:
            return True
        return any(self.dataset_dir(data_dir).glob(self.golden_ready_glob))


REGISTRY: dict[str, DatasetSpec] = {
    "open_ragbench": DatasetSpec(
        dataset_id=open_ragbench.DATASET_ID,
        repo_id=open_ragbench.REPO_ID,
        corpus_subpath=("pdf", "arxiv", "corpus"),
        download=open_ragbench.download,
        iter_chunks=open_ragbench.iter_chunks,
        iter_chunks_routed=open_ragbench.iter_chunks_routed,
        load_golden=golden.load_open_ragbench_golden,
        build_unanswerable=unanswerable.build_unanswerable_for_open_ragbench,
    ),
    "ledger": DatasetSpec(
        dataset_id=ledger.DATASET_ID,
        repo_id=ledger.REPO_ID,
        corpus_subpath=("eval", "mmd"),
        download=ledger.download,
        iter_chunks=ledger.iter_chunks,
        iter_chunks_routed=ledger.iter_chunks_routed,
        load_golden=golden.load_ledger_golden,
        prepare_golden=ledger.download_qa,
        golden_ready_glob="eval/data-*-of-*.parquet",
        build_unanswerable=unanswerable.build_unanswerable_for_ledger,
    ),
}

#: Il valore che gli script accettano per dire "tutti".  Non è un dataset e non
#: sta in REGISTRY: `resolve()` lo espande.
ALL = "all"


def dataset_ids() -> list[str]:
    """Gli identificativi, nell'ordine di dichiarazione."""
    return list(REGISTRY)


def cli_choices() -> list[str]:
    """Cosa passare a `argparse(choices=...)`, `all` compreso."""
    return [*REGISTRY, ALL]


def get(dataset_id: str) -> DatasetSpec:
    try:
        return REGISTRY[dataset_id]
    except KeyError:
        known = ", ".join(REGISTRY)
        raise KeyError(f"dataset sconosciuto: {dataset_id!r} (noti: {known})") from None


def resolve(choice: str) -> list[str]:
    """Da un valore di `--dataset` alla lista di dataset da elaborare."""
    return dataset_ids() if choice == ALL else [choice]
