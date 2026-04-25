# Proposal: Connect or Remove the Specification Pattern Dead Code

**Change ID**: `specification-pattern-integration`
**Priority**: Medium
**Status**: Proposed

---

## Problem Statement

`src/domain/kanban/specifications/card_move/` contains three specification classes:

- `SameBoardMoveSpecification` — checks that source and target board IDs are the same.
- `TargetColumnExistsSpecification` — checks that the target column exists.
- A `CardMoveCandidate` value object as the specification subject.

None of these specifications are used anywhere in the codebase. `Board.move_card` re-implements the same invariant checks inline:

```python
# src/domain/kanban/models/board.py
def move_card(self, card_id, source_column_id, target_column_id, requested_position):
    source_col = self.get_column(source_column_id)
    target_col = self.get_column(target_column_id)
    if not source_col or not target_col:
        return KanbanError.INVALID_CARD_MOVE    # ← duplicates TargetColumnExistsSpecification
    if source_column_id == target_column_id:
        ...
```

Additionally, the `handle_patch_card` command handler does board-boundary checks with inline logic:

```python
# src/application/commands/handlers.py
source_col = next(
    (c for c in board.columns if any(ca.id == command.card_id for ca in c.cards)),
    None,
)
target_col_id = command.column_id if command.column_id is not None else source_col.id
err = board.move_card(command.card_id, source_col.id, target_col_id, command.position)
```

The cross-board guard (ensuring a card cannot move to a column on a different board) is enforced by the fact that `board.get_column` only finds columns on the current board — but this invariant is implicit and not expressed through the specification pattern that was built for it.

This creates two quality problems:
1. **Dead code**: `src/domain/kanban/specifications/` is never called — it is maintained but has no effect on correctness.
2. **Implicit invariants**: The same-board rule is enforced as a side effect of `get_column` scope, not as an explicit domain rule.

---

## Rationale

A specification pattern is valuable when it:
1. Makes invariants explicit and composable.
2. Is actually invoked at the point where invariants must hold.

This codebase built the infrastructure for specifications but never connected it to the domain logic that was meant to use it. Either:
- **Option A (Connect)**: Integrate `SameBoardMoveSpecification` and `TargetColumnExistsSpecification` into `Board.move_card` to make the validation explicit and document the invariants as code.
- **Option B (Remove)**: Delete `src/domain/kanban/specifications/` entirely. Keep the inline checks in `Board.move_card` which already produce correct behavior. Document the invariants with comments instead.

**Recommended: Option A** — Connect the specifications. The `hex-design-guide.md` identifies "business invariants" as domain concerns. Specifications are the cleanest way to name and enforce them. The dead code was clearly intended to be used; the gap is simply that it was never wired in.

---

## Scope

**In scope:**
- Wire `SameBoardMoveSpecification` and `TargetColumnExistsSpecification` into `Board.move_card`.
- Introduce a composed `ValidCardMoveSpecification` that combines both checks.
- Add existing `tests/unit/test_specification_pattern.py` tests that exercise the specification against real move scenarios.
- Ensure `Board.move_card` returns `KanbanError.INVALID_CARD_MOVE` on specification failure (unchanged behavior).

**Out of scope:**
- Changing the public API of `Board.move_card`.
- Adding new specifications for unrelated domain rules.
- Removing the base specification infrastructure.

---

## Affected Modules

| File | Change |
|---|---|
| `src/domain/kanban/models/board.py` | Modified — use specifications in `move_card` |
| `src/domain/kanban/specifications/card_move/__init__.py` | Modified — export composed spec |
| `src/domain/kanban/specifications/card_move/target_column_exists.py` | Verified — confirm implementation |
| `tests/unit/test_specification_pattern.py` | Modified/Added — add integration scenarios |

---

## Acceptance Criteria

1. `Board.move_card` uses `SameBoardMoveSpecification` and `TargetColumnExistsSpecification` (or a composed form) to validate the move instead of or in addition to inline checks.
2. The specifications are exercised by at least one test path in `tests/unit/test_specification_pattern.py`.
3. All existing move-related tests in `test_kanban_command_handlers.py` continue to pass with identical behavior.
4. No public method of `Board.move_card` changes signature.
5. `src/domain/kanban/specifications/` contains no unreachable code.

---

## Migration Strategy

1. Read `TargetColumnExistsSpecification` — verify it checks `candidate.target_column_exists`.
2. Construct a `CardMoveCandidate` inside `Board.move_card` using available column presence data.
3. Create a composed `ValidCardMoveSpecification = SameBoardMoveSpecification().and_spec(TargetColumnExistsSpecification())`.
4. Evaluate the composed spec before executing the move.
5. Return `KanbanError.INVALID_CARD_MOVE` if the spec is not satisfied.
6. Add unit tests that create a `CardMoveCandidate` and assert the specifications.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| `Board.move_card` currently does not know the board ID of the target column | The board aggregate contains all its columns; the board itself is the context. `SameBoardMoveSpecification` checks `current_board_id == target_board_id`. The handler already resolves board context; the board aggregate can derive both values from its own column list. |
| Double-checking (spec + existing inline guard) | Remove the inline guard once the spec replaces it, keeping the logic in one place. |

---

## Test Strategy

```python
# tests/unit/test_specification_pattern.py additions

def test_valid_card_move_spec_satisfied_for_same_board():
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-1",
    )
    spec = ValidCardMoveSpecification()
    assert spec.is_satisfied_by(candidate) is True

def test_valid_card_move_spec_fails_for_cross_board():
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-2",
    )
    spec = ValidCardMoveSpecification()
    assert spec.is_satisfied_by(candidate) is False

def test_valid_card_move_spec_fails_when_target_column_missing():
    candidate = CardMoveCandidate(
        target_column_exists=False,
        current_board_id="board-1",
        target_board_id="board-1",
    )
    spec = ValidCardMoveSpecification()
    assert spec.is_satisfied_by(candidate) is False
```
