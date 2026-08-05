.PHONY: fetch-datasets ingest eval demo

fetch-datasets:
	python scripts/fetch_dataset.py

ingest:
	python scripts/ingest.py

eval:
	python scripts/eval.py

eval-generation:
	python scripts/eval_generation.py --baseline A

demo:
	docker compose --profile demo up
