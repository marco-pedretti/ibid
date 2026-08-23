#!/usr/bin/env python3
"""D-17 / U-23: gli esempi dello stato vuoto fanno quello che dichiarano?

`ui/src/app/esempi.ts` diceva che le sue domande sono query d'oro vere, *«perche'
il primo clic di chi prova il progetto non deve finire in un'astensione»*. La
premessa era vera e la conclusione no: una query d'oro ha dei **qrels**, non la
garanzia che il recupero li trovi. Su `ledger` solo il 35% delle query d'oro
porta il proprio chunk nei primi cinque -- e uno degli esempi di allora non
arrivava affatto.

Questo e' il controllo che mancava, ed e' fatto per essere **rieseguito**: gli
esempi vanno riverificati ogni volta che cambia l'indice, il modello d'embedding
o il default del recupero. OQ-09 ha mostrato che l'indice puo' cambiare **da
solo**, sotto un task che non lo toccava.

    python scripts/verify_esempi.py                    # controlla quelli in vigore
    python scripts/verify_esempi.py --cerca ledger     # ne propone di nuovi

**Non verifica che "funzioni": verifica cio' che l'esempio dichiara.** Ogni voce
di `esempi.ts` porta un campo `atteso` -- il chunk e la posizione, oppure che il
gate si chiuda -- ed e' quello il criterio. Un controllo che si accontentasse di
"ha trovato qualcosa" passerebbe anche il giorno in cui trova un chunk diverso.

**Tutto due volte, in ricerca approssimata e in esatta.** Il default oggi e'
l'ANN, il ROADMAP prevede che la demo giri in esatta, e `make dev` e il profilo
`demo` potrebbero non coincidere. Un esempio che regge solo in una delle due si
rompe a seconda di come lo si avvia -- ed e' precisamente il modo in cui questo
difetto e' nato.

**Il terzo esempio di ogni dataset deve chiudere il gate**, non limitarsi a
essere assente. Le due astensioni non sono la stessa cosa: la soglia di C-04 e'
decisa in codice (§15), il rifiuto scritto dal modello e' una gentilezza che non
si controlla (D-19). I «fuori corpus» di prima non chiudevano il gate.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.provenance import load_golden
from src.index.store import get_client
from src.retrieval.abstention import decide
from src.retrieval.backends import RETRIEVERS

ESEMPI_TS = ROOT / "ui" / "src" / "app" / "esempi.ts"
GOLDEN = ROOT / "eval" / "golden"

#: Quanti esempi per dataset, e quanti fuori corpus. Fissati perche' lo script
#: fallisca se `esempi.ts` cambia forma, invece di controllare in silenzio meno
#: di quello che dovrebbe.
ATTESI_PER_DATASET = 3
FUORI_CORPUS_PER_DATASET = 1


def _atteso(corpo: str) -> dict:
    """Il letterale `atteso` di un esempio, come dizionario."""
    esito = re.search(r'esito: "([^"]+)"', corpo)
    if not esito:
        raise SystemExit(f"atteso senza esito: {corpo.strip()!r}")
    d: dict = {"esito": esito.group(1)}
    for chiave, testo in re.findall(r'(chunk): "([^"]+)"', corpo):
        d[chiave] = testo
    for chiave, numero in re.findall(r"(posizione|margine): ([\d.]+)", corpo):
        d[chiave] = int(numero) if chiave == "posizione" else float(numero)
    return d


def esempi_dal_ts(path: Path = ESEMPI_TS) -> dict[str, list[tuple[str, dict]]]:
    """Le query di `esempi.ts` con la loro aspettativa, per dataset e in ordine.

    **Legge il TypeScript invece di duplicare l'elenco** perche' due elenchi da
    tenere allineati a mano sono un elenco solo che a volte mente, e qui il
    difetto da evitare e' esattamente quello: una lista che dichiara una cosa
    che nessuno ha verificato.

    Il parser e' volutamente rigido -- conta gli esempi e pretende che ogni
    `query` abbia il suo `atteso` -- cosi' un cambio di forma del file lo fa
    **fallire** invece di fargli controllare meno di quel che deve.
    """
    testo = path.read_text(encoding="utf-8")
    blocchi = re.split(r"^  (\w+): \[$", testo, flags=re.M)
    # `re.split` con un gruppo restituisce [prima, nome1, corpo1, nome2, corpo2...]
    fuori: dict[str, list[tuple[str, dict]]] = {}
    for nome, corpo in zip(blocchi[1::2], blocchi[2::2]):
        queries = re.findall(r'query:\s*"((?:[^"\\]|\\.)*)"', corpo)
        attesi = [_atteso(a) for a in re.findall(r"atteso: \{([^}]*)\}", corpo)]
        if len(queries) != len(attesi):
            raise SystemExit(
                f"{path.name}: {nome} ha {len(queries)} query e {len(attesi)} attesi. "
                "Ogni esempio deve dichiarare cosa deve succedere."
            )
        if len(queries) != ATTESI_PER_DATASET:
            raise SystemExit(
                f"{path.name}: {nome} ha {len(queries)} esempi invece di "
                f"{ATTESI_PER_DATASET}. Se e' voluto, cambia ATTESI_PER_DATASET qui."
            )
        fuori[nome] = list(zip(queries, attesi))
    if not fuori:
        raise SystemExit(f"{path.name}: nessun dataset riconosciuto, la forma del file e' cambiata")
    return fuori


def _posizione(chunk_ids: list[str], chunk: str) -> int | None:
    """Rango (da 1) di **quel** chunk, o `None` se non c'e'."""
    return chunk_ids.index(chunk) + 1 if chunk in chunk_ids else None


def _primo_oro(chunk_ids: list[str], oro: set[str]) -> int | None:
    """Rango del primo chunk d'oro qualsiasi: serve a `--cerca`, non al controllo."""
    for i, c in enumerate(chunk_ids, 1):
        if c in oro:
            return i
    return None


