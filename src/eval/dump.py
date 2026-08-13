"""Risultati per query, scritti mentre la run gira (Q-02).

Estratto da `citation_harness.GenerationWriter`, che lo aveva inventato per C-01
ed e' l'unico dei tre harness ad averlo avuto per un anno. Il meccanismo non ha
niente di specifico alle generazioni, e stava per essere copiato una terza volta.

## Le due proprieta' che questo file esiste per garantire

**Una run che muore non porta via tutto.** Prima di C-01 non si scriveva niente
fino alla fine: una valutazione morta alla query 190 su 200 perdeva quaranta
minuti di GPU e centonovanta risultati utilizzabili. Qui ogni record viene
aggiunto e scaricato su disco appena esiste.

**Un file troncato non si confonde con uno finito.** I record si accumulano
sotto un nome che finisce in `.partial`, e la rinomina avviene **solo dopo
l'ultimo**: quindi l'esistenza del nome definitivo e' la prova che la run e'
arrivata in fondo. Senza questa parte, un file a meta' verrebbe letto come
completo e produrrebbe un tasso calcolato su un denominatore diverso da quello
che dichiara -- che e' peggio di nessun file.

## Perche' serve al di la' del non perdere lavoro

Senza risultati per query si possono confrontare **due medie e nient'altro**.
Con essi si fa un test appaiato, che e' la differenza fra "il tasso e' salito"
e "e' salito su queste query, e non e' il caso" (§15).

Il 2026-08-13, in R-08, il confronto con le run archiviate del retrieval e'
stato marginale proprio per questo, e McNemar e' stato possibile solo perche'
lo stato pre-correzione era **riproducibile a comando**. Non e' una fortuna su
cui contare due volte.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def partial_path(path: Path) -> Path:
    """Dove i record si accumulano finche' la run e' in corso."""
    return path.with_suffix(path.suffix + ".partial")


def _as_dict(record: Any) -> dict:
    if is_dataclass(record) and not isinstance(record, type):
        return asdict(record)
    if isinstance(record, dict):
        return record
    raise TypeError(f"record non serializzabile: {type(record).__name__}")


class JsonlWriter:
    """Scrive record JSONL uno alla volta, e rinomina solo alla fine.

    `sidecar` e' un testo da scrivere subito accanto al file -- il prompt di
    sistema, per l'harness delle citazioni. Sta li' e non dentro ogni record
    perche' il JSONL viene letto riga per riga, e ripetere seicento caratteri di
    prompt su ogni riga seppellirebbe gli output che il file esiste per mostrare.
    Viene scritto **subito**, non alla fine: una run che muore lascia comunque i
    propri risultati interpretabili.
    """

    def __init__(self, path: Path, sidecar: str | None = None,
                 sidecar_suffix: str = ".prompt.txt"):
        self.path = path
        self.tmp = partial_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tmp.write_text("", encoding="utf-8")
        self.n = 0
        if sidecar is not None:
            self.path.with_suffix(sidecar_suffix).write_text(sidecar, encoding="utf-8")

    def append(self, record: Any) -> None:
        with self.tmp.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_as_dict(record), ensure_ascii=False) + "\n")
            fh.flush()
        self.n += 1

    def finish(self) -> Path:
        """Promuove il file parziale al nome definitivo."""
        self.tmp.replace(self.path)
        return self.path


def write_all(path: Path, records: list[Any], sidecar: str | None = None) -> Path:
    """Scrive tutto in una volta: per i test e per gli strumenti di ri-scoring."""
    writer = JsonlWriter(path, sidecar)
    for r in records:
        writer.append(r)
    return writer.finish()


def aligned(a: dict[str, dict], b: dict[str, dict]) -> list[str]:
    """Gli id comuni ai due dump, o un errore se non coincidono.

    Un test appaiato su un'intersezione decisa dal caso non e' un test appaiato:
    la popolazione la sceglierebbe la differenza fra i due file invece di chi
    misura. Meglio rifiutarsi e dire di quanto differiscono.
    """
    if set(a) != set(b):
        only_a, only_b = len(set(a) - set(b)), len(set(b) - set(a))
        raise ValueError(
            f"i due dump non coprono le stesse query: {only_a} solo in A, "
            f"{only_b} solo in B"
        )
    return sorted(a)


def read_jsonl(path: Path) -> list[dict]:
    """Legge un dump. Rifiuta i `.partial`, che sono run non finite.

    Leggerli in silenzio e' esattamente il difetto che il suffisso previene: si
    otterrebbe un numero calcolato su meno query di quante il file dichiara.
    """
    if path.suffix == ".partial":
        raise ValueError(
            f"{path.name} e' una run non finita: il nome definitivo compare solo "
            "quando l'ultima query e' stata scritta"
        )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
