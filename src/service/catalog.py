"""Cosa si puo' interrogare, e come rileggere una fonte citata.

Due casi d'uso piccoli, e nessuno dei due e' accessorio.

`datasets()` esiste per U-01: cambiare dataset senza riavviare, e senza che il
frontend porti una lista scritta a mano — la stessa lezione di Q-06, dove
quattordici `choices=[...]` copiate a mano dicevano cose diverse fra loro.  Il
registro e' l'unico posto in cui i dataset sono elencati; qui viene solo
chiesto a Qdrant se sono stati indicizzati davvero.

`chunk()` esiste per U-06: una citazione porta un `chunk_id`, e un link deve
poter riportare al testo esatto che l'ha sostenuta.  Senza, la verifica e'
un'affermazione che il lettore deve accettare sulla fiducia.

`models()` e' arrivata con A-07, per la stessa ragione di `datasets()`: e' il
backend a sapere cosa c'e', e il browser non deve parlare con Ollama.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import src.config as cfg
from src.datasets import registry
from src.datasets.schema import Chunk
from src.generation import chat
from src.index.store import (
    chunk_from_payload,
    get_by_chunk_id,
    get_client,
    list_documents,
    payloads_of_document,
)


@dataclass(frozen=True)
class DatasetInfo:
    """Un dataset e lo stato del suo indice.

    `ready` e `n_chunks` sono separati di proposito: una collection che esiste
    ed e' vuota e' uno stato reale — succede fra `ensure_collection` e la fine
    dell'ingestione — e va distinta da una che non c'e'.  Un frontend che le
    confonde mostra un dataset interrogabile che restituisce sempre niente.
    """

    dataset_id: str
    collection: str
    ready: bool
    n_chunks: int


def datasets(client=None) -> list[DatasetInfo]:
    """I dataset del registro, con lo stato del loro indice.

    Nell'ordine di dichiarazione del registro, che e' stabile: un elenco che
    cambia ordine a ogni chiamata fa saltare la selezione a chi lo mostra.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)

    out: list[DatasetInfo] = []
    for dataset_id in registry.dataset_ids():
        collection = dataset_id
        if client.collection_exists(collection):
            info = client.get_collection(collection)
            out.append(DatasetInfo(
                dataset_id=dataset_id,
                collection=collection,
                ready=True,
                n_chunks=info.points_count or 0,
            ))
        else:
            out.append(DatasetInfo(
                dataset_id=dataset_id, collection=collection, ready=False, n_chunks=0
            ))
    return out


@dataclass(frozen=True)
class CollectionInfo:
    """Una collection e la forma del suo indice.

    I tre campi oltre al nome non sono statistica per curiosità: sono ciò che
    dice se l'indice è quello che si crede. `dense_size` diverso da quello del
    modello di embedding significa che l'indice è stato costruito da un altro,
    e da lì ogni risultato è plausibile e privo di senso — **senza errore**.
    `has_sparse` distingue una collection su cui `hybrid` funziona da una su
    cui restituirebbe solo il ramo denso.
    """

    name: str
    points: int
    dense_size: int
    has_sparse: bool


