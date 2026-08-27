"""All retrieval and inference parameters live here.

An ablation is a loop over config, not a code change — see ROADMAP §3.4.

**Non tutti i parametri sono la stessa cosa, e A-02 e' il task che lo ha reso
esplicito.** Le costanti di questo modulo si dividono in quattro categorie, e la
differenza decide chi puo' cambiarle:

1. **Per richiesta** — due richieste concorrenti possono legittimamente volerle
   diverse: profondita', modalita' di retrieval, reranker, modello, temperatura,
   budget di token. Vivono in `RequestConfig`, non qui, e **non vanno lette da
   questo modulo lungo il percorso di servizio**: un modulo globale condiviso da
   due richieste e' esattamente il modo in cui la configurazione dell'una
   diventa quella dell'altra.

2. **Legate all'indice** — `EMBEDDING_MODEL`, `SPARSE_EMBEDDING_MODEL`. Non
   possono variare per richiesta perche' l'indice e' stato costruito con loro:
   interrogarlo con un altro embedder restituisce spazzatura **senza errore**.
   Metterle nella richiesta renderebbe esprimibile una richiesta sbagliata.

3. **Di deployment** — `QDRANT_URL`, `LLM_BASE_URL`, `FASTEMBED_CACHE`,
   `ONNX_PROVIDERS`, `DATA_DIR`. Una richiesta HTTP non puo' spostare la
   macchina su cui gira il servizio.

4. **Calibrate sui dati** — `ABSTENTION_THRESHOLDS`, `ENTAILMENT_THRESHOLD`,
   `NUMERIC_ROW_MATCH_RATIO`, `ABSTENTION_BUDGET`. Sono **derivate da misure**,
   non preferenze. Lasciarle scegliere a chi chiama permetterebbe di tarare la
   soglia sulla stessa risposta che quella soglia deve giudicare — la trappola
   che i commenti qui sotto passano il tempo a evitare.

Le ultime tre restano costanti di modulo, ed e' la risposta giusta: non sono
rimaste indietro, non appartengono alla richiesta.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _int_or_none(raw: str | None) -> int | None:
    """Un intero da variabile d'ambiente, dove "non impostata" e' un valore.

    Serve dove il default non e' un numero ma "lascia decidere alla libreria":
    `HNSW_EF` non impostato significa il default di Qdrant, che e' lo stato in
    cui e' stato misurato tutto il progetto fino a R-11.
    """
    return int(raw) if raw not in (None, "") else None

# ---------------------------------------------------------------------------
# LLM (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:latest")
LLM_QUANTIZATION: str = os.getenv("LLM_QUANTIZATION", "Q4_K_M")
CONTEXT_WINDOW: int = 32768
TEMPERATURE: float = 0.0
# Overridable because C-07 needs both of its arms at 2048: with reasoning on,
# 1024 is spent thinking before the answer starts and half the generations come
# back truncated (see scripts/probe_reasoning.py). Raising it for the reasoning
# arm alone would change two things at once, so the control moves with it — and
# the control does not notice, since it never reaches the cap at either value.
MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "1024"))

# Gemma 4 is a thinking model. "none" suppresses the reasoning tokens through
# the OpenAI-compatible contract — see src/generation/chat.py for what does and
# does not work on Ollama's /v1. Set to "low"/"medium"/"high" for C-07, which
# measures the effect of extended reasoning. `EvalRun.reasoning_enabled` is
# derived from this value, so it stops being a hardcoded claim.
REASONING_EFFORT: str = os.getenv("REASONING_EFFORT", "none")

# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
# Dense: multilingual-e5-large via fastembed + onnxruntime-directml (AMD RX 6750 XT).
# Windows ML not used: MIGraphX EP requires exact driver and doesn't support GenAI models;
# DirectML (maintenance mode) remains the correct backend for this GPU.
# Target: BAAI/bge-m3 when fastembed PR #602 merges — re-ingest required.
EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
EMBEDDING_BATCH: int = 32  # TODO: provare 64 — I-07 ha girato 122 min con 32; se DirectML scala bene può dimezzare

# Sparse: BM25 via fastembed SparseTextEmbedding (CPU, no GPU needed — statistical model).
# Multilingual (18 language stopword lists), Apache 2.0. Used in R-01 hybrid RRF.
SPARSE_EMBEDDING_MODEL: str = "Qdrant/bm25"

# Dove fastembed tiene i pesi. Il suo default e' `%TEMP%/fastembed_cache`, cioe'
# una cartella che il sistema operativo ha il diritto di svuotare: il 2026-08-12
# Windows ha cancellato la directory `blobs` **durante** I-10, lasciando i
# symlink dello snapshot a puntare nel vuoto. L'indicizzazione era finita, la
# valutazione e' morta su `NO_SUCHFILE` dopo 80 minuti di GPU.
#
# `~/.cache/fastembed` sta accanto a `~/.cache/huggingface`, che nella stessa
# occasione e' sopravvissuta: e' una cache utente, non temporanea.
FASTEMBED_CACHE: str = os.getenv(
    "FASTEMBED_CACHE_PATH", str(Path.home() / ".cache" / "fastembed")
)

# Quale acceleratore ONNX usare, se si vuole imporlo (Q-05). Vuoto = decide
# `src/providers.py` guardando cosa la piattaforma offre, che e' il caso normale.
# Sta qui accanto a FASTEMBED_CACHE perche' e' la stessa categoria: una manopola
# di piattaforma, non un parametro di retrieval (§3.4).
#
#   ONNX_PROVIDERS=CPUExecutionProvider     confronta i tempi senza GPU
#   ONNX_PROVIDERS=ROCMExecutionProvider,CPUExecutionProvider
ONNX_PROVIDERS: str = os.getenv("ONNX_PROVIDERS", "")

# Se l'API deve servire anche il frontend, dalla stessa origine (U-08).
# **Acceso solo dentro l'immagine**, che e' l'unico posto dove `ui/dist` e'
# costruito per questa origine: il `Dockerfile` compila con `VITE_API_BASE=""`,
# cosi' il bundle chiama `/datasets` invece di `/api/datasets`.
#
# Spento di default, e non e' timidezza. Una `ui/dist` in un clone c'e' appena
# qualcuno lancia `make ui-check`, ed e' costruita col default `/api`: servirla
# da qui darebbe una pagina che si carica e non parla col backend, cioe' il
# guasto peggiore da riconoscere. Fuori dal container il frontend sta dietro
# Vite, che ha il suo proxy.
SERVE_UI: bool = os.getenv("SERVE_UI", "").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K: int = 5

# Quanto a fondo HNSW cammina nel grafo prima di rispondere (R-11).
#
# La ricerca vettoriale di Qdrant e' **approssimata**: percorre un grafo di
# prossimita' invece di confrontare la query con tutti i punti. Funziona finche'
# c'e' una pendenza da seguire; se i punti sono quasi equidistanti dalla query, la
# camminata si ferma in un vicinato plausibile e non sa che poco piu' in la' ce
# n'e' uno migliore.
#
# R-10 ha misurato quanto costa su questo corpus. Su `ledger_routed` -- 228.331
# punti in una banda di similarita' larga 0,0085 -- la ricerca esatta recupera
# **857 query su 10.000** che quella approssimata perdeva, contro 33 perse:
# doc-recall@5 da 0,7647 a 0,8471. Su `ledger` (47.110 punti) lo stesso confronto
# vale +0,37 punti. Non e' una proprieta' del dataset: e' della densita'.
#
# `None` lascia il default di Qdrant, cioe' lo stato in cui e' stato misurato
# tutto quanto precede R-11. Un valore alto costa tempo di query e nient'altro:
# non tocca l'indice, non richiede re-ingestione, si cambia a ogni chiamata.
HNSW_EF: int | None = _int_or_none(os.getenv("HNSW_EF"))

# Salta il grafo e confronta con tutti i punti (R-11). Esatto per definizione.
# Su 228k punti costa 2,5 ms/query contro 1,4 -- quanto `hnsw_ef=512`, ed e' piu'
# preciso. Su collection molto piu' grandi il conto cambia, ed e' il motivo per
# cui questo resta un parametro e non una scelta cablata.
SEARCH_EXACT: bool = os.getenv("SEARCH_EXACT", "").lower() in ("1", "true", "yes")

# Hybrid RRF (R-01): smoothing constant and candidate pool per index.
# Fetch HYBRID_FETCH_K from each of dense and sparse before fusing.
RRF_K: int = 60
HYBRID_FETCH_K: int = 20

# Cross-encoder reranker (R-02): model and candidate pool fed into the reranker.
# RERANK_FETCH_K candidates are fetched from initial retrieval; the reranker
# then scores all of them and returns the top_k best.
RERANKER_MODEL: str = "BAAI/bge-reranker-base"
RERANK_FETCH_K: int = 20

# ---------------------------------------------------------------------------
# Abstention gate (C-04)
# ---------------------------------------------------------------------------
# What a human chooses is the budget: how many *answerable* questions the system
# may refuse. The thresholds below are then derived from data by
# scripts/calibrate_abstention.py — that derivation is what makes the gate
# "decided by code" (ROADMAP §15) rather than a number somebody liked.
#
# 1% and not more, because the gate cannot improve the metric it is measured on:
# on E-02 the model already abstains 35/35 on both datasets. The gate exists as a
# guarantee for models that will not (C-06 runs E2B and E4B), and a guarantee
# should cost as little as possible.
ABSTENTION_BUDGET: float = 0.01

# Derived, per Qdrant collection. Only valid for the retrieval mode below and
# for the embedding model that produced the index: dense cosine scores sit
# around 0.8, RRF fusion scores around 0.02, and one threshold applied to the
# other abstains on everything or on nothing. Re-run the calibration after any
# re-ingestion or embedding change.
ABSTENTION_CALIBRATED_MODE: str = "dense"
ABSTENTION_THRESHOLDS: dict[str, float] = {
    "open_ragbench": 0.7924,
    "ledger": 0.8289,
}

# ---------------------------------------------------------------------------
# Entailment verification (C-03)
# ---------------------------------------------------------------------------
# The verifier behind citation_precision. Replaced mDeBERTa-v3 NLI after the
# measurement in scripts/probe_entailment.py — see STACK.md. MIT, multilingual,
# ships its own ONNX export, binary entailment/not_entailment head.
ENTAILMENT_MODEL: str = "MoritzLaurer/bge-m3-zeroshot-v2.0"

# The model's window is 8194 tokens. Truncation is set just under it.
ENTAILMENT_MAX_LEN: int = 8192

# Premise cap. Below it a chunk is one premise and there is no max-over-windows
# artefact; 96% of chunks are under it. Above it, windowing is cheaper than one
# quadratic pass: 123 ms at 758 tokens, 762 ms at 2951, 19.7 s at 7693.
ENTAILMENT_PREMISE_CAP: int = 4096

# Decision boundary for "supported". Deliberately the model's own natural
# boundary for a binary head, NOT tuned on our data: a threshold fitted on the
# same answers the metric is reported over inflates that metric by construction.
# Calibrating it needs a held-out split and is its own task. At 0.5 the verifier
# is pessimistic — it missed a third of verbatim-copied claims in the floor test
# — so citation_precision reported with it is a lower bound, which is the safe
# direction for a number meant to show the system can be trusted.
ENTAILMENT_THRESHOLD: float = 0.5

# ---------------------------------------------------------------------------
# Verifica numerica su tabelle (C-09)
# ---------------------------------------------------------------------------
# Quota delle parole di contenuto dell'etichetta di riga che devono comparire
# nel claim perche' la riga sia considerata combaciante. 0,5 e' un compromesso:
# "Cost of goods sold" da' {cost, goods, sold} dopo le stopword, e la meta'
# lascia passare le riformulazioni parziali senza accettare qualunque cosa.
# Come per ENTAILMENT_THRESHOLD, **non e' tarata sui dati su cui la metrica
# viene riportata**: una soglia adattata al proprio campione gonfia la metrica
# per costruzione.
NUMERIC_ROW_MATCH_RATIO: float = 0.5

# Le premesse LEDGER sono OCR Mathpix: prosa con markup `<table>` dentro, fino al
# 77% dei token della premessa. Con questo attivo il markup diventa righe
# `cella | cella` prima della verifica. Parametro e non costante perche' il
# confronto fra le due varianti deve girare sulle stesse generazioni salvate
# (§3.4: un'ablation e' un ciclo sulla config). Default spento finche' C-08 non
# ha misurato: cambiarlo cambia `citation_precision` gia' riportata.
ENTAILMENT_RENDER_TABLES: bool = os.getenv("ENTAILMENT_RENDER_TABLES", "") == "1"

# Query rewriting (R-03): LLM rewrites the query before embedding.
# Uses LLM_BASE_URL / LLM_MODEL; override here for a dedicated smaller model.
QUERY_REWRITE_MODEL: str = os.getenv("QUERY_REWRITE_MODEL", "")  # "" = use LLM_MODEL

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR: Path = ROOT / "data"


# ---------------------------------------------------------------------------
# La configurazione di una richiesta (A-02)
# ---------------------------------------------------------------------------
#: Le modalita' di recupero, in un posto solo. Erano ripetute in ogni
#: `choices=[...]` degli script — la stessa forma di duplicazione che Q-06 ha
#: tolto per i dataset.
RETRIEVAL_MODES: tuple[str, ...] = ("dense", "sparse", "hybrid")

#: I due prompt del confronto E-04/E-05, che U-04 espone come toggle.
BASELINE_PROMPTS: tuple[str, ...] = ("permissive", "strict")

#: I livelli di ragionamento che l'endpoint accetta davvero. Non e' una scelta
#: nostra: Ollama ne verifica cinque in `openai/openai.go` e risponde 400 a
#: qualunque altro (la citazione del sorgente sta in `src/generation/chat.py`).
#: Serve ad A-07 perche' la UI possa esporre il toggle senza portarsi dietro
#: una copia dell'elenco — e perche' un valore inventato diventi un 422 con il
#: nome del campo invece di un 400 opaco dal modello.
#:
#: `""` non e' qui pur essendo trattato come «spento» da `reasoning_enabled`:
#: e' uno stato raggiungibile solo da `REASONING_EFFORT=""` nell'ambiente, e
#: mandarlo sul filo produrrebbe proprio il 400 che questo elenco evita.
REASONING_EFFORTS: tuple[str, ...] = ("none", "low", "medium", "high", "max")


@dataclass(frozen=True)
class RequestConfig:
    """Come rispondere a **questa** richiesta. Uno per richiesta, immutabile.

    Fino ad A-02 questi valori si leggevano dal modulo. Comodo per uno script,
    che ne ha una configurazione sola per tutta la sua vita — e **impossibile per
    un servizio**: due richieste concorrenti con `top_k` diverso condividerebbero
    la stessa costante, e la seconda leggerebbe la scelta della prima. Il difetto
    non e' teorico ed e' del tipo peggiore da diagnosticare, perche' compare solo
    sotto carico e non si riproduce da soli.

    **`frozen=True` non e' decorazione.** E' la garanzia: una configurazione che
    nessuno puo' modificare non puo' essere modificata *da un'altra richiesta*.
    Senza, basterebbe un `config.top_k = 3` in un ramo del codice per riportare
    esattamente il problema che questa classe esiste per togliere.

    **Nessun campo ha un default.** Si costruisce solo con `from_defaults()`, che
    e' l'unico posto in tutto il repo dove queste costanti globali vengono
    lette. Un default qui dentro sarebbe una seconda sorgente di verita', e la
    prima cosa che farebbe e' divergere.

    Cosa **non** c'e', e non e' una dimenticanza: modello di embedding (legato
    all'indice), URL di Qdrant e dell'LLM (deployment), soglie calibrate. Le
    ragioni stanno in cima al modulo.
    """

    # --- recupero ---
    top_k: int
    retrieval_mode: str
    rerank: bool
    reranker_model: str
    rerank_fetch_k: int
    hybrid_fetch_k: int
    rrf_k: int
    #: R-11: come cercare nel grafo HNSW, o se saltarlo. Per richiesta perche'
    #: non tocca l'indice — si cambia a ogni chiamata e costa solo tempo.
    search_exact: bool
    hnsw_ef: int | None
    query_rewrite: bool
    #: "" significa "usa `model`", non "nessuno".
    query_rewrite_model: str
    #: "" nessun filtro, "auto" dedotto dalla query, altrimenti il tipo (R-04).
    filter_content_type: str

    # --- generazione ---
    model: str
    temperature: float
    max_new_tokens: int
    reasoning_effort: str

    # --- il braccio (U-03, U-04) ---
    #: `False` risponde **senza contesto**: niente recupero, niente citazioni,
    #: niente gate. E' l'altra meta' del confronto affiancato che U-03 chiede, e
    #: la ragione per cui e' un parametro e non due percorsi di codice: la
    #: risposta nuda e quella citata devono venire dalla stessa query, nella
    #: stessa sessione, o non sono confrontabili.
    rag: bool
    #: Quale prompt usare quando `rag` e' spento: "permissive" (E-04) o
    #: "strict" (E-05). Ignorato quando `rag` e' acceso — li' il prompt e' quello
    #: che chiede le citazioni, e non e' una scelta dell'utente. E' il toggle di
    #: U-04, e la differenza che mostra e' misurata: 45%→17% di invenzione.
    baseline_prompt: str

    # --- verifica ---
    verify: bool

    @classmethod
    def from_defaults(cls, **overrides) -> "RequestConfig":
        """L'**unico** posto che legge le costanti di questo modulo.

        Un `overrides` con una chiave sconosciuta solleva `TypeError` invece di
        essere ignorato in silenzio: un parametro scritto male che non ha
        effetto e' peggio di uno rifiutato, perche' la richiesta sembra
        rispettata.
        """
        base = dict(
            top_k=TOP_K,
            retrieval_mode="dense",
            rerank=False,
            reranker_model=RERANKER_MODEL,
            rerank_fetch_k=RERANK_FETCH_K,
            hybrid_fetch_k=HYBRID_FETCH_K,
            rrf_k=RRF_K,
            search_exact=SEARCH_EXACT,
            hnsw_ef=HNSW_EF,
            query_rewrite=False,
            query_rewrite_model=QUERY_REWRITE_MODEL,
            filter_content_type="",
            model=LLM_MODEL,
            temperature=TEMPERATURE,
            max_new_tokens=MAX_NEW_TOKENS,
            reasoning_effort=REASONING_EFFORT,
            rag=True,
            baseline_prompt="strict",
            verify=True,
        )
        return cls(**{**base, **overrides})

    def __post_init__(self) -> None:
        """I valori che non esistono si rifiutano alla costruzione.

        Un `baseline_prompt="severo"` scritto per sbaglio ripiegherebbe sul
        permissivo, e il confronto di U-04 mostrerebbe due volte lo stesso
        braccio dicendo di mostrarne due diversi. Meglio un errore subito.
        """
        if self.baseline_prompt not in BASELINE_PROMPTS:
            raise ValueError(
                f"baseline_prompt sconosciuto: {self.baseline_prompt!r} "
                f"(ammessi: {', '.join(BASELINE_PROMPTS)})"
            )
        if self.retrieval_mode not in RETRIEVAL_MODES:
            raise ValueError(
                f"retrieval_mode sconosciuta: {self.retrieval_mode!r} "
                f"(ammesse: {', '.join(RETRIEVAL_MODES)})"
            )

    @property
    def reasoning_enabled(self) -> bool:
        """Il modello sta ragionando? Dedotto, mai asserito.

        Scritto a mano come `False`, questo valore e' stato falso in ogni run
        per un periodo: il modello ragionava attraverso l'intero budget di token
        mentre il risultato diceva di no (C-01).
        """
        return self.reasoning_effort not in ("none", "", None)

    @property
    def rewrite_model(self) -> str:
        """Il modello che riscrive le query: il suo, o quello di generazione."""
        return self.query_rewrite_model or self.model
