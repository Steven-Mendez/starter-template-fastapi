## 1. Dependencies

- [x] 1.1 Add runtime dependency `pydantic` and dev dependencies `pytest`, `httpx`; run `uv sync`

## 2. Tests first (TDD)

- [x] 2.1 Add `tests/conftest.py` with `TestClient` and `KanbanStore` dependency override for isolation
- [x] 2.2 Add `tests/test_kanban_api.py` covering boards, columns, cards, move, 404s, and delete cascades

## 3. Implementation

- [x] 3.1 Add `kanban/schemas.py` (Pydantic v2 models for API bodies and responses)
- [x] 3.2 Add `kanban/store.py` (in-memory `KanbanStore` and `get_store` for `Depends`)
- [x] 3.3 Add `kanban/router.py` (REST routes under `/api`) and `kanban/__init__.py`
- [x] 3.4 Wire router in `main.py` with `include_router`

## 4. Developer ergonomics

- [x] 4.1 Add `test` target to `Makefile` (`uv run pytest`)
