PORT ?= 8000

# Branch-coverage floor enforced by the Makefile after every coverage run.
# Set to the value `main` achieves rounded down to the nearest 5%. Override
# via env: `BRANCH_COVERAGE_FLOOR=70 make cov`.
BRANCH_COVERAGE_FLOOR ?= 60

.DEFAULT_GOAL := help

.PHONY: help sync dev worker outbox-retry-failed outbox-prune format lint lint-arch lint-fix typecheck quality check app-import-smoke audit sast migration-check migrations-check docker-smoke docker-build-worker ci ci-local precommit-install precommit-run prepush-run precommit-update test test-integration test-e2e test-feature cov cov-html cov-xml cov-open report report-open clean-reports check-branch-coverage

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

sync: ## Sync dependencies (uv lock + install)
	uv sync

dev: ## Run API with auto-reload (FastAPI CLI)
	uv run fastapi dev src/main.py --host 0.0.0.0 --port $(PORT)

worker: ## Run the arq background-jobs worker (requires APP_JOBS_BACKEND=arq)
	PYTHONPATH=src uv run python -m worker

outbox-retry-failed: ## Re-arm outbox rows that reached APP_OUTBOX_MAX_ATTEMPTS
	PYTHONPATH=src uv run python -m features.outbox.management retry-failed

outbox-prune: ## Prune terminal outbox rows and stale dedup marks past their retention
	PYTHONPATH=src uv run python -m cli.outbox_prune

format: ## Format code with Ruff formatter
	uv run ruff format .

lint: ## Run Ruff lint checks
	uv run ruff check .

lint-arch: ## Check Hexagonal Architecture import contracts (Import Linter)
	PYTHONPATH=src uv run lint-imports

lint-fix: ## Run Ruff lint checks and auto-fix
	uv run ruff check --fix .

typecheck: ## Run static type checks (mypy)
	uv run mypy

quality: lint lint-arch typecheck ## Run lint + import contracts + typing

check: quality ## Alias for the local quality gate

app-import-smoke: ## Verify the ASGI entrypoint imports in a fresh process
	APP_AUTH_JWT_SECRET_KEY=ci-test-secret-key-min-32-chars \
	APP_ENVIRONMENT=development \
	PYTHONPATH=src uv run python -c "import main"

audit: ## Audit dependencies for known vulnerabilities
	uv run pip-audit

sast: ## Run Bandit static security scan
	uv run --with bandit bandit -r src \
		--exclude '*/tests,*/tests/*' \
		--severity-level medium

migration-check: ## Verify Alembic upgrade/check/downgrade against ephemeral PostgreSQL
	scripts/migration-check.sh

migrations-check: ## Enforce migration policy (destructive ops must raise on downgrade)
	uv run pytest tests/quality/test_migration_policy.py -q

docker-smoke: ## Build and smoke-test the runtime Docker image
	scripts/docker-smoke.sh

docker-build-worker: ## Build the worker Docker image (runtime-worker stage)
	docker build --target runtime-worker --tag worker:latest .

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

cov: ## Run tests with terminal coverage report (gates line + branch)
	@mkdir -p reports
	uv run pytest -m "not integration" \
	    --cov --cov-branch \
	    --cov-report=term-missing \
	    --cov-report=json:reports/coverage.json \
	    --cov-fail-under=80
	@$(MAKE) --no-print-directory check-branch-coverage

cov-html: ## Run tests and generate fancy HTML coverage report at reports/coverage/index.html
	@mkdir -p reports
	uv run pytest -m "not integration" \
	    --cov --cov-branch \
	    --cov-report=html:reports/coverage \
	    --cov-report=json:reports/coverage.json \
	    --cov-report=term \
	    --cov-fail-under=80
	@$(MAKE) --no-print-directory check-branch-coverage
	@echo ""
	@echo "Coverage report: file://$(CURDIR)/reports/coverage/index.html"

cov-xml: ## Run tests and emit Cobertura XML at reports/coverage.xml (CI artifacts)
	@mkdir -p reports
	uv run pytest -m "not integration" \
	    --cov --cov-branch \
	    --cov-report=xml:reports/coverage.xml \
	    --cov-report=json:reports/coverage.json \
	    --cov-fail-under=80
	@$(MAKE) --no-print-directory check-branch-coverage

check-branch-coverage: ## Fail if branch coverage in reports/coverage.json is below BRANCH_COVERAGE_FLOOR
	@uv run python -c "import json, sys, os; \
floor = float(os.environ.get('BRANCH_COVERAGE_FLOOR', '$(BRANCH_COVERAGE_FLOOR)')); \
data = json.load(open('reports/coverage.json'))['totals']; \
pct = data.get('percent_branches_covered'); \
sys.exit('FAIL: branch coverage not measured — invoke pytest with --cov-branch') if pct is None else None; \
print(f'Branch coverage: {pct:.2f}% (floor: {floor:.0f}%)'); \
sys.exit(f'FAIL: branch coverage {pct:.2f}% < floor {floor:.0f}%') if pct < floor else None"

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

ci: quality migrations-check cov test-integration ## Full gate: quality + migration policy + unit + e2e (with line+branch coverage gate) + integration

ci-local: quality app-import-smoke cov test-integration migration-check audit sast docker-smoke ## Local pre-push gate mirroring CI jobs

precommit-install: ## Install git pre-commit and pre-push hooks
	uv run pre-commit install --install-hooks

precommit-run: ## Run pre-commit-stage hooks on all files
	uv run pre-commit run --hook-stage pre-commit --all-files

prepush-run: ## Run pre-push-stage hooks on all files
	uv run pre-commit run --hook-stage pre-push --all-files

precommit-update: ## Update pre-commit hook versions
	uv run pre-commit autoupdate