def _recupera(client, dataset: str, testi: list[str], esatta: bool, top_k: int):
    config = cfg.RequestConfig.from_defaults(
        top_k=top_k, retrieval_mode="dense", search_exact=esatta
    )
    return RETRIEVERS["dense"](client, dataset, testi, top_k, None, config)


def controlla(dataset: str, esempi: list[tuple[str, dict]], top_k: int) -> bool:
    """Stampa il verdetto per un dataset. `True` se ognuno fa quel che dichiara."""
    dorate = {q.query_text: q for q in load_golden(GOLDEN / f"{dataset}.jsonl") if q.answerable}
    risponde = [(q, a) for q, a in esempi if a["esito"] == "risponde"]
    astiene = [(q, a) for q, a in esempi if a["esito"] == "si astiene"]

    print("")
    print(f"=== {dataset}: {len(risponde)} rispondono, {len(astiene)} si astengono")
    ok = True

    if len(astiene) != FUORI_CORPUS_PER_DATASET:
        print(f"  NO  attesi {FUORI_CORPUS_PER_DATASET} fuori corpus, trovati {len(astiene)}")
        ok = False

    client = get_client(cfg.QDRANT_URL)
    testi = [q for q, _ in esempi]
    per_query = dict(
        zip(
            testi,
            zip(
                _recupera(client, dataset, testi, False, top_k),
                _recupera(client, dataset, testi, True, top_k),
            ),
        )
    )

    for q, atteso in risponde:
        if q not in dorate:
            print(f"  NO  non e' una query d'oro rispondibile   {q[:66]}")
            ok = False
            continue
        oro = {r.chunk_id for r in dorate[q].qrels}
        if atteso["chunk"] not in oro:
            print(f"  NO  il chunk dichiarato non e' fra i qrels   {atteso['chunk']}")
            ok = False
            continue
        a, e = per_query[q]
        pa = _posizione(a.chunk_ids, atteso["chunk"])
        pe = _posizione(e.chunk_ids, atteso["chunk"])
        voluta = atteso["posizione"]
        buono = pa == voluta and pe == voluta
        ok = ok and buono
        segno = "ok " if buono else "NO "
        print(f"  {segno} attesa {voluta}, ANN {pa or '-'} esatta {pe or '-'}   {q[:60]}")

    for q, atteso in astiene:
        if q in dorate:
            print(f"  NO  e' una query d'oro RISPONDIBILE   {q[:60]}")
            ok = False
            continue
        a, e = per_query[q]
        da, de = decide(a.scores, dataset, "dense"), decide(e.scores, dataset, "dense")
        chiude = da.abstain and de.abstain
        ok = ok and chiude
        margini = [m for m in (da.margin, de.margin) if m is not None]
        peggiore = -max(margini) if margini else 0.0
        segno = "ok " if chiude else "NO "
        stato = "chiuso" if chiude else "APERTO"
        print(f"  {segno} gate {stato}, margine {peggiore:+.4f} "
              f"(dichiarato +{atteso['margine']:.4f})   {q[:44]}")
        if chiude and peggiore < atteso["margine"] / 2:
            print("      margine dimezzato: aggiorna il numero o cambia l'esempio")

    return ok


