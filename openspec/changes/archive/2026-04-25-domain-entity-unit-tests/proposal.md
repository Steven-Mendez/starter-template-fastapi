# Proposal: Add Domain Entity Unit Tests

**Change ID**: `domain-entity-unit-tests`
**Priority**: High
**Status**: Proposed

---

## Problem Statement

The domain layer contains non-trivial business behavior:

- `Board.move_card` — validates source/target columns, delegates to `Column.extract_card` and `Column.insert_card`, enforces position bounds.
- `Board.delete_column` — removes a column and recalculates positions of remaining columns.
- `Board._recalculate_column_positions` — reindexes columns after mutation.
- `Column.insert_card` — inserts a card at a bounded position and recalculates card positions.
- `Column.extract_card` — removes a card by ID and recalculates positions.
- `Column.move_card_within` — reorders a card within the same column.
- `Column._recalculate_positions` — reindexes cards after insertion or extraction.

None of this behavior has dedicated **pure domain unit tests**. The only tests that exercise domain behavior do so indirectly through the application handler layer (`test_kanban_command_handlers.py`) or through repository contract tests (`test_kanban_repository_contract.py`), which additionally involve in-memory or SQLite persistence.

This is a significant gap: if a domain invariant is broken, the failure surface is a handler test or a repository test — not a fast, isolated domain test. The hexagonal architecture's primary promise is that domain logic is testable without infrastructure.

From `hex-design-guide.md`:
> Unit tests for domain: No database. No FastAPI. No mocks usually. These tests should be fast and numerous.

---

## Rationale

- **Speed**: Domain unit tests run in microseconds. Handler tests require building `KanbanCommandHandlers`, wiring a `UnitOfWork`, and using an `InMemoryKanbanRepository`. Adding domain tests reduces the feedback loop for domain logic changes.
- **Precision**: When a domain invariant breaks, a domain test points directly at the entity method. A handler test points at a compound of application + domain + adapter code.
- **Documentation**: Domain tests serve as executable specifications of business rules. They document what `Board.move_card` is supposed to do without needing to read the implementation.
- **Regression safety**: Domain models are the most stable part of the system. Tests at this level catch regressions early.

---

## Scope

**In scope:**
- Add `tests/unit/domain/` directory with:
  - `test_board_domain.py` — tests for `Board` entity methods.
  - `test_column_domain.py` — tests for `Column` entity methods.
  - `test_card_domain.py` — tests for `Card` value object (minimal — Card is a simple dataclass).
- Tests must use domain objects directly with no application layer, no repository, no UoW.

**Out of scope:**
- Integration tests.
- Tests that involve `KanbanCommandHandlers` or any repository.
- Changing domain entity behavior (test only, no production code changes).

---

## Affected Modules

| File | Change |
|---|---|
| `tests/unit/domain/__init__.py` | Added |
| `tests/unit/domain/test_board_domain.py` | Added |
| `tests/unit/domain/test_column_domain.py` | Added |
| `tests/unit/domain/test_card_domain.py` | Added (optional, minimal) |
| `tests/conftest.py` | No change expected |

---

## Behavior to Test

### `Board`

| Method | Behavior to Assert |
|---|---|
| `get_column(column_id)` | Returns column if present, None if absent |
| `delete_column(column_id)` | Removes column and recalculates sibling positions |
| `delete_column(missing_id)` | Returns `KanbanError.COLUMN_NOT_FOUND` |
| `move_card(...)` — same column reorder | Reorders card within column using `move_card_within` |
| `move_card(...)` — cross-column | Moves card from source to target column |
| `move_card(...)` — missing source column | Returns `KanbanError.INVALID_CARD_MOVE` |
| `move_card(...)` — missing target column | Returns `KanbanError.INVALID_CARD_MOVE` |
| `_recalculate_column_positions` | After delete, remaining columns have contiguous 0-based positions |

### `Column`

| Method | Behavior to Assert |
|---|---|
| `extract_card(card_id)` | Returns card and removes it from list; remaining cards reindexed |
| `extract_card(missing_id)` | Returns None |
| `insert_card(card, position=None)` | Appends when no position given |
| `insert_card(card, position=0)` | Inserts at head |
| `insert_card(card, position=beyond_end)` | Clamps to tail |
| `move_card_within(card_id, position)` | Reorders card correctly |
| `_recalculate_positions` | After insert or extract, positions are contiguous from 0 |

---

## Acceptance Criteria

1. `tests/unit/domain/test_board_domain.py` exists with at least 8 test functions covering `Board` methods.
2. `tests/unit/domain/test_column_domain.py` exists with at least 6 test functions covering `Column` methods.
3. All domain tests pass with `pytest.mark.unit`.
4. No test in `tests/unit/domain/` imports from `src.application`, `src.infrastructure`, or `fastapi`.
5. Domain tests run in under 100ms total.
6. The architecture boundary test in `test_hexagonal_boundaries.py` does not need to be changed (no new imports).

---

## Migration Strategy

This change is purely additive. No production code changes.

1. Create `tests/unit/domain/__init__.py`.
2. Write `test_column_domain.py` first (simpler entity).
3. Write `test_board_domain.py` second (uses Column as a dependency).
4. Run `python -m pytest tests/unit/domain/ -v` to confirm all pass.
5. Run `python -m pytest tests/unit/domain/ --co -q` to confirm no infrastructure imports appear.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Domain entity tests may couple to internal implementation details | Write tests against public method contracts (`insert_card`, `extract_card`, `move_card`), not private helpers. |
| Domain entity fields are mutable (dataclass with `slots=True`) | Tests construct fresh entities per test function; no shared state issues. |

---

## Test Strategy

Tests must construct domain entities directly without helpers:

```python
# tests/unit/domain/test_column_domain.py

def _make_card(id: str, title: str, position: int = 0) -> Card:
    return Card(
        id=id, column_id="col-1", title=title,
        description=None, position=position,
        priority=CardPriority.MEDIUM, due_at=None,
    )

def _make_column(id: str = "col-1") -> Column:
    return Column(id=id, board_id="board-1", title="Test", position=0)

def test_insert_card_appends_when_no_position():
    col = _make_column()
    card = _make_card("c1", "First")
    col.insert_card(card)
    assert col.cards == [card]
    assert card.position == 0

def test_insert_card_at_position_zero_places_at_head():
    col = _make_column()
    col.insert_card(_make_card("c1", "First"))
    new_card = _make_card("c2", "Head")
    col.insert_card(new_card, requested_position=0)
    assert col.cards[0].id == "c2"
    assert col.cards[1].id == "c1"
    assert col.cards[0].position == 0
    assert col.cards[1].position == 1
```
