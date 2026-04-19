## 1. Domain Layer Alignment

- [x] 1.1 Move `src/application/ports/repository.py` to `src/domain/kanban/repository.py`.
- [x] 1.2 Update all import paths in the application handlers and infrastructure implementations to reflect the new Driven Port location.
- [x] 1.3 Update the `KanbanRepository` interface to use an aggregate-root signature for reordering state (e.g. `save_card_sequence(self, columns: list[Column]) -> Result[None, KanbanError]`) instead of opaque parameters.

## 2. Command Handler Orchestration

- [x] 2.1 Refactor `KanbanCommandHandlers.handle_patch_card` to fetch the source and target columns state before doing the move.
- [x] 2.2 Invoke `validate_card_move` from the domain specs inside `handle_patch_card`.
- [x] 2.3 Invoke `reorder_between_columns` and `reorder_within_column` inside `handle_patch_card`.
- [x] 2.4 Call the newly modified repository sequence saving method with the exactly calculated arrays.

## 3. Repository Implementation Refactoring

- [x] 3.1 Refactor `SQLModelKanbanRepository.update_card` and any new reorder methods to strictly persist the provided sequences, removing internal calls to validation and domain utilities.
- [x] 3.2 Refactor `InMemoryKanbanRepository` similarly to strip it of all domain logic.

## 4. Testing & Verification

- [x] 4.1 Update `test_sqlmodel_repository.py` and `test_in_memory_repository.py` unit tests by stripping out validation-specific fail cases, as these are now orchestrator responsibilities.
- [x] 4.2 Add or update tests in the command handlers layer covering validation error flows (e.g., cannot move to non-existent board/column).
