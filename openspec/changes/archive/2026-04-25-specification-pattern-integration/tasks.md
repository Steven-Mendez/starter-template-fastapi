# Tasks: Connect or Remove the Specification Pattern Dead Code

**Change ID**: `specification-pattern-integration`

---

## Implementation Checklist

### Phase 1 — Audit existing specifications

- [ ] Read `src/domain/kanban/specifications/card_move/target_column_exists.py` — confirm it evaluates `candidate.target_column_exists`.
- [ ] Read `src/domain/kanban/specifications/card_move/same_board.py` — confirm logic matches the cross-board invariant.
- [ ] Read `src/domain/kanban/specifications/base/and_specification.py` and `or_specification.py` — confirm composability works.
- [ ] Read `tests/unit/test_specification_pattern.py` — identify what is already tested vs. what is missing.

### Phase 2 — Introduce composed specification

- [ ] In `src/domain/kanban/specifications/card_move/__init__.py`, export a composed `ValidCardMoveSpecification` that is `SameBoardMoveSpecification().and_spec(TargetColumnExistsSpecification())`.
- [ ] Alternatively, define `ValidCardMoveSpecification` as a named class for clarity.

### Phase 3 — Wire specification into `Board.move_card`

- [ ] In `Board.move_card`, construct a `CardMoveCandidate`:
  - `target_column_exists`: whether `target_col` is not None.
  - `current_board_id`: the board's own `id`.
  - `target_board_id`: derive from the target column's `board_id` if accessible, or use the current board's `id` as the context (since the board aggregate can only see its own columns — cross-board moves will fail to resolve `target_col`).
- [ ] Evaluate `ValidCardMoveSpecification().is_satisfied_by(candidate)`.
- [ ] If not satisfied, return `KanbanError.INVALID_CARD_MOVE`.
- [ ] Remove the now-redundant inline `if not source_col or not target_col` check (if fully replaced by the spec).

### Phase 4 — Add and update tests

- [ ] Add tests to `tests/unit/test_specification_pattern.py`:
  - `test_valid_card_move_spec_satisfied_for_same_board`
  - `test_valid_card_move_spec_fails_for_cross_board`
  - `test_valid_card_move_spec_fails_when_target_column_missing`
- [ ] Run `python -m pytest tests/unit/test_kanban_command_handlers.py -v` — all move-card tests pass unchanged.
- [ ] Run `python -m pytest tests/unit/test_specification_pattern.py -v` — all tests pass.

### Phase 5 — Verify no dead code remains

- [ ] Search for any class in `src/domain/kanban/specifications/` that is never imported or instantiated. Remove or use all of them.
- [ ] Run full test suite: `python -m pytest tests/ -x`.
