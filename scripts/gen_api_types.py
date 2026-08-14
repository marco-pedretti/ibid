#!/usr/bin/env python3
"""U-00: i tipi TypeScript del contratto del §3.5, generati da `src/api/`.

La Fase 8 dice «il frontend non importa niente da `src/`», ed e' la regola
giusta: un frontend che importasse la pipeline non sarebbe un consumatore
dell'API, sarebbe un secondo posto in cui la pipeline vive. Ma la conseguenza e'
che il contratto va scritto **due volte**, in due linguaggi -- e due elenchi
scritti a mano divergono. E' la lezione di Q-06, in TypeScript.

Quindi `ui/src/api/types.ts` non si scrive: si genera. `tests/test_ui_types.py`
fallisce se il file committato non e' cio' che questo script produce oggi, cosi'
un campo aggiunto ad `AnswerResponse` senza rigenerare rompe **la suite Python**
-- si scopre prima di arrivare al browser, e senza che serva Node per accorgersene.

**Gli eventi SSE non sono modelli pydantic.** `to_wire()` costruisce i payload a
mano, e sono proprio il punto in cui una divergenza resterebbe invisibile: un
campo tolto li' non rompe nessun tipo Python. Per questo il generatore non li
legge, li **esegue**: i nomi dei campi vengono dal dizionario che finisce
davvero sul filo.

`/health` non ha un tipo qui: risponde `{"status": "ok"}` e nient'altro: e' una
sonda di vitalita', non un contratto dati.

Usage:
    python scripts/gen_api_types.py            # riscrive ui/src/api/types.ts
    python scripts/gen_api_types.py --check    # esce 1 se il file e' vecchio
"""

from __future__ import annotations

import argparse
import sys
import types as pytypes
from pathlib import Path
from typing import Union, get_args, get_origin

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402

import src.config as cfg  # noqa: E402
from src.api.schema import (  # noqa: E402
    EVENT_NAMES,
    AnswerResponse,
    Capabilities,
    ChunkView,
    ConfigView,
    DocumentChunksResponse,
    DocumentsResponse,
    ErrorEvent,
    QueryRequest,
    RetrieveRequestBody,
    RetrieveResponse,
    to_wire,
)
from src.retrieval.abstention import AbstentionDecision  # noqa: E402
from src.service.answer import (  # noqa: E402
    ABSTAINED_BY_GATE,
    ABSTAINED_BY_MODEL,
    NO_ABSTENTION,
    Answer,
    AnswerEvent,
    ChunksEvent,
    CitationsEvent,
    DoneEvent,
    TokenEvent,
)

OUT = ROOT / "ui" / "src" / "api" / "types.ts"

#: Cio' che un client manda. Ogni campo con un default diventa opzionale in TS:
#: e' il criterio di A-07 («la richiesta minima basta ancora») espresso nel tipo
#: invece che in un test, dove il compilatore lo fa rispettare a ogni chiamata.
RICHIESTE: tuple[type[BaseModel], ...] = (QueryRequest, RetrieveRequestBody)

#: Cio' che un client riceve. Le dipendenze (`ChunkView`, `GateView`, ...) non
#: sono elencate: si raccolgono da sole, cosi' un modello nuovo annidato in uno
#: gia' esposto non puo' essere dimenticato.
RISPOSTE: tuple[type[BaseModel], ...] = (
    ConfigView,          # GET /config
    ChunkView,           # GET /chunk/{chunk_id}
    AnswerResponse,      # POST /query
    RetrieveResponse,    # POST /retrieve
    DocumentsResponse,   # GET /documents
    DocumentChunksResponse,  # GET /document/{doc_id}/chunks
    Capabilities,        # GET /datasets
)

#: I soli campi del filo il cui tipo non si deduce dal valore d'esempio, perche'
#: sono contenitori e l'esempio li lascia vuoti. Dichiarati qui e **verificati**:
#: se uno di questi nomi sparisce da `to_wire()`, il generatore solleva invece di
#: emettere un tipo che non esiste piu'.
TIPI_ESPLICITI: dict[str, str] = {
    "chunks": "ChunkView[]",
    "citations": "CitationView[]",
    "uncited_claims": "string[]",
    "config": "ConfigView",
}


# ---------------------------------------------------------------------------
# Dalle annotazioni Python ai tipi TypeScript
# ---------------------------------------------------------------------------


def _fra_parentesi(ts: str) -> str:
    """`(A | null)[]` e non `A | null[]`, che significherebbe un'altra cosa."""
    return f"({ts})" if " | " in ts else ts


