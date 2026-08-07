.PHONY: fetch-datasets ingest eval eval-generation noise-floor dashboard demo

fetch-datasets:
	python scripts/fetch_dataset.py

ingest:
	python scripts/ingest.py

eval:
	python scripts/eval.py

eval-generation:
	python scripts/eval_generation.py --baseline A

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
