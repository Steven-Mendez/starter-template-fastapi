PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help sync dev format lint lint-arch lint-fix typecheck quality check ci precommit-install precommit-run precommit-update

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

sync: ## Sync dependencies (uv lock + install)
	uv sync

dev: ## Run API with auto-reload
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port $(PORT)

format: ## Format code with Ruff formatter
	uv run ruff format .

lint: ## Run Ruff lint checks
	uv run ruff check .

lint-arch: ## Check Hexagonal Architecture import contracts (Import Linter)
	uv run lint-imports

lint-fix: ## Run Ruff lint checks and auto-fix
	uv run ruff check --fix .

typecheck: ## Run static type checks (mypy)
	uv run mypy

quality: lint lint-arch typecheck ## Run lint + import contracts + typing

check: quality ## Alias for the local quality gate

ci: quality ## Run the same quality gate as GitHub Actions

precommit-install: ## Install git pre-commit and pre-push hooks
	uv run pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push

precommit-run: ## Run all pre-commit hooks
	uv run pre-commit run --all-files

precommit-update: ## Update pre-commit hook versions
	uv run pre-commit autoupdate
