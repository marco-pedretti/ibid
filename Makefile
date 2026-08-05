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

dashboard:
	streamlit run dashboard/app.py

demo:
	docker compose --profile demo up
