# Proposal: Extract Infrastructure ORM Mapper Module

**Change ID**: `infrastructure-mapper-module`
**Priority**: Medium
**Status**: Proposed

---

## Problem Statement

`SQLModelKanbanRepository` (and `_BaseSQLModelKanbanRepository`) contains inline ORM-to-domain mapping logic distributed across multiple methods:

- In `get_board` / `find_by_id`: `ColumnTable` and `CardTable` rows are manually mapped to `Column` and `Card` domain objects within a loop.
- In `save_board` / `save`: domain `Board`, `Column`, and `Card` objects are manually mapped back to `BoardTable`, `ColumnTable`, and `CardTable` rows inline.
- In `_to_card_read`: a static helper exists for `CardTable → Card` but only for reads, not writes, and lives on the repository class.

The `hex-design-guide.md` explicitly calls out this pattern:

> Better: `OrderModel = persistence representation`, `Order = domain representation`, `Mapper = translation between them`

And provides an example of a dedicated `mappers.py` module with explicit `order_model_to_domain` and `order_domain_to_model` functions.

The current approach has these problems:
1. **Readability**: The `save_board` method is 70+ lines because mapping and persistence logic are interleaved. It is hard to understand what data transformation is happening versus what SQL session mutation is happening.
2. **Testability**: Mapping logic cannot be unit-tested without instantiating a SQLModel session.
3. **Inconsistency**: The static `_to_card_read` helper is a partial mapper on the wrong class. The equivalent write mapper is inline in `save_board`.

---

## Rationale

A dedicated mapper module:
- Separates the concern of **data representation translation** from the concern of **database session management**.
- Makes mapping functions unit-testable: given a `BoardTable` row, assert the resulting `Board` has the expected fields — no session required.
- Reduces the length of repository methods, making them easier to read and maintain.
- Follows the explicit recommendation in `hex-design-guide.md`.

---

## Scope

**In scope:**
- Create `src/infrastructure/persistence/sqlmodel/mappers.py` with:
  - `board_table_to_domain(board, columns_with_cards) -> Board`
  - `board_domain_to_table(board) -> BoardTable`
  - `column_table_to_domain(column, cards) -> Column`
  - `column_domain_to_table(column) -> ColumnTable`
  - `card_table_to_domain(card) -> Card`
  - `card_domain_to_table(card) -> CardTable`
- Refactor `SQLModelKanbanRepository` methods to call these mapper functions.
- Remove `_to_card_read` static helper from the repository class.

**Out of scope:**
- Changing the repository port interface.
- Changing domain entity fields.
- Adding async support.

---

## Affected Modules

| File | Change |
|---|---|
| `src/infrastructure/persistence/sqlmodel/mappers.py` | Added |
| `src/infrastructure/persistence/sqlmodel/__init__.py` | Modified — re-export mappers |
| `src/infrastructure/persistence/sqlmodel_repository.py` | Modified — use mappers, remove inline translation |

---

## Proposed Mapper Signatures

```python
# src/infrastructure/persistence/sqlmodel/mappers.py
from datetime import datetime, timezone
from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.infrastructure.persistence.sqlmodel.models import BoardTable, CardTable, ColumnTable

def board_table_to_summary(row: BoardTable) -> BoardSummary: ...
def board_table_to_domain(row: BoardTable, columns: list[Column]) -> Board: ...
def column_table_to_domain(row: ColumnTable, cards: list[Card]) -> Column: ...
def card_table_to_domain(row: CardTable) -> Card: ...
def board_domain_to_table(board: Board) -> BoardTable: ...
def column_domain_to_table(column: Column, board_id: str) -> ColumnTable: ...
def card_domain_to_table(card: Card, column_id: str) -> CardTable: ...
```

---

## Acceptance Criteria

1. `src/infrastructure/persistence/sqlmodel/mappers.py` exists with all six mapper functions.
2. No inline `Card(id=card.id, ...)` or `CardTable(id=card.id, ...)` construction exists inside `sqlmodel_repository.py`.
3. `_to_card_read` static method is removed from `_BaseSQLModelKanbanRepository`.
4. Mapper functions can be imported and tested independently of a database session.
5. All existing integration and unit tests continue to pass.
6. Add at least 3 unit tests for mapper functions in `tests/unit/test_infrastructure_mappers.py`.

---

## Migration Strategy

1. Create `mappers.py` with pure functions that translate between table rows and domain objects.
2. Replace the inline construction in `get_board` / `find_by_id` with calls to `card_table_to_domain` and `column_table_to_domain`.
3. Replace the inline construction in `save_board` / `save` with calls to `card_domain_to_table` and `column_domain_to_table`.
4. Remove `_to_card_read`.
5. Run tests to confirm no behavioral change.
6. Optionally add mapper unit tests.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Mapper functions may need to be pure (no session logic) — some construction depends on session state | Design mappers to receive fully-loaded data as arguments; session I/O stays in repository methods. |
| Extracting mappers changes no behavior but introduces a new module boundary | Risk is low — pure data transformation, no side effects. The test suite catches any accidental data loss. |
