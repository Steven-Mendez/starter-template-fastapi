# Spec: API Adapter Boundary — Error Handler Location

**Capability**: api-adapter-boundary
**Change**: migrate-problem-details-to-api-adapter

---

## ADDED Requirements

### Requirement: AAB-01 — `src/api/error_handlers.py` exists and contains RFC 9457 error handler registration

The system MUST satisfy this requirement as specified below.


**Priority**: Medium

The RFC 9457 Problem Details error handler implementation lives in the API adapter layer (`src/api/error_handlers.py`), not at the project root.

**Acceptance Criteria**:
1. `src/api/error_handlers.py` exists.
2. It exports `register_problem_details(app: FastAPI) -> None`.
3. It exports `problem_json_response(...)`.
4. `problem_json_response` constructs RFC 9457-compliant payloads (fields: `type`, `title`, `status`, `instance`).
5. `main.py` imports `register_problem_details` from `src.api.error_handlers`, not from `problem_details`.

#### Scenario: Error handler module is importable from API layer

- Given: the project source tree
- When: `from src.api.error_handlers import register_problem_details, problem_json_response` is executed
- Then: both names resolve without error

#### Scenario: `main.py` uses the relocated module

- Given: `main.py` source file
- When: its import statements are inspected
- Then: `from src.api.error_handlers import register_problem_details` appears
- And: `from problem_details import` does not appear

## ADDED Requirements

### Requirement: AAB-03 — Boundary test classifies `src.api.error_handlers` as `"api"` layer


**Priority**: Medium

The `get_layer` function in `test_hexagonal_boundaries.py` MUST correctly classify the error handler module as belonging to the API layer, subjecting it to API layer import rules.

**Acceptance Criteria**:
1. `get_layer("src.api.error_handlers")` returns `"api"`.
2. `src.api.error_handlers` passes the API layer import rules (it imports `fastapi`, which is allowed for the API layer).
3. `test_hexagonal_architecture_boundaries()` passes with `src.api.error_handlers` classified.

#### Scenario: Error handler passes API layer boundary rules

- Given: the boundary test with `src.api.error_handlers` present in the module graph
- When: `test_hexagonal_architecture_boundaries()` runs
- Then: no violation is reported for `src.api.error_handlers`
- And: `src.api.error_handlers` is classified as `"api"` layer, not `"other"` or `"runtime"`

## ADDED Requirements

### Requirement: AAB-02 — `problem_details.py` does not exist at the project root

The system MUST satisfy this requirement as specified below.


**Priority**: Medium

The root-level `problem_details.py` is removed. Its absence prevents the `RUNTIME_MODULE_FILES` exemption in the boundary test from being needed.

**Acceptance Criteria**:
1. `problem_details.py` does not exist at the project root.
2. `python -c "import problem_details"` raises `ModuleNotFoundError`.
3. `RUNTIME_MODULE_FILES` in `tests/unit/test_hexagonal_boundaries.py` contains only `"main.py"`.

#### Scenario: Root-level module absence confirmed

- Given: the project root directory listing
- When: `problem_details.py` is searched for
- Then: it is not found
