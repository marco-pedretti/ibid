.PHONY: fetch-datasets ingest eval eval-generation eval-citations noise-floor dashboard demo

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
