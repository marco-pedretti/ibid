.PHONY: fetch-datasets ingest eval demo

fetch-datasets:
	python scripts/fetch_dataset.py

ingest:
	python scripts/ingest.py

eval:
	python scripts/eval.py

demo:
	docker compose --profile demo up
