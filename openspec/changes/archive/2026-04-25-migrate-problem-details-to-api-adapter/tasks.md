# Tasks: Migrate `problem_details.py` to the API Adapter Layer

**Change ID**: `migrate-problem-details-to-api-adapter`

---

## Implementation Checklist

### Phase 1 — Move the module

- [ ] Create `src/api/error_handlers.py` with the exact content of `problem_details.py`.
- [ ] Verify `src/api/error_handlers.py` contains all four names: `register_problem_details`, `problem_json_response`, `_status_title`, `_http_exception_detail`.

### Phase 2 — Update import in `main.py`

- [ ] Change `from problem_details import register_problem_details` to `from src.api.error_handlers import register_problem_details`.
- [ ] Run `python -c "from main import create_app"` to confirm the import works.

### Phase 3 — Remove old file

- [ ] Delete `problem_details.py` from the project root.
- [ ] Confirm `python -c "import problem_details"` raises `ModuleNotFoundError`.

### Phase 4 — Update boundary test

- [ ] In `tests/unit/test_hexagonal_boundaries.py`, remove `"problem_details.py"` from `RUNTIME_MODULE_FILES`.
- [ ] Verify `get_layer("src.api.error_handlers")` returns `"api"` (it should by default — no change needed if `get_layer` maps `src.api.*` → `"api"`).
- [ ] Run `python -m pytest tests/unit/test_hexagonal_boundaries.py -v` — all tests pass.

### Phase 5 — Verify

- [ ] Run `python -m pytest tests/integration/test_problem_details_rfc9457.py -v` — all tests pass.
- [ ] Run `python -m pytest tests/ -x` — no regressions.
- [ ] Confirm `rg "problem_details" .` only returns OpenSpec and documentation references, no production code references.
