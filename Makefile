PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help sync dev lint typecheck test test-cov test-unit test-integration test-e2e test-fast

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

sync: ## Sync dependencies (uv lock + install)
	uv sync

dev: ## Run API with auto-reload
	uv run uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

lint: ## Run Ruff lint checks
	uv run ruff check .

typecheck: ## Run static type checks (mypy)
	uv run mypy

test: ## Full pytest suite
	uv run pytest

test-cov: ## Run non-e2e pytest with coverage report
	uv run pytest -m "not e2e" --cov=. --cov-report=term-missing --cov-report=xml --cov-report=html --cov-fail-under=90

test-fast: ## Skip e2e (no subprocess server)
	uv run pytest -m "not e2e"

test-unit: ## -m unit
	uv run pytest -m unit

test-integration: ## -m integration
	uv run pytest -m integration

test-e2e: ## -m e2e
	uv run pytest -m e2e
