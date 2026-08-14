"""Il backend visto da fuori (A-06).

Prima di questo file la dashboard **era** un secondo backend: apriva il suo
client Qdrant, embeddava le query per conto suo, fondeva con RRF, chiamava il
cross-encoder. Tre copie della stessa pipeline — questa, quella del servizio e
quella dell'harness — e le tre erano già divergenti: due leggevano `cfg` globale
invece della configurazione di richiesta, e nessuna delle due lo sapeva.

Il ROADMAP dice perché è A-06 e non un extra: *«è il consumatore più esigente
che esista già. Se l'API le basta, basterà anche al frontend — e se non le
basta, si scopre ora invece che a React scritto.»* Non le bastava, ed è così che
è nato `POST /retrieve`.

**`urllib` e non `httpx`**: nessuna dipendenza nuova per quattro chiamate HTTP.
È la stessa scelta di `src/generation/chat.py`, che parla con l'LLM allo stesso
modo — un progetto che rifiuta un framework di orchestrazione non aggiunge un
client HTTP per risparmiare dieci righe.

Nessun import di Streamlit: verificabile senza un'app in esecuzione.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

#: Dove sta il backend. Una variabile e non una costante perché la dashboard può
#: girare altrove — è la stessa proprietà che A-05 ha dato al backend, applicata
#: al suo consumatore. Il default è il caso comune: entrambi sulla stessa
#: macchina, che è come si sviluppa.
BASE_URL = os.getenv("IBID_API_URL", "http://localhost:8000")

#: Quanto aspettare. Generoso di proposito: la prima richiesta dopo un avvio
#: carica ~2,5 GB di pesi, e una dashboard che va in timeout proprio lì
#: sembrerebbe rotta nel momento in cui è solo lenta.
TIMEOUT_S = 300


class ApiError(RuntimeError):
    """Il backend ha risposto, e ha detto di no.

    Distinta da `ApiUnreachable` perché le due chiedono cose diverse a chi
    legge: qui c'è un servizio vivo che rifiuta la richiesta, là non c'è nessuno
    che risponde. Confonderle manda a cercare nel posto sbagliato.
    """

    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class ApiUnreachable(RuntimeError):
    """Nessuno risponde su `BASE_URL`."""


def _call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE_URL.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        try:
            detail = json.loads(detail).get("detail", detail)
        except Exception:
            pass
        raise ApiError(e.code, str(detail)) from e
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ApiUnreachable(f"{BASE_URL} non risponde: {e}") from e


# --- i casi d'uso, uno per endpoint ----------------------------------------


#: Il valore di partenza dei controlli, prima che il backend abbia risposto.
#: Non è «il top_k del sistema» — quello lo dice `/config`, e cambia col
#: deployment. È solo dove mettere lo slider al primo disegno, e tenerlo qui
#: evita di leggere `cfg` dalla dashboard per una posizione di widget.
DEFAULT_TOP_K = 5


def effective_config() -> dict:
    """I default di richiesta di **questo** backend.

    Serve a una dashboard che voglia mostrare da dove parte, invece di
    indovinarlo: due deployment possono avere `top_k` diversi, e un controllo
    che parte dal valore sbagliato fa credere di aver chiesto una cosa e
    chiederne un'altra.
    """
    return _call("GET", "/config")


def health() -> bool:
    """Il backend risponde. `False` invece di sollevare: è una domanda a cui
    «no» è una risposta legittima, e la dashboard la usa per dirlo a schermo."""
    try:
        return _call("GET", "/health").get("status") == "ok"
    except (ApiError, ApiUnreachable):
        return False


@dataclass(frozen=True)
class Capabilities:
    """Cosa questo backend accetta. **Letto, non indovinato.**

    La dashboard aveva `KNOWN_DATASETS = ("open_ragbench", "ledger")` scritto a
    mano in `state.py`: la quindicesima copia di quella lista, in un file che
    Q-06 non poteva raggiungere perché non è uno script.
    """

    datasets: list[dict]
    collections: list[str]
    retrieval_modes: list[str]
    baseline_prompts: list[str]

    @property
    def dataset_ids(self) -> tuple[str, ...]:
        return tuple(d["dataset_id"] for d in self.datasets)


def capabilities() -> Capabilities:
    d = _call("GET", "/datasets")
    return Capabilities(
        datasets=d.get("datasets", []),
        collections=d.get("collections", []),
        retrieval_modes=d.get("retrieval_modes", []),
        baseline_prompts=d.get("baseline_prompts", []),
    )


def retrieve(
    queries: list[str],
    *,
    collection: str,
    dataset_id: str = "open_ragbench",
    top_k: int = 5,
    retrieval_mode: str = "dense",
    rerank: bool = False,
) -> list[list[dict]]:
    """Cosa il sistema recupererebbe. Una lista di risultati per query.

    **Molte query in una chiamata**, e non è un'ottimizzazione: il Failure
    Explorer ne manda 200, e 200 viaggi di rete con 200 passate di embedding
    renderebbero la pagina inusabile. L'endpoint esiste in questa forma proprio
    perché è questo il consumatore che l'ha chiesto.
    """
    if not queries:
        return []
    corpo = _call("POST", "/retrieve", {
        "queries": queries,
        "dataset_id": dataset_id,
        "collection": collection,
        "top_k": top_k,
        "retrieval_mode": retrieval_mode,
        "rerank": rerank,
    })
    return corpo["results"]


def chunk(chunk_id: str, collection: str | None = None) -> dict | None:
    """Un chunk per id, o `None` se in quella collection non c'è.

    `None` e non un'eccezione: un `chunk_id` d'oro assente dalla collection
    interrogata **è il dato** — è la differenza fra un retrieval sbagliato e
    un'etichetta sbagliata, e le due chiedono correzioni opposte.
    """
    path = f"/chunk/{chunk_id}"
    if collection:
        path += f"?collection={urllib.parse.quote(collection)}"
    try:
        return _call("GET", path)
    except ApiError as e:
        if e.status in (400, 404):
            return None
        raise


def chunks(chunk_ids: list[str], collection: str | None = None) -> dict[str, dict]:
    """Più chunk per id, come mappa. Gli assenti semplicemente non ci sono.

    Un giro per id, e va bene così: qui gli id sono i qrels di **una** query,
    cioè una manciata. Un endpoint apposta si aggiunge quando il numero lo
    chiede — la stessa ragione per cui `/retrieve` accetta una lista e questo no.
    """
    trovati = {}
    for cid in chunk_ids:
        if (c := chunk(cid, collection)) is not None:
            trovati[cid] = c
    return trovati
