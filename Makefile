PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help sync dev

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

sync: ## Sync dependencies (uv lock + install)
	uv sync

dev: ## Run API with auto-reload
	uv run uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)
