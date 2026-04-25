# Spec: Specification Pattern Integration for Card Moves

**Capability**: specification-pattern
**Change**: specification-pattern-integration

---

## ADDED Requirements

### Requirement: SPI-01 — `Board.move_card` validates moves with composed card-move specifications

**Priority**: Medium

`Board.move_card` MUST evaluate card-move invariants through the specification pattern, using `SameBoardMoveSpecification` and `TargetColumnExistsSpecification` (directly or via a composed `ValidCardMoveSpecification`) before applying mutations.

**Acceptance Criteria**:
1. `Board.move_card` invokes specification-based validation for card move candidates.
2. Validation covers same-board and target-column-exists invariants.
3. If specification validation fails, `Board.move_card` returns `KanbanError.INVALID_CARD_MOVE`.
4. The public method signature of `Board.move_card` is unchanged.

#### Scenario: Specification allows valid same-board move to existing column

- Given: a board with source and target columns and a card in the source column
- When: `Board.move_card(card_id, source_column_id, target_column_id, requested_position)` is called for a valid move
- Then: the composed specification is satisfied
- And: the move is applied without returning `KanbanError.INVALID_CARD_MOVE`

#### Scenario: Specification rejects move when target column does not exist

- Given: a board with a source column and card but no column matching `target_column_id`
- When: `Board.move_card(card_id, source_column_id, missing_target_column_id, requested_position)` is called
- Then: specification validation fails
- And: the method returns `KanbanError.INVALID_CARD_MOVE`

### Requirement: SPI-02 — Card-move specification flow is exercised by unit tests

**Priority**: Medium

Specification classes in `src/domain/kanban/specifications/card_move/` MUST be part of at least one passing unit-test path so the specification pattern is active code rather than dead code.

**Acceptance Criteria**:
1. `tests/unit/test_specification_pattern.py` includes tests for valid and invalid card-move candidates.
2. Tests cover same-board success, cross-board failure, and missing-target failure outcomes.
3. At least one board move behavior test path executes logic gated by the composed specification.
4. No card-move specification class remains unused by all tests.

#### Scenario: Cross-board candidate fails same-board specification

- Given: a `CardMoveCandidate` with `current_board_id` different from `target_board_id`
- When: the composed card-move specification is evaluated
- Then: `is_satisfied_by(candidate)` returns `False`

#### Scenario: Valid candidate satisfies composed specification

- Given: a `CardMoveCandidate` with `target_column_exists=True` and matching board IDs
- When: the composed card-move specification is evaluated
- Then: `is_satisfied_by(candidate)` returns `True`