def collections(client=None) -> list[CollectionInfo]:
    """Le collection che esistono davvero su Qdrant, in ordine.

    **Non è la stessa cosa di `datasets()`**, e la differenza è il motivo per
    cui esistono entrambe. Il registro dice quali dataset il progetto conosce;
    questa dice cosa c'è nel server — comprese le varianti `_routed` di R-07 e
    le collection nate da un esperimento, che nessun registro conterrà mai.

    Serve a chi ispeziona invece di interrogare: una collection che il registro
    non nomina è comunque interrogabile passando `collection`, e uno strumento
    di debug che non la vede non può metterla a confronto con l'originale.
    Prima di A-06 la dashboard le elencava chiedendole a Qdrant per conto suo.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    fuori: list[CollectionInfo] = []
    for c in sorted(client.get_collections().collections, key=lambda x: x.name):
        info = client.get_collection(c.name)
        vettori = info.config.params.vectors
        dense = vettori.get("dense") if isinstance(vettori, dict) else vettori
        fuori.append(CollectionInfo(
            name=c.name,
            points=info.points_count or 0,
            dense_size=getattr(dense, "size", 0) or 0,
            has_sparse=bool(info.config.params.sparse_vectors),
        ))
    return fuori


def models(
    base_url: str | None = None,
    *,
    fetch: Callable[[str, int], dict] | None = None,
) -> list[str]:
    """I modelli che l'endpoint di inferenza dichiara di avere (A-07).

    **La lista vuota non e' un errore, ed e' una scelta.** `/datasets` la
    include, e un frontend la chiede all'avvio: se questa funzione sollevasse
    quando l'LLM e' spento, tutta la risposta fallirebbe — compresi i dataset,
    che con l'LLM non c'entrano niente. E' lo stesso difetto per cui `/health`
    non interroga Qdrant.

    Chi la riceve vuota mostra il modello dei default (`/config`), che e'
    l'unico di cui si sappia il nome con certezza, e dice che l'elenco non e'
    disponibile. **Dichiarare l'assenza, non simularla**: aggiungere qui il
    modello configurato per non restituire mai una lista vuota affermerebbe
    che esiste, che e' precisamente cio' che non si e' potuto verificare.
    """
    try:
        return chat.list_models(base_url or cfg.LLM_BASE_URL, fetch=fetch)
    except RuntimeError:
        return []


@dataclass(frozen=True)
class ModelInfo:
    """Un modello del catalogo, con cio' che il motore sa dirne.

    Tutti i campi tranne `name` sono **best-effort**: vuoti o `None` quando il
    motore non li pubblica. Non e' pigrizia, e' la stessa scelta di `models()`
    che restituisce `[]` invece di inventare -- dichiarare l'assenza, non
    simularla. Un frontend che riceve `context_max=None` non offre la scelta
    della finestra, esattamente come non offre il ragionamento quando l'asse non
    c'e'.
    """

    name: str
    #: `gemma4`, `qwen35`. Vuota se il motore non la dice.
    family: str = ""
    #: La finestra piu' grande che questo modello regge. `None` = non si sa.
    context_max: int | None = None
    #: La finestra con cui questa voce e' **configurata**, se qualcuno l'ha
    #: fissata. `None` = decide il motore. Non e' `context_max`: quello dice cosa
    #: l'architettura regge, questo cosa girera' davvero.
    context: int | None = None
    #: Il modello da cui questa voce deriva, se deriva da uno. Lo dice il motore
    #: (`details.parent_model`), quindi raggruppare le taglie sotto il loro
    #: modello **non richiede di interpretare i nomi**: `gemma4-8k` -> `gemma4`
    #: spezzando una stringa sarebbe una convenzione, e le convenzioni si
    #: rompono il giorno in cui qualcuno chiama un modello diversamente.
    parent: str = ""
    #: `Q4_K_M`. Sostituisce la costante `LLM_QUANTIZATION`, che era vera per
    #: coincidenza -- vedi A-08 nel ROADMAP.
    quantization: str = ""
    #: `8.0B`. Testo del motore, non un numero: la forma non e' nostra.
    parameter_size: str = ""


#: L'endpoint nativo che pubblica i dettagli di un modello. **Non e' inferenza**,
#: ed e' la ragione per cui puo' stare qui senza contraddire STACK.md: il
#: vincolo dice che le risposte si generano attraverso un endpoint
#: OpenAI-compatibile, cosi' che il repo giri anche su vLLM o llama.cpp. Questa
#: e' *scoperta*, e degrada a «non lo so» ovunque non esista -- il catalogo resta
#: valido, solo piu' povero, e l'interfaccia nasconde le scelte che non puo'
#: sostenere. Il contratto OpenAI non ha un modo di chiedere queste tre cose:
#: `/v1/models` restituisce solo gli id (misurato, A-08).
_MOSTRA = "/api/show"


def _nativo(base_url: str) -> str:
    """Da `http://host:11434/v1` a `http://host:11434`.

    Si toglie **solo** il `/v1` finale: se `LLM_BASE_URL` punta a un altro
    motore, l'URL che ne esce non risponde a `/api/show` e la scoperta fallisce
    da sola -- che e' il comportamento voluto, non un caso da prevenire.
    """
    u = base_url.rstrip("/")
    return u[: -len("/v1")] if u.endswith("/v1") else u


#: I dettagli gia' chiesti, per nome. **Non e' un'ottimizzazione prematura**:
#: misurato il 2026-08-19, `/api/show` costa ~2 s e va chiesto una volta per
#: modello, quindi con sedici modelli `/datasets` passava da 2 a **35 secondi** --
#: e `/datasets` e' la prima chiamata che il frontend fa all'avvio.
#:
#: La chiave e' il nome, e i nomi vengono da `/v1/models` a ogni richiesta: un
#: modello creato adesso non e' in cache e viene chiesto, uno cancellato sparisce
#: dall'elenco e non viene piu' letto. Resta un caso scoperto, ed e' scritto qui
#: perche' non si scopra da soli: un modello **sostituito tenendo lo stesso
#: nome** continua a leggersi con i dettagli vecchi finche' il processo vive.
_dettagli_noti: dict[str, ModelInfo] = {}


def dimentica_modelli() -> None:
    """Svuota la cache dei dettagli. Serve ai test e a chi ricrea i modelli
    nello stesso processo -- non c'e' un momento, nel servizio, in cui valga la
    pena chiamarla da sola."""
    _dettagli_noti.clear()


def model_catalog(
    base_url: str | None = None,
    *,
    fetch: Callable[[str, int], dict] | None = None,
    dettagli: Callable[[str, str, int], dict] | None = None,
) -> list[ModelInfo]:
    """I modelli, con famiglia, finestra massima e quantizzazione di ciascuno.

    I **nomi** vengono da `/v1/models` come sempre (`models()`); i **dettagli**
    dall'endpoint nativo, uno per modello, e ogni fallimento e' isolato: un
    modello che non risponde entra nel catalogo col solo nome invece di far
    cadere gli altri.

    **La finestra si legge per pattern, non per nome.** Ollama la pubblica sotto
    una chiave che contiene la famiglia -- `gemma4.context_length`,
    `qwen35.context_length` -- quindi cercarla per nome funzionerebbe su un
    modello solo. Misurato il 2026-08-19 sui quattro installati: `gemma4:latest`
    131.072, `gemma4:12b` e `qwen3.5` 262.144. Il massimo **non e' uno solo**, ed
    e' la ragione per cui il catalogo esiste invece di una costante.
    """
    base = base_url or cfg.LLM_BASE_URL
    nomi = models(base, fetch=fetch)
    if not nomi:
        return []

    chiedi = dettagli or _mostra
    nativo = _nativo(base)

    def uno(nome: str) -> ModelInfo:
        noto = _dettagli_noti.get(nome)
        if noto is not None:
            return noto
        try:
            d = chiedi(nativo, nome, 10)
        except Exception:
            # Un motore che non e' Ollama, o un modello sparito fra l'elenco e
            # la domanda: si tiene il nome, che e' l'unica cosa certa. **Non si
            # ricorda**: un motore che non risponde adesso puo' rispondere fra
            # un minuto, e memorizzare il fallimento lo renderebbe permanente.
            return ModelInfo(name=nome)
        info = _come_info(nome, d)
        _dettagli_noti[nome] = info
        return info

    # **In parallelo, e non e' una micro-ottimizzazione.** Sono richieste HTTP
    # indipendenti da ~2 s l'una: in fila, sedici modelli costavano 35 s alla
    # prima chiamata dopo un riavvio -- cioe' il primo caricamento della pagina.
    # La cache da sola nasconde quel costo alla seconda volta invece di toglierlo.
    # L'ordine resta quello dei nomi, che e' alfabetico: `map` lo conserva, e un
    # menu che si riordina da solo fa saltare la selezione.
    with ThreadPoolExecutor(max_workers=min(8, len(nomi))) as pool:
        return list(pool.map(uno, nomi))


def _mostra(base_nativo: str, nome: str, timeout: int) -> dict:
    """La POST nativa. Sta **qui** e non in `chat.py`: quel modulo e' il contratto
    OpenAI, e mettergli dentro una chiamata nativa lo renderebbe il posto dove la
    regola si aggira invece di quello dove e' scritta."""
    req = urllib.request.Request(
        f"{base_nativo}{_MOSTRA}",
        data=json.dumps({"model": nome}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        letto = json.loads(resp.read())
    return letto if isinstance(letto, dict) else {}


def _come_info(nome: str, d: object) -> ModelInfo:
    """Il payload di `/api/show` ridotto a cio' che serve, senza fidarsi."""
    if not isinstance(d, dict):
        return ModelInfo(name=nome)

    info = d.get("model_info")
    contesto: int | None = None
    if isinstance(info, dict):
        for chiave, valore in info.items():
            if str(chiave).endswith(".context_length") and isinstance(valore, int):
                contesto = valore
                break

    det = d.get("details")
    det = det if isinstance(det, dict) else {}
    return ModelInfo(
        name=nome,
        family=str(det.get("family") or ""),
        context_max=contesto,
        context=_num_ctx(d.get("parameters")),
        parent=str(det.get("parent_model") or ""),
        quantization=str(det.get("quantization_level") or ""),
        parameter_size=str(det.get("parameter_size") or ""),
    )


def _num_ctx(parametri: object) -> int | None:
    """`num_ctx` dentro il blocco di testo che `/api/show` chiama `parameters`.

    E' testo e non JSON -- `"num_ctx                        8192"` -- quindi si
    legge riga per riga invece che con una chiave. Assente significa **non
    fissato**, cioe' decide il motore: e' un'informazione, non un dato mancante,
    ed e' la differenza fra «questo modello gira a 8192» e «questo modello gira
    a quello che il servizio ha deciso».
    """
    if not isinstance(parametri, str):
        return None
    for riga in parametri.splitlines():
        pezzi = riga.split()
        if len(pezzi) == 2 and pezzi[0] == "num_ctx":
            try:
                return int(pezzi[1])
            except ValueError:
                return None
    return None


@dataclass(frozen=True)
class DocumentInfo:
    """Un documento della collection, e quanti chunk ne sono usciti.

    **Il genere non e' qui, ed e' una decisione.** `doc_genre` e `pipeline`
    stanno sul chunk perche' e' li' che sono veri: metterli sul documento
    sarebbe un'aggregazione che il dato non garantisce — una collection
    `_routed` puo' mescolare pipeline dentro lo stesso documento, ed e'
    esattamente il caso che l'esploratore deve poter mostrare. Chi apre il
    documento li vede sui chunk, dove non c'e' niente da riassumere.
    """

    doc_id: str
    n_chunks: int


def documents(
    dataset_id: str, collection: str | None = None, client=None
) -> list[DocumentInfo]:
    """I documenti di una collection, in ordine alfabetico (A-07).

    Il buco che disegnare la Fase 8 ha rivelato: c'era `/chunk/{id}` (uno, per
    id) e `/retrieve` (per query), e nessun modo di **navigare**. Senza,
    l'esploratore del corpus puo' solo cercare — mai mostrare come un documento
    e' stato spezzato, che e' cio' che rende visibile il routing (U-05).
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    return [
        DocumentInfo(doc_id=doc_id, n_chunks=n)
        for doc_id, n in list_documents(client, collection or dataset_id)
    ]


def document_chunks(
    doc_id: str, dataset_id: str, collection: str | None = None, client=None
) -> list[Chunk]:
    """I chunk di un documento, nell'ordine in cui sono stati prodotti.

    Lista vuota quando il documento non c'e': come `chunk()`, e' una risposta
    legittima a una domanda legittima — un `doc_id` copiato da una citazione
    vecchia — e chi chiama deve poterla distinguere da un guasto.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    payloads = payloads_of_document(client, collection or dataset_id, doc_id)
    return [chunk_from_payload(p) for p in payloads]


def dataset_of(chunk_id: str) -> str:
    """Il dataset a cui un `chunk_id` appartiene.

    Lo schema del §3 impone `{dataset_id}:{doc_id}:{seq}`, quindi il dataset e'
    gia' dentro l'identificativo.  E' per questo che `/chunk/{chunk_id}` non ha
    bisogno di un secondo parametro: chiederlo permetterebbe di passarne uno
    incoerente con l'id, cioe' di sbagliare.
    """
    return chunk_id.split(":", 1)[0]


def chunk(chunk_id: str, collection: str | None = None, client=None) -> Chunk | None:
    """Il chunk citato, o `None` se quell'id non e' nell'indice.

    `None` e non un'eccezione: un id che non c'e' e' una risposta legittima a
    una domanda legittima — un link vecchio dopo una re-ingestione — e chi
    chiama deve poterlo distinguere da un guasto.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    payload = get_by_chunk_id(client, collection or dataset_of(chunk_id), chunk_id)
    return chunk_from_payload(payload) if payload else None
