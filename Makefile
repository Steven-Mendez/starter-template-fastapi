PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help sync dev format lint lint-fix typecheck check precommit-install precommit-run precommit-update test test-cov test-unit test-integration test-e2e test-fast

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

sync: ## Sync dependencies (uv lock + install)
	uv sync

dev: ## Run API with auto-reload
	uv run uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

format: ## Format code with Ruff formatter
	uv run ruff format .

lint: ## Run Ruff lint checks
	uv run ruff check .

lint-fix: ## Run Ruff lint checks and auto-fix
	uv run ruff check --fix .

typecheck: ## Run static type checks (mypy)
	uv run mypy

check: lint typecheck ## Run lint + type checks

precommit-install: ## Install git pre-commit hooks
	uv run pre-commit install

precommit-run: ## Run all pre-commit hooks
	uv run pre-commit run --all-files

precommit-update: ## Update pre-commit hook versions
	uv run pre-commit autoupdate

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
