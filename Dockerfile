# Il backend come immagine (A-05).
#
# Due stadi: il primo costruisce l'ambiente, il secondo porta solo il risultato.
# Serve a non spedire `uv`, la cache dei wheel e gli header di compilazione in
# un'immagine che deve solo eseguire.
#
# **Non installa il progetto**, lo copia. `pyproject.toml` e' configurato per
# hatchling e `pip install -e .` funzionerebbe, ma oggi gli script di `scripts/`
# mettono la radice del repo su `sys.path` a mano (vedi la nota su E402 in
# `pyproject.toml`): finche' quel modo di lavorare regge fuori, cambiarlo qui
# dentro creerebbe due layout diversi per lo stesso codice.

FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./

# Le sole dipendenze, non il progetto. `-r pyproject.toml` legge
# `[project.dependencies]`; l'acceleratore ONNX resta fuori di proposito -- e'
# un extra che dipende dalla piattaforma (Q-05), e un'immagine che lo cablasse
# girerebbe su una macchina sola.
#
# **Senza lockfile, e va detto**: `uv.lock` non esiste in questo repo, quindi due
# build a distanza di mesi possono risolvere versioni diverse. Per un servizio
# che si vuole riproducibile il lock e' il passo giusto, ed e' un task suo.
RUN uv venv /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r pyproject.toml

FROM python:3.12-slim

# `curl` per l'healthcheck: piu' leggibile di un one-liner Python, e in un
# container di debug e' la prima cosa che si cerca.
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY src ./src

# I pesi dei modelli vivono qui, e **vanno montati** (vedi `compose.yml`).
# Dentro l'immagine sarebbero ~2,5 GB di layer; ricreati a ogni avvio sarebbero
# ~2,5 GB di download prima della prima risposta. Un volume e' l'unica delle tre
# strade che non paga due volte.
ENV FASTEMBED_CACHE_PATH=/cache/fastembed \
    HF_HOME=/cache/huggingface
RUN mkdir -p /cache/fastembed /cache/huggingface

# Non root: il processo non installa niente e non scrive nel codice, quindi non
# ha ragione di poterlo fare. `/cache` resta scrivibile perche' i pesi arrivano
# al primo uso.
RUN useradd --create-home --uid 10001 ibid \
 && chown -R ibid:ibid /cache
USER ibid

EXPOSE 8000

# Nessun indirizzo cablato: `QDRANT_URL` e `LLM_BASE_URL` arrivano dall'ambiente
# (`src/config.py`), ed e' cio' che permette a questo container di parlare con
# servizi su un'altra macchina senza toccare il sorgente.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