def tipo_ts(ann: object) -> str:
    """Il tipo TypeScript di un'annotazione Python, o un errore.

    Solleva su cio' che non sa tradurre invece di ripiegare su `any`: un `any`
    silenzioso e' un campo su cui il compilatore smette di controllare, cioe'
    esattamente il buco che questo file esiste per chiudere.
    """
    if ann is str:
        return "string"
    if ann is bool:  # prima di int: in Python `bool` e' un `int`
        return "boolean"
    if ann in (int, float):
        return "number"

    origine = get_origin(ann)
    if origine in (Union, pytypes.UnionType):
        args = get_args(ann)
        parti = [tipo_ts(a) for a in args if a is not type(None)]
        if type(None) in args:
            parti.append("null")
        return " | ".join(parti)
    if origine is list:
        return f"{_fra_parentesi(tipo_ts(get_args(ann)[0]))}[]"
    if origine is tuple:
        return "[" + ", ".join(tipo_ts(a) for a in get_args(ann)) + "]"
    if origine is dict:
        chiave, valore = get_args(ann)
        return f"Record<{tipo_ts(chiave)}, {tipo_ts(valore)}>"
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann.__name__

    raise TypeError(f"nessun tipo TypeScript per {ann!r}")


def _modelli_in(ann: object) -> list[type[BaseModel]]:
    """I modelli pydantic annidati in un'annotazione, a qualsiasi profondita'."""
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return [ann]
    return [m for a in get_args(ann) for m in _modelli_in(a)]


def in_ordine(modelli: tuple[type[BaseModel], ...]) -> list[type[BaseModel]]:
    """I modelli chiesti piu' quelli da cui dipendono, dipendenze per prime.

    TypeScript non lo pretenderebbe, le `interface` sono issate. Ma un file in
    cui `ChunkView` compare prima di `AnswerResponse` si legge dal basso verso
    l'alto, ed e' l'ordine in cui il contratto e' stato pensato.
    """
    ordinati: list[type[BaseModel]] = []

    def visita(m: type[BaseModel]) -> None:
        if m in ordinati:
            return
        for campo in m.model_fields.values():
            for dipendenza in _modelli_in(campo.annotation):
                visita(dipendenza)
        if m not in ordinati:
            ordinati.append(m)

    for modello in modelli:
        visita(modello)
    return ordinati


def interfaccia(modello: type[BaseModel], *, opzionali: bool) -> str:
    """Un'`interface` TypeScript, con la prima riga della docstring sopra."""
    doc = (modello.__doc__ or "").strip().splitlines()
    righe = [f"/** {doc[0]} */"] if doc and doc[0] else []
    righe.append(f"export interface {modello.__name__} {{")
    for nome, campo in modello.model_fields.items():
        forse = "?" if opzionali and not campo.is_required() else ""
        righe.append(f"  {nome}{forse}: {tipo_ts(campo.annotation)};")
    righe.append("}")
    return "\n".join(righe)


# ---------------------------------------------------------------------------
# Gli eventi: non letti, eseguiti
# ---------------------------------------------------------------------------


def _risposta_di_esempio() -> Answer:
    """Un `Answer` minimo, che serve solo a far girare `to_wire(DoneEvent(...))`.

    I valori non contano, i **tipi** si': `timings` non e' vuoto perche' da un
    dizionario vuoto non si dedurrebbe il tipo dei valori.
    """
    return Answer(
        query="", dataset_id="", collection="",
        config=cfg.RequestConfig.from_defaults(),
        chunks=[], raw_text="", text="", repaired=False,
        abstained=False, abstention="",
        gate=AbstentionDecision(abstain=False, active=False, score=0.0, threshold=None),
        cited=[], citations=[], uncited_claims=[], verified=False,
        truncated=False, completion_tokens=0,
        timings={"retrieval": 0.0},
    )


def eventi_di_esempio() -> list[object]:
    """Uno per tipo, nell'ordine del §3.5. `EVENT_NAMES` ne verifica la completezza."""
    return [
        ChunksEvent(chunks=[]),
        TokenEvent(text=""),
        AnswerEvent(text="", raw_text="", repaired=False, abstained=False,
                    abstention="", truncated=False, verification_pending=False),
        CitationsEvent(citations=[], uncited_claims=[]),
        DoneEvent(answer=_risposta_di_esempio()),
        ErrorEvent(message="", stage=""),
    ]


def tipo_da_valore(nome: str, valore: object) -> str:
    if nome in TIPI_ESPLICITI:
        return TIPI_ESPLICITI[nome]
    if isinstance(valore, bool):
        return "boolean"
    if isinstance(valore, str):
        return "string"
    if isinstance(valore, (int, float)):
        return "number"
    if isinstance(valore, dict) and valore:
        primo = next(iter(valore.values()))
        return f"Record<string, {tipo_da_valore('', primo)}>"
    raise TypeError(
        f"il campo {nome!r} del filo vale {valore!r}: aggiungilo a TIPI_ESPLICITI"
    )


def _nome_interfaccia(evento: str) -> str:
    return "".join(p.capitalize() for p in evento.split("_")) + "Payload"


