PORT ?= 8000

.DEFAULT_GOAL := help

.PHONY: help sync dev worker format lint lint-arch lint-fix typecheck quality check app-import-smoke audit sast migration-check docker-smoke ci ci-local precommit-install precommit-run prepush-run precommit-update test test-integration test-e2e test-feature cov cov-html cov-xml cov-open report report-open clean-reports

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

sync: ## Sync dependencies (uv lock + install)
	uv sync

dev: ## Run API with auto-reload (FastAPI CLI)
	uv run fastapi dev src/main.py --host 0.0.0.0 --port $(PORT)

worker: ## Run the arq background-jobs worker (requires APP_JOBS_BACKEND=arq)
	uv run python -m src.worker

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

app-import-smoke: ## Verify the ASGI entrypoint imports in a fresh process
	APP_AUTH_JWT_SECRET_KEY=ci-test-secret-key-min-32-chars \
	APP_ENVIRONMENT=development \
	uv run python -c "import src.main"

audit: ## Audit dependencies for known vulnerabilities
	uv run pip-audit

sast: ## Run Bandit static security scan
	uv run --with bandit bandit -r src \
		--exclude src/features/authentication/tests,src/features/_template/tests,src/features/authorization/tests,src/platform/tests \
		--severity-level medium

migration-check: ## Verify Alembic upgrade/check/downgrade against ephemeral PostgreSQL
	scripts/migration-check.sh

docker-smoke: ## Build and smoke-test the runtime Docker image
	scripts/docker-smoke.sh

test: ## Run unit + e2e tests (no docker)
	uv run pytest -m "not integration"

test-integration: ## Run integration tests (requires Docker)
	uv run pytest -m integration

test-e2e: ## Run only end-to-end tests
	uv run pytest -m e2e

test-feature: ## Run tests for a single feature: make test-feature FEATURE=authentication
	@if [ -z "$(FEATURE)" ]; then echo "Usage: make test-feature FEATURE=<name>"; exit 2; fi
	@feature="$(FEATURE)"; \
	if [ "$$feature" = "auth" ]; then \
		echo "warning: FEATURE=auth is deprecated; use FEATURE=authentication"; \
		feature=authentication; \
	fi; \
	uv run pytest src/features/$$feature/tests

cov: ## Run tests with terminal coverage report
	uv run pytest -m "not integration" --cov --cov-report=term-missing --cov-fail-under=80

cov-html: ## Run tests and generate fancy HTML coverage report at reports/coverage/index.html
	@mkdir -p reports
	uv run pytest -m "not integration" \
	    --cov --cov-report=html:reports/coverage --cov-report=term --cov-fail-under=80
	@echo ""
	@echo "Coverage report: file://$(CURDIR)/reports/coverage/index.html"

cov-xml: ## Run tests and emit Cobertura XML at reports/coverage.xml (CI artifacts)
	@mkdir -p reports
	uv run pytest -m "not integration" \
	    --cov --cov-report=xml:reports/coverage.xml --cov-fail-under=80

cov-open: ## Open the latest HTML coverage report in the default browser
	@if [ ! -f reports/coverage/index.html ]; then echo "Run 'make cov-html' first."; exit 1; fi
	@open reports/coverage/index.html 2>/dev/null || xdg-open reports/coverage/index.html 2>/dev/null || echo "Open: file://$(CURDIR)/reports/coverage/index.html"

report: ## Generate HTML test report + HTML coverage at reports/
	@mkdir -p reports
	uv run pytest -m "not integration" \
	    --cov --cov-report=html:reports/coverage --cov-report=term --cov-fail-under=80 \
	    --html=reports/tests.html --self-contained-html
	@echo ""
	@echo "Test report:     file://$(CURDIR)/reports/tests.html"
	@echo "Coverage report: file://$(CURDIR)/reports/coverage/index.html"

report-open: ## Open the latest test report and coverage report
	@open reports/tests.html reports/coverage/index.html 2>/dev/null \
	  || (xdg-open reports/tests.html; xdg-open reports/coverage/index.html) 2>/dev/null \
	  || echo "Open: file://$(CURDIR)/reports/tests.html and file://$(CURDIR)/reports/coverage/index.html"

clean-reports: ## Remove generated reports/ and .coverage artifacts
	rm -rf reports/ .coverage .coverage.* htmlcov/

ci: quality test test-integration ## Full gate: quality + unit + e2e + integration

ci-local: quality app-import-smoke test test-integration migration-check audit sast docker-smoke ## Local pre-push gate mirroring CI jobs

precommit-install: ## Install git pre-commit and pre-push hooks
	uv run pre-commit install --install-hooks

precommit-run: ## Run pre-commit-stage hooks on all files
	uv run pre-commit run --hook-stage pre-commit --all-files

prepush-run: ## Run pre-push-stage hooks on all files
	uv run pre-commit run --hook-stage pre-push --all-files

precommit-update: ## Update pre-commit hook versions
	uv run pre-commit autoupdate
