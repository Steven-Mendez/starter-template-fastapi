## 1. Config

- [x] 1.1 Expand `[tool.ruff.lint] select` in `pyproject.toml` to `["E","F","I","B","UP","S","C4","RUF","SIM","PT","TRY","RET","ARG","DTZ","ASYNC","PERF","PL"]`.
- [x] 1.2 Add `[tool.ruff.lint.extend-ignore] = ["TRY003","PLC0415"]`.
- [x] 1.3 Add `[tool.ruff.lint.per-file-ignores]`:
  - `"**/tests/**" = ["S101","S105","S106","ARG","PLR2004"]`
  - `"**/conftest.py" = ["S101","S105","S106","ARG","PLR2004"]`
  - `"src/features/**/adapters/outbound/persistence/sqlmodel/models.py" = ["RUF012"]`
  - `"alembic/versions/*.py" = ["ALL"]`

## 2. Triage

- [x] 2.1 Run `make lint` and capture finding counts by rule to `reports/ruff-expand-baseline.txt`.
- [x] 2.2 Run `make lint-fix` to auto-fix the trivial families (`UP`, `SIM`, `C4`, `RET`).
- [x] 2.3 Hand-fix the remainder (mostly `S` security findings — review each before suppressing).

## 3. Cleanup `# noqa`

- [x] 3.1 With `RUF100` enabled, remove `# noqa` lines that ruff now flags as unused.

## 4. Verify

- [x] 4.1 `make lint` clean.
- [x] 4.2 `make ci` green.
