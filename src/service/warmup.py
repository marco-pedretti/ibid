"""D-21: i modelli ONNX si caricano all'avvio, in un thread di sottofondo.

Prima di questo, il primo costo lo pagava **chi guardava**: l'embedder si
caricava alla prima query e il verificatore NLI alla prima citazione da
verificare (`entailment.py`, `_load` dietro `lru_cache`). In mezzo a una
dimostrazione sono ~2,5 GB di pesi letti dal disco, e su una cache vuota anche
scaricati: `hf_hub_download` contatta l'Hub **anche a cache piena**, per
controllare la revisione. Il warning *«unauthenticated requests to the HF Hub»*
e' quella richiesta, ed e' la ragione per cui dietro una rete chiusa il guasto
arriva a meta' della prima risposta invece che all'avvio.

**Il riscaldamento si sovrappone al frontend che si carica**, che sono qualche
secondo, e a chi legge lo stato vuoto, che sono di piu'. Quando non fa in tempo,
la prima query paga quel che pagava prima: non e' mai peggio.

## I tre vincoli che un'implementazione sbaglierebbe per primi

**Non blocca l'avvio.** `/health` deve continuare a voler dire «vivo, e
nient'altro»: `depends_on: service_healthy` di U-09 lo usa per l'ordine di
avvio, e scaldare prima di rispondere farebbe aspettare l'orchestratore per
2,5 GB su una cache fredda.

**Non fa cadere niente se fallisce.** Un modello che non si carica qui e' un
modello che si ricarichera' (o fallira') alla prima richiesta, esattamente come
prima: il thread scrive un avviso nel log e muore. Un riscaldamento che
uccidesse il servizio avrebbe trasformato un'ottimizzazione in un guasto nuovo.

**Scalda cio' che serve davvero**, e lo chiede alla configurazione invece di
tenerne una lista sua: con i default di oggi (`dense`, `rerank=False`,
`verify=True`) sono l'embedder e il verificatore. Il reranker non si carica,
perche' con il flag spento nessuna richiesta lo tocca e sarebbe ~1 GB di VRAM
occupata per niente. Chi accende il flag paga il caricamento allora, ed e' la
stessa attesa di prima.

*Limite dichiarato:* questo rende **raro** il caso brutto, non impossibile.
Garantirlo vorrebbe dire un endpoint di *readiness* separato da `/health`, cioe'
toccare il contratto per un caso che dura trenta secondi una volta per avvio.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable

import src.config as cfg

log = logging.getLogger("ibid.warmup")

#: Spegnerlo e' una riga d'ambiente, e serve a un caso vero: sviluppare
#: sull'interfaccia mentre la GPU e' occupata da una valutazione. Le sessioni
#: ONNX restano residenti per tutta la vita del processo, e su una scheda da
#: 12 GB caricarle **all'avvio** invece che alla prima domanda anticipa la
#: contesa di memoria misurata in `docs/video.md` (8 s contro 26).
ATTIVO: bool = os.getenv("WARMUP", "1").lower() not in ("0", "false", "no")


def da_scaldare(config: cfg.RequestConfig | None = None) -> list[tuple[str, Callable[[], object]]]:
    """I modelli che la **configurazione di default** fara' usare, in ordine d'uso.

    L'ordine non e' estetico: l'embedder serve alla prima ricerca, il
    verificatore qualche secondo dopo, alla prima citazione. Scaldarli al
    contrario significherebbe avere pronto il secondo mentre si aspetta il
    primo.
    """
    c = config or cfg.RequestConfig.from_defaults()
    voci: list[tuple[str, Callable[[], object]]] = []

    from src.index import embed

    if c.retrieval_mode in ("dense", "hybrid"):
        voci.append((cfg.EMBEDDING_MODEL, lambda: embed._dense_model(cfg.EMBEDDING_MODEL)))
    if c.retrieval_mode in ("sparse", "hybrid"):
        voci.append(
            (cfg.SPARSE_EMBEDDING_MODEL, lambda: embed._sparse_model(cfg.SPARSE_EMBEDDING_MODEL))
        )
    if c.verify:
        from src.generation import entailment

        voci.append((cfg.ENTAILMENT_MODEL, lambda: entailment._load(cfg.ENTAILMENT_MODEL)))
    if c.rerank:
        from src.retrieval import reranker

        voci.append((c.reranker_model, lambda: reranker._get_reranker(c.reranker_model)))
    return voci


def scalda(voci: list[tuple[str, Callable[[], object]]] | None = None) -> list[tuple[str, float]]:
    """Carica, misurando. Bloccante: e' `in_sottofondo` a non esserlo.

    Restituisce `(nome, secondi)` per ciascuno, e **un modello che fallisce non
    ferma gli altri**: sono indipendenti, e averne pronto uno su due e' meglio
    che nessuno.
    """
    fatti: list[tuple[str, float]] = []
    for nome, carica in voci if voci is not None else da_scaldare():
        t0 = time.perf_counter()
        try:
            carica()
        except Exception as e:  # noqa: BLE001 - vedi la nota in testa: non deve cadere niente
            log.warning(
                "riscaldamento fallito per %s: %s (si ricarichera' alla prima richiesta)", nome, e
            )
            continue
        durata = time.perf_counter() - t0
        fatti.append((nome, durata))
        log.info("scaldato %s in %.1f s", nome, durata)
    return fatti


def _rendi_visibile() -> None:
    """Fa uscire le righe di `ibid.*` dove escono quelle di uvicorn.

    Senza questo il riscaldamento e' **muto sotto uvicorn**, che e' l'unico
    posto in cui gira: uvicorn configura i propri logger e lascia la radice
    senza gestori, quindi un `INFO` di un logger nostro finisce nel nulla e un
    `WARNING` esce spoglio, senza ora ne' livello. Verificato guardando l'avvio:
    si vedevano gli avvisi di fastembed e dell'Hub, non le nostre due righe.

    Prende i gestori invece di aggiungerne uno suo, cosi' il formato resta
    quello del resto dell'avvio. Se uvicorn non c'e' (un test, uno script) non
    fa niente e il logging si comporta come `logging` di serie.
    """
    nostro = logging.getLogger("ibid")
    if nostro.handlers:
        return
    # **Risalendo la catena, non guardando `uvicorn.error` e basta**: quel
    # logger non ha gestori suoi, li eredita da `uvicorn`. Cercarli solo li'
    # e' precisamente l'errore che ha reso muta la prima versione di questa
    # funzione, e il modo in cui l'ho scoperto e' guardare l'avvio.
    corrente: logging.Logger | None = logging.getLogger("uvicorn.error")
    livello = corrente.level if corrente else logging.INFO
    while corrente is not None:
        if corrente.handlers:
            nostro.handlers = corrente.handlers
            nostro.setLevel(livello or corrente.level or logging.INFO)
            return
        corrente = corrente.parent if corrente.propagate else None


def in_sottofondo(
    voci: list[tuple[str, Callable[[], object]]] | None = None,
) -> threading.Thread | None:
    """Avvia il riscaldamento e torna subito. `None` se e' spento.

    `daemon=True` perche' un riscaldamento a meta' non deve tenere in piedi il
    processo quando l'utente ferma il servizio: interromperlo non lascia niente
    di rotto, i pesi arrivano al primo uso.
    """
    _rendi_visibile()
    if not ATTIVO:
        log.info("riscaldamento disattivato (WARMUP=0): i modelli si caricano al primo uso")
        return None
    t = threading.Thread(target=scalda, args=(voci,), name="riscaldamento", daemon=True)
    t.start()
    return t
