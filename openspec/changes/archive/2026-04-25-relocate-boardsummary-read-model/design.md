# Design: Relocate `BoardSummary` Read Model from Domain to Application Layer

**Change ID**: `relocate-boardsummary-read-model`

---

## Why Infrastructure Can Import `AppBoardSummary`

A concern when infrastructure adapters import from `src.application.contracts` is that it might create an unusual dependency direction. The hexagonal rules are:

```
domain        → stdlib only
application   → domain, ports (self-owned)
infrastructure → application ports, domain, ORM/SDK libraries
api           → FastAPI, application use cases
```

Infrastructure already imports application ports (after `relocate-ports-to-application-layer`). Importing an application contract type (`AppBoardSummary`) from `src.application.contracts` is the same category — infrastructure satisfies application contracts. The dependency direction is correct: infrastructure → application.

---

## Eliminating the Redundant Mapping Layer

Before this change, the pipeline for listing boards is:

```
repository.list_boards()
  → list[BoardSummary]           ← domain type
  → to_app_board_summary(...)    ← copies id, title, created_at to AppBoardSummary
  → list[AppBoardSummary]        ← application type
  → to_board_summary_response()  ← copies to API schema
  → list[BoardSummary (schema)]  ← API response type
```

Three types with identical structure. Two copy operations. After this change:

```
repository.list_all()
  → list[AppBoardSummary]        ← directly from repository
  → to_board_summary_response()  ← copies to API schema
  → list[BoardSummary (schema)]  ← API response type
```

One copy operation remains — the API schema copy is correct and intentional (the API schema and application contract have different purposes: the API schema is the HTTP contract, the application contract is the use-case output).

---

## Sequencing

This change depends on:
1. `relocate-ports-to-application-layer` (Change 1) — ports must be in `src.application.ports` before their return types are changed to reference `AppBoardSummary`.
2. `aggregate-repository-and-infrastructure-ports` (Change 2) — the command port's `create_board` return type is also `BoardSummary` (will be removed in Change 2 anyway, replaced by constructing `Board` in application).

Apply this change after Changes 1 and 2.

---

## Boundary Test Impact

After this change, `src.infrastructure.persistence.*` will import from `src.application.contracts`. The `DENY_MATRIX` in `test_hexagonal_boundaries.py`:

```python
"infrastructure": [
    "src.api",
    "dependencies",
],
```

Infrastructure is NOT denied from importing `src.application.contracts`. The boundary test will continue to pass without modification. Confirm this by running the boundary test after the change.

---

## `AppBoardSummary` Location Remains Unchanged

`AppBoardSummary` stays in `src/application/contracts/kanban.py`. No renaming of the type is required. The only change is:

1. Delete `BoardSummary` (domain model) which is now fully superseded.
2. Repository port + adapters directly produce `AppBoardSummary`.

---

## Code Changes Summary

### `src/application/ports/kanban_query_repository.py` (after Change 1)

```python
from src.application.contracts import AppBoardSummary

class KanbanQueryRepositoryPort(Protocol):
    def list_all(self) -> list[AppBoardSummary]: ...     # ← was list[BoardSummary]
    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...
    def find_board_id_by_card(self, card_id: str) -> str | None: ...
```

### `src/infrastructure/persistence/sqlmodel_repository.py`

```python
from src.application.contracts import AppBoardSummary

def list_all(self) -> list[AppBoardSummary]:
    with self._session_scope() as session:
        rows = session.exec(select(BoardTable).order_by("created_at")).all()
    return [
        AppBoardSummary(
            id=row.id,
            title=row.title,
            created_at=_ensure_utc(row.created_at),
        )
        for row in rows
    ]
```

### `src/infrastructure/persistence/in_memory_repository.py`

```python
from src.application.contracts import AppBoardSummary

def list_all(self) -> list[AppBoardSummary]:
    return [
        AppBoardSummary(id=b.id, title=b.title, created_at=b.created_at)
        for b in self._boards.values()
    ]
```

### `src/application/queries/handlers.py`

```python
def handle_list_boards(self, query: ListBoardsQuery) -> list[AppBoardSummary]:
    return self.repository.list_all()    # no mapper call needed
```

### `src/application/contracts/mappers.py`

Remove `to_app_board_summary` function and its import of `BoardSummary`.
