# Il backend come immagine (A-05).
#
# Tre stadi: Node costruisce il frontend (U-08), il secondo costruisce l'ambiente
# Python, il terzo porta solo i due risultati.
# Serve a non spedire `uv`, la cache dei wheel, gli header di compilazione e i
# ~200 MB di `node_modules` in un'immagine che deve solo eseguire.
#
# **Non installa il progetto**, lo copia. `pyproject.toml` e' configurato per
# hatchling e `pip install -e .` funzionerebbe, ma oggi gli script di `scripts/`
# mettono la radice del repo su `sys.path` a mano (vedi la nota su E402 in
# `pyproject.toml`): finche' quel modo di lavorare regge fuori, cambiarlo qui
# dentro creerebbe due layout diversi per lo stesso codice.

# --- il frontend (U-08) ------------------------------------------------------
#
# **Nella consegna il proxy di sviluppo non esiste.** Vite ne ha uno che manda
# `/api/...` al backend, e serve a chi sviluppa con due processi su due porte;
# qui l'API serve `ui/dist` dalla **stessa origine**, che e' un container in meno
# e soprattutto la ragione per cui il backend non ha CORS smette di essere
# un'aspirazione e diventa vera.
#
# `VITE_API_BASE=""` e' cio' che lo rende possibile: il client ha `?? "/api"`
# come default, e con la stringa vuota chiama `/datasets` invece di
# `/api/datasets`. E' una variabile di **build**, non di esecuzione: finisce
# dentro il bundle.
FROM node:24-slim AS ui

WORKDIR /ui
# Prima il manifesto, poi il resto: cosi' `npm ci` si rifa' solo quando cambiano
# le dipendenze, non a ogni riga di TypeScript.
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
ENV VITE_API_BASE=""
RUN npm run build


FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./

# Quale acceleratore ONNX mettere nell'immagine. **Vuoto di default, e non e'
# timidezza**: gli extra si escludono a vicenda (forniscono tutti il modulo
# `onnxruntime`), dipendono dalla piattaforma, e un'immagine che ne cablasse uno
# girerebbe su una macchina sola -- il contrario di cio' che A-05 deve ottenere.
#
#   docker build --build-arg GPU_EXTRA=gpu-cuda .     # Linux + NVIDIA
#   docker build --build-arg GPU_EXTRA=gpu-rocm .     # Linux + AMD supportata
#
# `gpu-directml` **non e' un valore utile qui**: quel wheel esiste solo per
# Windows, e questa immagine e' Linux. Verificato il 2026-08-14 con
# `pip download --platform manylinux_2_28_x86_64`, che non trova nulla. Su
# Windows la strada e' `make api-local`, fuori dal container.
#
# Il container ha comunque bisogno che l'host gli passi la GPU (`--gpus all`,
# oppure `/dev/kfd` e `/dev/dri` per ROCm). Docker Desktop su Windows non lo fa
# per schede non-NVIDIA: nel container di sviluppo non c'e' nessun dispositivo.
# Provare davvero questi due extra e' U-12 -- qui sono **dichiarati, non
# verificati**, con la stessa onesta' di `PREFERRED_ACCELERATORS` in Q-05.
ARG GPU_EXTRA=""

# Le sole dipendenze, non il progetto. `-r pyproject.toml` legge
# `[project.dependencies]`.
#
# **Senza lockfile, e va detto**: `uv.lock` non esiste in questo repo, quindi due
# build a distanza di mesi possono risolvere versioni diverse. Per un servizio
# che si vuole riproducibile il lock e' il passo giusto, ed e' un task suo.
#
# `--extra` e non `.[extra]`: il secondo installerebbe anche **il progetto**, e
# a quel punto `src` esisterebbe due volte -- in `/app` e in site-packages --
# con la garanzia che prima o poi si importi quello sbagliato.
RUN uv venv /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r pyproject.toml \
      ${GPU_EXTRA:+--extra $GPU_EXTRA}

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

# L'indice ridotto della demo: 20 MB, e **dentro l'immagine di proposito**.
# Fino al 2026-08-30 arrivava montato da `compose.yml`, per poterlo rifare senza
# ricostruire l'immagine. Quel vantaggio costava piu' di quanto valesse: chi
# scarica l'immagine pubblicata non ha il repository, quindi non ha niente da
# montare, e la demo che dovrebbe partire da sola non partiva affatto. Chi
# ritaglia un indice nuovo con `build_demo_index.py` ricostruisce, e sono
# trenta secondi.
COPY data/demo ./data/demo

# Il frontend costruito. **Non le sorgenti**: l'immagine esegue, non compila, e
# `main.py` monta questa cartella solo se c'e' -- fuori dal container (`make
# dev`) non c'e', e Vite serve la sua.
COPY --from=ui /ui/dist ./ui/dist

# **Qui e solo qui.** Fuori dal container `ui/dist` puo' esistere lo stesso (la
# lascia `make ui-check`) ma e' costruita per il proxy di Vite: servirla darebbe
# una pagina che si carica e non parla col backend. Vedi `SERVE_UI`.
ENV SERVE_UI=1

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