def cerca(dataset: str, top_k: int, quanti: int, campione: int) -> None:
    """Propone query d'oro che il recupero **trova davvero**, in tutte e due le ricerche.

    Serve a scegliere gli esempi invece di indovinarli. Stampa anche il tasso di
    successo del campione, che e' il numero che spiega perche' indovinare non
    funziona.
    """
    dorate = [q for q in load_golden(GOLDEN / f"{dataset}.jsonl") if q.answerable][:campione]
    testi = [q.query_text for q in dorate]
    print(f"{dataset}: provo le prime {len(testi)} query d'oro...")

    client = get_client(cfg.QDRANT_URL)
    ann = _recupera(client, dataset, testi, False, top_k)
    esatta = _recupera(client, dataset, testi, True, top_k)

    buone = []
    for q, a, e in zip(dorate, ann, esatta):
        oro = {r.chunk_id for r in q.qrels}
        pa, pe = _primo_oro(a.chunk_ids, oro), _primo_oro(e.chunk_ids, oro)
        if pa is not None and pe is not None:
            chunk = next(c for c in a.chunk_ids if c in oro)
            buone.append((max(pa, pe), pa, pe, chunk, q.query_text))

    quota = len(buone) / len(testi) if testi else 0.0
    print(f"  ne reggono {len(buone)} su {len(testi)} ({quota:.1%}) "
          "-- ecco perche' una query d'oro presa a caso non basta")
    print("")
    for _, pa, pe, chunk, testo in sorted(buone)[:quanti]:
        print(f"  ANN {pa} esatta {pe}  {chunk}")
        print(f"      {testo}")


def main() -> None:
    p = argparse.ArgumentParser(description="D-17: gli esempi dello stato vuoto")
    p.add_argument("--cerca", metavar="DATASET",
                   help="invece di controllare, propone query d'oro verificate")
    p.add_argument("--top-k", type=int, default=cfg.TOP_K,
                   help="il top_k con cui parte la demo (default: quello di config.py)")
    p.add_argument("--quanti", type=int, default=15, help="quante proposte stampare (--cerca)")
    p.add_argument("--campione", type=int, default=300,
                   help="quante query d'oro provare (--cerca): tutte sarebbero minuti di GPU")
    args = p.parse_args()

    if args.cerca:
        cerca(args.cerca, args.top_k, args.quanti, args.campione)
        return

    tutto_bene = True
    for dataset, esempi in esempi_dal_ts().items():
        tutto_bene &= controlla(dataset, esempi, args.top_k)

    print("")
    if tutto_bene:
        print("Ogni esempio fa quel che dichiara, in ANN e in esatta.")
    else:
        print("Almeno un esempio non regge. `--cerca DATASET` ne propone di verificati.")
    sys.exit(0 if tutto_bene else 1)


if __name__ == "__main__":
    main()
