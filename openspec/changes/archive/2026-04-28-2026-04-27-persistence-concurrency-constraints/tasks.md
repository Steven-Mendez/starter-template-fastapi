# Tasks: Persistence Concurrency and Constraints

**Change ID**: `2026-04-27-persistence-concurrency-constraints`

---

## Implementation Checklist

- [x] Add optimistic concurrency marker/version column for persisted board aggregate.
- [x] Update repository save path to enforce version checks and raise deterministic conflict error.
- [x] Add DB-level uniqueness constraints for:
  - [x] `(board_id, position)` on columns
  - [x] `(column_id, position)` on cards
- [x] Add DB-level check constraints for non-negative `position` fields.
- [x] Add/adjust migrations in `alembic/versions/`.
- [x] Add repository and integration tests for conflict/constraint behavior.

## Verification

- [x] `uv run pytest tests/unit/test_kanban_repository_contract.py`
- [x] `uv run pytest tests/integration/test_kanban_api.py`
- [x] `uv run pytest -m "not e2e"`
