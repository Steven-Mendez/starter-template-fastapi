# Tasks: Extract Infrastructure ORM Mapper Module

**Change ID**: `infrastructure-mapper-module`

---

## Implementation Checklist

### Phase 1 — Create mapper module

- [ ] Create `src/infrastructure/persistence/sqlmodel/mappers.py`.
- [ ] Implement `card_table_to_domain(row: CardTable) -> Card`:
  - Copy logic from `_to_card_read` static method.
  - Handle UTC timezone normalization via `_ensure_utc`.
- [ ] Implement `column_table_to_domain(row: ColumnTable, cards: list[Card]) -> Column`:
  - Constructs `Column` from table row + pre-mapped card list.
- [ ] Implement `board_table_to_domain(row: BoardTable, columns: list[Column]) -> Board`:
  - Constructs `Board` from table row + pre-mapped column list.
- [ ] Implement `board_table_to_summary(row: BoardTable) -> BoardSummary`:
  - Extracts `id`, `title`, `created_at` with UTC normalization.
- [ ] Implement `card_domain_to_table(card: Card, column_id: str) -> CardTable`:
  - Maps domain `Card` fields to `CardTable`; `priority` needs `.value`.
- [ ] Implement `column_domain_to_table(column: Column, board_id: str) -> ColumnTable`:
  - Maps domain `Column` fields to `ColumnTable`.
- [ ] Implement `board_domain_to_table(board: Board) -> BoardTable`:
  - Maps domain `Board` fields to `BoardTable`.

### Phase 2 — Update `sqlmodel_repository.py`

- [ ] Import mapper functions from `src.infrastructure.persistence.sqlmodel.mappers`.
- [ ] In `find_by_id` (currently `get_board`):
  - Replace `Column(id=column.id, ...)` inline construction with `column_table_to_domain(column, cards=[card_table_to_domain(c) for c in cards])`.
  - Replace `Board(id=board.id, ...)` inline construction with `board_table_to_domain(board, columns=out_columns)`.
- [ ] In `list_boards` / `list_all`:
  - Replace inline `BoardSummary(id=board.id, ...)` construction with `board_table_to_summary(board)`.
- [ ] In `save` (currently `save_board`):
  - For card writes, replace inline `CardTable(id=card.id, ...)` construction with `card_domain_to_table(card, column_id=column.id)`.
  - For column writes, replace inline `ColumnTable(id=column.id, ...)` construction with `column_domain_to_table(column, board_id=board.id)`.
- [ ] Remove `_to_card_read` static method from `_BaseSQLModelKanbanRepository`.

### Phase 3 — Update `__init__.py`

- [ ] Update `src/infrastructure/persistence/sqlmodel/__init__.py` to re-export key mapper functions if desired for convenience (optional).

### Phase 4 — Add mapper unit tests

- [ ] Create `tests/unit/test_infrastructure_mappers.py`.
- [ ] Write `test_card_table_to_domain_maps_all_fields` — verify `id`, `column_id`, `title`, `description`, `position`, `priority`, `due_at`.
- [ ] Write `test_card_table_to_domain_normalizes_naive_datetime_to_utc` — verify naive `due_at` gets UTC timezone.
- [ ] Write `test_card_domain_to_table_maps_priority_as_string` — verify `CardPriority.HIGH` becomes `"high"`.
- [ ] Write `test_board_table_to_summary_maps_fields` — basic field mapping test.
- [ ] Mark with `pytestmark = pytest.mark.unit`.

### Phase 5 — Verify

- [ ] Run `python -m pytest tests/ -x` — all tests pass.
- [ ] Run `rg "_to_card_read" src/` — expect zero results.
- [ ] Run `rg "Card\(id=card" src/infrastructure/` — expect zero results (all inline construction replaced).
