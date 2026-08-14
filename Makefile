.PHONY: fetch-datasets ingest eval eval-generation eval-citations noise-floor dashboard demo \n	api api-local ui ui-types ui-check up down logs

fetch-datasets:
	python scripts/fetch_dataset.py

ingest:
	python scripts/ingest.py

eval:
	python scripts/eval.py

eval-generation:
	python scripts/eval_generation.py --baseline A

# C-01. Il limite di 200 non e un default timido: una generazione costa ~20s
# di GPU, quindi il golden set completo sarebbe ~17 ore per dataset, e 200 e
# la taglia minima con cui un 98% osservato sostiene il criterio del 95%.
eval-citations:
	python scripts/eval_citations.py --dataset open_ragbench --limit 200

noise-floor:
	python scripts/eval_noise.py --mode retrieval --n-runs 5

# `python -m streamlit`, non `streamlit`: l'installazione via uv/pip mette il
# modulo ma non sempre l'eseguibile nel PATH (è il caso su Windows), e in quel
# caso il target fallisce con "command not found" pur essendo streamlit
# installato. Il prefisso funziona ovunque.
dashboard:
	python -m streamlit run dashboard/app.py

demo:
	docker compose --profile demo up

# --- Il servizio (A-05) ------------------------------------------------------
#
# `api` mette il backend in un container e lo fa parlare con Qdrant e l'LLM
# sulla macchina che ospita. Dal punto di vista del container quello **e' un
# altro host**: e' il modo in cui questo setup verifica il criterio di A-05 pur
# girando tutto su un PC solo.
#
# Per servizi davvero altrove basta l'ambiente, e nessun file cambia:
#   QDRANT_URL=http://10.0.0.5:6333 LLM_BASE_URL=http://10.0.0.7:11434/v1 make api
api:
	QDRANT_URL=$${QDRANT_URL:-http://host.docker.internal:6333} 	docker compose up --build api

# Senza container, contro i servizi gia' in ascolto: il giro di sviluppo.
# `--reload` non c'e' di proposito -- ricaricare a ogni salvataggio rilegge da
# capo ~2,5 GB di pesi, e l'attesa non si distingue da un blocco.
api-local:
	python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# --- Il frontend (U-00) ------------------------------------------------------
#
# Vuole `make api-local` gia' in ascolto: il backend non ha CORS, e non deve
# averne. In sviluppo `/api/...` esce da Vite e arriva al backend come `/...`;
# in produzione API e UI stanno dietro la stessa origine e il proxy non serve.
#
# Contro un backend altrove, senza toccare un file:
#   VITE_API_TARGET=http://10.0.0.7:8000 make ui
ui:
	cd ui && npm install && npm run dev

# I tipi del contratto sono generati: questo li riscrive dopo un cambio a
# `src/api/schema.py`. Senza, `tests/test_ui_types.py` fallisce -- ed e' cio'
# che rende impossibile che i due lati divergano in silenzio.
ui-types:
	python scripts/gen_api_types.py

ui-check:
	cd ui && npm run typecheck && npm test && npm run build

# Tutto: Qdrant nella rete di compose piu' il backend.
up:
	docker compose --profile full up -d --build

down:
	docker compose --profile full down

logs:
	docker compose logs -f api
