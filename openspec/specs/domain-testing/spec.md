# domain-testing Specification

## Purpose
TBD - created by archiving change domain-entity-unit-tests. Update Purpose after archive.
## Requirements
### Requirement: DT-01 — Domain entity tests exist with no infrastructure dependencies

The system MUST satisfy this requirement as specified below.

**Priority**: High

`tests/unit/domain/` contains test files that exercise domain entity behavior directly with no application layer, repository, UoW, or infrastructure imports.

**Acceptance Criteria**:
1. `tests/unit/domain/test_column_domain.py` exists.
2. `tests/unit/domain/test_board_domain.py` exists.
3. No file in `tests/unit/domain/` imports from `src.application`, `src.infrastructure`, or `fastapi`.
4. All tests in `tests/unit/domain/` are marked `pytest.mark.unit`.
5. All tests pass without a database connection or running FastAPI instance.

#### Scenario: Domain tests run in isolation

- Given: no database is available and no FastAPI app is running
- When: `pytest tests/unit/domain/ -v` is executed
- Then: all tests pass and total runtime is under 200ms

#### Scenario: Architecture boundary check on domain test imports

- Given: `tests/unit/domain/test_board_domain.py` is inspected
- When: its import statements are enumerated
- Then: no import from `src.application` or `src.infrastructure` appears

### Requirement: DT-02 — `Column` entity behavior is fully tested at the domain level

The system MUST satisfy this requirement as specified below.

**Priority**: High

All public methods of `Column` have at least one positive test and one edge-case test in `test_column_domain.py`.

**Acceptance Criteria**:
1. `insert_card` is tested for: append (no position), head insertion (position=0), clamped-to-tail (position beyond length).
2. `extract_card` is tested for: successful extraction with position reindex, and missing card (returns None).
3. `move_card_within` is tested for: moving a card to a new position within the column.
4. After any mutation, `card.position` values in `column.cards` are contiguous starting at 0.

#### Scenario: Insert at head reindexes all cards

- Given: a `Column` with two cards at positions 0 and 1
- When: a new card is inserted at `requested_position=0`
- Then: the new card has `position=0`, first original card has `position=1`, second has `position=2`

#### Scenario: Extract removes card and reindexes remainder

- Given: a `Column` with cards ["a" at pos 0, "b" at pos 1, "c" at pos 2]
- When: `extract_card("b")` is called
- Then: the returned card is "b"
- And: remaining cards are ["a" at pos 0, "c" at pos 1]

#### Scenario: Extract of missing card returns None

- Given: a `Column` with one card "a"
- When: `extract_card("nonexistent-id")` is called
- Then: `None` is returned and the column is unchanged

### Requirement: DT-03 — `Board` entity business behavior is fully tested at the domain level

The system MUST satisfy this requirement as specified below.

**Priority**: High

All public methods of `Board` that contain business logic have at least one positive and one negative test in `test_board_domain.py`.

**Acceptance Criteria**:
1. `delete_column` is tested for: successful deletion with position reindex, and missing column (returns error).
2. `move_card` is tested for: cross-column move, within-column reorder, missing source column (error), missing target column (error).
3. After `delete_column`, the remaining columns have contiguous 0-based positions.
4. After a cross-column `move_card`, the source column has no card with that ID and the target column has exactly one.

#### Scenario: Delete middle column reindexes remaining

- Given: a `Board` with columns at positions 0 ("A"), 1 ("B"), 2 ("C")
- When: `delete_column("B")` is called
- Then: the returned error is `None`
- And: remaining columns have positions 0 ("A") and 1 ("C")

#### Scenario: Move card to missing target column returns error

- Given: a `Board` with one column and one card
- When: `move_card(card_id, source_col_id, "nonexistent-col", None)` is called
- Then: `KanbanError.INVALID_CARD_MOVE` is returned

#### Scenario: Move card cross-column preserves card data

- Given: a `Board` with columns A and B; card "task" with priority HIGH in column A
- When: `move_card("task", "col-A", "col-B", None)` is called
- Then: column A has 0 cards; column B has 1 card with title "task" and priority HIGH

