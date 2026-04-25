# Tasks: Add Domain Entity Unit Tests

**Change ID**: `domain-entity-unit-tests`

---

## Implementation Checklist

### Phase 1 — Set up test directory

- [ ] Create `tests/unit/domain/__init__.py` (empty).

### Phase 2 — Write `test_column_domain.py`

- [ ] Define `_make_card(id, title, position=0) -> Card` helper.
- [ ] Define `_make_column(id="col-1") -> Column` helper.
- [ ] Write `test_insert_card_appends_when_no_position` — verify card appears at end with position 0.
- [ ] Write `test_insert_card_at_position_zero_places_at_head` — verify new card is at index 0 and positions reindex.
- [ ] Write `test_insert_card_beyond_end_clamps_to_tail` — verify position `999` places card at end.
- [ ] Write `test_extract_card_returns_card_and_removes_from_list` — verify card is returned and absent from `cards`.
- [ ] Write `test_extract_card_reindexes_remaining_cards` — verify remaining cards have contiguous positions.
- [ ] Write `test_extract_missing_card_returns_none` — verify `None` returned for unknown ID.
- [ ] Write `test_move_card_within_reorders_correctly` — move card from position 0 to position 1; verify order.
- [ ] Write `test_column_id_assigned_on_insert` — verify `card.column_id` is set to the column's ID after `insert_card`.

### Phase 3 — Write `test_board_domain.py`

- [ ] Define `_make_board(id="b1", num_columns=0) -> Board` helper.
- [ ] Define `_append_column(board, title) -> Column` helper (mutates board.columns in-place).
- [ ] Define `_append_card(column, title) -> Card` helper (calls `column.insert_card`).
- [ ] Write `test_get_column_returns_column_by_id` — verify correct column returned.
- [ ] Write `test_get_column_returns_none_for_missing_id` — verify `None` for unknown ID.
- [ ] Write `test_delete_column_removes_column` — verify column absent after delete.
- [ ] Write `test_delete_column_reindexes_remaining_columns` — delete middle column; verify positions are 0, 1.
- [ ] Write `test_delete_missing_column_returns_error` — verify `KanbanError.COLUMN_NOT_FOUND`.
- [ ] Write `test_move_card_cross_column_on_same_board` — card moves from col A to col B; verify col A empty, col B has card.
- [ ] Write `test_move_card_reorder_within_same_column` — card moves within same column; verify new position.
- [ ] Write `test_move_card_missing_source_column_returns_error` — verify `KanbanError.INVALID_CARD_MOVE`.
- [ ] Write `test_move_card_missing_target_column_returns_error` — use existing col as source but invalid target ID.
- [ ] Write `test_move_card_preserves_card_data` — verify title, priority, due_at unchanged after move.

### Phase 4 — Verify no infrastructure imports

- [ ] Run:
  ```bash
  python -m pytest tests/unit/domain/ -v --tb=short
  ```
  All tests pass.
- [ ] Confirm no import from `src.application`, `src.infrastructure`, or `fastapi` in any `tests/unit/domain/` file:
  ```bash
  rg "src\.application|src\.infrastructure|fastapi" tests/unit/domain/
  ```
  Expect zero results.
- [ ] Run full test suite: `python -m pytest tests/ -x` — no regressions.

### Phase 5 — Mark with pytest marker

- [ ] Add `pytestmark = pytest.mark.unit` to each test file in `tests/unit/domain/`.
