.PHONY: fetch-datasets ingest eval demo

fetch-datasets:
	@echo "TODO: T-04"

ingest:
	@echo "TODO: T-05"

eval:
	python scripts/eval.py

demo:
	docker compose --profile demo up
