# Proposal: Migrate `problem_details.py` to the API Adapter Layer

**Change ID**: `migrate-problem-details-to-api-adapter`
**Priority**: Medium
**Status**: Proposed

---

## Problem Statement

`problem_details.py` lives at the project root alongside `main.py`. Its content is entirely FastAPI-specific:

```python
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
```

It implements HTTP error formatting (RFC 9457 Problem Details) and registers FastAPI exception handlers. This is an **inbound adapter concern** — it belongs in `src/api/`, just like routers, schemas, and dependencies.

The current placement has two concrete consequences:

1. **Architecture hygiene**: The `test_hexagonal_boundaries.py` boundary test classifies both `main.py` and `problem_details.py` as `"runtime"` modules explicitly exempt from all import rules:
   ```python
   RUNTIME_MODULE_FILES = (
       "main.py",
       "problem_details.py",
   )
   ```
   This exemption exists purely because `problem_details.py` is at the root and would otherwise be unclassifiable. Moving it into `src/api/` removes the need for the exemption and places the file under proper boundary enforcement.

2. **Discoverability and ownership**: A developer adding a new error handler does not know to look at the project root. Error handling belongs with the API adapter code.

---

## Rationale

Per `hex-design-guide.md` Section 14:
> FastAPI maps domain/application exceptions to HTTP. Error handlers live in `app/api/error_handlers.py`.

The guide explicitly locates error handler registration in the API adapter layer. The current root placement is an artifact of incremental development, not an intentional architecture decision.

---

## Scope

**In scope:**
- Move `problem_details.py` → `src/api/error_handlers.py`.
- Update `main.py` to import `register_problem_details` from `src.api.error_handlers`.
- Remove `"problem_details.py"` from `RUNTIME_MODULE_FILES` in `test_hexagonal_boundaries.py`.
- Add `src.api.error_handlers` to the boundary test's `"api"` layer classification.
- Update `docs/architecture.md` if it references `problem_details.py`.

**Out of scope:**
- Changing the error handler logic itself (content is correct, location is wrong).
- Adding new error handlers.

---

## Affected Modules

| File | Change |
|---|---|
| `problem_details.py` | Removed (moved) |
| `src/api/error_handlers.py` | Added |
| `main.py` | Modified — update import path |
| `tests/unit/test_hexagonal_boundaries.py` | Modified — remove `"problem_details.py"` from `RUNTIME_MODULE_FILES`; update `get_layer` if needed |
| `tests/integration/test_problem_details_rfc9457.py` | Verified — no direct import of `problem_details` module needed |
| `docs/architecture.md` | Verified / modified |

---

## Proposed Change

Before:
```python
# main.py
from problem_details import register_problem_details
```

After:
```python
# main.py
from src.api.error_handlers import register_problem_details
```

The content of `src/api/error_handlers.py` is identical to the current `problem_details.py`.

In `test_hexagonal_boundaries.py`:
```python
# Before
RUNTIME_MODULE_FILES = (
    "main.py",
    "problem_details.py",      # ← exempted because it's at root
)

# After
RUNTIME_MODULE_FILES = (
    "main.py",                 # problem_details moved to src/api; no longer needs exemption
)
```

`get_layer` in the boundary test already maps `src.api.*` → `"api"`, so `src.api.error_handlers` will be correctly classified and subject to layer rules.

---

## Acceptance Criteria

1. `problem_details.py` does not exist at the project root.
2. `src/api/error_handlers.py` exists with identical content (functions `register_problem_details`, `problem_json_response`, `_status_title`, `_http_exception_detail`).
3. `main.py` imports `register_problem_details` from `src.api.error_handlers`.
4. `RUNTIME_MODULE_FILES` in `test_hexagonal_boundaries.py` contains only `"main.py"`.
5. All integration tests for problem details (`test_problem_details_rfc9457.py`) continue to pass.
6. The boundary test `test_hexagonal_architecture_boundaries` passes.

---

## Migration Strategy

1. Create `src/api/error_handlers.py` with the exact content of `problem_details.py`.
2. Update `from problem_details import register_problem_details` in `main.py`.
3. Delete `problem_details.py`.
4. Update `RUNTIME_MODULE_FILES` in `test_hexagonal_boundaries.py`.
5. Run `python -m pytest tests/ -x` to confirm no regressions.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| `src/api/error_handlers.py` importing `FastAPI` may trigger boundary rule failures | The `"api"` layer is allowed to import `fastapi` — this is correct. Verify the boundary test passes after the move. |
| `problem_details.py` is referenced in tests by name | Search for any `import problem_details` in tests — there are none. The test file `test_problem_details_rfc9457.py` does not import the module by name. |