def payload_degli_eventi() -> tuple[list[str], list[str]]:
    """Le `interface` dei payload e i rami dell'unione, dai dizionari veri.

    Nessuna lettura del sorgente di `to_wire()`: si guarda cosa restituisce. Un
    campo aggiunto li' compare qui senza che nessuno lo dichiari, e uno tolto
    sparisce -- che e' l'unico modo perche' i due lati non possano divergere.
    """
    blocchi, rami, visti = [], [], set()
    for evento in eventi_di_esempio():
        nome, payload = to_wire(evento)  # type: ignore[arg-type]
        interfaccia_ = _nome_interfaccia(nome)
        righe = [f"export interface {interfaccia_} {{"]
        for campo, valore in payload.items():
            righe.append(f"  {campo}: {tipo_da_valore(campo, valore)};")
            visti.add(campo)
        righe.append("}")
        blocchi.append("\n".join(righe))
        rami.append(f'  | {{ event: "{nome}"; data: {interfaccia_} }}')

    dimenticati = set(TIPI_ESPLICITI) - visti
    if dimenticati:
        raise RuntimeError(
            f"TIPI_ESPLICITI dichiara campi che il filo non porta piu': {sorted(dimenticati)}"
        )
    return blocchi, rami


# ---------------------------------------------------------------------------
# Il file
# ---------------------------------------------------------------------------

INTESTAZIONE = """\
// Generato da `python scripts/gen_api_types.py` -- non modificare a mano.
//
// Il contratto del §3.5 in TypeScript. La Fase 8 vieta al frontend di importare
// `src/`, quindi il contratto esiste due volte; questo file e' la copia che non
// si scrive. `tests/test_ui_types.py` fallisce se non e' aggiornato.
//
// `GET /health` non e' qui: risponde `{"status": "ok"}`, che e' una sonda di
// vitalita' e non un contratto dati.
"""


def genera() -> str:
    parti = [INTESTAZIONE.rstrip()]

    parti.append("// --- Cosa si puo' chiedere ---------------------------------------------\n"
                 "// Solo `query` (e `queries`) e' obbligatorio: tutto il resto ha un default\n"
                 "// lato server, ed e' il motivo per cui un client minimo continua a valere.")
    for modello in in_ordine(RICHIESTE):
        parti.append(interfaccia(modello, opzionali=True))

    parti.append("// --- Cosa si riceve ----------------------------------------------------")
    gia_emessi = set(in_ordine(RICHIESTE))
    for modello in in_ordine(RISPOSTE):
        if modello not in gia_emessi:
            parti.append(interfaccia(modello, opzionali=False))

    blocchi, rami = payload_degli_eventi()
    parti.append("// --- Lo stream ---------------------------------------------------------\n"
                 "// I payload sono presi eseguendo `to_wire()`, non leggendolo: e' l'unico\n"
                 "// punto del contratto costruito a mano, cioe' l'unico che potrebbe\n"
                 "// divergere in silenzio.")
    parti.extend(blocchi)
    parti.append("export type SseEvent =\n" + "\n".join(rami) + ";")
    parti.append(
        "/** I nomi degli eventi del §3.5, nell'ordine in cui uno stream li emette. */\n"
        "export const SSE_EVENTS = ["
        + ", ".join(f'"{n}"' for n in EVENT_NAMES.values())
        + "] as const;"
    )

    # `abstention` viaggia come `str` nel contratto, ma i suoi valori sono tre e
    # decisi in `src/service/answer.py`. Il frontend deve distinguerli — «non ho
    # trovato niente» e «il modello non se l'e' sentita» sono due risposte
    # diverse, e mostrarle uguali cancellerebbe cio' che C-04 misura. Copiarli a
    # mano sarebbe la costante del backend che U-00 vieta al frontend, quindi si
    # generano: se un giorno cambiano, cambia questo file e la suite Python se ne
    # accorge prima del browser.
    parti.append(
        "/** I valori di `abstention`, da `src/service/answer.py`. */\n"
        "export const ABSTENTION = {\n"
        f'  nessuna: "{NO_ABSTENTION}",\n'
        f'  gate: "{ABSTAINED_BY_GATE}",\n'
        f'  modello: "{ABSTAINED_BY_MODEL}",\n'
        "} as const;"
    )

    return "\n\n".join(parti) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="U-00: types.ts dal contratto dell'API")
    p.add_argument("--check", action="store_true",
                   help="non scrive: esce 1 se il file committato e' vecchio")
    args = p.parse_args()

    atteso = genera()
    if args.check:
        attuale = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if attuale != atteso:
            print(f"{OUT.relative_to(ROOT)} non e' aggiornato: "
                  "esegui python scripts/gen_api_types.py")
            raise SystemExit(1)
        print(f"{OUT.relative_to(ROOT)} aggiornato.")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(atteso, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(atteso.splitlines())} righe.")


if __name__ == "__main__":
    main()
